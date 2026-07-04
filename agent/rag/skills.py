"""RAG skill registry — named procedures over the atomic tools, escalating
to the deliberate (ReAct) lane when a skill can't handle the question.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agent.config import Config

from . import tools
from .state import RAGState
from .tools import AnswerResult


@dataclass
class Skill:
    name: str
    when_to_use: str
    run: Callable[[RAGState, Config], AnswerResult]
    can_handle: Callable[[RAGState, Config], bool] | None = None


def _summarize_paper(state: RAGState, cfg: Config) -> AnswerResult:
    sections = ["abstract", "introduction", "method", "results", "conclusion"]
    chunks = []
    for s in sections:
        chunks += tools.get_section(state.paper_id, s, k=2)
    if not chunks:
        chunks = tools.retrieve(state.standalone_query or state.question, state.paper_id, k=8, cfg=cfg)
    return tools.generate(state.question, chunks, state.history, cfg=cfg, component="skill")


def _extract_methodology(state: RAGState, cfg: Config) -> AnswerResult:
    chunks = tools.get_section(state.paper_id, "method", k=4)
    if len(chunks) < 2:
        chunks += tools.retrieve(state.standalone_query or state.question, state.paper_id, k=6, cfg=cfg)
    return tools.generate(state.question, chunks, state.history, cfg=cfg, component="skill")


def _extract_methodology_can_handle(state: RAGState, cfg: Config) -> bool:
    chunks = tools.get_section(state.paper_id, "method", k=4)
    if len(chunks) >= 2:
        return True
    return len(tools.retrieve(state.question, state.paper_id, k=4, cfg=cfg)) >= 2


def _extract_results(state: RAGState, cfg: Config) -> AnswerResult:
    chunks = tools.get_section(state.paper_id, "results", k=4)
    chunks += tools.retrieve(state.standalone_query or state.question, state.paper_id, k=4, cfg=cfg)
    return tools.generate(state.question, chunks, state.history, cfg=cfg, component="skill")


def _compare_baselines(state: RAGState, cfg: Config) -> AnswerResult:
    chunks = tools.get_section(state.paper_id, "results", k=4) + tools.get_section(state.paper_id, "related", k=4)
    if len(chunks) < 2:
        chunks += tools.retrieve(state.standalone_query or state.question, state.paper_id, k=6, cfg=cfg)
    return tools.generate(state.question, chunks, state.history, cfg=cfg, component="skill")


def _translate_section(state: RAGState, cfg: Config) -> AnswerResult:
    chunks = []
    for section in ("abstract", "introduction", "method", "results", "conclusion"):
        if section in (state.standalone_query or state.question).lower():
            chunks += tools.get_section(state.paper_id, section, k=5)
    if not chunks:
        chunks = tools.retrieve(state.standalone_query or state.question, state.paper_id, k=6, cfg=cfg)
    return tools.generate(state.question, chunks, state.history, cfg=cfg, component="skill")


def _find_limitations(state: RAGState, cfg: Config) -> AnswerResult:
    chunks = (
        tools.get_section(state.paper_id, "limitation", k=4)
        + tools.get_section(state.paper_id, "discussion", k=3)
        + tools.get_section(state.paper_id, "conclusion", k=3)
    )
    if len(chunks) < 2:
        chunks += tools.retrieve(state.standalone_query or state.question, state.paper_id, k=6, cfg=cfg)
    return tools.generate(state.question, chunks, state.history, cfg=cfg, component="skill")


def _explain_term(state: RAGState, cfg: Config) -> AnswerResult:
    chunks = tools.retrieve(state.standalone_query or state.question, state.paper_id, k=6, cfg=cfg)
    return tools.generate(state.question, chunks, state.history, cfg=cfg, component="skill")


def _make_study_note(state: RAGState, cfg: Config) -> AnswerResult:
    chunks = []
    for section in ("abstract", "introduction", "method", "results", "conclusion"):
        chunks += tools.get_section(state.paper_id, section, k=2)
    if not chunks:
        chunks = tools.retrieve(state.standalone_query or state.question, state.paper_id, k=8, cfg=cfg)
    return tools.generate(state.question, chunks, state.history, cfg=cfg, component="skill")


SKILL_REGISTRY: dict[str, Skill] = {
    "summarize_paper": Skill(
        name="summarize_paper",
        when_to_use="tóm tắt bài / summarize the paper / what is this paper about",
        run=_summarize_paper,
    ),
    "extract_methodology": Skill(
        name="extract_methodology",
        when_to_use="phương pháp là gì / how does the method work / explain the approach",
        run=_extract_methodology,
        can_handle=_extract_methodology_can_handle,
    ),
    "extract_results": Skill(
        name="extract_results",
        when_to_use="kết quả / accuracy / số liệu / results / metrics",
        run=_extract_results,
    ),
    "compare_baselines": Skill(
        name="compare_baselines",
        when_to_use="so sánh baseline / so với phương pháp khác / compare to prior work",
        run=_compare_baselines,
    ),
    "translate_section": Skill(
        name="translate_section",
        when_to_use="dịch abstract/section/đoạn trong paper / translate a section",
        run=_translate_section,
    ),
    "find_limitations": Skill(
        name="find_limitations",
        when_to_use="limitations / giới hạn / điểm yếu / future work",
        run=_find_limitations,
    ),
    "explain_term": Skill(
        name="explain_term",
        when_to_use="giải thích thuật ngữ / define term / what does this term mean in the paper",
        run=_explain_term,
    ),
    "make_study_note": Skill(
        name="make_study_note",
        when_to_use="tạo study note / reading note / ghi chú học thuật",
        run=_make_study_note,
    ),
}

# Keyword heuristics used by the dispatcher's cheap rule-based pre-filter
# (kept in sync with when_to_use, but as short matchable tokens).
SKILL_KEYWORDS: dict[str, list[str]] = {
    "summarize_paper": ["tóm tắt", "tom tat", "summary", "summarize", "what is this paper"],
    "extract_methodology": ["phương pháp", "phuong phap", "how does", "method work", "approach", "algorithm"],
    "extract_results": ["kết quả", "ket qua", "accuracy", "số liệu", "so lieu", "results", "metric", "benchmark"],
    "compare_baselines": ["so sánh", "so sanh", "compare", "baseline", "prior work", "so với", "so voi"],
    "translate_section": ["dịch", "dich", "translate"],
    "find_limitations": ["limitation", "limitations", "giới hạn", "gioi han", "điểm yếu", "diem yeu", "future work"],
    "explain_term": ["giải thích", "giai thich", "define", "thuật ngữ", "thuat ngu", "what does"],
    "make_study_note": ["study note", "reading note", "ghi chú", "ghi chu", "note học", "note hoc"],
}
