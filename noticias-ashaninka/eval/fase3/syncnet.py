"""LSE-D y LSE-C con SyncNet (tarea 3.8), calculados como en Wav2Lip.

El modelo y su código (MIT) son de Chung y Zisserman, https://github.com/joonson/syncnet_python,
confirmación ``907c0b5``. No se versionan en este repositorio: ``ensure_syncnet()`` los descarga
a ``models/syncnet/`` y verifica el hash de los pesos. Aquí solo se reproduce el preprocesado de
``SyncNetInstance.evaluate`` sin OpenCV ni detector de caras (la cámara del avatar es fija, el
rostro ocupa siempre el mismo recorte).
"""

from __future__ import annotations

import hashlib
import importlib.util
import math
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
from app.config import get_settings

COMMIT = "907c0b579c2e2d83f0eae1b2ac9e720cde4e5623"
MODEL_URL = "https://www.robots.ox.ac.uk/~vgg/software/lipsync/data/syncnet_v2.model"
CODE_URL = f"https://raw.githubusercontent.com/joonson/syncnet_python/{COMMIT}/SyncNetModel.py"
VSHIFT = 15  # igual que Wav2Lip
SIZE = 224


def syncnet_dir() -> Path:
    return get_settings().models_dir / "syncnet"


def ffmpeg_exe() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def ensure_syncnet() -> tuple[Path, str]:
    """Descarga código y pesos si faltan. Devuelve (carpeta, sha256 de los pesos)."""
    d = syncnet_dir()
    d.mkdir(parents=True, exist_ok=True)
    code, weights = d / "SyncNetModel.py", d / "syncnet_v2.model"
    if not code.exists():
        urllib.request.urlretrieve(CODE_URL, code)
    if not weights.exists():
        urllib.request.urlretrieve(MODEL_URL, weights)
    return d, hashlib.sha256(weights.read_bytes()).hexdigest()


def calc_pdist(feat1, feat2, vshift: int = VSHIFT):
    """Distancia por fotograma para cada desplazamiento (misma función que SyncNetInstance)."""
    import torch

    win = vshift * 2 + 1
    feat2p = torch.nn.functional.pad(feat2, (0, 0, vshift, vshift))
    return [
        torch.nn.functional.pairwise_distance(feat1[[i], :].repeat(win, 1), feat2p[i : i + win, :])
        for i in range(len(feat1))
    ]


def load_model(device: str = "cpu"):
    import torch

    d, _ = ensure_syncnet()
    spec = importlib.util.spec_from_file_location("SyncNetModel", d / "SyncNetModel.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    model = mod.S(num_layers_in_fc_layers=1024).to(device)
    state = torch.load(d / "syncnet_v2.model", map_location=device)
    model.load_state_dict({k: v for k, v in state.items()}, strict=True)
    return model.eval(), mod


def _frames(mp4: Path, tmp: Path) -> np.ndarray:
    """Fotogramas del clip como (T, 3, 224, 224) BGR en 0..255."""
    from PIL import Image

    subprocess.run(
        [ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(mp4), str(tmp / "%06d.png")],
        check=True,
    )
    out = []
    for p in sorted(tmp.glob("*.png")):
        im = Image.open(p).convert("RGB").resize((SIZE, SIZE), Image.Resampling.BILINEAR)
        out.append(np.asarray(im)[:, :, ::-1].transpose(2, 0, 1))  # RGB -> BGR
    return np.stack(out).astype(np.float32)


def _audio(wav: Path, tmp: Path) -> np.ndarray:
    from scipy.io import wavfile

    out = tmp / "a.wav"
    subprocess.run(
        [
            ffmpeg_exe(),
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(wav),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-acodec",
            "pcm_s16le",
            str(out),
        ],
        check=True,
    )
    sr, audio = wavfile.read(out)
    assert sr == 16000
    return audio


def evaluate(model, mod, mp4: Path, wav: Path, batch: int = 20) -> dict:
    """Desfase (fotogramas), LSE-D y LSE-C de un clip con el audio ``wav``."""
    import python_speech_features
    import torch

    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        (tmp / "f").mkdir()
        frames = _frames(mp4, tmp / "f")  # (T, 3, H, W)
        audio = _audio(wav, tmp)
    mfcc = np.stack(python_speech_features.mfcc(audio, 16000).T)  # (13, Tm)
    cct = torch.from_numpy(mfcc[None, None].astype(np.float32))
    imtv = torch.from_numpy(frames.transpose(1, 0, 2, 3)[None])  # (1, 3, T, H, W)
    min_len = min(frames.shape[0], math.floor(len(audio) / 640))
    last = min_len - 5
    if last <= VSHIFT:
        raise ValueError(f"clip demasiado corto para SyncNet ({min_len} fotogramas)")
    im_feat, cc_feat = [], []
    with torch.no_grad():
        for i in range(0, last, batch):
            idx = range(i, min(last, i + batch))
            im_feat.append(model.forward_lip(torch.cat([imtv[:, :, v : v + 5] for v in idx], 0)))
            cc_feat.append(
                model.forward_aud(torch.cat([cct[:, :, :, v * 4 : v * 4 + 20] for v in idx], 0))
            )
    dists = calc_pdist(torch.cat(im_feat), torch.cat(cc_feat), VSHIFT)
    mdist = torch.mean(torch.stack(dists, 1), 1)
    minval, minidx = torch.min(mdist, 0)
    return {
        "offset_fotogramas": int(VSHIFT - minidx.item()),
        "lse_d": float(minval.item()),
        "lse_c": float((torch.median(mdist) - minval).item()),
        "fotogramas": int(min_len),
    }
