import pytest
import yaml
from app.corpus import extract
from app.corpus.loader import CorpusError, Pair, load_split, read_lines, verify
from app.corpus.report import build_report, render_markdown
from conftest import requires_corpus

pytestmark = [pytest.mark.corpus]


@requires_corpus
def test_report_reproduces_plan_values():
    rep = build_report()
    assert rep["diferencias_con_plan"] == []
    assert rep["splits"]["train"]["oraciones"] == 3883
    md = render_markdown(rep)
    assert "Ninguna diferencia" in md


@requires_corpus
def test_extraction_is_deterministic_and_never_cites_test(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    counts = extract.extract_all(a)
    extract.extract_all(b)
    for f in sorted(a.iterdir()):
        assert f.read_bytes() == (b / f.name).read_bytes(), f.name
        text = f.read_text(encoding="utf-8")
        assert "test:" not in text
    assert counts["numerales"] > 0 and counts["pares_variantes"] > 0
    nums = yaml.safe_load((a / "numerals.yaml").read_text(encoding="utf-8"))
    assert all(n["status"] == "candidato-corpus" for n in nums)
    assert any(n["source_form"] == "aparoni" and n["value"] == "1" for n in nums)


@requires_corpus
def test_load_split_and_errors(tmp_path):
    pairs = load_split("dev")
    assert pairs[0].ref == "dev:1" and len(pairs) == 883
    with pytest.raises(ValueError):
        load_split("otro")
    with pytest.raises(CorpusError, match="Falta"):
        verify(tmp_path)
    for name in ["train.cni", "train.es", "dev.cni", "dev.es", "test.cni", "test.es"]:
        (tmp_path / name).write_text("x\n", encoding="utf-8")
    with pytest.raises(CorpusError, match="Hash"):
        verify(tmp_path)
    (tmp_path / "dev.es").write_text("x\ny\n", encoding="utf-8")
    with pytest.raises(CorpusError, match="líneas"):
        load_split("dev", base=tmp_path, check=False)


def test_extractors_on_synthetic_pairs():
    pairs = [
        Pair("train", 1, "Aparoni (1) shiyakotarori, apite (2) Lima", "Uno (1) dice, dos (2) Lima"),
        Pair("train", 2, "Ora amazónicos FOSPA VIII", "Los amazónicos del FOSPA VIII"),
        Pair("dev", 1, "maba kipatsi mava", "tres tierra tres"),
        Pair("dev", 2, "TITULO ENTERO AQUI", "TÍTULO"),
        Pair("dev", 3, "apapakoroni (0,5) itzimatsi itsimatsi", "medio"),
    ]
    nums = extract.extract_numerals(pairs)
    assert {(n["source_form"], n["value"]) for n in nums} >= {("aparoni", "1"), ("apite", "2")}
    half = next(n for n in nums if n["value"] == "0,5")
    assert "valor no entero" in half["noise"]
    acr = {a["source_form"]: a["kind"] for a in extract.extract_acronyms(pairs)}
    assert acr["FOSPA"] == "sigla" and acr["VIII"] == "romano" and "TITULO" not in acr
    loans, names = extract.extract_loans_and_names(pairs)
    assert "amazónicos" in {x["source_form"] for x in loans}
    assert "Lima" in {x["source_form"] for x in names}
    variants = extract.extract_variants(pairs, set(), set())
    keys = {v["key"] for v in variants}
    assert "maba" in keys and "itsimatsi" in keys
    g = extract.extract_graphemes(pairs, set(), {"Lima"})
    assert g["umbral_pct"] == 0.5 and "a" in g["nativas_candidatas"]


def test_helpers(tmp_path):
    assert extract.strip_accents("asháninka") == "ashaninka"
    assert extract.is_heading("ESTO ES TITULO") and not extract.is_heading("Esto no")
    assert extract.variant_key("tzimatsi") == "tsimatsi"
    assert extract.variant_key("quipatsi") == "kipatsi"
    p = tmp_path / "f.txt"
    p.write_bytes(b"a\r\nb\r\n")
    assert read_lines(p) == ["a", "b"]
