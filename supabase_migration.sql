-- PaperScout — shared Supabase schema.
-- Run once in the Supabase Dashboard → SQL Editor → New query (paste + Run).
-- Idempotent: safe to re-run.

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. paper_cache — metadata + expensive LLM outputs (VI abstract, HTML analysis)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS paper_cache (
  paper_id      TEXT PRIMARY KEY,
  title         TEXT,
  abstract_en   TEXT,
  abstract_vi   TEXT,
  authors       TEXT,                 -- JSON-encoded list
  keywords      TEXT,                 -- JSON-encoded list
  venue         TEXT,
  year          INT,
  url           TEXT,
  source        TEXT,
  analysis_html TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Shared cache, not per-user data → no row-level access control needed.
ALTER TABLE paper_cache DISABLE ROW LEVEL SECURITY;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. paper_chunks — RAG vector store (cosine computed in Python, no pgvector)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS paper_chunks (
  id          BIGSERIAL PRIMARY KEY,
  paper_id    TEXT        NOT NULL,
  chunk_index INT         NOT NULL,
  section     TEXT,
  text        TEXT        NOT NULL,
  embedding   TEXT        NOT NULL,   -- JSON-encoded float array
  token_count INT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (paper_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS paper_chunks_paper_id_idx ON paper_chunks (paper_id);
ALTER TABLE paper_chunks DISABLE ROW LEVEL SECURITY;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. paper_pdfs storage bucket — cached PDFs, keyed by <paper_id>.pdf
--    (scripts/setup_supabase.py already creates the bucket; this is the
--     idempotent SQL equivalent so a dashboard-only setup works too.)
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO storage.buckets (id, name, public)
VALUES ('paper_pdfs', 'paper_pdfs', true)
ON CONFLICT (id) DO UPDATE SET public = true;

-- storage.objects has RLS on by default. The publishable key every user ships
-- with is the 'anon' role, so grant it read + write on THIS bucket only.
DROP POLICY IF EXISTS "paper_pdfs read"   ON storage.objects;
DROP POLICY IF EXISTS "paper_pdfs insert" ON storage.objects;
DROP POLICY IF EXISTS "paper_pdfs update" ON storage.objects;

CREATE POLICY "paper_pdfs read" ON storage.objects
  FOR SELECT USING (bucket_id = 'paper_pdfs');
CREATE POLICY "paper_pdfs insert" ON storage.objects
  FOR INSERT WITH CHECK (bucket_id = 'paper_pdfs');
CREATE POLICY "paper_pdfs update" ON storage.objects
  FOR UPDATE USING (bucket_id = 'paper_pdfs') WITH CHECK (bucket_id = 'paper_pdfs');
