export interface Conference {
  id: string
  name: string
  full: string
  url?: string
}

export interface Paper {
  id: string
  titleEn: string
  titleVi?: string
  abstractEn?: string
  abstractVi?: string
  authors: string[]
  year?: number
  conf?: string
  venue?: string
  url?: string
  citations: number | null
  relevance: number
  keywords: string[]
  keyContributions?: string[]
}

export interface Filters {
  confs: string[]
  years: [number, number]
  hasPdf: boolean
  minCite: number
  author: string
  exclude: string
  minRel: number
}

export type SortKey = 'relevance' | 'citations' | 'year'
export type Screen = 'home' | 'results' | 'detail' | 'saved' | 'chat'

export const CURRENT_YEAR = new Date().getFullYear()
export const MIN_YEAR = 2018

export const SAMPLE_QUERIES = [
  'mô hình khuếch tán tạo ảnh y tế độ phân giải cao',
  'tăng tốc sinh ảnh từ văn bản với ít bước khử nhiễu',
  'LLM cho ngôn ngữ ít tài nguyên',
  'phân vùng tổn thương với ít dữ liệu gán nhãn',
]

export const DEFAULT_FILTERS: Filters = {
  confs: [],
  years: [2022, CURRENT_YEAR],
  hasPdf: false,
  minCite: 0,
  author: '',
  exclude: '',
  minRel: 0,
}
