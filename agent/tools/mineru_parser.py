"""Structure-aware PDF parsing via MinerU (https://github.com/opendatalab/mineru).

Replaces the old pypdf text dump. MinerU emits a ``content_list.json``: a flat list
of content blocks in reading order, each carrying its page index, heading level, and
type (text / title / table / equation / image). We normalize that into a list of
``Block`` objects that the structure-aware chunker consumes.

Why the CLI (subprocess) instead of the in-process ``do_parse`` API:
- The internal ``do_parse`` signature shifts between MinerU minor versions; the
  ``mineru`` CLI (``-p in -o out -b pipeline``) is the stable contract.
- Parsed output is cached in Supabase (see agent/tools/pdf_store.py), so each paper is
  parsed at most once ever — warm-model reuse across calls is not worth the fragility.

Heavy deps (torch + models) are only touched when the ``mineru`` binary runs, so
importing this module stays cheap and pytest never needs MinerU installed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Block:
    """One normalized content block from MinerU's content_list.json."""
    type: str                 # text | title | table | equation | image
    text: str = ""            # body text, equation LaTeX, or table caption+body as text
    text_level: int | None = None  # >=1 => heading level (title blocks); None => body
    page: int = 0             # 0-based page index
    table_html: str | None = None  # raw HTML table (for table blocks)
    caption: str | None = None     # table/image caption
    latex: str | None = None       # equation LaTeX source


class MineruError(RuntimeError):
    pass


def _mineru_cmd() -> list[str]:
    """Locate the mineru executable, preferring the one shipped in the running env.

    On Windows the console script lives in ``<env>\\Scripts\\mineru.exe`` (python.exe is
    in the env root), on POSIX in ``<env>/bin/mineru`` (next to python). We probe both
    so a non-activated conda env (PATH lacks Scripts/bin) still resolves it.
    """
    exe = shutil.which("mineru")
    if exe:
        return [exe]
    pyparent = Path(sys.executable).parent
    search_dirs = [pyparent, pyparent / "Scripts", pyparent / "bin", pyparent.parent / "Scripts"]
    for d in search_dirs:
        for name in ("mineru.exe", "mineru"):
            cand = d / name
            if cand.exists():
                return [str(cand)]
    # Last resort: run the CLI module through the current interpreter.
    return [sys.executable, "-m", "mineru.cli.client"]


def _find_content_list(out_dir: Path) -> Path | None:
    matches = sorted(out_dir.rglob("*content_list.json"))
    return matches[0] if matches else None


def run_mineru(
    path: Path,
    *,
    backend: str = "pipeline",
    device: str = "cpu",
    lang: str = "en",
    model_source: str | None = None,
    timeout: int = 900,
) -> list[Block]:
    """Parse *path* with MinerU and return normalized blocks in reading order.

    Raises MineruError if the binary is missing, fails, or produces no content_list.
    """
    raw = run_mineru_content_list(
        path, backend=backend, device=device, lang=lang,
        model_source=model_source, timeout=timeout,
    )
    return blocks_from_content_list(raw)


def run_mineru_content_list(
    path: Path,
    *,
    backend: str = "pipeline",
    device: str = "cpu",
    lang: str = "en",
    model_source: str | None = None,
    timeout: int = 900,
) -> list[dict]:
    """Parse *path* with MinerU and return the raw content_list.json (list of dicts).

    Callers can cache this cheaply and re-derive Blocks via ``blocks_from_content_list``
    without re-running MinerU. Raises MineruError on failure.
    """
    cmd = _mineru_cmd()
    env = dict(os.environ)
    env.setdefault("MINERU_DEVICE_MODE", device)
    if model_source:
        env.setdefault("MINERU_MODEL_SOURCE", model_source)

    with tempfile.TemporaryDirectory(prefix="mineru_") as tmp:
        out_dir = Path(tmp)
        full = cmd + ["-p", str(path), "-o", str(out_dir), "-b", backend, "-l", lang]
        try:
            proc = subprocess.run(
                full, env=env, timeout=timeout,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
        except FileNotFoundError as e:
            raise MineruError(f"MinerU không được cài (thiếu binary 'mineru'): {e}") from e
        except subprocess.TimeoutExpired as e:
            raise MineruError(f"MinerU quá thời gian ({timeout}s) khi parse PDF.") from e

        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()[-500:]
            raise MineruError(f"MinerU lỗi (exit {proc.returncode}): {tail}")

        cl_path = _find_content_list(out_dir)
        if not cl_path:
            raise MineruError("MinerU không sinh ra content_list.json.")
        try:
            raw = json.loads(cl_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise MineruError(f"Không đọc được content_list.json: {e}") from e

    return raw if isinstance(raw, list) else []


def blocks_from_content_list(raw: list[dict]) -> list[Block]:
    """Pure transform: MinerU content_list entries -> Block list. Unit-testable
    without MinerU installed."""
    blocks: list[Block] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        itype = item.get("type") or "text"
        page = int(item.get("page_idx") or 0)

        # Drop page furniture that pollutes the index.
        if itype in ("header", "footer", "page_number", "page_footnote", "discarded"):
            continue

        if itype == "table":
            caption = _join_list(item.get("table_caption"))
            footnote = _join_list(item.get("table_footnote"))
            text = "\n".join(t for t in (caption, footnote) if t)
            blocks.append(Block(
                type="table", text=text, page=page,
                table_html=item.get("table_body") or None,
                caption=caption or None,
            ))
        elif itype in ("equation", "interline_equation"):
            latex = item.get("text") or item.get("latex") or ""
            blocks.append(Block(type="equation", text=latex, page=page, latex=latex or None))
        elif itype in ("image", "chart"):
            caption = _join_list(item.get("image_caption") or item.get("chart_caption"))
            if caption:
                blocks.append(Block(type="image", text=caption, page=page, caption=caption))
        else:  # text / title / list / code / aside_text
            text = (item.get("text") or "").strip()
            if not text:
                continue
            level = item.get("text_level")
            level = int(level) if isinstance(level, int) or (isinstance(level, str) and level.isdigit()) else None
            btype = "title" if level and level >= 1 else "text"
            blocks.append(Block(type=btype, text=text, text_level=level, page=page))
    return blocks


def _join_list(v) -> str:
    if isinstance(v, list):
        return " ".join(str(x).strip() for x in v if str(x).strip())
    return str(v).strip() if v else ""


# Canonical section taxonomy — the single source of truth shared by the chunker
# (labeling) and the RAG skills (which request sections by name, see rag/skills.py).
# Keep these keys in sync with SKILL section requests.
_SECTION_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("abstract", ("abstract",)),
    ("introduction", ("introduction", "intro")),
    ("related_work", ("related work", "related", "background", "prior work")),
    ("method", ("method", "methodology", "approach", "model", "framework",
                "architecture", "proposed", "our ")),
    ("experiments", ("experiment", "experimental setup", "setup",
                     "implementation detail", "training detail", "datasets", "dataset")),
    ("results", ("result", "evaluation", "main result", "performance", "findings")),
    ("ablation", ("ablation",)),
    ("limitations", ("limitation", "failure", "threats to validity")),
    ("discussion", ("discussion", "analysis")),
    ("conclusion", ("conclusion", "concluding", "future work", "summary")),
    ("references", ("references", "bibliography")),
    ("appendix", ("appendix", "supplementary", "supplement")),
]


def canonical_section(heading: str | None) -> str | None:
    """Map a raw heading string to a canonical section key, or None if it doesn't
    look like a known section heading. Strips leading section numbers ("3.1 Method")."""
    if not heading:
        return None
    import re
    h = heading.strip().lower()
    h = re.sub(r"^[\divx]+[.)]*\s*", "", h)  # drop "3", "3.1", "IV." prefixes
    h = re.sub(r"^[.\d\s]+", "", h).strip()
    for key, needles in _SECTION_PATTERNS:
        for n in needles:
            if h.startswith(n) or (f" {n}" in f" {h}" and len(h) < 60):
                return key
    return None
