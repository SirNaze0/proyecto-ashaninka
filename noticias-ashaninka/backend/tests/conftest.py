"""Fixtures compartidos.

IMPORTANTE: los recursos de ``fake_resources`` son FICTICIOS (alfabeto "xyz" inventado). Sirven
para probar los motores sin depender de datos lingüísticos sin validar. Nunca se presentan como
asháninka.
"""

from __future__ import annotations

import pytest
from app.corpus.loader import corpus_available
from app.pipeline.resources import Resource


def res(name: str, entries: list[dict] | None = None, config: dict | None = None) -> Resource:
    return Resource.model_validate(
        {
            "resource": name,
            "description": f"FICTICIO para pruebas: {name}",
            "config": config or {},
            "entries": entries or [],
            "sha256": f"fake-{name}",
        }
    )


def e(id_: str, status: str = "validado", **kw) -> dict:
    return {"id": id_, "source": "fixture ficticio", "status": status, **kw}


@pytest.fixture
def fake_inventory() -> Resource:
    # Alfabeto inventado: a e i o m n s t x y z + dígrafo "xy"
    letters = list("aeiomnstxyz")
    entries = [e("INV-XY", grapheme="xy", phoneme="X")]
    entries += [e(f"INV-{c.upper()}", grapheme=c, phoneme=c.upper()) for c in letters]
    return res("g2p_inventory", entries, {"excluidas_por_unificacion": ["q"]})


@pytest.fixture
def fake_resources() -> dict[str, Resource]:
    return {
        "orthography_variants": res(
            "orthography_variants",
            [e("F-ORT-1", pattern="q", replacement="x", status="SUPUESTO-LING")],
            {"apply_statuses": ["validado", "SUPUESTO-LING"]},
        ),
        "numerals_cni": res(
            "numerals_cni",
            [
                e("F-NUM-1", replacement="mon", value=1),
                e("F-NUM-2", replacement="tos", value=2),
                e("F-NUM-3", status="candidato-corpus", replacement="tix", value=3),
            ],
            {"small_max": None},
        ),
        "acronyms": res(
            "acronyms",
            [
                e("F-ACR-1", source_form="XYZ", replacement="ixiz", gloss_cni="mano tasi"),
                e("F-ACR-2", source_form="ONU", reading="spell"),
            ],
            {"letter_names_es": {"O": "o", "N": "ene", "U": "u"}},
        ),
        "loanwords": res("loanwords", [e("F-LOAN-1", source_form="radio", replacement="ratio")]),
        "es_to_cni_phonology": res(
            "es_to_cni_phonology",
            [
                e("F-P2D-1", pattern="d", replacement="t"),
                e("F-P2D-2", pattern="r", replacement="n"),
            ],
        ),
        "neologisms": res("neologisms", [e("F-NEO-1", source_form="vacuna", replacement="mosi")]),
        "proper_nouns": res("proper_nouns", [e("F-PN-1", source_form="Lima", replacement="nima")]),
        "relative_dates": res("relative_dates", config={"es": ["ayer", "hoy"], "cni": []}),
    }


@pytest.fixture
def fake_normalizer(fake_resources, fake_inventory):
    from app.pipeline.normalize.engine import Normalizer

    return Normalizer(fake_resources, fake_inventory)


requires_corpus = pytest.mark.skipif(
    not corpus_available(), reason="corpus AmericasNLP no descargado (ejecuta ./init.sh)"
)


# Token administrativo de las pruebas (16 caracteres o más: si no, el servidor lo rechaza)
ADMIN_TOKEN = "token-admin-de-pruebas-0123456789"
ADMIN = {"x-admin-token": ADMIN_TOKEN}


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Base de datos SQLite temporal y aislada para cada prueba."""
    monkeypatch.setenv("NA_ADMIN_TOKEN", ADMIN_TOKEN)
    from app.db import session as db_session

    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    monkeypatch.setenv("NA_DATABASE_URL", url)
    db_session.get_engine.cache_clear()
    engine = db_session.get_engine()
    db_session.init_db(engine)
    yield engine
    engine.dispose()
    db_session.get_engine.cache_clear()
