"""Descarga un modelo de Hugging Face en una revisión fijada (lo invoca init.sh).

Uso: python -m eval.fase1.download_models <repo> <revisión>
"""

from __future__ import annotations

import sys

from app.config import get_settings


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    repo, revision = argv
    from huggingface_hub import snapshot_download

    target = get_settings().models_dir / repo.replace("/", "__")
    path = snapshot_download(
        repo_id=repo,
        revision=revision,
        local_dir=target,
        # Solo el modelo base y el adaptador cni (mms-1b-all trae más de mil adaptadores)
        allow_patterns=[
            "config.json",
            "preprocessor_config.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.json",
            "model.safetensors",
            "adapter.cni.safetensors",
        ],
    )
    print(f"[modelos] {repo}@{revision[:7]} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
