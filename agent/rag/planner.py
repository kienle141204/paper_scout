"""RAG deliberate lane — bounded ReAct loop generalizing the original
plan -> gather -> answer -> verify sequence.

Retrieval strategy (parallel multi-query + section-targeted fan-out) is
preserved from the original implementation. New vs. before: the planner LLM
call now runs at the `planner` registry tier (analysis_model, upgraded from
cheap_model per user-confirmed decision), and a bounded sufficiency-check
loop can trigger one extra targeted retrieval round before answering,
whereas the original code only ever gathered once.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from agent.config import Config
from agent.core.governor import DegradeLevel, Governor
from agent.core.llm_json import llm_json
from agent.core.model_registry import resolve
from agent.tools.prompts import PAPER_RAG_PLANNER

from . import tools
from .memory import WorkingMemory
from .state import RAGState, ReActStep
from .tools import AnswerResult

_MAX_REACT_ITERS = 2


def _plan(state: RAGState, *, cfg: Config, degrade: DegradeLevel) -> dict:
    spec = resolve("planner", cfg, degrade=degrade)
    try:
        plan = llm_json(
            PAPER_RAG_PLANNER,
            f"Question: {state.standalone_query or state.question}",
            provider=spec.provider, model=spec.model, base_url=spec.base_url,
        )
    except Exception:
        plan = {}
    state.scratchpad.append(ReActStep(thought=str(plan), action="plan", observation=None))
    return plan


def _gather(state: RAGState, queries: list[str], sections: list[str], *, cfg: Config, degrade: DegradeLevel, working: WorkingMemory) -> list[dict]:
    per_query_k = 2 if degrade >= DegradeLevel.LIGHT else 4

    def _search_query(q: str) -> list[dict]:
        try:
            return tools.retrieve(q, state.paper_id, per_query_k, cfg=cfg)
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=min(max(len(queries), 1), 4)) as pool:
        gathered_batches = list(pool.map(_search_query, queries))

    if degrade < DegradeLevel.MODERATE:
        for sec in sections[:3]:
            gathered_batches.append(tools.get_section(state.paper_id, sec, k=3))

    new_chunks: list[dict] = []
    for batch in gathered_batches:
        new_chunks += working.add(batch)

    state.scratchpad.append(ReActStep(action="gather", observation=f"{len(new_chunks)} new chunks"))
    return new_chunks


def _is_sufficient_rag(retrieved: list[dict], iteration: int) -> bool:
    return len(retrieved) >= 3 or iteration + 1 >= _MAX_REACT_ITERS


def run_deliberate(state: RAGState, *, cfg: Config, governor: Governor) -> AnswerResult:
    level = governor.check_before_step("plan")
    plan = _plan(state, cfg=cfg, degrade=level)

    sub_questions: list[str] = plan.get("sub_questions") or []
    search_queries: list[str] = plan.get("search_queries") or []
    sections: list[str] = plan.get("sections") or []
    base_query = state.standalone_query or state.question
    all_queries = list(dict.fromkeys([base_query] + search_queries))[:5]

    working = WorkingMemory()
    for iteration in range(_MAX_REACT_ITERS):
        level = governor.check_before_step(f"gather_{iteration}")
        new_chunks = _gather(state, all_queries, sections, cfg=cfg, degrade=level, working=working)
        state.retrieved += new_chunks
        if _is_sufficient_rag(state.retrieved, iteration):
            break
        # Not enough evidence yet — narrow to the original question for one more pass.
        all_queries = [base_query]

    if not state.retrieved:
        return AnswerResult(answer="", citations=[], chunks_used=[], confidence="low", coverage="insufficient")

    level = governor.check_before_step("answer")
    if level >= DegradeLevel.SEVERE:
        result = tools.generate(state.question, state.retrieved[:6], state.history, cfg=cfg, degrade=level, component="fast_generate")
        result.warning = "partial - budget limit reached"
    else:
        component = "fast_generate" if level >= DegradeLevel.MODERATE else "skill"
        result = tools.generate(state.question, state.retrieved, state.history, cfg=cfg, degrade=level, component=component)

    result.plan_meta = {
        "sub_questions": sub_questions,
        "queries_used": all_queries,
        "sections_searched": sections,
    }
    state.scratchpad.append(ReActStep(action="answer", observation=result.answer[:200]))
    return result
