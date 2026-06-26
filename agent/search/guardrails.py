"""Search Agent guardrails — cheap rule-based pass + one cheap-model classification."""
from __future__ import annotations

from agent.config import Config
from agent.core.guardrail import GuardrailResult, has_injection_marker
from agent.core.llm_json import llm_json
from agent.core.model_registry import resolve
from agent.tools.prompts import SEARCH_INPUT_GUARDRAIL

from .synthesize import SynthesisResult


def input_guardrail(query: str, *, cfg: Config) -> GuardrailResult:
    if has_injection_marker(query):
        return GuardrailResult(passed=False, reason="injection_marker_detected")

    spec = resolve("guardrail", cfg)
    try:
        data = llm_json(SEARCH_INPUT_GUARDRAIL, query, provider=spec.provider, model=spec.model, base_url=spec.base_url)
    except Exception:
        # Guardrail call failing must never block a legitimate search — fail open.
        return GuardrailResult(passed=True)

    if not data:
        return GuardrailResult(passed=True)

    if data.get("injection_detected") or data.get("harmful_intent"):
        return GuardrailResult(passed=False, reason=str(data.get("reason") or "guardrail_flagged"))
    if data.get("in_scope") is False:
        return GuardrailResult(passed=False, reason="out_of_scope")
    return GuardrailResult(passed=True)


def output_guardrail(synthesis: SynthesisResult, candidates: list[dict]) -> SynthesisResult:
    """Deterministic, no LLM call: strip any citation whose paper_id isn't a
    real candidate rather than blocking the whole response.
    """
    if not synthesis.text:
        return synthesis
    valid_ids = {c.get("paper_id") for c in candidates}
    kept = [c for c in synthesis.citations if c.get("paper_id") in valid_ids]
    return SynthesisResult(text=synthesis.text, citations=kept, degraded=synthesis.degraded)
