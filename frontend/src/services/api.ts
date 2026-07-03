import type { Conference, Paper } from '../types/paper'
import type { ChatRequest, ChatResponse } from '../types/chat'
import type { User } from '../contexts/AuthContext'
import type { IngestResult, AskResult } from '../types/rag'

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

// Routes a paper's PDF through our backend so <iframe> embedding works
// regardless of the source's X-Frame-Options/CORS policy (e.g. OpenReview
// blocks cross-origin framing; arXiv doesn't — proxying makes both uniform).
export function pdfProxyUrl(pdfUrl: string): string {
  return `${BASE}/api/papers/pdf/proxy?url=${encodeURIComponent(pdfUrl)}`
}

// ── Backend shapes ───────────────────────────────
interface BackendConference {
  name: string
  full_name: string
  areas: string[]
  url?: string
}

interface BackendAuthor {
  name: string
  author_id?: string
}

interface BackendPaper {
  paper_id: string
  title: string
  abstract?: string
  summary?: string
  title_vi?: string
  authors: BackendAuthor[]
  year?: number
  venue?: string
  conference?: string
  url?: string
  pdf_url?: string
  citation_count?: number
  relevance_score?: number
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
  synthesis?: string | null
  synthesis_citations?: SearchSynthesisCitation[]
}

// ── Mappers ──────────────────────────────────────
function mapPaper(p: BackendPaper): Paper {
  return {
    id: p.paper_id,
    titleEn: p.title,
    titleVi: p.title_vi,
    abstractEn: p.abstract,
    abstractVi: p.summary,
    authors: p.authors.map((a) => a.name),
    year: p.year,
    conf: p.conference,
    venue: p.venue,
    url: p.url,
    pdfUrl: p.pdf_url,
    citations: p.citation_count ?? null,
    relevance: Math.round((p.relevance_score ?? 0) * 100),
    keywords: p.tags ?? [],
    keyContributions: p.key_contributions,
  }
}

function mapAgentPaper(p: AgentPaper): Paper {
  return {
    id: p.id ?? p.doi ?? p.url ?? p.title,
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

// ── Auth API functions ───────────────────────────
export interface AuthResponse {
  token: string
  user: User
}

export async function authLogin(params: { email: string; password: string }): Promise<AuthResponse> {
  const res = await fetch(`${BASE}/auth/login`, {
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

export async function authRegister(params: { email: string; password: string; display_name?: string }): Promise<AuthResponse> {
  const res = await fetch(`${BASE}/auth/register`, {
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

export async function updateLanguagePref(token: string, lang: 'en' | 'vi'): Promise<void> {
  await fetch(`${BASE}/auth/me`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ language_pref: lang }),
  })
}

export async function searchPapers(
  params: SearchParams,
): Promise<{
  papers: Paper[]
  total: number
  query: string
  hasMore: boolean
  correctedQuery: string | null
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
    synthesis: data.synthesis ?? null,
    synthesisCitations: data.synthesis_citations ?? [],
  }
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
