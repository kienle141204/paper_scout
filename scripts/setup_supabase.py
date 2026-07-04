"""One-off Supabase setup for the shared paper store.

Uses the ADMIN secret key (env only — never committed) to create the
`paper_pdfs` storage bucket, then checks whether the required tables exist.
Table DDL + storage policies cannot be run over the data API, so if the tables
are missing this prints the exact next step (paste supabase_migration.sql into
the Dashboard SQL Editor).

Run from the repo root, after putting SUPABASE_SECRET_KEY in backend/.env:

    python scripts/setup_supabase.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / "backend" / ".env")
except Exception:
    pass

from agent.tools.shared_supabase import (  # noqa: E402
    PDF_BUCKET,
    get_supabase_anon_key,
    get_supabase_secret_key,
    get_supabase_url,
)
from supabase import create_client  # noqa: E402

URL = get_supabase_url()
SECRET = get_supabase_secret_key()
PUB = get_supabase_anon_key()


def ensure_bucket() -> None:
    if not SECRET:
        print("[!] SUPABASE_SECRET_KEY not set — skipping bucket creation.")
        print("  Add it to backend/.env, or create the bucket via the SQL migration.")
        return
    admin = create_client(URL, SECRET)
    existing = {getattr(b, "name", None) for b in admin.storage.list_buckets()}
    if PDF_BUCKET in existing:
        print(f"[OK] bucket '{PDF_BUCKET}' already exists")
        return
    admin.storage.create_bucket(
        PDF_BUCKET,
        options={"public": True, "allowed_mime_types": ["application/pdf"], "file_size_limit": 52428800},
    )
    print(f"[OK] created bucket '{PDF_BUCKET}' (public)")


def check_tables() -> bool:
    client = create_client(URL, PUB)
    ok = True
    for table in ("paper_cache", "paper_chunks"):
        try:
            client.table(table).select("*").limit(1).execute()
            print(f"[OK] table '{table}' reachable")
        except Exception as e:
            ok = False
            print(f"[MISSING] table '{table}' missing: {str(e)[:120]}")
    return ok


def main() -> None:
    print(f"Supabase project: {URL}")
    ensure_bucket()
    tables_ok = check_tables()
    if not tables_ok:
        print()
        print("-> Tables/policies are not set up yet. Open the Supabase Dashboard ->")
        print("  SQL Editor -> New query, paste the contents of supabase_migration.sql,")
        print("  and click Run. (DDL + storage policies can't be applied over the API.)")
        sys.exit(1)
    print("\nAll set.")


if __name__ == "__main__":
    main()
