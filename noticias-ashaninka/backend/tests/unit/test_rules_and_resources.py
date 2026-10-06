import pytest
from app.pipeline import resources as R
from app.pipeline.rules import RewriteEngine, RewriteRule, check_map, merge_identity
from app.pipeline.types import CharMapEntry, NormalizedSpan, to_jsonable


@pytest.mark.smoke
def test_engine_applies_first_matching_rule_and_maps():
    eng = RewriteEngine([RewriteRule("A", "ab", "X"), RewriteRule("B", "a", "YY")])
    out, cmap = eng.apply("abac")
    assert out == "XYYc"
    assert check_map(cmap, "abac", out) == []
    assert [e.rule_id for e in cmap] == ["A", "B", None]


def test_engine_context_and_deletion():
    eng = RewriteEngine([RewriteRule("K", "k(?=[ei])", "qu"), RewriteRule("D", "-", "")])
    out, cmap = eng.apply("ki-ka")
    assert out == "quika"
    assert check_map(cmap, "ki-ka", out) == []


def test_merge_identity_and_check_map_detects_gaps():
    merged = merge_identity([CharMapEntry(0, 1, 0, 1), CharMapEntry(1, 2, 1, 2)])
    assert merged == [CharMapEntry(0, 2, 0, 2)]
    bad = [CharMapEntry(0, 1, 0, 1), CharMapEntry(2, 3, 1, 2)]
    problems = check_map(bad, "abc", "ab")
    assert any("hueco" in p for p in problems)
    assert check_map([CharMapEntry(0, 1, 0, 1)], "ab", "ab")  # cobertura incompleta


def test_to_jsonable():
    span = NormalizedSpan(0, 1, "a", "a", "identity")
    assert to_jsonable([span])[0]["category"] == "identity"
    assert to_jsonable(3) == 3


@pytest.mark.smoke
def test_all_real_resources_are_valid():
    counts = R.validate_all()
    assert "mms_cni.yaml" in counts
    assert "inventory.yaml" in counts


def test_entry_rejects_test_split_examples(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(
        "resource: x\ndescription: d\nentries:\n"
        "  - id: X-1\n    source: s\n    status: validado\n"
        "    examples: [{input: a, output: b, ref: 'test:12'}]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="test"):
        R.load_resource(p)


def test_duplicate_ids_rejected(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(
        "resource: x\ndescription: d\nentries:\n"
        "  - {id: A, source: s, status: validado}\n  - {id: A, source: s, status: validado}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicados"):
        R.load_resource(p)


def test_usable_entries_and_bundle_hash(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(
        "resource: x\ndescription: d\nentries:\n"
        "  - {id: A, source: s, status: validado}\n"
        "  - {id: B, source: s, status: candidato-corpus}\n",
        encoding="utf-8",
    )
    r = R.get_resource(p)
    assert [e.id for e in r.usable_entries()] == ["A"]
    assert [e.id for e in r.usable_entries(allow_candidates=True)] == ["A", "B"]
    assert r.counts() == {"validado": 1, "candidato-corpus": 1}
    assert r.entries[0].usable and not r.entries[1].usable
    h1 = R.bundle_hash([r])
    assert h1 == R.bundle_hash([r]) and len(h1) == 64


def test_no_real_resource_cites_test_split():
    for path in R.all_resource_paths():
        assert "test:" not in path.read_text(encoding="utf-8").replace("ref: 'test", "")
