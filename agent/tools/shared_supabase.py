"""Shared Supabase connection for the community paper store.

This app is a local single-user research assistant, but the *paper* data
(translation cache in `paper_cache`, RAG vector store in `paper_chunks`, and the
cached PDFs in the `paper_pdfs` storage bucket) lives in one **shared online
Supabase** so everyone who clones the repo reads/writes the same corpus. The URL
+ publishable key below are intentionally committed defaults — a *publishable*
key is designed to be shippable — so a fresh clone works with zero Supabase
setup; users only add their own LLM key.

Key model (new Supabase API keys):
  - `sb_publishable_...` — client key, safe to commit. Access is gated by RLS /
    storage policies, exactly like the legacy anon key it replaces. This is the
    committed default below and what every user's backend uses at runtime.
  - `sb_secret_...` — full-access admin key (bypasses RLS). MUST NOT be
    committed. It is read from the environment ONLY (SUPABASE_SECRET_KEY) and is
    used solely for one-off admin setup (creating the bucket, running DDL) — see
    scripts/setup_supabase.py. Never bake it into a committed default.

Override by setting SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY in the environment
(e.g. to point at your own private Supabase project instead of the shared one).

Security note: the shared tables have RLS disabled and the `paper_pdfs` bucket
has open read/write policies, so anyone with the publishable key can write to
them. If abuse becomes a concern, tighten the policies on the Supabase project
(see README).
"""
from __future__ import annotations

import os

# Committed defaults for the shared community paper DB. The publishable key is
# safe to ship (RLS/policies gate what it can do). NEVER put the secret key here.
_DEFAULT_SUPABASE_URL = "https://ghnyipgnokpxijbaicer.supabase.co"
_DEFAULT_SUPABASE_PUBLISHABLE_KEY = "sb_publishable_x6XbpEixErv8MvdOOmbnIg_2wIfK-TT"

# Storage bucket holding cached paper PDFs (public read; see migration SQL).
PDF_BUCKET = "paper_pdfs"


def get_supabase_url() -> str:
    """Shared paper DB URL — env override wins over the committed default."""
    return os.getenv("SUPABASE_URL") or _DEFAULT_SUPABASE_URL


def get_supabase_anon_key() -> str:
    """Shared paper DB *client* key (publishable / anon) — safe to ship.

    Env overrides win, accepting several names for convenience: the new
    SUPABASE_PUBLISHABLE_KEY, the legacy SUPABASE_ANON_KEY, or a generic
    SUPABASE_KEY. Falls back to the committed publishable default."""
    return (
        os.getenv("SUPABASE_PUBLISHABLE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
        or os.getenv("SUPABASE_KEY")
        or _DEFAULT_SUPABASE_PUBLISHABLE_KEY
    )


def get_supabase_secret_key() -> str | None:
    """Admin key (secret / service_role) — read from the environment ONLY.

    Returns None when unset. There is deliberately no committed default: this
    key bypasses RLS, so it must never live in the repo. Used only by one-off
    admin tooling (bucket creation, DDL), never by the request path."""
    return (
        os.getenv("SUPABASE_SECRET_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or None
    )
