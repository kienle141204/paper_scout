// Types for the conversational chat feature

export type ChatRole = 'user' | 'assistant'

export interface ChatMessage {
  role: ChatRole
  content: string
}

export interface PaperSummary {
  paper_id: string
  title: string
  conference: string | null
  year: number | null
}

export interface ChatContext {
  keywords: string | null
  venues: string[]
  year_from: number | null
  year_to: number | null
  papers_shown: PaperSummary[]
}

export interface ChatSearchParams {
  keywords: string
  venues: string[]
  year_from: number | null
  year_to: number | null
  limit: number
}

export interface ChatFilterParams {
  exclude_keywords: string[]
  include_only_keywords: string[]
  year_from: number | null
  year_to: number | null
  venues: string[] | null
}

export type ChatAction = 'search' | 'clarify' | 'filter' | 'done'

export interface ChatRequest {
  messages: ChatMessage[]
  context: ChatContext
  session_id: string
}

export interface ChatResponse {
  reply: string
  action: ChatAction
  search_params?: ChatSearchParams
  filter_params?: ChatFilterParams
  follow_up_question?: string | null
}

// UI-layer extension: a message that may carry attached paper results
export interface ChatUIMessage extends ChatMessage {
  /** Paper results attached to this assistant message (after a search action) */
  papers?: import('./paper').Paper[]
  /** Whether this message is still loading */
  loading?: boolean
}
