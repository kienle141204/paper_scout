import type { Conference, Paper } from '../types/paper'
import type { ChatRequest, ChatResponse } from '../types/chat'

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

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
  citation_count?: number
  relevance_score?: number
  key_contributions?: string[]
  tags?: string[]
}

interface BackendSearchResponse {
  papers: BackendPaper[]
  total: number
  query: string
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
    citations: p.citation_count ?? null,
    relevance: Math.round((p.relevance_score ?? 0) * 100),
    keywords: p.tags ?? [],
    keyContributions: p.key_contributions,
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
  conferences: string[]
  yearFrom?: number
  yearTo?: number
  language?: string
  limit?: number
}

export interface ParsedQuery {
  keywords: string
  venues: string[]
  year_from: number | null
  year_to: number | null
  fallback: boolean
}

export async function parseQuery(query: string): Promise<ParsedQuery> {
  const res = await fetch(`${BASE}/api/parse-query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })
  if (!res.ok) {
    return { keywords: query, venues: [], year_from: null, year_to: null, fallback: true }
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

export async function searchPapers(
  params: SearchParams,
): Promise<{ papers: Paper[]; total: number; query: string }> {
  const res = await fetch(`${BASE}/api/papers/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query: params.query,
      conferences: params.conferences,
      year_from: params.yearFrom,
      year_to: params.yearTo,
      language: params.language ?? 'vi',
      limit: params.limit ?? 20,
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
  }
}
