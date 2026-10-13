"""Material sintético para probar el experimento: noticias aptas con segmentos listos.

Solo para pruebas, la simulación y el servidor E2E. NO son noticias reales ni están revisadas por un
hablante: ``revisada=True`` solo sirve para que ``News.apta_experimento`` las admita en el modo real.
"""

from __future__ import annotations

from app.db.models import News, Provenance, Segment
from sqlmodel import Session


def crear_noticias(
    engine,
    n: int = 4,
    bloqueadas: tuple[int, ...] = (),
    revisada: bool = True,
    tipo: str = "traduccion_humana",
) -> list[int]:
    """Crea ``n`` noticias con 2 segmentos con audio; las de ``bloqueadas`` (posiciones 0..n-1)
    llevan además un segmento bloqueado (sin P2d). Devuelve los ids."""
    ids: list[int] = []
    with Session(engine) as s:
        for i in range(n):
            news = News(
                titulo_cni=f"PRUEBA {i + 1}", cuerpo_cni="Okantzi kemetsa. Tzimatsi kitaiteri."
            )
            news.provenance = Provenance(tipo=tipo, revisado_por_hablante=revisada)
            s.add(news)
            s.flush()
            textos = ["Okantzi kemetsa.", "Tzimatsi kitaiteri."]
            if i in bloqueadas:
                textos.append("Irotake Pablo Lima.")
            pos = 0
            for k, txt in enumerate(textos):
                s.add(
                    Segment(
                        news_id=news.id,
                        idx=k,
                        paragraph_idx=0 if k < 2 else 1,
                        orig_start=pos,
                        orig_end=pos + len(txt),
                        text_orig=txt,
                        text_canonical=txt.lower(),
                        text_tts=txt.lower() if i not in bloqueadas or k < 2 else None,
                        tts_ready=not (i in bloqueadas and k == 2),
                    )
                )
                pos += len(txt) + 1
            ids.append(news.id)
        s.commit()
    return ids
