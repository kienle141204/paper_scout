-- RAG paper chunks table
-- Run this once in your Supabase SQL editor (Dashboard → SQL Editor → New query)
-- No pgvector extension required — similarity is computed in Python.

CREATE TABLE IF NOT EXISTS paper_chunks (
  id          BIGSERIAL PRIMARY KEY,
  paper_id    TEXT        NOT NULL,
  chunk_index INT         NOT NULL,
  section     TEXT,                         -- e.g. 'abstract', 'method', 'experiments'
  text        TEXT        NOT NULL,
  embedding   TEXT        NOT NULL,         -- JSON-encoded float array
  token_count INT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (paper_id, chunk_index)
);

-- Index for fast per-paper lookup
CREATE INDEX IF NOT EXISTS paper_chunks_paper_id_idx ON paper_chunks (paper_id);

-- Disable RLS: paper_chunks is a shared cache (not user-specific data).
-- The backend uses SUPABASE_SERVICE_ROLE_KEY (or ANON_KEY) to read/write —
-- no user-level access control needed here.
ALTER TABLE paper_chunks DISABLE ROW LEVEL SECURITY;
