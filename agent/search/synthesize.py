"""Grounded synthesis over Search Agent candidates, with citation enforcement."""
from __future__ import annotations

from dataclasses import dataclass, field

from agent.config import Config
from agent.core.governor import DegradeLevel
from agent.core.llm_json import llm_json
from agent.core.model_registry import resolve
from agent.tools.prompts import SEARCH_SYNTHESIZE


@dataclass
class SynthesisResult:
    text: str | None
    citations: list[dict] = field(default_factory=list)
    degraded: bool = False


def synthesize(query: str, selected: list[dict], *, cfg: Config, degrade: DegradeLevel = DegradeLevel.NONE) -> SynthesisResult:
    if degrade >= DegradeLevel.SEVERE or not selected:
        return SynthesisResult(text=None, citations=[], degraded=degrade >= DegradeLevel.SEVERE)

    context_lines = []
    for i, p in enumerate(selected, 1):
        context_lines.append(
            f"[{i}] paper_id={p.get('paper_id')} | {p.get('title')} ({p.get('year')}, {p.get('venue') or 'N/A'})\n"
            f"Abstract: {(p.get('abstract') or '')[:400]}"
        )
    context_str = "\n\n".join(context_lines)

    spec = resolve("synthesis", cfg, degrade=degrade)
    data = llm_json(
        SEARCH_SYNTHESIZE,
        f"User query: {query}\n\nCandidates:\n{context_str}",
        provider=spec.provider, model=spec.model, base_url=spec.base_url,
    )

    text = str(data.get("synthesis") or "").strip() or None
    raw_citations = data.get("citations") or []
    citations = [
        {"ref": c.get("ref"), "paper_id": c.get("paper_id")}
        for c in raw_citations
        if isinstance(c, dict) and c.get("paper_id")
    ]
    return SynthesisResult(text=text, citations=citations, degraded=False)
