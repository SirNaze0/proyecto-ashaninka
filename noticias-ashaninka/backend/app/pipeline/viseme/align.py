"""Alineación por fonema y por palabra (tarea 3.2).

Entrada: el texto canónico del segmento y los tiempos por carácter canónico que ya produce
``batch/timings.py`` a partir de las duraciones REALES de VITS. El G2P (segmentación grafémica)
dice qué caracteres forman cada fonema; el tiempo de un fonema es el intervalo
[inicio de su primer carácter, fin de su último carácter].

No se usa ningún alineador externo: la validación contra el alineador forzado de MMS está en
``eval/fase3/alignment.py``.

SUPUESTO-LING: mientras P1 no esté validado, el "fonema" es el grafema segmentado por el G2P.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.pipeline.g2p.engine import G2P, WORD_RX


@dataclass(frozen=True)
class PhonemeTime:
    g: str  # grafema canónico (en minúscula) que produjo el fonema
    label: str  # etiqueta del G2P: "<ts>" mientras no haya inventario validado
    word: int  # índice de la palabra dentro del segmento
    c0: int  # offset inicial en el texto canónico (incluido)
    c1: int  # offset final (excluido)
    t0: float
    t1: float

    def to_dict(self) -> dict:
        d = asdict(self)
        d["t0"], d["t1"] = round(self.t0, 4), round(self.t1, 4)
        return d


@dataclass(frozen=True)
class WordTime:
    text: str
    c0: int
    c1: int
    t0: float
    t1: float

    def to_dict(self) -> dict:
        d = asdict(self)
        d["t0"], d["t1"] = round(self.t0, 4), round(self.t1, 4)
        return d


def align_text(
    text_canonical: str, canon_times: list[tuple[float, float]], g2p: G2P
) -> tuple[list[WordTime], list[PhonemeTime]]:
    """Tiempos por palabra y por fonema. Los caracteres que el G2P no reconoce no tienen fonema."""
    if len(canon_times) != len(text_canonical):
        raise ValueError("canon_times debe tener un intervalo por carácter canónico")
    words: list[WordTime] = []
    phonemes: list[PhonemeTime] = []
    for m in WORD_RX.finditer(text_canonical):
        pw, _unknown = g2p.word(m.group(0), offset=m.start())
        if not pw.phonemes:
            continue
        widx = len(words)
        w_phs: list[PhonemeTime] = []
        i = 0
        while i < len(pw.phonemes):
            # Los fonemas que comparten el mismo tramo de caracteres se reparten el intervalo
            j = i
            while j + 1 < len(pw.phonemes) and pw.char_spans[j + 1] == pw.char_spans[i]:
                j += 1
            a, b = pw.char_spans[i]
            c0, c1 = m.start() + a, m.start() + b
            t0, t1 = canon_times[c0][0], canon_times[c1 - 1][1]
            n = j - i + 1
            for k in range(n):
                w_phs.append(
                    PhonemeTime(
                        g=text_canonical[c0:c1].lower(),
                        label=pw.phonemes[i + k],
                        word=widx,
                        c0=c0,
                        c1=c1,
                        t0=t0 + (t1 - t0) * k / n,
                        t1=t0 + (t1 - t0) * (k + 1) / n,
                    )
                )
            i = j + 1
        phonemes.extend(w_phs)
        words.append(WordTime(m.group(0), m.start(), m.end(), w_phs[0].t0, w_phs[-1].t1))
    return words, phonemes
