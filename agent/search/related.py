"""Related-paper recommender for the Search Agent.

The first tier ranks papers already present in the current search session. If
that does not produce enough results and the focus paper has an OpenAlex id,
the second tier wraps the existing OpenAlex graph recommender.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from agent.config import Config
from agent.tools.recommend import recommend_from_openalex

from .workspace import get_search_session


_TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]+")


@dataclass
class RelatedPaperParams:
    focus_paper_id: str
    current_session_id: str | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    limit: int = 3


@dataclass
class RelatedPaperResult:
    focus_paper_id: str
    related: list[dict[str, Any]]

    def to_response_dict(self) -> dict[str, Any]:
        return {"focus_paper_id": self.focus_paper_id, "related": self.related}


def _text_tokens(paper: dict[str, Any]) -> set[str]:
    text = f"{paper.get('title') or ''} {paper.get('abstract') or ''} {' '.join(paper.get('tags') or [])}"
    return {t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 2}


def _authors(paper: dict[str, Any]) -> set[str]:
    out = set()
    for a in paper.get("authors") or []:
        if isinstance(a, dict):
            name = a.get("name")
        else:
            name = str(a)
        if name:
            out.add(str(name).strip().lower())
    return out


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _year_score(a: Any, b: Any) -> float:
    try:
        diff = abs(int(a) - int(b))
    except Exception:
        return 0.0
    return max(0.0, 1.0 - min(diff, 8) / 8)


def _quality_score(paper: dict[str, Any]) -> float:
    score = 0.0
    if paper.get("pdf_url"):
        score += 0.35
    if paper.get("citation_count"):
        score += min(0.35, math.log10(max(int(paper["citation_count"]), 1) + 1) / 8)
    if (paper.get("quality_signals") or {}).get("source_count"):
        score += min(0.30, 0.10 * int(paper["quality_signals"]["source_count"]))
    return min(score, 1.0)


def _relation_for(focus: dict[str, Any], candidate: dict[str, Any], semantic: float, shared_authors: float) -> str:
    if shared_authors > 0:
        return "same_authors"
    if focus.get("conference") and focus.get("conference") == candidate.get("conference"):
        return "same_venue"
    if semantic >= 0.18:
        return "semantic_similarity"
    return "same_topic"


def _reason_for(relation: str, focus: dict[str, Any], candidate: dict[str, Any]) -> str:
    if relation == "same_authors":
        return "Shares at least one author with the focused paper."
    if relation == "same_venue":
        return "Appears in the same venue and is close in topic."
    if relation == "semantic_similarity":
        return "Title, abstract, and keywords are semantically close to the focused paper."
    return "Matches overlapping topic terms from the current search session."


def _score_session_candidates(focus: dict[str, Any], candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    focus_tokens = _text_tokens(focus)
    focus_authors = _authors(focus)
    scored: list[tuple[float, dict[str, Any]]] = []

    for candidate in candidates:
        if candidate.get("paper_id") == focus.get("paper_id"):
            continue
        semantic = _jaccard(focus_tokens, _text_tokens(candidate))
        author_overlap = _jaccard(focus_authors, _authors(candidate))
        venue_match = 1.0 if focus.get("conference") and focus.get("conference") == candidate.get("conference") else 0.0
        if semantic <= 0 and author_overlap <= 0 and venue_match <= 0:
            continue
        recency = _year_score(focus.get("year"), candidate.get("year"))
        quality = _quality_score(candidate)
        score = 0.55 * semantic + 0.15 * author_overlap + 0.10 * venue_match + 0.10 * recency + 0.10 * quality
        if score <= 0:
            continue
        relation = _relation_for(focus, candidate, semantic, author_overlap)
        item = {
            **candidate,
            "relation": relation,
            "score": round(score, 4),
            "reason": _reason_for(relation, focus, candidate),
        }
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


def _openalex_id(paper: dict[str, Any]) -> str | None:
    source_ids = paper.get("source_ids") or {}
    openalex = source_ids.get("openalex") if isinstance(source_ids, dict) else None
    if openalex:
        return str(openalex)
    pid = paper.get("paper_id")
    if isinstance(pid, str) and ("openalex.org/" in pid or pid.startswith("W")):
        return pid
    return None


def _paper_from_model_dict(paper: dict[str, Any], *, relation: str) -> dict[str, Any]:
    pid = paper.get("id") or paper.get("doi") or paper.get("url") or paper.get("title")
    return {
        "paper_id": pid,
        "title": paper.get("title") or "",
        "abstract": paper.get("abstract"),
        "authors": [{"name": a} for a in (paper.get("authors") or [])],
        "year": paper.get("year"),
        "venue": paper.get("venue") or "",
        "conference": paper.get("venue"),
        "url": paper.get("url"),
        "pdf_url": None,
        "citation_count": None,
        "relevance_score": None,
        "rank_score": None,
        "source_ids": {"openalex": paper.get("id") if paper.get("source") == "openalex" else None, "doi": paper.get("doi")},
        "quality_signals": {"matched_filters": [], "source_count": 1, "has_pdf": False},
        "why_recommended": "Suggested from the OpenAlex citation/related-work graph.",
        "relation": relation,
        "score": 0.5,
        "reason": "Suggested from OpenAlex's related/citing works graph.",
    }


def recommend_related_papers(params: RelatedPaperParams, *, cfg: Config) -> RelatedPaperResult:
    limit = min(max(params.limit, 1), 5)
    pool = list(params.candidates)

    session = get_search_session(params.current_session_id) if params.current_session_id else None
    if session:
        pool = list(session.get("papers") or []) + pool

    seen_ids: set[str] = set()
    deduped_pool: list[dict[str, Any]] = []
    for p in pool:
        pid = p.get("paper_id")
        if not pid or pid in seen_ids:
            continue
        seen_ids.add(pid)
        deduped_pool.append(p)

    focus = next((p for p in deduped_pool if p.get("paper_id") == params.focus_paper_id), None)
    if not focus and params.candidates:
        focus = next((p for p in params.candidates if p.get("paper_id") == params.focus_paper_id), None)
    if not focus:
        return RelatedPaperResult(focus_paper_id=params.focus_paper_id, related=[])

    related = _score_session_candidates(focus, deduped_pool, limit)

    if len(related) < limit:
        seed = _openalex_id(focus)
        if seed:
            try:
                rec = recommend_from_openalex(seed_work_id=seed, limit=limit, openalex_email=cfg.openalex_email)
                for rel_name, papers in rec.items():
                    for p in papers:
                        item = _paper_from_model_dict(p.to_dict(), relation="cited_by" if rel_name == "citing" else "citation_graph")
                        if item["paper_id"] == params.focus_paper_id or item["paper_id"] in {r.get("paper_id") for r in related}:
                            continue
                        related.append(item)
                        if len(related) >= limit:
                            break
                    if len(related) >= limit:
                        break
            except Exception:
                pass

    return RelatedPaperResult(focus_paper_id=params.focus_paper_id, related=related[:limit])
