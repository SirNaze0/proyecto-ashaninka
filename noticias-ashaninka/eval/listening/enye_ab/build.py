"""Escucha A/B dirigida a la ñ: compara las escrituras H1 (ñ->ny), H2 (ñ->y) y H3 (ñ->n).

Diseño (fijado antes de recoger respuestas):
* 20 palabras con ñ del corpus (train + dev), en su forma canónica: 10 con ñ inicial y 10 con ñ
  interna, las más frecuentes, de hasta 12 letras y sin repetir raíz (prefijo de 4 letras).
* Cada palabra se sintetiza con las tres escrituras, con la MISMA semilla, de modo que solo
  cambia la escritura de la ñ.
* Comparaciones por pares (A/B) a ciegas: H1–H2, H1–H3 y H2–H3 por palabra = 60 pares, más
  4 pares de control con el mismo audio en A y en B (respuesta esperada: "igual").
* Orden de los pares y lado (A/B) aleatorizados con semilla fija. La clave va en un archivo
  aparte que la persona oyente no debe abrir.

Pregunta para cada par: "¿Cuál suena más como lo diría un hablante de asháninka?" (A / B / igual).

Uso: uv run python -m eval.listening.enye_ab.build
Salida en eval/listening/enye_ab/out/: audio/*.wav, hoja_escucha.html, hoja_escucha.csv y clave.csv
"""

from __future__ import annotations

import csv
import html
import json
import random
from collections import Counter
from pathlib import Path

from app.config import get_settings
from app.corpus.loader import load_split
from app.pipeline.normalize.engine import DocumentState, Normalizer
from app.pipeline.tts.adapters.mms_cni import MmsCniAdapter

HERE = Path(__file__).parent
OUT = HERE / "out"
SEED = 20261006
HYPS = ["H1", "H2", "H3"]
PAIRS = [("H1", "H2"), ("H1", "H3"), ("H2", "H3")]
N_INITIAL, N_MEDIAL, MAX_LEN, N_CATCH = 10, 10, 12, 4


def select_words(normalizer: Normalizer, adapters: dict[str, MmsCniAdapter]) -> list[dict]:
    counts: Counter[str] = Counter()
    first_ref: dict[str, str] = {}
    for split in ("train", "dev"):
        for p in load_split(split):
            for s in normalizer.normalize(p.cni, DocumentState()).spans:
                if s.category == "cni" and "ñ" in s.norm_text:
                    counts[s.norm_text] += 1
                    first_ref.setdefault(s.norm_text, p.ref)
    ranked = sorted(counts, key=lambda w: (-counts[w], w))
    chosen: list[dict] = []
    prefixes: set[str] = set()
    for want_initial, quota in ((True, N_INITIAL), (False, N_MEDIAL)):
        taken = 0
        for w in ranked:
            if taken >= quota:
                break
            if w.startswith("ñ") != want_initial or len(w) > MAX_LEN or w[:4] in prefixes:
                continue
            if any(adapters[h].oov_after(w) for h in HYPS):
                continue
            prefixes.add(w[:4])
            chosen.append(
                {
                    "palabra": w,
                    "posicion": "inicial" if want_initial else "interna",
                    "frecuencia": counts[w],
                    "ref": first_ref[w],
                }
            )
            taken += 1
    return chosen


def main() -> int:
    normalizer = Normalizer.from_files()
    adapters = {h: MmsCniAdapter.from_files(h) for h in HYPS}
    words = select_words(normalizer, adapters)

    tts_dir = get_settings().models_dir / "facebook__mms-tts-cni"
    if not (tts_dir / "model.safetensors").exists():
        raise SystemExit("Falta mms-tts-cni: ejecuta ./init.sh --with-audio-eval")
    import soundfile as sf
    import torch
    from transformers import VitsModel, VitsTokenizer

    tok, model = VitsTokenizer.from_pretrained(tts_dir), VitsModel.from_pretrained(tts_dir).eval()
    sr = model.config.sampling_rate
    audio: dict[tuple[int, str], object] = {}
    for i, w in enumerate(words):
        w["texto_tts"] = {}
        for h in HYPS:
            text = adapters[h].adapt_validated(w["palabra"]).text_tts
            torch.manual_seed(SEED + i)  # misma semilla para las tres escrituras
            with torch.no_grad():
                audio[(i, h)] = model(**tok(text, return_tensors="pt")).waveform[0].numpy()
            w["texto_tts"][h] = text

    # A ciegas: cada lado de cada par recibe un archivo con código aleatorio (también los
    # controles, para que A y B no compartan nombre). La correspondencia solo está en la clave.
    audio_dir = OUT / "audio"
    if audio_dir.exists():
        for old in audio_dir.glob("*.wav"):
            old.unlink()
    audio_dir.mkdir(parents=True, exist_ok=True)
    codes = iter(random.Random(SEED + 7).sample(range(100000, 999999), 2 * len(words) * 4))

    def coded(i: int, h: str) -> str:
        name = f"audio/s{next(codes)}.wav"
        sf.write(OUT / name, audio[(i, h)], sr)
        return name

    rng = random.Random(SEED)
    trials = [(i, a, b) for i in range(len(words)) for a, b in PAIRS]
    catch_words = rng.sample(range(len(words)), N_CATCH)
    trials += [(i, "H1", "H1") for i in catch_words]
    rng.shuffle(trials)

    sheet, key = [], []
    for n, (i, h_a, h_b) in enumerate(trials, 1):
        if rng.random() < 0.5:
            h_a, h_b = h_b, h_a
        file_a, file_b = coded(i, h_a), coded(i, h_b)
        sheet.append(
            {
                "par": n,
                "audio_A": file_a,
                "audio_B": file_b,
                "respuesta(A/B/igual)": "",
                "comentario": "",
            }
        )
        key.append(
            {
                "par": n,
                "palabra": words[i]["palabra"],
                "posicion": words[i]["posicion"],
                "A": h_a,
                "B": h_b,
                "audio_A": file_a,
                "audio_B": file_b,
                "control": h_a == h_b,
            }
        )

    with open(OUT / "hoja_escucha.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(sheet[0]))
        wr.writeheader()
        wr.writerows(sheet)
    with open(OUT / "clave.csv", "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(key[0]))
        wr.writeheader()
        wr.writerows(key)
    (OUT / "palabras.json").write_text(
        json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "hoja_escucha.html").write_text(render_html(sheet), encoding="utf-8")
    kit = build_kit()
    print(f"[ñ A/B] {len(words)} palabras, {len(trials)} pares ({N_CATCH} de control) en {OUT}")
    print(f"[ñ A/B] kit para la persona oyente (sin la clave): {kit}")
    return 0


def build_kit() -> Path:
    """Zip para enviar a la persona oyente: HTML, CSV, audios e instrucciones. NUNCA la clave."""
    import zipfile

    kit = OUT / "kit_escucha_enye.zip"
    with zipfile.ZipFile(kit, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(HERE / "INSTRUCCIONES.md", "escucha_enye/INSTRUCCIONES.md")
        for name in ("hoja_escucha.html", "hoja_escucha.csv"):
            z.write(OUT / name, f"escucha_enye/{name}")
        for wav in sorted((OUT / "audio").glob("*.wav")):
            z.write(wav, f"escucha_enye/audio/{wav.name}")
    with zipfile.ZipFile(kit) as z:
        assert not any("clave" in n or "palabras" in n for n in z.namelist())
    return kit


def render_html(sheet: list[dict]) -> str:
    rows = []
    for t in sheet:
        n = t["par"]
        radios = "".join(
            f'<label><input type="radio" name="p{n}" value="{v}"> {lab}</label>'
            for v, lab in (("A", "A"), ("B", "B"), ("igual", "Igual"))
        )
        rows.append(
            f'<tr><td class="n">{n}</td>'
            f'<td><audio controls preload="none" src="{html.escape(t["audio_A"])}"></audio></td>'
            f'<td><audio controls preload="none" src="{html.escape(t["audio_B"])}"></audio></td>'
            f'<td class="r">{radios}</td>'
            f'<td><input type="text" name="c{n}" placeholder="opcional"></td></tr>'
        )
    total = len(sheet)
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Escucha de la ñ</title>
<style>
:root {{ --bg:#fafaf7; --fg:#1d1d1b; --muted:#6b6b66; --line:#deded8; --accent:#2f6f4f; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#161614; --fg:#ececea; --muted:#a3a39c; --line:#33332f; --accent:#7cc39b; }} }}
body {{ background:var(--bg); color:var(--fg); font:16px/1.5 system-ui, sans-serif; margin:0 auto; max-width:980px; padding:16px; }}
h1 {{ font-size:1.4rem; margin:.2rem 0; }} p {{ color:var(--muted); }}
table {{ border-collapse:collapse; width:100%; }} td {{ border-top:1px solid var(--line); padding:8px 6px; vertical-align:middle; }}
td.n {{ color:var(--muted); width:2.5rem; }} td.r label {{ margin-right:.8rem; white-space:nowrap; }}
audio {{ width:200px; max-width:100%; }} input[type=text] {{ width:100%; min-width:120px; background:transparent; color:var(--fg); border:1px solid var(--line); border-radius:6px; padding:4px; }}
button {{ background:var(--accent); color:var(--bg); border:0; border-radius:8px; padding:10px 16px; font-size:1rem; cursor:pointer; }}
.bar {{ position:sticky; bottom:0; background:var(--bg); padding:12px 0; display:flex; gap:12px; align-items:center; border-top:1px solid var(--line); }}
@media (max-width:640px) {{ td {{ display:block; border:0; padding:4px 0; }} tr {{ display:block; border-top:1px solid var(--line); padding:8px 0; }} }}
</style></head><body>
<h1>Escucha: ¿cuál suena como lo diría un hablante?</h1>
<p>Cada fila tiene dos audios (A y B) de la <b>misma palabra</b> en asháninka, dicha por una voz sintética.
Escucha los dos y marca cuál suena <b>más como lo diría un hablante</b>. Si no notas diferencia, marca <b>Igual</b>.
Puedes repetir los audios las veces que quieras. Usa audífonos si es posible.</p>
<form id="f"><table>{"".join(rows)}</table>
<div class="bar"><button type="button" onclick="descargar()">Descargar respuestas</button>
<span id="estado"></span></div></form>
<script>
const TOTAL = {total};
function descargar() {{
  const f = document.getElementById('f');
  let csv = 'par,respuesta,comentario\\n', faltan = 0;
  for (let n = 1; n <= TOTAL; n++) {{
    const r = f.querySelector('input[name="p' + n + '"]:checked');
    if (!r) faltan++;
    const c = (f.querySelector('input[name="c' + n + '"]').value || '').replace(/"/g, '""');
    csv += n + ',' + (r ? r.value : '') + ',"' + c + '"\\n';
  }}
  document.getElementById('estado').textContent = faltan ? ('Faltan ' + faltan + ' pares sin responder') : 'Completo';
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], {{type: 'text/csv'}}));
  a.download = 'respuestas_escucha_enye.csv';
  a.click();
}}
</script></body></html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
