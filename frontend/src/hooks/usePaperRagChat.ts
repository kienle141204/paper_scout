import { useState, useRef, useEffect, useCallback } from 'react'
import type { Paper } from '../types/paper'
import type { RagMessage } from '../types/rag'
import { ingestPaper, askPaper } from '../services/api'

export type IngestStatus = 'idle' | 'ingesting' | 'ready' | 'error'

/** Shared ingest+ask state machine for chatting with a paper via the RAG agent.
 * Used by both the floating PaperAgentBubble (DetailScreen) and the full-page
 * ReaderScreen chat panel — keeps the ingest/ask control flow in one place.
 */
export function usePaperRagChat(paper: Paper) {
  const [ingestStatus, setIngestStatus] = useState<IngestStatus>('idle')
  const [ingestSource, setIngestSource] = useState<'pdf' | 'abstract' | 'cached' | null>(null)
  const [messages, setMessages] = useState<RagMessage[]>([])
  const [input, setInput] = useState('')
  const [askLoading, setAskLoading] = useState(false)

  // Reset state when paper changes
  const lastPaperId = useRef(paper.id)
  useEffect(() => {
    if (lastPaperId.current === paper.id) return
    lastPaperId.current = paper.id
    setIngestStatus('idle')
    setIngestSource(null)
    setMessages([])
    setInput('')
    setAskLoading(false)
  }, [paper.id])

  const doIngest = useCallback(async () => {
    setIngestStatus('ingesting')
    try {
      const result = await ingestPaper({
        paper_id: paper.id,
        title: paper.titleEn,
        abstract: paper.abstractEn,
        authors: paper.authors,
        url: paper.url,
        pdf_url: paper.pdfUrl,
        conference: paper.conf,
        year: paper.year,
      })
      setIngestSource(result.source)
      setIngestStatus('ready')

      const welcome =
        result.source === 'pdf'
          ? `Tôi đã đọc xong **${result.chunk_count} đoạn** từ bài báo này. Hỏi tôi bất kỳ điều gì về phương pháp, kết quả, hay giới hạn của paper nhé!`
          : result.source === 'cached'
          ? `Tôi đã có nội dung bài báo này trong bộ nhớ. Hỏi tôi bất kỳ điều gì nhé!`
          : `Không tải được PDF — tôi sẽ trả lời dựa trên **abstract** của paper. Hỏi tôi nhé!`

      setMessages([{ role: 'assistant', content: welcome, citations: [] }])
    } catch (e) {
      setIngestStatus('error')
      setMessages([{
        role: 'assistant',
        content: e instanceof Error
          ? `Không thể khởi tạo: ${e.message}`
          : 'Không thể khởi tạo agent. Vui lòng kiểm tra Supabase và API key.',
        citations: [],
      }])
    }
  }, [paper])

  const handleSend = useCallback(async (text?: string) => {
    const q = (text ?? input).trim()
    if (!q || askLoading) return
    setInput('')

    const userMsg: RagMessage = { role: 'user', content: q, citations: [] }
    const placeholderMsg: RagMessage = { role: 'assistant', content: '', citations: [], loading: true }
    setMessages((prev) => [...prev, userMsg, placeholderMsg])
    setAskLoading(true)

    try {
      const history = messages
        .filter((m) => !m.loading)
        .map((m) => ({ role: m.role, content: m.content }))
        .slice(-10)

      const res = await askPaper({
        paper_id: paper.id,
        question: q,
        history,
        title: paper.titleEn,
        abstract: paper.abstractEn,
        authors: paper.authors,
        url: paper.url,
        pdf_url: paper.pdfUrl,
        conference: paper.conf,
        year: paper.year,
      })
      setMessages((prev) => [
        ...prev.slice(0, -1),
        {
          role: 'assistant',
          content: res.answer,
          citations: res.citations,
          chunks: res.chunks,
          confidence: res.confidence,
          coverage: res.coverage,
          plan: res.plan,
          verification: res.verification,
        },
      ])
    } catch (e) {
      setMessages((prev) => [
        ...prev.slice(0, -1),
        {
          role: 'assistant',
          content: e instanceof Error ? e.message : 'Xin lỗi, có lỗi xảy ra. Vui lòng thử lại.',
          citations: [],
        },
      ])
    } finally {
      setAskLoading(false)
    }
  }, [input, askLoading, messages, paper])

  return {
    ingestStatus,
    ingestSource,
    messages,
    input,
    setInput,
    askLoading,
    doIngest,
    handleSend,
  }
}
