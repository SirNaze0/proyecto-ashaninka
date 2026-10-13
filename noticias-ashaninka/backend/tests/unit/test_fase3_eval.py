"""Pruebas de las utilidades de la evaluación de la Fase 3 (sin modelos, sin navegador)."""

from __future__ import annotations

import io
import json
import struct

import numpy as np
import pytest
from PIL import Image

from eval.fase3.ctc import error_stats, forced_align, words_from_chars
from eval.fase3.lipsync import envelope, lag_xcorr, resumen
from eval.fase3.praat import errores_limites, leer_textgrid, limites, textgrid_vacio


# ------------------------------------------------------------------ alineación forzada CTC
def emisiones(path: list[int], vocab: int = 5, pico: float = 0.97) -> np.ndarray:
    lp = np.full((len(path), vocab), np.log((1 - pico) / (vocab - 1)))
    for t, k in enumerate(path):
        lp[t, k] = np.log(pico)
    return lp


def test_forced_align_recovers_known_alignment():
    # blanco=0; tokens 1,2,3 en los fotogramas 2-3, 5 y 7-8
    camino = [0, 0, 1, 1, 0, 2, 0, 3, 3, 0]
    spans = forced_align(emisiones(camino), [1, 2, 3])
    assert spans == [(2, 4), (5, 6), (7, 9)]


def test_forced_align_handles_repeated_tokens_and_short_audio():
    camino = [1, 1, 0, 1, 1, 0]  # "aa": exige un blanco entre las dos
    assert forced_align(emisiones(camino), [1, 1]) == [(0, 2), (3, 5)]
    with pytest.raises(ValueError, match="demasiado corto"):
        forced_align(emisiones([1, 1]), [1, 1])
    assert forced_align(emisiones([0, 0]), []) == []


def test_words_from_chars_and_stats():
    spans = [(0.0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.5)]
    assert words_from_chars("ab cd"[:2] + " " + "c", spans[:4])[0] == ("ab", 0.0, 0.2)
    with pytest.raises(ValueError):
        words_from_chars("ab", spans)
    s = error_stats([-10.0, 10.0, 60.0, -100.0])
    assert s["n"] == 4 and s["mae_ms"] == 45.0 and s["dentro_de_50ms"] == 0.5
    assert error_stats([]) == {"n": 0}


# ------------------------------------------------------------------ desfase por correlación
def senal(hz: int = 50, dur: float = 6.0, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(hz * dur)
    x = np.convolve(rng.random(n), np.hanning(7), mode="same")
    return (x - x.min()) / (x.max() - x.min())


@pytest.mark.parametrize("retraso_ms", [-120, -40, 0, 20, 80, 140])
def test_lag_xcorr_recovers_the_delay(retraso_ms):
    a = senal()
    k = retraso_ms // 20  # 50 Hz -> 20 ms por muestra
    m = np.roll(a, k)  # boca retrasada k muestras respecto del audio
    lag, corr = lag_xcorr(a, m)
    assert lag == pytest.approx(retraso_ms, abs=4)
    assert corr > 0.9


def test_lag_xcorr_subsample_interpolation():
    a = senal(dur=10)
    t = np.arange(len(a))
    m = np.interp(t - 0.5, t, a)  # retraso de media muestra = 10 ms
    assert lag_xcorr(a, m)[0] == pytest.approx(10, abs=4)


def test_envelope_follows_amplitude():
    sr = 16000
    wav = np.concatenate([np.zeros(sr), 0.5 * np.sin(np.linspace(0, 2000, sr))])
    e = envelope(wav, sr, 100)
    assert e[:40].max() < 0.01 and e[60:].min() > 0.2
    assert resumen([1.0, 3.0, 5.0])["mediana"] == 3.0


# ------------------------------------------------------------------ Praat
def test_textgrid_roundtrip_and_errors(tmp_path):
    vacio = textgrid_vacio(2.0, ["palabras", "fonemas"])
    p = tmp_path / "x.TextGrid"
    p.write_text(vacio, encoding="utf-8")
    niveles = leer_textgrid(p)
    assert set(niveles) == {"palabras", "fonemas"} and limites(niveles["palabras"]) == []

    anotado = vacio.replace('text = ""', 'text = "tee"', 1)
    p.write_text(anotado, encoding="utf-8")
    assert limites(leer_textgrid(p)["palabras"]) == [(0.0, 2.0)]

    err = errores_limites([(0.0, 0.30), (0.4, 0.9)], [(0.01, 0.28), (0.45, 0.9)])
    assert err == pytest.approx([10, -20, 50, 0])
    with pytest.raises(ValueError, match="número distinto"):
        errores_limites([(0, 1)], [(0, 1), (1, 2)])


# ------------------------------------------------------------------ recompresión del VRM
def glb_minimo() -> bytes:
    from scripts.optimize_vrm import escribir_glb

    img = Image.new("RGB", (2048, 2048), (200, 120, 80))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    png = buf.getvalue()
    geom = struct.pack("<3f", 0, 0, 0) * 3
    doc = {
        "asset": {"version": "2.0"},
        "extensions": {"VRMC_vrm": {"specVersion": "1.0"}},
        "extensionsUsed": ["VRMC_vrm"],
        "buffers": [{"byteLength": len(geom) + len(png)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(geom)},
            {"buffer": 0, "byteOffset": len(geom), "byteLength": len(png)},
        ],
        "images": [{"bufferView": 1, "mimeType": "image/png"}],
    }
    return escribir_glb(doc, geom + png)


def test_optimize_vrm_shrinks_textures_and_keeps_extensions(tmp_path):
    from scripts.optimize_vrm import leer_glb, optimizar

    ent, sal = tmp_path / "a.vrm", tmp_path / "b.vrm"
    ent.write_bytes(glb_minimo())
    r = optimizar(ent, sal, max_px=512)
    assert r["bytes_despues"] < r["bytes_antes"]
    doc, binario = leer_glb(sal.read_bytes())
    assert doc["extensions"]["VRMC_vrm"]["specVersion"] == "1.0"  # el VRM sigue siendo VRM
    v = doc["bufferViews"][1]
    img = Image.open(io.BytesIO(binario[v["byteOffset"] : v["byteOffset"] + v["byteLength"]]))
    assert max(img.size) == 512 and doc["images"][0]["mimeType"] == "image/jpeg"
    assert doc["buffers"][0]["byteLength"] <= len(binario)
    json.dumps(doc)  # sigue siendo serializable


def glb_con_morphs() -> bytes:
    """GLB con una malla de 3 morph targets (A, B, C) y dos expresiones VRM (aa -> A, blink -> C)."""
    from scripts.optimize_vrm import escribir_glb

    n = 4  # vértices
    base = struct.pack("<12f", *range(12))
    deltas = [struct.pack("<12f", *[float(k)] * 12) for k in (1, 2, 3)]
    binario = base + b"".join(deltas)
    doc = {
        "asset": {"version": "2.0"},
        "extensionsUsed": ["VRMC_vrm"],
        "extensions": {
            "VRMC_vrm": {
                "specVersion": "1.0",
                "expressions": {
                    "preset": {
                        "aa": {"morphTargetBinds": [{"node": 0, "index": 0, "weight": 1}]},
                        "blink": {"morphTargetBinds": [{"node": 0, "index": 2, "weight": 1}]},
                        "happy": {"morphTargetBinds": [{"node": 0, "index": 1, "weight": 1}]},
                    }
                },
            }
        },
        "nodes": [{"mesh": 0}],
        "meshes": [
            {
                "extras": {"targetNames": ["A", "B", "C"]},
                "primitives": [
                    {
                        "attributes": {"POSITION": 0},
                        "targets": [{"POSITION": 1}, {"POSITION": 2}, {"POSITION": 3}],
                    }
                ],
            }
        ],
        "accessors": [
            {"bufferView": i, "componentType": 5126, "count": n, "type": "VEC3"} for i in range(4)
        ],
        "bufferViews": [{"buffer": 0, "byteOffset": i * 48, "byteLength": 48} for i in range(4)],
        "buffers": [{"byteLength": len(binario)}],
    }
    return escribir_glb(doc, binario)


def test_recorte_de_expresiones_elimina_morph_targets_sin_uso(tmp_path):
    from scripts.optimize_vrm import leer_glb, optimizar

    ent, sal = tmp_path / "m.vrm", tmp_path / "m2.vrm"
    ent.write_bytes(glb_con_morphs())
    r = optimizar(ent, sal, mantener_expresiones={"aa", "blink"})
    assert r["expresiones"] == ["aa", "blink"] and r["bytes_despues"] < r["bytes_antes"]
    doc, binario = leer_glb(sal.read_bytes())
    prim = doc["meshes"][0]["primitives"][0]
    assert len(prim["targets"]) == 2 and doc["meshes"][0]["extras"]["targetNames"] == ["A", "C"]
    binds = doc["extensions"]["VRMC_vrm"]["expressions"]["preset"]
    assert binds["aa"]["morphTargetBinds"][0]["index"] == 0
    assert binds["blink"]["morphTargetBinds"][0]["index"] == 1
    assert "happy" not in binds
    assert len(doc["accessors"]) == 3 and len(doc["bufferViews"]) == 3  # base + 2 targets
    # el delta del target "C" (valor 3.0) quedó en el segundo target
    acc = doc["accessors"][prim["targets"][1]["POSITION"]]
    v = doc["bufferViews"][acc["bufferView"]]
    assert struct.unpack_from("<f", binario, v["byteOffset"])[0] == 3.0
