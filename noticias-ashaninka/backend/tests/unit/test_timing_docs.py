import math

import pytest
from app.config import CANDIDATES_DIR
from app.docs_builder import build_normalization_docs
from app.metrics.timing import Timer, percentile
from app.pipeline.g2p.inventory_builder import build_inventory


def test_percentile_and_timer():
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([5], 95) == 5
    assert math.isnan(percentile([], 50))
    t = Timer()
    for _ in range(3):
        with t.measure("x"):
            pass
    s = t.summary()["x"]
    assert s["n"] == 3 and s["p95"] >= s["p50"] >= 0


def test_build_docs(tmp_path):
    out = build_normalization_docs(tmp_path / "rules.md")
    text = out.read_text(encoding="utf-8")
    assert "GENERADO" in text and "mms_cni_adapter" in text and "SUPUESTO-LING" in text


@pytest.mark.skipif(not (CANDIDATES_DIR / "graphemes.yaml").exists(), reason="sin candidatos")
def test_inventory_builder_excludes_unified_letters():
    inv = build_inventory()
    graphemes = {e["grapheme"] for e in inv["entries"]}
    assert {"ts", "sh", "ch", "ty"} <= graphemes
    assert not {"v", "z", "c"} & graphemes
    assert all(e["status"] == "candidato-corpus" and e["phoneme"] is None for e in inv["entries"])
