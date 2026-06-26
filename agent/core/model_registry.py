"""Model registry — single seam all components resolve a (provider, model, base_url) through.

Maps the design doc's component names onto the existing 3-tier Config
(cheap_model / model / analysis_model). The governor can force a cheaper tier
by passing a DegradeLevel >= MODERATE, without any mutable global state.
"""
from __future__ import annotations

from dataclasses import dataclass

from agent.config import Config

from .governor import DegradeLevel

# Components that always use the cheap tier — every-request, must stay cheap.
_CHEAP_COMPONENTS = {"guardrail", "dispatcher", "contextualize", "grounding"}
# Components that use the standard tier.
_STANDARD_COMPONENTS = {"skill", "fast_generate", "synthesis"}
# Components that use the premium tier.
_PREMIUM_COMPONENTS = {"planner", "judge"}

# Best-effort price table for trace cost accounting. Placeholders — fill in
# real per-1k-token USD prices from platform.openai.com/docs/models (or the
# Gemini pricing page) once config.toml's chosen models are confirmed. Never
# raises on a missing key (cost tracking is passive, not billing-grade).
PRICE_PER_1K: dict[str, float] = {
    "gpt-4.1-nano": 0.0,
    "gpt-4.1-mini": 0.0,
    "gpt-4.1": 0.0,
    "gemini-2.0-flash-lite": 0.0,
    "gemini-2.5-flash": 0.0,
    "gemini-2.5-pro": 0.0,
}


@dataclass
class ModelSpec:
    provider: str
    model: str
    base_url: str | None


def _tier_for(component: str, degrade: DegradeLevel) -> str:
    if degrade >= DegradeLevel.MODERATE:
        return "cheap"
    if component in _CHEAP_COMPONENTS:
        return "cheap"
    if component in _PREMIUM_COMPONENTS:
        return "premium"
    if component in _STANDARD_COMPONENTS:
        return "standard"
    return "standard"


def resolve(component: str, cfg: Config, *, degrade: DegradeLevel = DegradeLevel.NONE) -> ModelSpec:
    provider = cfg.llm_provider
    tier = _tier_for(component, degrade)
    if provider == "openai":
        model = {"cheap": cfg.openai_cheap_model, "standard": cfg.openai_model, "premium": cfg.openai_analysis_model}[tier]
        base_url = cfg.openai_base_url
    else:
        model = {"cheap": cfg.gemini_cheap_model, "standard": cfg.gemini_model, "premium": cfg.gemini_analysis_model}[tier]
        base_url = cfg.gemini_base_url
    return ModelSpec(provider=provider, model=model, base_url=base_url)


def resolve_embedding(cfg: Config) -> ModelSpec:
    provider = cfg.llm_provider
    if provider == "openai":
        return ModelSpec(provider="openai", model="text-embedding-3-small", base_url=cfg.openai_base_url)
    return ModelSpec(provider="gemini", model="gemini-embedding-001", base_url=cfg.gemini_base_url)


def embed_one(text: str, cfg: Config) -> list[float]:
    spec = resolve_embedding(cfg)
    if spec.provider == "openai":
        from agent.tools.openai_embeddings import embed
        return embed(text=text, model=spec.model, base_url=spec.base_url)
    from agent.tools.gemini_embeddings import embed as g_embed
    return g_embed(text=text, model=spec.model, base_url=spec.base_url or "https://generativelanguage.googleapis.com/v1beta")
