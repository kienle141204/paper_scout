import type { Conference, Paper } from '../types/paper'
import type { ChatRequest, ChatResponse } from '../types/chat'
import type { IngestResult, AskResult } from '../types/rag'

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

// Routes a paper's PDF through our backend so <iframe> embedding works
// regardless of the source's X-Frame-Options/CORS policy (e.g. OpenReview
// blocks cross-origin framing; arXiv doesn't — proxying makes both uniform).
export function pdfProxyUrl(pdfUrl: string, title?: string, paperId?: string): string {
  const t = title ? `&title=${encodeURIComponent(title)}` : ''
  const p = paperId ? `&paper_id=${encodeURIComponent(paperId)}` : ''
  return `${BASE}/api/papers/pdf/proxy?url=${encodeURIComponent(pdfUrl)}${t}${p}`
}

// Ask the backend whether an embeddable PDF exists (OpenReview blocks framing +
// anonymous fetch, so it resolves an arXiv copy by title). Returns the url to
// embed via pdfProxyUrl, or null when the Reader should fall back to the
// reading view instead of showing a broken iframe.
export async function resolvePdfUrl(pdfUrl: string, title?: string, paperId?: string): Promise<string | null> {
  const t = title ? `&title=${encodeURIComponent(title)}` : ''
  const p = paperId ? `&paper_id=${encodeURIComponent(paperId)}` : ''
  try {
    const r = await fetch(`${BASE}/api/papers/pdf/resolve?url=${encodeURIComponent(pdfUrl)}${t}${p}`)
    if (!r.ok) return null
    const data = await r.json()
    return data.embeddable ? (data.url as string) : null
  } catch {
    return null
  }
}

// ── Backend shapes ───────────────────────────────
interface BackendConference {
  name: string
  full_name: string
  areas: string[]
  url?: string
}

interface BackendAuthor {
  name?: string
  author_id?: string
}
type BackendAuthorLike = BackendAuthor | string

interface BackendPaper {
  paper_id: string
  source?: string
  source_ids?: {
    semantic_scholar?: string | null
    openalex?: string | null
    arxiv?: string | null
    doi?: string | null
    openreview?: string | null
  }
  title: string
  abstract?: string
  summary?: string
  title_vi?: string
  authors?: BackendAuthorLike[]
  year?: number
  venue?: string
  conference?: string
  url?: string
  pdf_url?: string
  citation_count?: number
  relevance_score?: number
  rank_score?: number
  quality_signals?: {
    matched_filters?: string[]
    source_count?: number
    has_pdf?: boolean
  }
  why_recommended?: string | null
  relation?: string
  score?: number
  reason?: string
  key_contributions?: string[]
  tags?: string[]
}

interface AgentPaper {
  source: string
  id: string | null
  title: string
  year?: number | null
  venue?: string | null
  url?: string | null
  doi?: string | null
  abstract?: string | null
  authors?: string[]
  keywords?: string[]
}

export interface SearchSynthesisCitation {
  ref: number
  paper_id: string
}

interface BackendSearchResponse {
  papers: BackendPaper[]
  total: number
  query: string
  has_more?: boolean
  corrected_query?: string | null
  session_id?: string | null
  query_plan?: Record<string, unknown>
  source_stats?: Record<string, unknown>
  warnings?: string[]
  synthesis?: string | null
  synthesis_citations?: SearchSynthesisCitation[]
}

// ── Mappers ──────────────────────────────────────
function mapAuthors(authors: BackendAuthorLike[] | undefined): string[] {
  return (authors ?? [])
    .map((author) => (typeof author === 'string' ? author : author.name))
    .filter((name): name is string => Boolean(name && name.trim()))
}

function mapPaper(p: BackendPaper): Paper {
  return {
    id: p.paper_id,
    source: p.source,
    sourceIds: p.source_ids,
    titleEn: p.title,
    titleVi: p.title_vi,
    abstractEn: p.abstract,
    abstractVi: p.summary,
    authors: mapAuthors(p.authors),
    year: p.year,
    conf: p.conference,
    venue: p.venue,
    url: p.url,
    pdfUrl: p.pdf_url,
    citations: p.citation_count ?? null,
    relevance: Math.round((p.relevance_score ?? 0) * 100),
    rankScore: p.rank_score ?? null,
    qualitySignals: p.quality_signals,
    whyRecommended: p.why_recommended,
    relation: p.relation,
    relatedScore: p.score,
    relatedReason: p.reason,
    keywords: p.tags ?? [],
    keyContributions: p.key_contributions,
  }
}

function mapAgentPaper(p: AgentPaper): Paper {
  return {
    id: p.id ?? p.doi ?? p.url ?? p.title,
    source: p.source,
    sourceIds: { doi: p.doi ?? null, openalex: p.source === 'openalex' ? p.id : null, arxiv: p.source === 'arxiv' ? p.id : null },
    titleEn: p.title,
    abstractEn: p.abstract ?? undefined,
    authors: p.authors ?? [],
    year: p.year ?? undefined,
    conf: p.venue ?? undefined,
    venue: p.venue ?? undefined,
    url: p.url ?? undefined,
    citations: null,
    relevance: 0,
    keywords: p.keywords ?? [],
  }
}

// ── API functions ────────────────────────────────
export async function getConferences(): Promise<Conference[]> {
  const res = await fetch(`${BASE}/api/conferences`)
  if (!res.ok) throw new Error(`Không thể tải danh sách hội nghị (HTTP ${res.status})`)
  const data: { conferences: BackendConference[] } = await res.json()
  return data.conferences.map((c) => ({
    id: c.name,
    name: c.name,
    full: c.full_name,
    url: c.url,
  }))
}

export interface ViewPaperParams {
  paper_id: string
  title: string
  abstract?: string
  authors?: string[]
  keywords?: string[]
  venue?: string
  year?: number
  url?: string
  source?: string
  conference?: string
}

export async function viewPaper(
  params: ViewPaperParams,
): Promise<{ abstract_vi: string | null; from_cache: boolean }> {
  const res = await fetch(`${BASE}/api/papers/view`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error(`Lỗi (HTTP ${res.status})`)
  return res.json()
}

export interface SearchParams {
  query: string
  keywordVariants?: string[]
  conferences: string[]
  yearFrom?: number
  yearTo?: number
  language?: string
  limit?: number
  offset?: number
  correctedQuery?: string | null
  includeSynthesis?: boolean
  sessionId?: string | null
  sources?: string[]
}

export interface ParsedQuery {
  keywords: string
  keyword_variants: string[]
  venues: string[]
  year_from: number | null
  year_to: number | null
  corrected_query: string | null
  fallback: boolean
}

export async function parseQuery(query: string): Promise<ParsedQuery> {
  const res = await fetch(`${BASE}/api/parse-query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })
  if (!res.ok) {
    return { keywords: query, keyword_variants: [], venues: [], year_from: null, year_to: null, corrected_query: null, fallback: true }
  }
  return res.json()
}

export interface AgentStatus {
  paper_cache_configured: boolean
  vector_store_configured: boolean
  paper_ingested?: boolean
}

export async function getAgentStatus(paperId?: string): Promise<AgentStatus> {
  const qs = paperId ? `?paper_id=${encodeURIComponent(paperId)}` : ''
  const res = await fetch(`${BASE}/api/agent/status${qs}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getPaperCitation(params: {
  doi: string
  formats?: Array<'apa' | 'bibtex'>
}): Promise<{ doi: string; apa?: string; bibtex?: string }> {
  const res = await fetch(`${BASE}/api/papers/citation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ doi: params.doi, formats: params.formats ?? ['apa', 'bibtex'] }),
  })
  if (!res.ok) {
    const err: { detail?: string } = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export async function recommendPapers(params: {
  work_id: string
  limit?: number
}): Promise<{ related: Paper[]; citing: Paper[] }> {
  const res = await fetch(`${BASE}/api/papers/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ work_id: params.work_id, limit: params.limit ?? 25 }),
  })
  if (!res.ok) {
    const err: { detail?: string } = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  const data: { related: AgentPaper[]; citing: AgentPaper[] } = await res.json()
  return {
    related: data.related.map(mapAgentPaper),
    citing: data.citing.map(mapAgentPaper),
  }
}

export async function scorePaperRelevance(params: {
  query: string
  text: string
  provider?: 'openai' | 'gemini'
  model?: string
  base_url?: string
}): Promise<number> {
  const res = await fetch(`${BASE}/api/papers/score`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const err: { detail?: string } = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  const data: { score: number } = await res.json()
  return data.score
}

export interface PdfParseResult {
  abstract: string | null
  method: string | null
  experiments: string | null
  table_mentions: string[]
  figure_mentions: string[]
}

export async function parsePaperPdf(file: File, maxPages = 8): Promise<PdfParseResult> {
  const body = new FormData()
  body.append('file', file)
  const res = await fetch(`${BASE}/api/papers/pdf/parse?max_pages=${maxPages}`, {
    method: 'POST',
    body,
  })
  if (!res.ok) {
    const err: { detail?: string } = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export async function chatWithAgent(req: ChatRequest): Promise<ChatResponse> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 30_000)
  try {
    const res = await fetch(`${BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
      signal: controller.signal,
    })
    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const err: { detail?: string } = await res.json()
        if (err.detail) detail = err.detail
      } catch { /* empty */ }
      return {
        reply: `Không thể kết nối AI (${detail}). Vui lòng thử lại.`,
        action: 'clarify',
      }
    }
    return res.json() as Promise<ChatResponse>
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      return { reply: 'Yêu cầu mất quá nhiều thời gian. Vui lòng thử lại.', action: 'clarify' }
    }
    return { reply: 'Lỗi kết nối mạng. Vui lòng kiểm tra lại.', action: 'clarify' }
  } finally {
    clearTimeout(timeoutId)
  }
}

export interface AnalyzePaperParams {
  paper_id: string
  title: string
  abstract?: string
  authors?: string[]
  keywords?: string[]
  venue?: string
  year?: number
  url?: string
  conference?: string
}

export async function analyzePaper(
  params: AnalyzePaperParams,
): Promise<{ html: string; from_cache: boolean }> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 90_000)
  try {
    const res = await fetch(`${BASE}/api/papers/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
      signal: controller.signal,
    })
    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const err: { detail?: string } = await res.json()
        if (err.detail) detail = err.detail
      } catch { /* empty */ }
      throw new Error(detail)
    }
    return res.json()
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Phân tích mất quá nhiều thời gian. Vui lòng thử lại.')
    }
    throw err
  } finally {
    clearTimeout(timeoutId)
  }
}

export async function searchPapers(
  params: SearchParams,
): Promise<{
  papers: Paper[]
  total: number
  query: string
  hasMore: boolean
  correctedQuery: string | null
  sessionId: string | null
  queryPlan: Record<string, unknown>
  sourceStats: Record<string, unknown>
  warnings: string[]
  synthesis: string | null
  synthesisCitations: SearchSynthesisCitation[]
}> {
  const res = await fetch(`${BASE}/api/papers/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: params.query,
      keyword_variants: params.keywordVariants ?? [],
      conferences: params.conferences,
      year_from: params.yearFrom,
      year_to: params.yearTo,
      language: params.language ?? 'vi',
      limit: params.limit ?? 20,
      offset: params.offset ?? 0,
      corrected_query: params.correctedQuery ?? null,
      include_synthesis: params.includeSynthesis ?? false,
      session_id: params.sessionId ?? null,
      sources: params.sources ?? ['openreview'],
    }),
  })

  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const err: { detail?: string } = await res.json()
      if (err.detail) detail = err.detail
    } catch { /* empty */ }
    throw new Error(detail)
  }

  const data: BackendSearchResponse = await res.json()
  return {
    papers: data.papers.map(mapPaper),
    total: data.total,
    query: data.query,
    hasMore: data.has_more ?? false,
    correctedQuery: data.corrected_query ?? null,
    sessionId: data.session_id ?? null,
    queryPlan: data.query_plan ?? {},
    sourceStats: data.source_stats ?? {},
    warnings: data.warnings ?? [],
    synthesis: data.synthesis ?? null,
    synthesisCitations: data.synthesis_citations ?? [],
  }
}

function paperToBackendCandidate(p: Paper): BackendPaper {
  return {
    paper_id: p.id,
    source: p.source,
    source_ids: p.sourceIds,
    title: p.titleEn,
    abstract: p.abstractEn,
    authors: p.authors.map((name) => ({ name })),
    year: p.year,
    venue: p.venue,
    conference: p.conf,
    url: p.url,
    pdf_url: p.pdfUrl,
    citation_count: p.citations ?? undefined,
    relevance_score: p.relevance / 100,
    rank_score: p.rankScore ?? undefined,
    quality_signals: p.qualitySignals,
    why_recommended: p.whyRecommended,
    key_contributions: p.keyContributions,
    tags: p.keywords,
  }
}

export async function getRelatedPapers(params: {
  focusPaperId: string
  currentSessionId?: string | null
  candidates?: Paper[]
  limit?: number
}): Promise<Paper[]> {
  const res = await fetch(`${BASE}/api/papers/related`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      focus_paper_id: params.focusPaperId,
      current_session_id: params.currentSessionId ?? null,
      candidates: (params.candidates ?? []).map(paperToBackendCandidate),
      limit: params.limit ?? 3,
    }),
  })
  if (!res.ok) {
    const err: { detail?: string } = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  const data: { related: BackendPaper[] } = await res.json()
  return data.related.map(mapPaper)
}

// ── RAG paper agent ──────────────────────────────

export interface IngestPaperParams {
  paper_id: string
  title: string
  abstract?: string
  authors?: string[]
  url?: string
  pdf_url?: string
  conference?: string
  year?: number
  force?: boolean
}

export async function ingestPaper(params: IngestPaperParams): Promise<IngestResult> {
  const res = await fetch(`${BASE}/api/papers/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const err: { detail?: string } = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export interface AskPaperParams {
  paper_id: string
  question: string
  history: Array<{ role: 'user' | 'assistant'; content: string }>
  // Paper metadata for auto-ingest if not yet indexed
  title?: string
  abstract?: string
  authors?: string[]
  url?: string
  pdf_url?: string
  conference?: string
  year?: number
}

export async function askPaper(params: AskPaperParams): Promise<AskResult> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 60_000)
  try {
    const res = await fetch(`${BASE}/api/papers/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
      signal: controller.signal,
    })
    if (!res.ok) {
      const err: { detail?: string } = await res.json().catch(() => ({}))
      throw new Error(err.detail ?? `HTTP ${res.status}`)
    }
    return res.json()
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Phân tích mất quá nhiều thời gian. Vui lòng thử lại.')
    }
    throw err
  } finally {
    clearTimeout(timeout)
  }
}

export async function getMemory(): Promise<Record<string, unknown>> {
  const res = await fetch(`${BASE}/api/memory/me`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function patchMemoryPreferences(preferences: Record<string, unknown>): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE}/api/memory/preferences`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ preferences }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function deleteMemoryTopic(topicId: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE}/api/memory/topics/${encodeURIComponent(topicId)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function deleteAllMemory(): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE}/api/memory/me`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export interface NotionStatus {
  configured: boolean
  connected: boolean
  connection_type: 'static' | 'oauth' | null
  workspace_name?: string | null
  workspace_id?: string | null
  updated_at?: string | null
}

export async function getNotionStatus(): Promise<NotionStatus> {
  const res = await fetch(`${BASE}/api/notion/status`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getNotionConnectUrl(): Promise<{ authorization_url: string }> {
  const res = await fetch(`${BASE}/api/notion/connect`)
  if (!res.ok) {
    const err: { detail?: string } = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}

export async function disconnectNotion(): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE}/api/notion/connection`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function exportPaperToNotion(params: {
  paperId: string
  noteType?: 'summary' | 'qa' | 'full_reading_note'
  includeQaHistory?: boolean
  targetDatabaseId?: string | null
  targetPageId?: string | null
  paper?: Paper
  qaHistory?: Array<{ role: 'user' | 'assistant'; content: string }>
}): Promise<{ notion_page_id: string | null; created: boolean; updated: boolean; preview: string }> {
  const res = await fetch(`${BASE}/api/papers/export/notion`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      paper_id: params.paperId,
      note_type: params.noteType ?? 'summary',
      include_qa_history: params.includeQaHistory ?? false,
      target_database_id: params.targetDatabaseId ?? null,
      target_page_id: params.targetPageId ?? null,
      paper: params.paper ? paperToBackendCandidate(params.paper) : null,
      qa_history: params.qaHistory ?? [],
    }),
  })
  if (!res.ok) {
    const err: { detail?: string } = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json()
}
