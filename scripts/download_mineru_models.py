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
import shutil
import subprocess
import sys
from pathlib import Path


def _download_cmd() -> str | None:
    """Locate mineru-models-download even when the env's Scripts/bin isn't on PATH."""
    exe = shutil.which("mineru-models-download")
    if exe:
        return exe
    pyparent = Path(sys.executable).parent
    for d in (pyparent, pyparent / "Scripts", pyparent / "bin"):
        for name in ("mineru-models-download.exe", "mineru-models-download"):
            cand = d / name
            if cand.exists():
                return str(cand)
    return None


def main() -> int:
    source = os.environ.get("MINERU_MODEL_SOURCE", "huggingface")
    # Ensure downstream MinerU calls default to CPU on this machine.
    os.environ.setdefault("MINERU_DEVICE_MODE", "cpu")
    os.environ.setdefault("MINERU_MODEL_SOURCE", source)

    exe = _download_cmd()
    if not exe:
        print(
            "[mineru] 'mineru-models-download' not found. Install MinerU first:\n"
            "         conda run -n ai20k pip install -e .",
            file=sys.stderr,
        )
        return 1

    cmd = [exe, "-s", source, "-m", "pipeline"]
    print(f"[mineru] downloading pipeline models from {source} ...")
    print(f"[mineru] $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
