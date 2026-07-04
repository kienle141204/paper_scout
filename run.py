#!/usr/bin/env python3
"""One-command launcher for PaperScout — local personal research assistant.

Usage:
    python run.py

Does first-run setup (copy backend/.env from the example, `npm install`,
`pip install -e .` if needed), then starts the FastAPI backend (uvicorn on
:8000, --reload) and the Vite dev server (:5173) side by side, streaming both
logs. Ctrl+C stops both. Cross-platform (Windows / macOS / Linux); only the
Python standard library is used here so it runs before any deps are installed.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
BACKEND_ENV = ROOT / "backend" / ".env"
BACKEND_ENV_EXAMPLE = ROOT / "backend" / ".env.example"
LOG_DIR = ROOT / "logs"
RUN_LOG = LOG_DIR / "run.log"
BACKEND_LOG = LOG_DIR / "backend.log"
FRONTEND_LOG = LOG_DIR / "frontend.log"

BACKEND_PORT = 8000
FRONTEND_PORT = 5173


def _which(name: str) -> str | None:
    # On Windows npm is npm.cmd; shutil.which resolves the right one.
    return shutil.which(name) or shutil.which(f"{name}.cmd")


def _ensure_env() -> None:
    if not BACKEND_ENV.exists():
        if BACKEND_ENV_EXAMPLE.exists():
            shutil.copyfile(BACKEND_ENV_EXAMPLE, BACKEND_ENV)
            print(f"[setup] Created {BACKEND_ENV.relative_to(ROOT)} from the example.")
        else:
            BACKEND_ENV.write_text("OPENAI_API_KEY=\n", encoding="utf-8")
            print(f"[setup] Created empty {BACKEND_ENV.relative_to(ROOT)}.")
        print("[setup] >>> Add your OPENAI_API_KEY (or GEMINI_API_KEY) to "
              f"{BACKEND_ENV.relative_to(ROOT)} then re-run. <<<")

    # Warn (don't block) if no LLM key looks set.
    text = BACKEND_ENV.read_text(encoding="utf-8") if BACKEND_ENV.exists() else ""
    has_key = any(
        line.strip().startswith((f"{k}=",)) and line.split("=", 1)[1].strip()
        for line in text.splitlines()
        for k in ("OPENAI_API_KEY", "GEMINI_API_KEY")
        if line.strip().startswith(k)
    )
    if not has_key:
        print("[setup] WARNING: no OPENAI_API_KEY / GEMINI_API_KEY set in "
              f"{BACKEND_ENV.relative_to(ROOT)} — LLM features won't work until you add one.")


def _ensure_python_deps() -> None:
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
    except ImportError:
        print("[setup] Installing Python dependencies (pip install -e .) ...")
        print("[setup] NOTE: MinerU (mineru[core]) pulls torch + OCR/layout models — the first")
        print("[setup]       install is large and can take several minutes. Run")
        print("[setup]       'python scripts/download_mineru_models.py' once to pre-fetch models.")
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], cwd=ROOT, check=True)


def _ensure_node_deps(npm: str) -> None:
    if not (FRONTEND / "node_modules").exists():
        print("[setup] Installing frontend dependencies (npm install) ...")
        subprocess.run([npm, "install"], cwd=FRONTEND, check=True)


def _ensure_logs() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    for path in (RUN_LOG, BACKEND_LOG, FRONTEND_LOG):
        path.write_text("", encoding="utf-8")


def _log_run(message: str) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(message.rstrip() + "\n")


def _stream(proc: subprocess.Popen, prefix: str, log_path: Path) -> None:
    assert proc.stdout is not None
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{prefix} log started\n")
        log_file.flush()
        _log_run(f"{prefix} writing to {log_path.relative_to(ROOT)}")
    for line in proc.stdout:
        text = f"{prefix} {line}"
        sys.stdout.write(text)
        sys.stdout.flush()
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(text)


def main() -> int:
    npm = _which("npm")
    if not npm:
        print("[error] npm not found on PATH. Install Node.js (https://nodejs.org) first.")
        return 1

    _ensure_env()
    _ensure_python_deps()
    _ensure_node_deps(npm)
    _ensure_logs()

    env = os.environ.copy()
    # Backend must run from repo root so `import agent` / `import backend` resolve.
    backend_cmd = [
        sys.executable, "-m", "uvicorn", "backend.api:app",
        "--host", "127.0.0.1", "--port", str(BACKEND_PORT), "--reload",
    ]
    frontend_cmd = [npm, "run", "dev", "--", "--port", str(FRONTEND_PORT), "--strictPort"]

    print(f"\n[run] Backend  → http://127.0.0.1:{BACKEND_PORT}")
    print(f"[run] Frontend → http://localhost:{FRONTEND_PORT}  (open this in your browser)")
    print(f"[run] Logs     → {LOG_DIR.relative_to(ROOT)}\\backend.log and {LOG_DIR.relative_to(ROOT)}\\frontend.log")
    print("[run] Press Ctrl+C to stop both.\n")
    _log_run(f"Backend  -> http://127.0.0.1:{BACKEND_PORT}")
    _log_run(f"Frontend -> http://localhost:{FRONTEND_PORT}")
    _log_run(f"Logs     -> {LOG_DIR}")

    popen_kw = dict(
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, env=env,
    )
    backend = subprocess.Popen(backend_cmd, cwd=ROOT, **popen_kw)
    frontend = subprocess.Popen(frontend_cmd, cwd=FRONTEND, **popen_kw)
    procs = [backend, frontend]

    threads = [
        threading.Thread(target=_stream, args=(backend, "[backend]", BACKEND_LOG), daemon=True),
        threading.Thread(target=_stream, args=(frontend, "[frontend]", FRONTEND_LOG), daemon=True),
    ]
    for th in threads:
        th.start()

    def _shutdown(*_a) -> None:
        for p in procs:
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    try:
        # Exit as soon as either process dies (so a crash doesn't leave a half-up stack).
        while True:
            for p in procs:
                if p.poll() is not None:
                    print(f"\n[run] A process exited (code {p.returncode}); shutting down the other.")
                    _log_run(f"A process exited (code {p.returncode}); shutting down the other.")
                    _shutdown()
                    for other in procs:
                        try:
                            other.wait(timeout=10)
                        except Exception:
                            pass
                    return p.returncode or 0
            for p in procs:
                try:
                    p.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    pass
    except KeyboardInterrupt:
        _shutdown()
        for p in procs:
            try:
                p.wait(timeout=10)
            except Exception:
                pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
