export interface RagCitation {
  ref: number
  chunk_index: number
  section: string
  quote: string
  valid?: boolean
}

export interface RagChunk {
  chunk_index: number
  section: string
  text: string
}

export interface RagPlan {
  sub_questions: string[]
  queries_used: string[]
  sections_searched: string[]
}

export interface RagVerification {
  is_grounded: boolean
  hallucination_risk: 'none' | 'low' | 'medium' | 'high'
  issues: string[]
}

export interface RagMessage {
  role: 'user' | 'assistant'
  content: string
  citations: RagCitation[]
  chunks?: RagChunk[]
  confidence?: 'high' | 'medium' | 'low'
  coverage?: 'full' | 'partial' | 'insufficient'
  plan?: RagPlan
  verification?: RagVerification
  action?: 'suggest_search' | null
  suggested_query?: string | null
  loading?: boolean
}

export interface IngestResult {
  paper_id: string
  already_done: boolean
  chunk_count: number
  source: 'pdf' | 'abstract' | 'cached'
}

export interface AskResult {
  answer: string
  citations: RagCitation[]
  chunks: RagChunk[]
  confidence?: 'high' | 'medium' | 'low'
  coverage?: 'full' | 'partial' | 'insufficient'
  plan?: RagPlan
  verification?: RagVerification
  action?: 'suggest_search' | null
  suggested_query?: string | null
}
