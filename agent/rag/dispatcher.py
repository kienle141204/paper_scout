"""RAG dispatcher — classifies a question into skill|fast|deliberate.

Cheapest path first: a rule-based pre-filter handles the bulk of traffic with
no LLM call; only ambiguous questions fall through to one cheap-model call.
"""
from __future__ import annotations

import re

from agent.config import Config
from agent.core.llm_json import llm_json
from agent.core.model_registry import resolve

from .skills import SKILL_KEYWORDS, SKILL_REGISTRY

_FAST_MARKERS = re.compile(
    r"\b(bao nhiêu|bao nhieu|what is the value|how many|accuracy of|number of params|"
    r"giá trị|gia tri)\b",
    re.IGNORECASE,
)
_MULTI_HOP_MARKERS = re.compile(
    r"\b(and|và|va)\b.*\b(why|tại sao|tai sao|how|compare|so sánh|so sanh)\b|"
    r"\b(compare|so sánh|so sanh)\b",
    re.IGNORECASE,
)


def _build_dispatcher_prompt() -> str:
    skill_lines = "\n".join(f"- {s.name}: {s.when_to_use}" for s in SKILL_REGISTRY.values())
    return f"""\
You are a routing classifier for a paper Q&A agent. Classify the question into
exactly one lane.

Available skills (use lane="skill" + the matching skill_name if one applies):
{skill_lines}

fast = a single factual question answerable in one retrieve+generate pass
       (no skill matches, not multi-hop).
deliberate = multi-hop / requires combining multiple pieces of evidence / a
       comparison or "why" question not covered by a skill.

Output ONLY valid JSON: {{"lane": "skill|fast|deliberate", "skill_name": "<name>|null"}}
"""


def classify_lane(question: str, *, cfg: Config) -> tuple[str, str | None]:
    q_lower = question.lower()

    # Step 1: cheap rule-based pre-filter, no LLM call.
    for name, keywords in SKILL_KEYWORDS.items():
        if any(kw in q_lower for kw in keywords):
            return "skill", name

    if _MULTI_HOP_MARKERS.search(question):
        return "deliberate", None

    if _FAST_MARKERS.search(question) and len(question) < 120:
        return "fast", None

    # Step 2: ambiguous — one cheap-model call.
    spec = resolve("dispatcher", cfg)
    try:
        data = llm_json(_build_dispatcher_prompt(), question, provider=spec.provider, model=spec.model, base_url=spec.base_url)
    except Exception:
        return "deliberate", None

    lane = str(data.get("lane") or "deliberate")
    if lane not in ("skill", "fast", "deliberate"):
        lane = "deliberate"
    skill_name = data.get("skill_name")
    if lane == "skill" and skill_name not in SKILL_REGISTRY:
        lane, skill_name = "deliberate", None
    return lane, skill_name
