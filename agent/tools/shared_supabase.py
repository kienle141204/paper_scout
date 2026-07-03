"""Shared Supabase connection for the community paper store.

This app is a local single-user research assistant, but the *paper* data
(translation cache in `paper_cache` + RAG vector store in `paper_chunks`) lives
in one **shared online Supabase** so everyone who clones the repo reads/writes
the same corpus. The URL + anon key below are intentionally committed defaults —
an anon key is designed to be shippable — so a fresh clone works with zero
Supabase setup; users only add their own LLM key.

Override by setting SUPABASE_URL / SUPABASE_ANON_KEY in the environment (e.g.
to point at your own private Supabase project instead of the shared one).

Security note: the shared tables currently have RLS disabled, so anyone with
this anon key can write to them. If abuse becomes a concern, enable RLS with a
read-mostly policy on the Supabase project (see README).
"""
from __future__ import annotations

import os

# Committed defaults for the shared community paper DB.
_DEFAULT_SUPABASE_URL = "https://yobizptmpgusnhzxymmr.supabase.co"
_DEFAULT_SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlvYml6cHRtcGd1c25oenh5bW1yIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAzMjE2MzAsImV4cCI6MjA5NTg5NzYzMH0."
    "O_09H8ce0rwg0TswlBXtjqCFPzP0faOU3oOEjRttq4w"
)


def get_supabase_url() -> str:
    """Shared paper DB URL — env override wins over the committed default."""
    return os.getenv("SUPABASE_URL") or _DEFAULT_SUPABASE_URL


def get_supabase_anon_key() -> str:
    """Shared paper DB anon key — env override wins over the committed default."""
    return os.getenv("SUPABASE_ANON_KEY") or _DEFAULT_SUPABASE_ANON_KEY
