"""Pre-fetch MinerU pipeline models once so the first RAG ingest isn't slowed by a
model download inside the request.

Run once after installing deps (via conda env ai20k):

    conda run -n ai20k python scripts/download_mineru_models.py

By default it pulls the `pipeline` backend models (CPU-friendly, what this app uses)
from Hugging Face. Override the source with MINERU_MODEL_SOURCE=modelscope if HF is
slow/blocked in your region. Models are cached and reused; re-running is a no-op.
"""
from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    source = os.environ.get("MINERU_MODEL_SOURCE", "huggingface")
    # Ensure downstream MinerU calls default to CPU on this machine.
    os.environ.setdefault("MINERU_DEVICE_MODE", "cpu")
    os.environ.setdefault("MINERU_MODEL_SOURCE", source)

    cmd = ["mineru-models-download", "-s", source, "-m", "pipeline"]
    print(f"[mineru] downloading pipeline models from {source} ...")
    print(f"[mineru] $ {' '.join(cmd)}")
    try:
        return subprocess.run(cmd, check=False).returncode
    except FileNotFoundError:
        print(
            "[mineru] 'mineru-models-download' not found. Install MinerU first:\n"
            "         conda run -n ai20k pip install -e .",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
