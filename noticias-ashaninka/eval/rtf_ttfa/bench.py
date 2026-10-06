"""Tarea 2.8 — Banco de pruebas de rendimiento (definiciones en docs/metrics.md).

Subcomandos (todos escriben en eval/rtf_ttfa/out/ y en eval/results/fase_2_rendimiento.json):
  prepare   pseudo-noticias de 300-500 caracteres con oraciones de dev listas para el TTS
  rtf       RTF en caliente por motor (>= 100 segmentos) y carga en frío
  sweep     barrido hilos de torch x trabajadores (>= 30 síntesis por combinación)
  http      TTFA servidor/cliente (bajo demanda, caché fría) y por lotes (caché caliente) con
            uvicorn real y 1, 4 y 8 clientes; rendimiento y pico de memoria
  figures   gráficos PNG en docs/figures/
  all       todo lo anterior en orden

Uso: uv run python -m eval.rtf_ttfa.bench all
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import shutil
import statistics
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "out"
BENCH_DB = OUT / "bench.db"
# La base del banco es propia: se fija ANTES de importar la app
os.environ["NA_DATABASE_URL"] = f"sqlite:///{BENCH_DB.as_posix()}"

from app.config import (  # noqa: E402
    MMS_TTS_REVISION,
    RESULTS_DIR,
    ROOT,
    get_settings,
)
from app.metrics.timing import percentile  # noqa: E402

SEED = 20261006
RESULT_FILE = RESULTS_DIR / "fase_2_rendimiento.json"
CONCURRENCY = [1, 4, 8]
THREADS = [1, 4, 8, 16]
WORKERS = [1, 2, 4]


# ------------------------------------------------------------------ utilidades
def stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "media": round(statistics.fmean(values), 4),
        "de": round(statistics.stdev(values), 4) if len(values) > 1 else 0.0,
        "p50": round(percentile(values, 50), 4),
        "p95": round(percentile(values, 95), 4),
        "p99": round(percentile(values, 99), 4),
    }


def load_results() -> dict:
    return json.loads(RESULT_FILE.read_text(encoding="utf-8")) if RESULT_FILE.exists() else {}


def save_results(update: dict) -> None:
    data = load_results()
    data.update(update)
    data["commit"] = git_commit()
    data["hardware"] = hardware()
    data["versiones_fijadas"] = {"mms-tts-cni": MMS_TTS_REVISION}
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # pragma: no cover
        return "sin-commit"


def hardware() -> dict:
    import psutil

    return {
        "cpu": platform.processor() or platform.machine(),
        "nucleos": os.cpu_count(),
        "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
        "os": platform.platform(),
        "python": platform.python_version(),
    }


# ------------------------------------------------------------------ prepare
def prepare(n_news: int = 110) -> dict:
    """Pseudo-noticias de 300-500 caracteres; se importan en la base propia del banco."""
    from app.corpus.loader import load_split
    from app.db.session import get_engine, init_db
    from app.pipeline.normalize.engine import DocumentState, Normalizer
    from app.pipeline.tts.adapters.mms_cni import MmsCniAdapter
    from app.schemas import NewsIn
    from app.services import import_payloads, process_all

    OUT.mkdir(parents=True, exist_ok=True)
    BENCH_DB.unlink(missing_ok=True)
    get_engine.cache_clear()
    init_db()
    norm, ad = Normalizer.from_files(), MmsCniAdapter.from_files()
    ready = []
    for p in load_split("dev"):
        text = p.cni.strip()
        canon = norm.normalize(text, DocumentState()).text_canonical
        if 15 <= len(text) <= 200 and not ad.oov_after(canon) and text[-1] in ".!?":
            ready.append(text)
    rng = random.Random(SEED)
    news, used = [], 0
    while len(news) < n_news:
        rng.shuffle(ready)
        body = ""
        for s in ready:
            if len(body) + len(s) + 1 > 500:
                continue
            body = f"{body} {s}".strip()
            if len(body) >= 300:
                break
        if 300 <= len(body) <= 500 and body not in news:
            news.append(body)
        used += 1
        if used > 5000:
            break
    payloads = [
        NewsIn(
            titulo_cni=f"bench-{i:03d}",
            cuerpo_cni=b,
            fuente_original="pseudo-noticia dev",
            procedencia={"tipo": "traduccion_automatica", "sistema": "corpus-dev"},
        )
        for i, b in enumerate(news)
    ]
    import_payloads(payloads)
    stats_proc = process_all()
    lengths = [len(b) for b in news]
    info = {
        "noticias": len(news),
        "oraciones_listas_dev": len(ready),
        "caracteres": stats(lengths),
        "segmentos": stats_proc["segmentos"],
        "semilla": SEED,
    }
    save_results({"pseudo_noticias": info})
    print(f"[2.8] pseudo-noticias: {json.dumps(info, ensure_ascii=False)}")
    return info


def segment_texts(engine_name: str) -> list[str]:
    from app.db.models import Segment
    from app.db.session import get_engine
    from sqlmodel import Session, select

    with Session(get_engine()) as s:
        segs = s.exec(select(Segment).where(Segment.tts_ready == True)).all()  # noqa: E712
        return [seg.text_tts if engine_name != "espeak_ng" else seg.text_canonical for seg in segs]


# ------------------------------------------------------------------ rtf
def rtf(min_n: int = 100) -> dict:
    from app.pipeline.tts.base import derive_seed
    from app.pipeline.tts.espeak import find_espeak
    from app.pipeline.tts.registry import create_engine

    out = {"carga_en_frio_ms": {}, "rtf": {}}
    engines = ["mms_vits"] + (["espeak_ng"] if find_espeak(get_settings().espeak_path) else [])
    for name in engines:
        eng = create_engine(name)
        out["carga_en_frio_ms"][name] = round(eng.warmup(), 1)
        texts = segment_texts(name)[: max(min_n, 100)]
        eng.synthesize(texts[0], 1)  # calentamiento del primer forward
        values, durations = [], []
        for t in texts:
            r = eng.synthesize(t, derive_seed(t, name, "bench", "rtf"))
            values.append(r.rtf)
            durations.append(r.duration_s)
        out["rtf"][name] = {
            **stats(values),
            "duracion_audio_s": stats(durations),
            "torch_threads": get_settings().torch_threads or "defecto",
        }
        print(f"[2.8] RTF {name}: {out['rtf'][name]}")
    if "espeak_ng" not in out["rtf"]:
        out["rtf"]["espeak_ng"] = "no_medido (eSpeak-NG no instalado)"
    save_results(out)
    return out


# ------------------------------------------------------------------ sweep
SWEEP_CHILD = r"""
import json, os, sys, time, threading
from concurrent.futures import ThreadPoolExecutor
os.environ["NA_TORCH_THREADS"] = sys.argv[1]
workers = int(sys.argv[2]); texts = json.loads(sys.stdin.read())
from app.pipeline.tts.registry import EnginePool
pool = EnginePool("mms_vits", workers); pool.warmup()
with pool.acquire() as e: e.synthesize(texts[0], 1)
lat, audio = [], []
def job(i_t):
    i, t = i_t
    with pool.acquire() as e:
        r = e.synthesize(t, i)
    lat.append(r.synth_ms / 1000); audio.append(r.duration_s)
    return r.rtf
t0 = time.perf_counter()
with ThreadPoolExecutor(workers) as ex:
    rtfs = list(ex.map(job, enumerate(texts)))
wall = time.perf_counter() - t0
print(json.dumps({"rtf": rtfs, "wall_s": wall, "audio_s": sum(audio)}))
"""


def sweep(n: int = 30) -> dict:
    texts = segment_texts("mms_vits")[:n]
    combos = {}
    for th in THREADS:
        for w in WORKERS:
            proc = subprocess.run(
                [sys.executable, "-c", SWEEP_CHILD, str(th), str(w)],
                input=json.dumps(texts),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=ROOT,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            if proc.returncode != 0:
                combos[f"t{th}_w{w}"] = {"error": proc.stderr[-500:]}
                continue
            r = json.loads(proc.stdout.strip().splitlines()[-1])
            combos[f"t{th}_w{w}"] = {
                "torch_threads": th,
                "workers": w,
                "rtf": stats(r["rtf"]),
                "rendimiento_audio_s_por_s": round(r["audio_s"] / r["wall_s"], 3),
            }
            print(
                f"[2.8] sweep t{th} w{w}: {combos[f't{th}_w{w}']['rendimiento_audio_s_por_s']} "
                f"s/s, RTF p95 {combos[f't{th}_w{w}']['rtf']['p95']}"
            )
    valid = [c for c in combos.values() if "error" not in c and c["rtf"]["p95"] < 1]
    best = max(valid, key=lambda c: c["rendimiento_audio_s_por_s"]) if valid else None
    out = {
        "barrido": combos,
        "configuracion_por_defecto": (
            {
                "torch_threads": best["torch_threads"],
                "tts_workers": best["workers"],
                "criterio": "mayor rendimiento con RTF p95 < 1",
            }
            if best
            else None
        ),
    }
    save_results(out)
    return out


# ------------------------------------------------------------------ http
class Server:
    def __init__(
        self,
        static_dir: Path,
        threads: int,
        workers: int,
        port: int = 8777,
        engine: str = "mms_vits",
    ):
        self.port, self.static_dir = port, static_dir
        env = {
            **os.environ,
            "NA_STATIC_DIR": str(static_dir),
            "NA_TTS_ENGINE": engine,
            "NA_TORCH_THREADS": str(threads),
            "NA_TTS_WORKERS": str(workers),
            "NA_MAX_CONCURRENT_SYNTH": "64",
            "NA_TTS_PRELOAD": "true",
            "PYTHONIOENCODING": "utf-8",
        }
        self.proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--port",
                str(port),
                "--host",
                "127.0.0.1",
                "--log-level",
                "warning",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self.peak_rss = 0
        self._stop = threading.Event()

    def wait_ready(self, timeout: float = 180) -> None:
        import httpx

        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if (
                    httpx.get(f"http://127.0.0.1:{self.port}/api/health", timeout=2).status_code
                    == 200
                ):
                    threading.Thread(target=self._monitor, daemon=True).start()
                    return
            except Exception:
                time.sleep(0.5)
        raise RuntimeError(
            "el servidor no arrancó: " + (self.proc.stderr.read() or b"").decode()[-800:]
        )

    def _monitor(self) -> None:
        import psutil

        p = psutil.Process(self.proc.pid)
        while not self._stop.is_set():
            try:
                rss = p.memory_info().rss + sum(c.memory_info().rss for c in p.children(True))
                self.peak_rss = max(self.peak_rss, rss)
            except Exception:
                pass
            time.sleep(0.2)

    def stop(self) -> None:
        self._stop.set()
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            self.proc.kill()


def on_demand_request(base: str, news_id: int) -> dict:
    """Como un cliente real: al recibir el primer evento ``segment`` descarga de inmediato los
    primeros bytes de ese audio (empezaría a reproducir) y luego sigue leyendo el stream."""
    import httpx

    t0 = time.perf_counter()
    server_ttfa = client_ttfa = None
    total_audio = 0.0
    with httpx.Client(timeout=120) as c, c.stream("GET", f"{base}/api/synthesize/{news_id}") as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            ev = json.loads(line)
            if ev["event"] != "segment":
                continue
            total_audio += ev["duration_s"] or 0
            if client_ttfa is None:
                server_ttfa = ev["t_ms"]
                with (
                    httpx.Client(timeout=60) as c2,
                    c2.stream("GET", base + ev["audio"]["opus"]) as ra,
                ):
                    next(ra.iter_bytes(1024))
                client_ttfa = (time.perf_counter() - t0) * 1000
    return {
        "server_ttfa_ms": server_ttfa,
        "client_ttfa_ms": client_ttfa,
        "total_s": time.perf_counter() - t0,
        "audio_s": total_audio,
    }


def batch_request(base: str, news_id: int) -> float:
    import httpx

    t0 = time.perf_counter()
    with httpx.Client(timeout=60) as c:
        m = c.get(f"{base}/static/news/{news_id}/manifest.json").json()
        url = next(s["audio"]["opus"] for s in m["segments"] if s["audio"])
        with c.stream("GET", base + url) as ra:
            next(ra.iter_bytes(1024))
    return (time.perf_counter() - t0) * 1000


def http(n_requests: int = 100) -> dict:
    from app.db.models import News
    from app.db.session import get_engine
    from sqlmodel import Session, select

    res = load_results()
    cfg = res.get("configuracion_por_defecto") or {"torch_threads": 0, "tts_workers": 1}
    th, w = cfg["torch_threads"], cfg["tts_workers"]
    with Session(get_engine()) as s:
        ids = [n.id for n in s.exec(select(News)).all()]
    ids = ids[:n_requests]
    if len(ids) < n_requests:
        print(f"[2.8] aviso: solo hay {len(ids)} noticias distintas")
    out = {
        "ttfa_ms": {"bajo_demanda_servidor": {}, "bajo_demanda_cliente": {}, "por_lotes": {}},
        "rendimiento_audio_s_por_s": {},
        "memoria_pico_mb": {},
        "http_config": cfg,
    }
    for conc in CONCURRENCY:
        static = OUT / f"static_c{conc}"
        shutil.rmtree(static, ignore_errors=True)
        srv = Server(static, th, w)
        try:
            srv.wait_ready()
            base = f"http://127.0.0.1:{srv.port}"
            t0 = time.perf_counter()
            with ThreadPoolExecutor(conc) as ex:
                rows = list(ex.map(on_demand_request, [base] * len(ids), ids))
            wall = time.perf_counter() - t0
            with ThreadPoolExecutor(conc) as ex:  # caché ya caliente
                batch = list(ex.map(batch_request, [base] * len(ids), ids))
        finally:
            srv.stop()
        key = f"c{conc}"
        out["ttfa_ms"]["bajo_demanda_servidor"][key] = stats(
            [r["server_ttfa_ms"] for r in rows if r["server_ttfa_ms"] is not None]
        )
        out["ttfa_ms"]["bajo_demanda_cliente"][key] = stats(
            [r["client_ttfa_ms"] for r in rows if r["client_ttfa_ms"] is not None]
        )
        out["ttfa_ms"]["por_lotes"][key] = stats(batch)
        out["rendimiento_audio_s_por_s"][key] = round(sum(r["audio_s"] for r in rows) / wall, 3)
        out["memoria_pico_mb"][key] = round(srv.peak_rss / 2**20, 1)
        print(
            f"[2.8] c{conc}: TTFA servidor p95 "
            f"{out['ttfa_ms']['bajo_demanda_servidor'][key].get('p95')} ms; "
            f"rendimiento {out['rendimiento_audio_s_por_s'][key]} s/s; "
            f"RSS {out['memoria_pico_mb'][key]} MB"
        )
    save_results(out)
    return out


# ------------------------------------------------------------------ figures
def figures() -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    res = load_results()
    fig_dir = ROOT / "docs" / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    made = []
    t = res.get("ttfa_ms", {})
    if t:
        fig, ax = plt.subplots(figsize=(6, 3.5))
        for label, key in [
            ("Servidor (bajo demanda)", "bajo_demanda_servidor"),
            ("Cliente (bajo demanda)", "bajo_demanda_cliente"),
            ("Por lotes", "por_lotes"),
        ]:
            xs = [int(k[1:]) for k in t[key]]
            ax.plot(xs, [t[key][k]["p95"] for k in t[key]], marker="o", label=label)
        ax.axhline(2000, color="grey", linestyle="--", linewidth=1, label="Meta p95 = 2 s")
        ax.set_xlabel("Clientes simultáneos")
        ax.set_ylabel("TTFA p95 (ms)")
        ax.set_xticks(CONCURRENCY)
        ax.legend(fontsize=8)
        ax.set_title("Tiempo hasta el primer audio (p95)")
        fig.tight_layout()
        path = fig_dir / "ttfa_p95.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        made.append(str(path))
    b = res.get("barrido", {})
    if b:
        fig, ax = plt.subplots(figsize=(6, 3.5))
        for w in WORKERS:
            pts = [
                (c["torch_threads"], c["rendimiento_audio_s_por_s"])
                for c in b.values()
                if "error" not in c and c["workers"] == w
            ]
            if pts:
                ax.plot(*zip(*sorted(pts), strict=True), marker="o", label=f"{w} trabajador(es)")
        ax.set_xlabel("Hilos de torch")
        ax.set_ylabel("Segundos de audio por segundo")
        ax.set_xticks(THREADS)
        ax.legend(fontsize=8)
        ax.set_title("Rendimiento de síntesis (mms_vits, CPU)")
        fig.tight_layout()
        path = fig_dir / "sweep_rendimiento.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        made.append(str(path))
    print(f"[2.8] figuras: {made}")
    return made


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prepare", "rtf", "sweep", "http", "figures", "all"])
    args = ap.parse_args(argv)
    steps = {"prepare": prepare, "rtf": rtf, "sweep": sweep, "http": http, "figures": figures}
    order = list(steps) if args.cmd == "all" else [args.cmd]
    for name in order:
        steps[name]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
