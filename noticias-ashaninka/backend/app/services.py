"""Servicios compartidos por la CLI y la API: ingesta, procesamiento y reporte editorial."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session, select

from app.config import get_settings
from app.db.models import News, Provenance, ResourceVersion, Segment
from app.db.session import get_engine, init_db
from app.metrics.timing import Timer
from app.pipeline.g2p.engine import G2P
from app.pipeline.normalize.engine import DocumentState, Normalizer
from app.pipeline.segment import Segmenter
from app.pipeline.tts.adapters.mms_cni import MmsCniAdapter
from app.pipeline.tts.adapters.validate import OutOfVocabularyError, validate_tts_text
from app.pipeline.types import Unresolved, to_jsonable
from app.schemas import NewsIn


# ---------------------------------------------------------------------------- ingesta
def news_from_payload(payload: NewsIn) -> News:
    news = News(**payload.model_dump(exclude={"procedencia"}))
    news.provenance = Provenance(**payload.procedencia.model_dump())
    return news


def _exists(session: Session, titulo: str, cuerpo: str, fuente: str) -> bool:
    q = select(News.id).where(
        News.titulo_cni == titulo, News.cuerpo_cni == cuerpo, News.fuente_original == fuente
    )
    return session.exec(q).first() is not None


def import_payloads(
    payloads: list[NewsIn], session: Session | None = None, skip_existing: bool = False
) -> list[int]:
    """Guarda noticias. Con ``skip_existing`` omite las ya importadas (mismo título, cuerpo y
    fuente), de modo que reimportar una carpeta es idempotente."""
    own = session is None
    session = session or Session(get_engine())
    try:
        items = [
            news_from_payload(p)
            for p in payloads
            if not (
                skip_existing and _exists(session, p.titulo_cni, p.cuerpo_cni, p.fuente_original)
            )
        ]
        session.add_all(items)
        session.commit()
        return [n.id for n in items if n.id is not None]
    finally:
        if own:
            session.close()


def import_news_dir(path: str | Path) -> list[int]:
    init_db()
    base = Path(path)
    payloads: list[NewsIn] = []
    for f in sorted(base.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for item in data if isinstance(data, list) else [data]:
            payloads.append(NewsIn.model_validate(item))
    return import_payloads(payloads, skip_existing=True)


def import_from_corpus(split: str, limit: int = 20) -> list[int]:
    """Pseudo-noticias del corpus SOLO para pruebas de integración y carga (nunca experimento).
    Idempotente: no reimporta oraciones ya presentes."""
    from app.corpus.loader import load_split

    init_db()
    pairs = load_split(split)[:limit]
    with Session(get_engine()) as session:
        items = []
        for p in pairs:
            fuente = f"AmericasNLP2021@d3f519c {p.ref}"
            if _exists(session, p.ref, p.cni, fuente):
                continue
            n = News(
                titulo_cni=p.ref,
                cuerpo_cni=p.cni,
                titulo_es=p.ref,
                cuerpo_es=p.es,
                variante_dialectal="mixta (corpus AmericasNLP)",
                fuente_original=fuente,
            )
            n.provenance = Provenance(
                tipo="corpus_americasnlp",
                sistema="AmericasNLP2021",
                version="d3f519c",
                revisado_por_hablante=False,
            )
            items.append(n)
        session.add_all(items)
        session.commit()
        return [n.id for n in items if n.id is not None]


# ---------------------------------------------------------------------------- pipeline
@dataclass
class Pipeline:
    segmenter: Segmenter
    normalizer: Normalizer
    adapter: MmsCniAdapter
    g2p: G2P

    @classmethod
    def default(cls) -> Pipeline:
        s = get_settings()
        return cls(
            Segmenter.from_files(),
            Normalizer.from_files(s.allow_candidates),
            MmsCniAdapter.from_files(s.mms_adapter),
            G2P.from_files(),
        )

    def process_text(self, text: str, timer: Timer | None = None) -> list[dict]:
        """Procesa un documento y devuelve un dict por segmento (listo para guardar)."""
        timer = timer or Timer()
        with timer.measure("segmentacion"):
            segments = self.segmenter.segment(text)
        state = DocumentState()
        out = []
        for seg in segments:
            with timer.measure("normalizacion"):
                norm = self.normalizer.normalize(seg.text, state)
            unresolved = list(norm.unresolved)
            with timer.measure("adaptador_mms"):
                adapted = self.adapter.adapt(norm.text_canonical)
                try:
                    validate_tts_text(adapted.text_tts, self.adapter.vocab())
                    tts_ready = True
                except OutOfVocabularyError as err:
                    tts_ready = False
                    chars = "".join(sorted({o.char for o in err.oov}))
                    unresolved.append(
                        Unresolved(
                            0,
                            len(seg.text),
                            seg.text,
                            f"bloqueado para TTS: fuera del vocabulario '{chars}'",
                        )
                    )
            with timer.measure("g2p"):
                g2p = self.g2p.text(norm.text_canonical)
            out.append(
                {
                    "idx": seg.idx,
                    "paragraph_idx": seg.paragraph_idx,
                    "orig_start": seg.start,
                    "orig_end": seg.end,
                    "text_orig": seg.text,
                    "text_canonical": norm.text_canonical,
                    "text_tts": adapted.text_tts if tts_ready else None,
                    "tts_ready": tts_ready,
                    "alignment_map": to_jsonable(norm.spans),
                    "tts_char_map": to_jsonable(adapted.char_map),
                    "phonemes": to_jsonable(g2p.words),
                    "editorial_flags": to_jsonable(norm.editorial_flags),
                    "unresolved": to_jsonable(
                        unresolved
                        + [
                            Unresolved(
                                u.orig_start,
                                u.orig_end,
                                u.text,
                                f"G2P: {u.reason} (posición en el texto canónico)",
                            )
                            for u in g2p.unknown
                        ]
                    ),
                    "resources_hash": norm.resources_hash,
                    "adapter_id": adapted.adapter_id,
                    "used_candidates": norm.used_candidates,
                }
            )
        return out


def _record_resources(session: Session, normalizer: Normalizer) -> None:
    h = normalizer.resources_hash
    if session.exec(select(ResourceVersion).where(ResourceVersion.bundle_hash == h)).first():
        return
    for r in normalizer.resources.values():
        session.add(ResourceVersion(bundle_hash=h, resource=r.resource, sha256=r.sha256 or ""))


def process_news(session: Session, news: News, pipeline: Pipeline, timer: Timer) -> int:
    for old in list(news.segments):
        session.delete(old)
    session.flush()
    try:
        rows = pipeline.process_text(news.cuerpo_cni, timer)
    except Exception as err:  # se registra y se sigue con las demás noticias
        news.estado, news.error = "error", repr(err)
        return 0
    for row in rows:
        session.add(Segment(news_id=news.id, **row))
    news.estado, news.error = "processed", None
    return len(rows)


def _process(query) -> dict:
    init_db()
    pipeline = Pipeline.default()
    timer = Timer()
    with Session(get_engine()) as session:
        _record_resources(session, pipeline.normalizer)
        news_list = session.exec(query).all()
        n_seg = sum(process_news(session, n, pipeline, timer) for n in news_list)
        session.commit()
        errors = sum(1 for n in news_list if n.estado == "error")
    return {
        "noticias": len(news_list),
        "segmentos": n_seg,
        "errores": errors,
        "latencia_ms": timer.summary(),
    }


def process_all() -> dict:
    return _process(select(News))


def process_news_by_id(news_id: int) -> dict:
    return _process(select(News).where(News.id == news_id))


# ---------------------------------------------------------------------------- reportes
def editorial_report(news_id: int) -> dict:
    with Session(get_engine()) as session:
        news = session.get(News, news_id)
        if news is None:
            raise KeyError(f"No existe la noticia {news_id}")
        segs = []
        for s in news.segments:
            segs.append(
                {
                    "idx": s.idx,
                    "texto": s.text_orig,
                    "tts_ready": s.tts_ready,
                    "marcas_editoriales": [
                        {**f, "fragmento": s.text_orig[f["orig_start"] : f["orig_end"]]}
                        for f in s.editorial_flags
                    ],
                    "sin_resolver": s.unresolved,
                }
            )
        return {
            "news_id": news.id,
            "titulo_cni": news.titulo_cni,
            "estado": news.estado,
            "procedencia": news.provenance.tipo if news.provenance else None,
            "segmentos": segs,
        }


def editorial_report_text(news_id: int) -> str:
    rep = editorial_report(news_id)
    lines = [
        f"Noticia {rep['news_id']} — {rep['titulo_cni']} [{rep['estado']}; "
        f"procedencia: {rep['procedencia']}]",
        "",
    ]
    for s in rep["segmentos"]:
        status = "listo para TTS" if s["tts_ready"] else "BLOQUEADO para TTS"
        lines.append(f"[{s['idx']}] ({status}) {s['texto']}")
        for f in s["marcas_editoriales"]:
            lines.append(f"    · editorial/{f['kind']}: {f['note']}")
        for u in s["sin_resolver"]:
            lines.append(f"    · sin resolver: '{u['text']}' — {u['reason']}")
    return "\n".join(lines)
