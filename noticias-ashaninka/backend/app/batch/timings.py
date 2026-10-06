"""Proyección de tiempos: carácter de ``text_tts`` -> carácter canónico -> fragmento original.

Usa los dos mapas de la Fase 1: ``tts_char_map`` (canónico <-> MMS) y ``alignment_map``
(original <-> canónico). Las reglas, documentadas en docs/manifest_schema.md:

* un tramo canónico que produjo N caracteres TTS recibe el intervalo [inicio del primero, fin
  del último] y, si tiene varios caracteres canónicos, se reparte en partes iguales;
* un tramo que no produjo audio (p. ej. puntuación eliminada) recibe un intervalo de duración 0
  en el instante en que terminó lo anterior;
* un fragmento original recibe [inicio de su primer carácter canónico, fin del último].

Estos tiempos son la ENTRADA de la Fase 3; su exactitud se valida allí (tarea 3.2).
"""

from __future__ import annotations


def canonical_times(
    canonical_len: int, tts_char_times: list[tuple[float, float]], tts_char_map: list[dict]
) -> list[tuple[float, float]]:
    out: list[tuple[float, float] | None] = [None] * canonical_len
    last_end = 0.0
    for e in sorted(tts_char_map, key=lambda m: m["src_start"]):
        s0, s1, d0, d1 = e["src_start"], e["src_end"], e["dst_start"], e["dst_end"]
        if d1 > d0 and d0 < len(tts_char_times):
            d1 = min(d1, len(tts_char_times))
            t0, t1 = tts_char_times[d0][0], tts_char_times[d1 - 1][1]
        else:
            t0 = t1 = last_end
        n = max(s1 - s0, 0)
        for k in range(n):
            a = t0 + (t1 - t0) * k / n
            b = t0 + (t1 - t0) * (k + 1) / n
            if s0 + k < canonical_len:
                out[s0 + k] = (round(a, 5), round(b, 5))
        last_end = max(last_end, t1)
    # Caracteres canónicos no cubiertos por el mapa (no debería ocurrir): duración 0
    fill = 0.0
    result = []
    for t in out:
        if t is None:
            t = (fill, fill)
        fill = t[1]
        result.append(t)
    return result


def span_times(alignment_map: list[dict], canon_times: list[tuple[float, float]]) -> list[dict]:
    """Tiempo de cada fragmento original (para el resaltado sincronizado de la Fase 4)."""
    spans, pos = [], 0
    for s in alignment_map:
        n = len(s["norm_text"])
        if n and pos < len(canon_times):
            t0 = canon_times[pos][0]
            t1 = canon_times[min(pos + n, len(canon_times)) - 1][1]
        else:
            t0 = t1 = canon_times[pos - 1][1] if pos and canon_times else 0.0
        spans.append(
            {
                "orig_start": s["orig_start"],
                "orig_end": s["orig_end"],
                "orig_text": s["orig_text"],
                "category": s["category"],
                "t0": round(t0, 5),
                "t1": round(t1, 5),
            }
        )
        pos += n
    return spans
