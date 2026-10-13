"""Síntesis con caché por contenido, compartida por el modo por lotes y el bajo demanda.

Caché: ``static/audio/<k[:2]>/<k>.{opus,mp3,json}`` con ``k = sha256`` de (texto que recibe el
motor, motor, modelo, revisión, adaptador, parámetros que afectan al audio). Un texto ya
sintetizado no se vuelve a sintetizar. Por noticia: ``static/news/<id>/manifest.json`` y un JSON
de tiempos por segmento (``seg_NNN.json``).

Regla 1 del prompt: un segmento con ``tts_ready=false`` NUNCA se sintetiza.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from app.audio import atomic_write, encode, kbps
from app.batch.manifest import (
    AudioFiles,
    EngineRef,
    Manifest,
    ManifestSegment,
    Notices,
    VisemeInfo,
)
from app.batch.timings import canonical_times, span_times
from app.config import get_settings
from app.db.models import AudioAsset, News, Segment, SynthesisRun
from app.pipeline.g2p.engine import G2P
from app.pipeline.tts.base import SYNTHETIC_NOTICE, derive_seed
from app.pipeline.tts.registry import EnginePool, get_pool
from app.pipeline.viseme.align import align_text
from app.pipeline.viseme.track import VisemeMap, build_track

log = logging.getLogger("noticias.tts")

# Parámetros que NO cambian el audio y por tanto no entran en la clave de caché
NON_AUDIO_PARAMS = {"torch_threads"}
NON_COMMERCIAL_WARNING = (
    "El modelo de voz tiene licencia no comercial (CC-BY-NC 4.0): un servicio público con fines "
    "comerciales no puede usarlo. Alternativa sin restricción: motor espeak_ng (línea base)."
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class SegmentAudio:
    cache_key: str
    opus: str  # rutas relativas a static/
    mp3: str
    meta: dict
    reused: bool
    durations: dict | None = None
    synth_ms: float | None = None

    @property
    def duration_s(self) -> float:
        return self.meta["duration_s"]


@dataclass
class Synthesizer:
    pool: EnginePool
    static_dir: Path = field(default_factory=lambda: get_settings().static_dir)
    opus_kbps: float = field(default_factory=lambda: get_settings().opus_kbps)

    def __post_init__(self) -> None:
        self.g2p = G2P.from_files()
        self.viseme_map = VisemeMap.from_file()
        self.cold_start_ms = self.pool.warmup()
        self.info = self.pool.info()
        if not self.info.commercial_use:
            log.warning(NON_COMMERCIAL_WARNING)

    # ------------------------------------------------------------------ claves y rutas
    def audio_params(self) -> dict:
        p = self.pool.engines[0].params()
        return {k: v for k, v in sorted(p.items()) if k not in NON_AUDIO_PARAMS}

    def cache_key(self, text: str, adapter_id: str) -> str:
        payload = {
            "text": text,
            "engine": self.info.engine,
            "model": self.info.model,
            "revision": self.info.revision,
            "adapter_id": adapter_id,
            "params": self.audio_params(),
            "opus_kbps": self.opus_kbps,
        }
        return _sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode())

    def text_for(self, seg: Segment) -> str:
        """Texto que recibe el motor según su tipo de entrada."""
        if self.info.input_kind == "text_tts":
            return seg.text_tts or ""
        return seg.text_canonical  # text_es / phonemes: el motor convierte a partir del canónico

    def _paths(self, key: str) -> dict[str, Path]:
        base = self.static_dir / "audio" / key[:2]
        return {ext: base / f"{key}.{ext}" for ext in ("opus", "mp3", "json")}

    def rel(self, path: Path) -> str:
        return path.relative_to(self.static_dir).as_posix()

    # ------------------------------------------------------------------ síntesis
    def synthesize_text(self, text: str, adapter_id: str) -> SegmentAudio:
        key = self.cache_key(text, adapter_id)
        paths = self._paths(key)
        if all(p.exists() for p in paths.values()):
            cached = json.loads(paths["json"].read_text(encoding="utf-8"))
            return SegmentAudio(
                key,
                self.rel(paths["opus"]),
                self.rel(paths["mp3"]),
                cached["meta"],
                True,
                cached.get("durations"),
            )
        seed = derive_seed(text, self.info.engine, self.info.revision, adapter_id)
        with self.pool.acquire() as engine:
            res = engine.synthesize(text, seed)
        opus = encode(res.wav, res.sample_rate, "opus", self.opus_kbps)
        mp3 = encode(res.wav, res.sample_rate, "mp3")
        meta = {
            **self.info.to_dict(),
            "aviso": SYNTHETIC_NOTICE,
            "sintetico": True,
            "adapter_id": adapter_id,
            "seed": seed,
            "text": text,
            "params": self.audio_params(),
            "duration_s": round(res.duration_s, 4),
            "synth_ms": round(res.synth_ms, 2),
            "rtf": round(res.rtf, 4),
            "opus_kbps": kbps(opus, res.duration_s),
            "mp3_kbps": kbps(mp3, res.duration_s),
            "opus_sha256": _sha256(opus),
            "mp3_sha256": _sha256(mp3),
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        durations = res.durations.to_dict() if res.durations else None
        atomic_write(paths["opus"], opus)
        atomic_write(paths["mp3"], mp3)
        atomic_write(
            paths["json"],
            json.dumps({"meta": meta, "durations": durations}, ensure_ascii=False).encode(),
        )
        return SegmentAudio(
            key,
            self.rel(paths["opus"]),
            self.rel(paths["mp3"]),
            meta,
            False,
            durations,
            res.synth_ms,
        )

    # ------------------------------------------------------------------ por segmento y noticia
    def segment_timings(self, seg: Segment, audio: SegmentAudio) -> dict:
        d = audio.durations
        if not d or self.info.input_kind != "text_tts":
            return {
                "durations": d,
                "canonical_times": None,
                "spans": None,
                "alignment": None,
                "visemes": None,
                "note": "el motor no expone duraciones",
            }
        canon = canonical_times(len(seg.text_canonical), d["char_times"], seg.tts_char_map)
        words, phonemes = align_text(seg.text_canonical, canon, self.g2p)
        total_s = d["char_times"][-1][1] if d["char_times"] else audio.duration_s
        return {
            "durations": d,
            "canonical_times": canon,
            "spans": span_times(seg.alignment_map, canon),
            **build_track(words, phonemes, total_s, self.viseme_map),
        }

    def write_segment(self, session: Session, news: News, seg: Segment, audio: SegmentAudio) -> str:
        timings_path = self.static_dir / "news" / str(news.id) / f"seg_{seg.idx:03d}.json"
        atomic_write(
            timings_path,
            json.dumps(
                {
                    "news_id": news.id,
                    "idx": seg.idx,
                    "text_orig": seg.text_orig,
                    "text_canonical": seg.text_canonical,
                    "engine_text": self.text_for(seg),
                    "cache_key": audio.cache_key,
                    **self.segment_timings(seg, audio),
                },
                ensure_ascii=False,
            ).encode(),
        )
        for old in session.exec(
            select(AudioAsset).where(
                AudioAsset.segment_id == seg.id, AudioAsset.engine == self.info.engine
            )
        ).all():
            session.delete(old)
        for fmt in ("opus", "mp3"):
            session.add(
                AudioAsset(
                    segment_id=seg.id,
                    engine=self.info.engine,
                    cache_key=audio.cache_key,
                    format=fmt,
                    path=getattr(audio, fmt),
                    sha256=audio.meta[f"{fmt}_sha256"],
                    duration_s=audio.duration_s,
                    kbps=audio.meta[f"{fmt}_kbps"],
                    meta=audio.meta,
                )
            )
        return self.rel(timings_path)

    def manifest_segment(
        self, seg: Segment, audio: SegmentAudio | None, timings: str | None
    ) -> ManifestSegment:
        if audio is None:
            reason = next(
                (u["reason"] for u in seg.unresolved if u["reason"].startswith("bloqueado")),
                "bloqueado para TTS",
            )
            return ManifestSegment(
                idx=seg.idx,
                paragraph_idx=seg.paragraph_idx,
                text_orig=seg.text_orig,
                tts_ready=False,
                audio=None,
                duration_s=None,
                timings=None,
                blocked_reason=reason,
            )
        return ManifestSegment(
            idx=seg.idx,
            paragraph_idx=seg.paragraph_idx,
            text_orig=seg.text_orig,
            tts_ready=True,
            duration_s=audio.duration_s,
            timings=f"/static/{timings}",
            blocked_reason=None,
            audio=AudioFiles(
                opus=f"/static/{audio.opus}",
                mp3=f"/static/{audio.mp3}",
                opus_kbps=audio.meta["opus_kbps"],
                mp3_kbps=audio.meta["mp3_kbps"],
            ),
        )

    def notices(self) -> Notices:
        return Notices(
            synthetic_voice=SYNTHETIC_NOTICE,
            license=self.info.license,
            commercial_use=self.info.commercial_use,
            non_commercial_warning=None if self.info.commercial_use else NON_COMMERCIAL_WARNING,
            dialect=self.info.dialect,
        )

    def engine_ref(self, adapter_id: str) -> EngineRef:
        return EngineRef(
            engine=self.info.engine,
            model=self.info.model,
            revision=self.info.revision,
            adapter_id=adapter_id,
            params=self.audio_params(),
        )

    def write_manifest(self, news: News, segments: list[ManifestSegment], adapter_id: str) -> Path:
        m = Manifest(
            news_id=news.id or 0,
            titulo_cni=news.titulo_cni,
            fecha_publicacion=news.fecha_publicacion.isoformat()
            if news.fecha_publicacion
            else None,
            generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
            engine=self.engine_ref(adapter_id),
            notices=self.notices(),
            segments=segments,
            visemes=VisemeInfo(
                status=self.viseme_map.status,
                map_sha256=self.viseme_map.sha256,
                channels=self.viseme_map.channels,
            ),
            total_duration_s=round(sum(s.duration_s or 0 for s in segments), 3),
            segments_with_audio=sum(1 for s in segments if s.audio),
            segments_blocked=sum(1 for s in segments if not s.audio),
        )
        path = self.static_dir / "news" / str(news.id) / "manifest.json"
        atomic_write(path, m.model_dump_json(indent=2).encode())
        return path

    def build_news(self, session: Session, news: News) -> dict:
        """Sintetiza (o reutiliza) todos los segmentos listos y escribe el manifiesto."""
        ensure_processed(session, news)
        stats = {"synthesized": 0, "reused": 0, "blocked": 0}
        segs: list[ManifestSegment] = []
        adapter_id = ""
        for seg in news.segments:
            adapter_id = adapter_id or seg.adapter_id
            if not seg.tts_ready:
                stats["blocked"] += 1
                segs.append(self.manifest_segment(seg, None, None))
                continue
            audio = self.synthesize_text(self.text_for(seg), seg.adapter_id)
            stats["reused" if audio.reused else "synthesized"] += 1
            timings = self.write_segment(session, news, seg, audio)
            segs.append(self.manifest_segment(seg, audio, timings))
        self.write_manifest(news, segs, adapter_id)
        return stats


def ensure_processed(session: Session, news: News) -> None:
    if news.estado != "processed" or not news.segments:
        from app.metrics.timing import Timer
        from app.services import Pipeline, process_news

        process_news(session, news, Pipeline.default(), Timer())
        session.flush()
        session.refresh(news)


def run_batch(news_ids: list[int] | None = None, engine: str | None = None) -> dict:
    from app.db.session import get_engine, init_db

    init_db()
    synth = Synthesizer(get_pool(engine))
    totals = {"synthesized": 0, "reused": 0, "blocked": 0, "errors": 0}
    with Session(get_engine()) as session:
        run = SynthesisRun(engine=synth.info.engine, mode="batch")
        session.add(run)
        query = select(News) if not news_ids else select(News).where(News.id.in_(news_ids))
        news_list = session.exec(query).all()
        for news in news_list:
            try:
                for k, v in synth.build_news(session, news).items():
                    totals[k] += v
            except Exception as err:  # se registra y se sigue con las demás
                totals["errors"] += 1
                log.exception("error al sintetizar la noticia %s: %s", news.id, err)
        run.news_count = len(news_list)
        run.synthesized, run.reused = totals["synthesized"], totals["reused"]
        run.blocked, run.errors = totals["blocked"], totals["errors"]
        run.finished_at = datetime.now(UTC)
        run.detail = {"cold_start_ms": synth.cold_start_ms}
        session.commit()
    return {"noticias": len(news_list), **totals, "carga_en_frio_ms": round(synth.cold_start_ms, 1)}
