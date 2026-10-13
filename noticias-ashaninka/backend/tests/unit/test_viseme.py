"""Pruebas de la alineación por fonema y de la pista de visemas (Fase 3, tareas 3.2–3.4).

Los datos lingüísticos reales (inventario del G2P y mapa de visemas) se usan solo para comprobar
propiedades estructurales; los casos con pesos concretos usan un mapa FICTICIO definido aquí.
"""

from __future__ import annotations

import pytest
from app.batch.timings import canonical_times
from app.pipeline.g2p.engine import G2P
from app.pipeline.resources import get_resource
from app.pipeline.viseme.align import PhonemeTime, WordTime, align_text
from app.pipeline.viseme.track import (
    MAP_PATH,
    VisemeMap,
    build_events,
    build_keyframes,
    build_track,
    sample,
)
from conftest import e, res


def mapa_ficticio() -> VisemeMap:
    ent = [
        e("V-A", "SUPUESTO-LING", grapheme="a", weights={"A": 1.0}, coarticulation=0.0),
        e("V-I", "SUPUESTO-LING", grapheme="i", weights={"I": 1.0}, coarticulation=0.0),
        e("V-M", "SUPUESTO-LING", grapheme="m", weights={"C": 1.0}, coarticulation=0.0),
        e("V-T", "SUPUESTO-LING", grapheme="t", weights={}, coarticulation=0.5),
    ]
    return VisemeMap(res("viseme_map", ent, {"channels": ["A", "I", "U", "E", "O", "C"]}))


def fonema(g: str, t0: float, t1: float, word: int = 0, c0: int = 0) -> PhonemeTime:
    return PhonemeTime(g, f"<{g}>", word, c0, c0 + len(g), t0, t1)


# ------------------------------------------------------------------ mapa real
def test_real_map_is_marked_supuesto_and_matches_inventory():
    r = get_resource(MAP_PATH)
    assert r.entries and all(x.status == "SUPUESTO-LING" for x in r.entries)
    vm = VisemeMap.from_file()
    assert vm.status == "SUPUESTO-LING" and len(vm.sha256) == 64
    inventario = get_resource(MAP_PATH.parents[2] / "g2p" / "rules" / "inventory.yaml")
    faltan = {x.model_extra["grapheme"] for x in inventario.entries} - set(vm.entries)
    assert not faltan, f"grafemas del inventario sin visema: {sorted(faltan)}"
    for ent in vm.entries.values():
        assert all(0.0 <= w <= 1.0 for w in ent.weights.values())
        assert 0.0 <= ent.coarticulation <= 1.0


def test_unknown_channel_is_rejected():
    ent = [e("V-X", "SUPUESTO-LING", grapheme="a", weights={"Z": 1.0})]
    with pytest.raises(ValueError, match="canales desconocidos"):
        VisemeMap(res("viseme_map", ent, {"channels": ["A"]}))


# ------------------------------------------------------------------ alineación (3.2)
def test_alignment_covers_words_and_graphemes():
    g2p = G2P.from_files()
    texto = "tee otimimotena."
    # 100 ms por carácter canónico, sin pausas especiales
    times = [(i * 0.1, (i + 1) * 0.1) for i in range(len(texto))]
    words, phs = align_text(texto, times, g2p)
    assert [w.text for w in words] == ["tee", "otimimotena"]
    assert words[0].t0 == 0.0 and words[0].t1 == pytest.approx(0.3)
    assert words[1].t0 == pytest.approx(0.4)  # tras el espacio
    assert "".join(p.g for p in phs if p.word == 0) == "tee"
    assert all(p.t0 <= p.t1 for p in phs)
    assert phs == sorted(phs, key=lambda p: p.t0)


def test_alignment_digraph_takes_both_characters():
    g2p = G2P.from_files()
    times = [(0.0, 0.1), (0.1, 0.3), (0.3, 0.4)]  # "tsa": el dígrafo "ts" ocupa 0.0–0.3
    _, phs = align_text("tsa", times, g2p)
    assert [p.g for p in phs] == ["ts", "a"]
    assert (phs[0].t0, phs[0].t1) == (0.0, 0.3)


def test_alignment_requires_one_interval_per_char():
    with pytest.raises(ValueError):
        align_text("ab", [(0.0, 1.0)], G2P.from_files())


def test_unknown_graphemes_have_no_phoneme():
    g2p = G2P.from_files()
    _, phs = align_text("a?", [(0.0, 0.1), (0.1, 0.2)], g2p)
    assert [p.g for p in phs] == ["a"]


# ------------------------------------------------------------------ pista de visemas (3.4)
def test_events_are_contiguous_and_cover_the_segment():
    vm = mapa_ficticio()
    phs = [fonema("a", 0.2, 0.4), fonema("m", 0.4, 0.5, c0=1), fonema("i", 0.6, 0.8, word=1, c0=3)]
    ev = build_events(phs, 1.0, vm)
    assert ev[0][0] == 0.0 and ev[-1][1] == 1.0
    for a, b in zip(ev, ev[1:], strict=False):
        assert a[1] == pytest.approx(b[0])
    assert ev[0][2] == [0.0] * 6 and ev[-1][2] == [0.0] * 6  # silencios inicial y final


def test_vowel_and_labial_weights():
    vm = mapa_ficticio()
    phs = [fonema("a", 0.0, 0.3), fonema("m", 0.3, 0.6, c0=1)]
    kf = build_events(phs, 0.6, vm)
    kf = build_keyframes(kf, 40, 0.5)
    assert sample(kf, 0.1) == [1.0, 0, 0, 0, 0, 0]
    assert sample(kf, 0.5)[5] == pytest.approx(1.0) and sample(kf, 0.5)[0] == pytest.approx(0.0)


def test_transition_width_and_lead():
    vm = mapa_ficticio()
    phs = [fonema("a", 0.0, 0.3), fonema("i", 0.3, 0.6, c0=1)]
    ev = build_events(phs, 0.6, vm)
    for lead in (0.5, 1.0, 0.0):
        kf = build_keyframes(ev, 60, lead)
        ini, fin = 0.3 - 0.06 * lead, 0.3 + 0.06 * (1 - lead)
        assert sample(kf, ini - 0.001)[0] == pytest.approx(1.0)
        assert sample(kf, fin + 0.001)[1] == pytest.approx(1.0)
        # en medio de la transición los dos canales están entre 0 y 1
        a = sample(kf, (ini + fin) / 2)
        assert 0 < a[0] < 1 and 0 < a[1] < 1


def test_transition_is_limited_by_short_events():
    vm = mapa_ficticio()
    phs = [fonema("a", 0.0, 0.02), fonema("i", 0.02, 0.5, c0=1)]  # 'a' dura solo 20 ms
    kf = build_keyframes(build_events(phs, 0.5, vm), 60, 0.5)
    tiempos = [k[0] for k in kf]
    assert tiempos == sorted(tiempos)
    assert all(0 <= t <= 0.5 for t in tiempos)


def test_zero_smoothing_gives_a_step():
    vm = mapa_ficticio()
    phs = [fonema("a", 0.0, 0.3), fonema("i", 0.3, 0.6, c0=1)]
    kf = build_keyframes(build_events(phs, 0.6, vm), 0, 0.5)
    assert sample(kf, 0.299)[0] == pytest.approx(1.0) and sample(kf, 0.301)[1] == pytest.approx(1.0)


def test_coarticulation_only_within_the_same_word_and_adjacent():
    vm = mapa_ficticio()
    # 't' (coart 0.5) seguida de 'a' contigua y de la misma palabra -> adopta 0,5 de A
    mismo = build_events([fonema("t", 0.0, 0.1), fonema("a", 0.1, 0.3, c0=1)], 0.3, vm)
    assert mismo[0][2][0] == pytest.approx(0.5)
    # otra palabra -> sin coarticulación
    otra = build_events([fonema("t", 0.0, 0.1), fonema("a", 0.1, 0.3, word=1, c0=2)], 0.3, vm)
    assert otra[0][2][0] == 0.0
    # con un hueco entre ambas -> sin coarticulación
    hueco = build_events([fonema("t", 0.0, 0.1), fonema("a", 0.2, 0.3, c0=1)], 0.3, vm)
    assert hueco[0][2][0] == 0.0


def test_identical_neighbours_are_merged():
    vm = mapa_ficticio()
    phs = [fonema("a", 0.0, 0.1), fonema("a", 0.1, 0.2, c0=1)]
    kf = build_keyframes(build_events(phs, 0.2, vm), 50, 0.5)
    assert len(kf) == 2 and kf[0][0] == 0.0 and kf[-1][0] == 0.2


def test_build_track_block_is_traceable_and_parametrizable():
    vm = mapa_ficticio()
    w = [WordTime("a", 0, 1, 0.0, 0.2)]
    out = build_track(w, [fonema("a", 0.0, 0.2)], 0.2, vm, smooth_ms=40, lead=0.25)
    v = out["visemes"]
    assert v["status"] == "SUPUESTO-LING" and v["map_sha256"] == vm.sha256
    assert (v["smooth_ms"], v["lead"], v["duration_s"]) == (40.0, 0.25, 0.2)
    assert v["channels"] == ["A", "I", "U", "E", "O", "C"]
    assert (
        out["alignment"]["words"][0]["text"] == "a" and "SUPUESTO-LING" in out["alignment"]["nota"]
    )
    with pytest.raises(ValueError):
        build_track(w, [], 0.2, vm, smooth_ms=-1)
    with pytest.raises(ValueError):
        build_track(w, [], 0.2, vm, lead=1.5)


def test_env_overrides_smoothing(monkeypatch):
    vm = mapa_ficticio()
    monkeypatch.setenv("NA_VISEME_SMOOTH_MS", "60")
    monkeypatch.setenv("NA_VISEME_LEAD", "0.25")
    v = build_track([], [], 0.1, vm)["visemes"]
    assert (v["smooth_ms"], v["lead"]) == (60.0, 0.25)


def test_sample_edge_cases():
    assert sample([], 0.1) == []
    kf = [[0.1, [1.0]], [0.2, [0.0]]]
    assert sample(kf, 0.0) == [1.0] and sample(kf, 0.3) == [0.0]
    assert sample(kf, 0.15)[0] == pytest.approx(0.5)


def test_pipeline_from_canonical_times_end_to_end():
    """Cadena completa sobre texto real: tiempos de carácter -> fonemas -> keyframes válidos."""
    g2p = G2P.from_files()
    texto = "tee otimimotena."
    tts_times = [(i * 0.08, (i + 1) * 0.08) for i in range(len(texto))]
    cmap = [
        {"src_start": i, "src_end": i + 1, "dst_start": i, "dst_end": i + 1}
        for i in range(len(texto))
    ]
    canon = canonical_times(len(texto), tts_times, cmap)
    words, phs = align_text(texto, canon, g2p)
    out = build_track(words, phs, tts_times[-1][1])["visemes"]
    kf = out["keyframes"]
    assert [k[0] for k in kf] == sorted(k[0] for k in kf)
    assert all(len(k[1]) == len(out["channels"]) for k in kf)
    assert all(0.0 <= x <= 1.0 for k in kf for x in k[1])
