"""RAG Agent guardrails — input scope/injection/PII check, output grounding +
citation enforcement + refusal-on-ungrounded.
"""
from __future__ import annotations

from agent.config import Config
from agent.core.guardrail import GuardrailResult, has_injection_marker
from agent.core.llm_json import llm_json
from agent.core.model_registry import resolve
from agent.tools.prompts import RAG_INPUT_GUARDRAIL

from .tools import AnswerResult, GroundingResult

_REFUSAL_VI = "Xin lỗi, tôi không tìm thấy thông tin này trong bài báo nên không thể trả lời chắc chắn."
_REFUSAL_EN = "Sorry, I couldn't find this information in the paper, so I can't answer confidently."


def input_guardrail(question: str, paper_id: str, *, cfg: Config) -> GuardrailResult:
    if has_injection_marker(question):
        return GuardrailResult(passed=False, reason="injection_marker_detected")

    spec = resolve("guardrail", cfg)
    try:
        data = llm_json(RAG_INPUT_GUARDRAIL, question, provider=spec.provider, model=spec.model, base_url=spec.base_url)
    except Exception:
        return GuardrailResult(passed=True)  # fail open — never block a legitimate question on guardrail errors

    if not data:
        return GuardrailResult(passed=True)

    if data.get("injection_detected") or data.get("harmful_intent"):
        return GuardrailResult(passed=False, reason=str(data.get("reason") or "guardrail_flagged"))
    if data.get("in_scope") is False:
        return GuardrailResult(passed=False, reason="out_of_scope")
    return GuardrailResult(passed=True)


def _is_vietnamese(text: str) -> bool:
    return any(ch in text for ch in "ăâđêôơưĂÂĐÊÔƠƯ") or any(w in text.lower() for w in (" là ", " gì", " không"))


def output_guardrail(result: AnswerResult, grounding: GroundingResult, *, question: str = "") -> AnswerResult:
    """Deterministic — no LLM call. Prefers to *show* the answer (optionally the
    verifier's cleaned-up ``refined_answer``) with a soft warning rather than
    nuke it. Only hard-refuses on a genuine high-risk fabrication that the
    verifier could not ground — everything else is surfaced to the user, letting
    the frontend's VerificationBadge flag medium/high risk (doc §4.9: warn, don't
    over-refuse).
    """
    # Hard refuse only when the answer is BOTH fabricated-level risky AND
    # untraceable to any chunk. A high-risk answer that is still grounded, or a
    # medium-risk one, is kept (cleaned up if the verifier offered a rewrite).
    if grounding.hallucination_risk == "high" and not grounding.is_grounded:
        refusal = _REFUSAL_VI if _is_vietnamese(question or result.answer) else _REFUSAL_EN
        return AnswerResult(
            answer=refusal, citations=[], chunks_used=result.chunks_used,
            confidence="low", coverage="insufficient", warning="refused_ungrounded",
        )

    # medium/high-but-grounded: prefer the verifier's cleaned answer, keep
    # citations, and flag it so the badge shows.
    warn = "grounding_warning" if grounding.hallucination_risk in ("medium", "high") else None
    answer_text = grounding.refined_answer or result.answer
    return AnswerResult(
        answer=answer_text, citations=result.citations, chunks_used=result.chunks_used,
        confidence=result.confidence, coverage=result.coverage, warning=warn,
    )
