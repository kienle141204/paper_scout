"""Shared guardrail primitives — cheap rule-based checks used by both agents.

Guardrails must be much cheaper than the agent core they wrap. Each agent's
own guardrails.py builds on these primitives plus one cheap-model call when
the rule-based pass is inconclusive.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) instructions",
    r"disregard (all |any )?(previous|prior|above) instructions",
    r"bỏ qua (mọi|tất cả|các)? ?(chỉ dẫn|hướng dẫn|lệnh)",
    r"you are now",
    r"system prompt",
    r"reveal your (system|instructions|prompt)",
    r"act as (a|an) (?!academic|researcher)",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


@dataclass
class GuardrailResult:
    passed: bool
    reason: str | None = None
    stripped: list[str] = field(default_factory=list)


def has_injection_marker(text: str) -> bool:
    return bool(_INJECTION_RE.search(text or ""))
