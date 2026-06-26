"""3-tier RAG memory: conversation (short-term), working (per-request dedup),
long-term (descoped — see note below).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from agent.config import Config
from agent.core.llm_json import llm_json
from agent.core.model_registry import resolve
from agent.tools.prompts import RAG_CONTEXTUALIZE


@dataclass
class ConversationMemory:
    """Thin wrapper over per-request history — the server stores no chat
    sessions today, so this tier needs no new storage.
    """
    turns: list[dict] = field(default_factory=list)

    def recent(self, n: int = 8) -> list[dict]:
        return self.turns[-n:]


@dataclass
class WorkingMemory:
    """Chunks already retrieved+used this request — dedups by chunk_index
    across dispatcher lanes within a single run_rag_ask call.
    """
    seen_chunk_indices: set[int] = field(default_factory=set)

    def add(self, chunks: list[dict]) -> list[dict]:
        fresh = []
        for c in chunks:
            idx = c.get("chunk_index")
            if idx in self.seen_chunk_indices:
                continue
            self.seen_chunk_indices.add(idx)
            fresh.append(c)
        return fresh


# Long-term memory (cross-session notes/preferences) is explicitly descoped:
# agent/tools/library.py's SQLite KV store is a single local file with no
# user_id scoping, so it can't safely back multi-user server-side long-term
# memory. Doing this properly needs a new Supabase table keyed by
# user_id+paper_id, which does not exist yet. The doc marks this tier
# optional — revisit only if multi-session personalization becomes a real
# requirement.


def contextualize(question: str, history: list[dict], *, cfg: Config) -> str:
    """Rewrite a follow-up question to be standalone using conversation
    history. Skips the LLM call entirely when there's no history.
    """
    if not history:
        return question

    spec = resolve("contextualize", cfg)
    history_text = "\n".join(f"{h.get('role')}: {h.get('content')}" for h in history[-8:])
    try:
        data = llm_json(
            RAG_CONTEXTUALIZE,
            f"Conversation history:\n{history_text}\n\nNew question: {question}",
            provider=spec.provider, model=spec.model, base_url=spec.base_url,
        )
    except Exception:
        return question

    standalone = str(data.get("standalone_query") or "").strip()
    return standalone or question
