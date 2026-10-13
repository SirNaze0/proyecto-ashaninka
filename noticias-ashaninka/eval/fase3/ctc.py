"""Alineación forzada CTC mínima (numpy) para validar los tiempos de VITS (tarea 3.2).

El alineador forzado de MMS del plan usa torchaudio, que no está entre las dependencias del
proyecto; aquí se usa el mismo algoritmo (Viterbi sobre la trellis CTC) con las emisiones de
``mms-1b-all`` (adaptador ``cni``), que ya es la dependencia de evaluación de las Fases 1 y 2.

LIMITACIÓN conocida de CTC: emite picos de 1–2 fotogramas (20 ms cada uno) separados por
blancos, así que el intervalo de un carácter es una cota INTERIOR del sonido real. Por eso se
informa el sesgo con signo además del error absoluto, y se compara también el CENTRO de cada
palabra, que es mucho menos sensible a ese efecto.
"""

from __future__ import annotations

import numpy as np

NEG = -1e30


def forced_align(log_probs: np.ndarray, tokens: list[int], blank: int = 0) -> list[tuple[int, int]]:
    """Viterbi CTC. ``log_probs``: (T, V). Devuelve (inicio, fin) en fotogramas por token.

    ``fin`` es exclusivo. Lanza ValueError si el audio es demasiado corto para los tokens.
    """
    T, L = log_probs.shape[0], len(tokens)
    if L == 0:
        return []
    S = 2 * L + 1
    ext = [blank] * S
    ext[1::2] = tokens
    # Repeticiones consecutivas exigen un blanco entre ambas: se cuentan para el mínimo de frames
    minimo = L + sum(1 for i in range(1, L) if tokens[i] == tokens[i - 1])
    if T < minimo:
        raise ValueError(f"audio demasiado corto: {T} fotogramas para {minimo} necesarios")
    dp = np.full((T, S), NEG)
    back = np.zeros((T, S), dtype=np.int8)
    dp[0, 0] = log_probs[0, ext[0]]
    if S > 1:
        dp[0, 1] = log_probs[0, ext[1]]
    for t in range(1, T):
        for s in range(S):
            best, arg = dp[t - 1, s], 0
            if s >= 1 and dp[t - 1, s - 1] > best:
                best, arg = dp[t - 1, s - 1], 1
            if s >= 2 and ext[s] != blank and ext[s] != ext[s - 2] and dp[t - 1, s - 2] > best:
                best, arg = dp[t - 1, s - 2], 2
            if best > NEG / 2:
                dp[t, s] = best + log_probs[t, ext[s]]
                back[t, s] = arg
    s = S - 1 if dp[T - 1, S - 1] >= dp[T - 1, S - 2] else S - 2
    path = [0] * T
    for t in range(T - 1, -1, -1):
        path[t] = s
        s -= int(back[t, s])
    spans: dict[int, list[int]] = {}
    for t, st in enumerate(path):
        if st % 2 == 1:
            spans.setdefault(st // 2, []).append(t)
    return [(min(spans[i]), max(spans[i]) + 1) for i in range(L)]


def words_from_chars(text: str, spans: list[tuple[float, float]]) -> list[tuple[str, float, float]]:
    """Agrupa tiempos por carácter en palabras (separadas por espacios)."""
    if len(text) != len(spans):
        raise ValueError("un intervalo por carácter")
    out: list[tuple[str, float, float]] = []
    i = 0
    while i < len(text):
        if text[i] == " ":
            i += 1
            continue
        j = i
        while j < len(text) and text[j] != " ":
            j += 1
        out.append((text[i:j], spans[i][0], spans[j - 1][1]))
        i = j
    return out


def error_stats(errors_ms: list[float]) -> dict:
    a = np.asarray(errors_ms, dtype=float)
    if a.size == 0:
        return {"n": 0}
    ab = np.abs(a)
    return {
        "n": int(a.size),
        "sesgo_ms": round(float(a.mean()), 1),
        "mae_ms": round(float(ab.mean()), 1),
        "mediana_abs_ms": round(float(np.median(ab)), 1),
        "p90_abs_ms": round(float(np.percentile(ab, 90)), 1),
        "dentro_de_50ms": round(float((ab <= 50).mean()), 3),
        "dentro_de_80ms": round(float((ab <= 80).mean()), 3),
    }
