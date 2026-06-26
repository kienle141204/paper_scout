"""RAG Agent top-level entrypoint — dispatcher + lanes + grounding convergence
+ governor/tracer/guardrails wiring.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from agent.config import Config
from agent.core.budget import default_budget
from agent.core.governor import BudgetExceeded, DegradeLevel, Governor
from agent.core.trace import new_trace
from agent.tools import rag_store

from . import dispatcher, guardrails, planner, tools
from .ingest import IngestError, IngestRequest, ingest_paper
from .memory import contextualize
from .skills import SKILL_REGISTRY
from .state import RAGState
from .tools import AnswerResult


@dataclass
class RagAskParams:
    """Plain-dataclass mirror of backend.api.RagAskRequest's fields — keeps
    agent/ FastAPI-free.
    """
    paper_id: str
    question: str
    history: list[dict] = field(default_factory=list)
    title: str | None = None
    abstract: str | None = None
    authors: list[str] = field(default_factory=list)
    url: str | None = None
    conference: str | None = None
    year: int | None = None


@dataclass
class RagAskResult:
    answer: str
    citations: list[dict]
    chunks: list[dict]
    confidence: str
    coverage: str
    plan: dict
    verification: dict
    refused: bool = False
    refusal_reason: str | None = None

    def to_response_dict(self) -> dict:
        return {
            "answer": self.answer,
            "citations": self.citations,
            "chunks": [{"chunk_index": c.get("chunk_index"), "section": c.get("section", "body"), "text": (c.get("text") or "")[:500]} for c in self.chunks],
            "confidence": self.confidence,
            "coverage": self.coverage,
            "plan": self.plan,
            "verification": self.verification,
        }


def _run_fast(state: RAGState, *, cfg: Config, governor: Governor) -> AnswerResult:
    level = governor.check_before_step("fast_retrieve")
    k = 3 if level >= DegradeLevel.LIGHT else 6
    chunks = tools.retrieve(state.standalone_query or state.question, state.paper_id, k, cfg=cfg)
    if level < DegradeLevel.LIGHT:
        chunks = tools.rerank(chunks, state.standalone_query or state.question, cfg=cfg)
    level = governor.check_before_step("fast_generate")
    return tools.generate(state.question, chunks, state.history, cfg=cfg, degrade=level, component="fast_generate")


def run_rag_ask(params: RagAskParams, *, cfg: Config, session_id: str | None = None) -> RagAskResult:
    trace = new_trace("rag", session_id=session_id, paper_id=params.paper_id)
    started_at = time.monotonic()

    gr = guardrails.input_guardrail(params.question, params.paper_id, cfg=cfg)
    trace.guardrails["input_pass"] = gr.passed
    if not gr.passed:
        trace.outcome = "refused"
        trace.log()
        return RagAskResult(
            answer="", citations=[], chunks=[], confidence="low", coverage="insufficient",
            plan={}, verification={"is_grounded": True, "hallucination_risk": "none", "issues": []},
            refused=True, refusal_reason=gr.reason,
        )

    if not rag_store.is_ingested(params.paper_id):
        if params.title or params.abstract:
            try:
                ingest_paper(IngestRequest(
                    paper_id=params.paper_id, title=params.title or "Unknown", abstract=params.abstract,
                    authors=params.authors, url=params.url, conference=params.conference, year=params.year,
                ), cfg=cfg)
            except IngestError:
                raise
        else:
            raise IngestError(404, "Paper chưa được ingest. Hãy gọi /api/papers/ingest trước.")

    state = RAGState(paper_id=params.paper_id, question=params.question, history=params.history)
    state.standalone_query = contextualize(params.question, state.history, cfg=cfg) if state.history else params.question

    lane, skill_name = dispatcher.classify_lane(state.standalone_query, cfg=cfg)
    state.mode = lane
    degraded = False

    governor = Governor(default_budget("rag", mode=lane), trace, started_at)

    try:
        if lane == "skill":
            skill = SKILL_REGISTRY[skill_name]
            if skill.can_handle is None or skill.can_handle(state, cfg):
                state.active_skill = skill.name
                result = skill.run(state, cfg)
            else:
                lane = state.mode = "deliberate"
                governor = Governor(default_budget("rag", mode="deliberate"), trace, started_at)
                result = planner.run_deliberate(state, cfg=cfg, governor=governor)
        elif lane == "fast":
            result = _run_fast(state, cfg=cfg, governor=governor)
        else:
            result = planner.run_deliberate(state, cfg=cfg, governor=governor)
    except BudgetExceeded:
        trace.outcome = "budget_exceeded"
        degraded = True
        result = AnswerResult(
            answer="Xin lỗi, tôi chưa kịp tìm đủ thông tin trong thời gian cho phép.",
            citations=[], chunks_used=state.retrieved, confidence="low", coverage="insufficient",
            warning="budget_exceeded",
        )

    grounding = tools.check_grounded(result.answer, result.chunks_used, cfg=cfg, question=params.question)
    final = guardrails.output_guardrail(result, grounding, question=params.question)
    trace.guardrails["grounded"] = grounding.is_grounded
    trace.outcome = trace.outcome or ("answered" if final.warning != "refused_ungrounded" else "refused")
    trace.log()

    plan_meta = dict(result.plan_meta)
    plan_meta.update({"mode": lane, "skill_used": state.active_skill, "degraded": degraded})

    return RagAskResult(
        answer=final.answer,
        citations=final.citations,
        chunks=final.chunks_used,
        confidence=final.confidence,
        coverage=final.coverage,
        plan=plan_meta,
        verification={
            "is_grounded": grounding.is_grounded,
            "hallucination_risk": grounding.hallucination_risk,
            "issues": grounding.issues,
        },
    )
