"""Construye el kit de escucha (tarea 5.7): inteligibilidad por palabras clave y MOS, MMS frente a eSpeak.

Diseño (definido en ``docs/metrics.md`` antes de construir):
* ``--n`` oraciones del split **test** (semilla fija, nunca se ajusta nada con ellas), cada una
  sintetizada con **ambos motores** (``mms_vits`` y ``espeak_ng``) por el registro de motores.
* Orden aleatorio fijo, nombres de archivo codificados (no revelan el motor) y mismo volumen (RMS)
  en todos los audios: el oyente no sabe qué motor oye ni lo delata el volumen.
* El 10 % de los ítems se repite más adelante con otro nombre (fiabilidad del propio oyente).
* El oyente escribe lo que entiende y puntúa la naturalidad de 1 a 5. Sin datos personales.
* La CLAVE (motor, palabras clave) va en ``clave.csv``, FUERA del zip que se entrega.

Uso: uv run python -m eval.listening.inteligibilidad_mos.build [--n 24] [--fake] [--out DIR]
Salida (carpeta ``out/``): audio/*.wav, hoja_escucha.html, hoja_escucha.csv, clave.csv,
kit_escucha.zip (para entregar) y diseno.json.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import random
import shutil
import zipfile
from pathlib import Path

import numpy as np

from eval.listening.inteligibilidad_mos import diseno as dz

HERE = Path(__file__).parent
OUT = HERE / "out"
SEMILLA = 20261012
N_ORACIONES = 24
RMS_OBJETIVO = 0.08
PICO_MAX = 0.95
MOTORES_REALES = {"mms_vits": "mms_vits", "espeak_ng": "espeak_ng"}
MOTORES_FAKE = {"mms_vits": "fake", "espeak_ng": "fake"}


def normalizar_rms(
    wav: np.ndarray, objetivo: float = RMS_OBJETIVO, pico: float = PICO_MAX
) -> np.ndarray:
    """Lleva el audio al mismo RMS sin recortar (si el pico pasa de ``pico`` baja la ganancia)."""
    x = np.asarray(wav, dtype=np.float32)
    rms = float(np.sqrt(np.mean(x**2))) if x.size else 0.0
    if rms == 0.0:
        return x
    y = x * (objetivo / rms)
    p = float(np.max(np.abs(y)))
    return y * (pico / p) if p > pico else y


def candidatas_del_split_test() -> list[dict]:
    """Oraciones de TEST listas para el TTS (texto canónico y texto del motor MMS dentro del vocabulario)."""
    from app.corpus.loader import load_split
    from app.pipeline.normalize.engine import DocumentState, Normalizer
    from app.pipeline.tts.adapters.mms_cni import MmsCniAdapter

    normalizer, adapter = Normalizer.from_files(), MmsCniAdapter.from_files()
    out = []
    for p in load_split("test"):
        canon = normalizer.normalize(p.cni, DocumentState()).text_canonical
        tts = adapter.adapt(canon).text_tts
        if tts and not adapter.oov_after(canon):
            out.append({"ref": p.ref, "canonical": canon, "text_tts": tts})
    return out


def sintetizar(
    oraciones: list[dict], motores: dict[str, str], audio_dir: Path, semilla: int
) -> dict:
    """Sintetiza cada oración con cada motor. Devuelve {(ref, etiqueta): (archivo, segundos)}."""
    import soundfile as sf
    from app.pipeline.tts.base import derive_seed
    from app.pipeline.tts.registry import create_engine

    audio_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(semilla)
    resultado: dict = {}
    for etiqueta, nombre in motores.items():
        eng = create_engine(nombre)
        eng.warmup()
        info = eng.info()
        for o in oraciones:
            texto = o["text_tts"] if info.input_kind == "text_tts" else o["canonical"]
            res = eng.synthesize(texto, derive_seed(texto, etiqueta, info.revision, "escucha"))
            archivo = f"s{rng.randrange(10**6):06d}.wav"
            while (audio_dir / archivo).exists():
                archivo = f"s{rng.randrange(10**6):06d}.wav"
            wav = normalizar_rms(res.wav)
            sf.write(audio_dir / archivo, wav, res.sample_rate)
            resultado[(o["ref"], etiqueta)] = (archivo, len(wav) / res.sample_rate)
    return resultado


def plan_items(oraciones: list[dict], audios: dict, semilla: int) -> list[dict]:
    """Ítems en el orden de presentación, con los repetidos ya insertados y numerados."""
    base = []
    for o in oraciones:
        for etiqueta in dz.MOTORES:
            archivo, seg = audios[(o["ref"], etiqueta)]
            base.append(
                {
                    "id": f"{o['ref']}|{etiqueta}",
                    "oracion": o["ref"],
                    "motor": etiqueta,
                    "audio": archivo,
                    "segundos": round(seg, 2),
                    "canonico": o["canonical"],
                    "claves": dz.palabras_clave(o["canonical"]),
                    "repite_de": "",
                }
            )
    orden = dz.ordenar_items(base, semilla)
    repetidos = dz.elegir_repetidos(orden, semilla)
    for r in repetidos:
        r["copia"] = {**r, "id": r["id"] + "|rep", "repite_de": r["id"], "audio": ""}
    final = dz.insertar_repetidos(orden, repetidos, semilla)
    for i, it in enumerate(final, 1):
        it["item"] = f"i{i:03d}"
    por_id = {it["id"].removesuffix("|rep"): it["item"] for it in final if not it["repite_de"]}
    for it in final:
        if it["repite_de"]:
            it["repite_de"] = por_id[it["repite_de"]]
    return final


PLANTILLA_HTML = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hoja de escucha</title>
<style>
body{font-family:system-ui,sans-serif;max-width:46rem;margin:1rem auto;padding:0 1rem;line-height:1.4}
fieldset{border:1px solid #888;margin:1rem 0;padding:.75rem}legend{font-weight:600}
textarea{width:100%;font:inherit}label.r{margin-right:.9rem;white-space:nowrap}
button{font:inherit;padding:.6rem 1.2rem}.aviso{background:#fff4d6;color:#4d3500;padding:.6rem;border-radius:4px}
</style></head><body>
<h1>Hoja de escucha</h1>
<p class="aviso">Va a escuchar voces <strong>sintéticas</strong> (generadas por computadora). No hay respuestas
correctas ni incorrectas. No escriba su nombre ni ningún dato personal.</p>
<p><label>Identificador que le dieron: <input id="oyente" maxlength="40" autocomplete="off"></label></p>
<p><label>Variante que habla:
<select id="variante">__VARIANTES__</select></label></p>
__FILAS__
<p><button id="bajar">Descargar respuestas</button></p>
<p id="msg" role="status"></p>
<script>
const filas = __IDS__;
const esc = (s) => '"' + String(s).replace(/"/g, '""') + '"';
document.getElementById('bajar').onclick = () => {
  const oyente = document.getElementById('oyente').value.trim();
  if (!/^[A-Za-z0-9_-]{1,40}$/.test(oyente)) { msg('Escriba el identificador que le dieron (letras y números).'); return; }
  const variante = document.getElementById('variante').value;
  const lineas = ['oyente,variante,item,transcripcion,mos,comentario'];
  let sinMos = 0;
  for (const id of filas) {
    const t = document.getElementById('t-' + id).value.replace(/\\s+/g, ' ').trim();
    const m = document.querySelector('input[name="m-' + id + '"]:checked');
    const c = document.getElementById('c-' + id).value.replace(/\\s+/g, ' ').trim();
    if (!m) sinMos++;
    lineas.push([esc(oyente), esc(variante), esc(id), esc(t), m ? m.value : '', esc(c)].join(','));
  }
  if (sinMos > 0 && !confirm('Faltan ' + sinMos + ' puntuaciones de naturalidad. ¿Descargar de todos modos?')) return;
  const blob = new Blob(['\\ufeff' + lineas.join('\\n') + '\\n'], {type: 'text/csv;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'respuestas_' + oyente + '.csv'; a.click();
  msg('Listo: envíe el archivo respuestas_' + oyente + '.csv.');
};
function msg(t) { document.getElementById('msg').textContent = t; }
</script></body></html>
"""


def hoja_html(items: list[dict]) -> str:
    filas = []
    for it in items:
        mos = "".join(
            f'<label class="r"><input type="radio" name="m-{it["item"]}" value="{v}"> {v}</label>'
            for v in range(dz.MOS_MIN, dz.MOS_MAX + 1)
        )
        filas.append(
            f"<fieldset><legend>Audio {it['item'][1:]}</legend>"
            f'<audio controls preload="none" src="audio/{html.escape(it["audio"])}"></audio>'
            f'<p><label>Escriba lo que entiende:<br><textarea id="t-{it["item"]}" rows="2"></textarea></label></p>'
            f"<p>Naturalidad de la voz (1 = muy artificial, 5 = muy natural):<br>{mos}</p>"
            f'<p><label>Comentario (opcional): <input id="c-{it["item"]}" maxlength="200"></label></p>'
            "</fieldset>"
        )
    variantes = "".join(f'<option value="{v}">{v.replace("_", " ")}</option>' for v in dz.VARIANTES)
    return (
        PLANTILLA_HTML.replace("__VARIANTES__", variantes)
        .replace("__FILAS__", "\n".join(filas))
        .replace("__IDS__", json.dumps([it["item"] for it in items]))
    )


def construir(
    oraciones: list[dict],
    salida: Path,
    motores: dict[str, str] | None = None,
    semilla: int = SEMILLA,
    sin_audio: bool = False,
) -> dict:
    """Escribe el kit completo en ``salida`` y devuelve un resumen."""
    motores = motores or MOTORES_REALES
    if salida.exists():
        shutil.rmtree(salida)
    audio_dir = salida / "audio"
    audio_dir.mkdir(parents=True)
    if sin_audio:  # solo el diseño: sin audio no hay nada que escuchar (pruebas)
        audios = {
            (o["ref"], e): (f"vacio_{i}_{e}.wav", 3.0)
            for i, o in enumerate(oraciones)
            for e in dz.MOTORES
        }
    else:
        audios = sintetizar(oraciones, motores, audio_dir, semilla)
    items = plan_items(oraciones, audios, semilla)
    # los repetidos reutilizan el audio del original con otro nombre
    for it in items:
        if it["repite_de"]:
            orig = next(x for x in items if x["item"] == it["repite_de"])
            nombre = "r" + orig["audio"][1:]
            it["audio"] = nombre
            if not sin_audio:
                shutil.copyfile(audio_dir / orig["audio"], audio_dir / nombre)

    (salida / "hoja_escucha.html").write_text(hoja_html(items), encoding="utf-8")
    with (salida / "hoja_escucha.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item", "audio", "transcripcion", "mos", "comentario"])
        for it in items:
            w.writerow([it["item"], f"audio/{it['audio']}", "", "", ""])
    with (salida / "clave.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["item", "audio", "oracion", "motor", "claves", "repite_de", "canonico", "segundos"]
        )
        for it in items:
            w.writerow(
                [
                    it["item"],
                    it["audio"],
                    it["oracion"],
                    it["motor"],
                    "|".join(it["claves"]),
                    it["repite_de"],
                    it["canonico"],
                    it["segundos"],
                ]
            )
    instrucciones = HERE / "INSTRUCCIONES.md"
    zip_path = salida / "kit_escucha.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(salida / "hoja_escucha.html", "hoja_escucha.html")
        z.write(salida / "hoja_escucha.csv", "hoja_escucha.csv")
        if instrucciones.exists():
            z.write(instrucciones, "INSTRUCCIONES.md")
        for it in items:
            if (audio_dir / it["audio"]).exists():
                z.write(audio_dir / it["audio"], f"audio/{it['audio']}")
        nombres = z.namelist()
    assert not any("clave" in n.lower() for n in nombres), "la clave no puede ir en el kit"
    resumen = {
        "semilla": semilla,
        "oraciones": len(oraciones),
        "items": len(items),
        "repetidos": sum(1 for it in items if it["repite_de"]),
        "motores": list(dz.MOTORES),
        "regla_clave": f"{dz.N_CLAVE} primeras palabras de {dz.LARGO_MIN} o más letras",
        "rms_objetivo": RMS_OBJETIVO,
        "zip": str(zip_path),
        "archivos_en_zip": len(nombres),
    }
    (salida / "diseno.json").write_text(
        json.dumps(resumen, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    return resumen


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--n", type=int, default=N_ORACIONES)
    ap.add_argument("--fake", action="store_true", help="motor de prueba para ambos (sin modelos)")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    cand = candidatas_del_split_test()
    oraciones = dz.elegir_oraciones(cand, a.n, SEMILLA)
    if len(oraciones) < a.n:
        print(f"[escucha] solo hay {len(oraciones)} oraciones elegibles de {a.n} pedidas")
    r = construir(oraciones, a.out, MOTORES_FAKE if a.fake else MOTORES_REALES)
    print(json.dumps(r, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
