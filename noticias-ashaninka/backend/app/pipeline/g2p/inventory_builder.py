"""Genera ``g2p/rules/inventory.yaml`` a partir de la evidencia del corpus (data/candidates/graphemes.yaml).

Criterios documentados (no son decisiones lingüísticas; todo queda ``candidato-corpus``):

* letras: las ``nativas_candidatas`` del extractor (frecuencia relativa >= 0,5 % en palabras no
  compartidas con la línea castellana), excluyendo las que la unificación 2-0 elimina de la
  ortografía canónica (``v`` -> ``b``; ``z`` solo aparece en ``tz`` -> ``ts``);
* dígrafos: secuencias observadas >= 1000 veces que la ortografía canónica conserva
  (``ch``, ``sh``, ``ts``, ``ty``). Que cada una sea un único fonema es P1 (SUPUESTO-LING).

``phoneme: null`` significa "sin validar": el G2P emite la etiqueta del grafema como marcador.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.config import CANDIDATES_DIR, G2P_RULES

REMOVED_BY_UNIFICATION = {"v", "z", "c"}
DIGRAPH_MIN_COUNT = 1000
DIGRAPHS_KEPT_IN_CANONICAL = ["ch", "sh", "ts", "ty"]


def build_inventory(graphemes_path: Path = CANDIDATES_DIR / "graphemes.yaml") -> dict:
    data = yaml.safe_load(graphemes_path.read_text(encoding="utf-8"))
    by_letter = {r["grapheme"]: r for r in data["letras"]}
    entries = []
    for dg in DIGRAPHS_KEPT_IN_CANONICAL:
        count = data["digrafos_observados"].get(dg, 0)
        if count < DIGRAPH_MIN_COUNT:
            continue
        entries.append(
            {
                "id": f"INV-{dg.upper()}",
                "description": f"Dígrafo observado {count} veces (train+dev)",
                "grapheme": dg,
                "phoneme": None,
                "frequency": count,
                "source": "AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml)",
                "status": "candidato-corpus",
            }
        )
    for letter in data["nativas_candidatas"]:
        if letter in REMOVED_BY_UNIFICATION:
            continue
        r = by_letter[letter]
        entries.append(
            {
                "id": f"INV-{letter.upper()}",
                "description": f"Letra con frecuencia relativa {r['pct']} %",
                "grapheme": letter,
                "phoneme": None,
                "frequency": r["count"],
                "source": "AmericasNLP2021@d3f519c (data/candidates/graphemes.yaml)",
                "status": "candidato-corpus",
            }
        )
    return {
        "resource": "g2p_inventory",
        "description": "Inventario de grafemas canónicos y su fonema",
        "config": {
            "criterio": data["criterio"],
            "digrafo_min": DIGRAPH_MIN_COUNT,
            "excluidas_por_unificacion": sorted(REMOVED_BY_UNIFICATION),
        },
        "entries": entries,
    }


HEADER = (
    "# Inventario de grafemas (P1). GENERADO por `uv run python -m app.cli corpus inventory`.\n"
    "# SUPUESTO-LING: todo es candidato-corpus y phoneme=null hasta validar con P1 (alfabeto oficial).\n"
    "# Para validar: completar 'phoneme' (IPA) y cambiar status a 'validado'. Tras editarlo a mano,\n"
    "# no volver a ejecutar la orden (sobrescribe el archivo).\n"
)


def write_inventory(out: Path = G2P_RULES / "inventory.yaml") -> Path:
    inv = build_inventory()
    out.write_text(
        HEADER + yaml.safe_dump(inv, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
        newline="\n",
    )
    return out
