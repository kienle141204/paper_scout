import { useState, useEffect, useRef, useCallback } from 'react'
import { Icon } from '../components/atoms'
import ChatPaperCard from '../components/ChatPaperCard'
import { chatWithAgent, searchPapers } from '../services/api'
import { applyFilterParams } from '../utils/filterChat'
import type { Conference, Paper } from '../types/paper'
import type { ChatUIMessage, ChatContext, PaperSummary } from '../types/chat'

interface Props {
  conferences: Conference[]
  savedIds: string[]
  onOpen: (paper: Paper) => void
  onToggleSave: (id: string) => void
  onGoSearch: () => void
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1" style={{ padding: '10px 14px' }}>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: 'var(--ink-3)',
            display: 'inline-block',
            animation: `chatDot 1.2s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
    </div>
  )
}

function SearchingIndicator() {
  return (
    <div
      className="flex items-center gap-2"
      style={{ fontSize: 13, color: 'var(--ink-3)', padding: '4px 0' }}
    >
      <Icon name="loader" size={14} style={{ animation: 'spin 1s linear infinite' }} />
      Đang tìm kiếm paper…
    </div>
  )
}

export default function ChatScreen({ conferences: _conf, savedIds, onOpen, onToggleSave, onGoSearch }: Props) {
  const sessionId = useRef(crypto.randomUUID())
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const [messages, setMessages] = useState<ChatUIMessage[]>([
    {
      role: 'assistant',
      content: 'Xin chào! Tôi có thể giúp bạn tìm paper học thuật. Bạn muốn tìm về chủ đề gì?',
    },
  ])
  const [context, setContext] = useState<ChatContext>({
    keywords: null,
    venues: [],
    year_from: null,
    year_to: null,
    papers_shown: [],
  })
  const [papers, setPapers] = useState<Paper[]>([])
  const [inputValue, setInputValue] = useState('')
  const [agentLoading, setAgentLoading] = useState(false)
  const [searchLoading, setSearchLoading] = useState(false)
  const [filterWarning, setFilterWarning] = useState<string | null>(null)

  // Auto-scroll to bottom whenever messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, agentLoading, searchLoading])

  const addAssistantMessage = (content: string, attachedPapers?: Paper[]) => {
    setMessages((prev) => [
      ...prev,
      { role: 'assistant', content, papers: attachedPapers },
    ])
  }

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || agentLoading || searchLoading) return

      setInputValue('')
      setFilterWarning(null)

      // Append user message
      const userMsg: ChatUIMessage = { role: 'user', content: trimmed }
      const nextMessages = [...messages, userMsg]
      setMessages(nextMessages)
      setAgentLoading(true)

      // Build history for API (strip UI-only fields)
      const apiMessages = nextMessages.map((m) => ({ role: m.role, content: m.content }))

      const response = await chatWithAgent({
        messages: apiMessages,
        context,
        session_id: sessionId.current,
      })

      setAgentLoading(false)

      if (response.action === 'search' && response.search_params) {
        const sp = response.search_params

        // Update context immediately
        setContext((prev) => ({
          ...prev,
          keywords: sp.keywords,
          venues: sp.venues,
          year_from: sp.year_from,
          year_to: sp.year_to,
        }))

        // Show agent reply first (without papers yet)
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: response.reply },
        ])

        // Run the actual search
        setSearchLoading(true)
        try {
          const result = await searchPapers({
            query: sp.keywords,
            conferences: sp.venues,
            yearFrom: sp.year_from ?? undefined,
            yearTo: sp.year_to ?? undefined,
            limit: sp.limit,
          })

          const newPapers = result.papers
          setPapers(newPapers)

          // Build papers_shown summary for next context
          const shown: PaperSummary[] = newPapers.slice(0, 20).map((p) => ({
            paper_id: p.id,
            title: p.titleEn,
            conference: p.conf ?? null,
            year: p.year ?? null,
          }))
          setContext((prev) => ({ ...prev, papers_shown: shown }))

          const countMsg =
            newPapers.length === 0
              ? 'Tôi không tìm được paper nào phù hợp. Bạn muốn thử với từ khóa khác không?'
              : `Tìm được ${newPapers.length} paper. ${response.follow_up_question ?? ''}`

          setMessages((prev) => [
            ...prev,
            { role: 'assistant', content: countMsg, papers: newPapers.slice(0, 8) },
          ])
        } catch {
          addAssistantMessage('Không thể tìm kiếm paper lúc này. Vui lòng thử lại.')
        } finally {
          setSearchLoading(false)
        }
      } else if (response.action === 'filter' && response.filter_params) {
        const { papers: filtered, warning } = applyFilterParams(papers, response.filter_params)
        setPapers(filtered)

        // Update context
        const shown: PaperSummary[] = filtered.slice(0, 20).map((p) => ({
          paper_id: p.id,
          title: p.titleEn,
          conference: p.conf ?? null,
          year: p.year ?? null,
        }))
        setContext((prev) => ({ ...prev, papers_shown: shown }))

        if (warning) setFilterWarning(warning)

        const replyText = warning
          ? `${response.reply}\n\n${warning}`
          : `${response.reply} Còn lại ${filtered.length} paper.`

        addAssistantMessage(replyText, filtered.slice(0, 8))
      } else {
        // clarify or done
        addAssistantMessage(response.reply)
      }
    },
    [agentLoading, searchLoading, messages, context, papers],
  )

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(inputValue)
    }
  }

  const isLoading = agentLoading || searchLoading

  return (
    <>
      {/* Keyframe styles injected once */}
      <style>{`
        @keyframes chatDot {
          0%, 60%, 100% { transform: translateY(0); opacity: .4; }
          30% { transform: translateY(-5px); opacity: 1; }
        }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>

      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          maxWidth: 760,
          margin: '0 auto',
          width: '100%',
          padding: '0 16px',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center gap-3"
          style={{ padding: '18px 0 12px', borderBottom: '1px solid var(--border)' }}
        >
          <button className="btn btn-ghost btn-sm" onClick={onGoSearch}>
            <Icon name="arrowL" size={15} /> Tìm kiếm
          </button>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 13, color: 'var(--ink-3)', fontWeight: 500 }}>Chat với AI</span>
          <button
            className="btn btn-ghost btn-sm"
            title="Xóa hội thoại"
            onClick={() => {
              setMessages([{ role: 'assistant', content: 'Xin chào! Tôi có thể giúp bạn tìm paper học thuật. Bạn muốn tìm về chủ đề gì?' }])
              setContext({ keywords: null, venues: [], year_from: null, year_to: null, papers_shown: [] })
              setPapers([])
              setFilterWarning(null)
            }}
            style={{ color: 'var(--ink-3)' }}
          >
            <Icon name="close" size={14} /> Xóa
          </button>
        </div>

        {/* Messages area */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '20px 0',
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          {messages.map((msg, idx) => (
            <div key={idx}>
              {/* Bubble */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                <div
                  style={{
                    maxWidth: '80%',
                    padding: '10px 14px',
                    borderRadius: msg.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                    background: msg.role === 'user' ? 'var(--ink)' : 'var(--surface-2)',
                    color: msg.role === 'user' ? 'var(--bg)' : 'var(--ink)',
                    fontSize: 14,
                    lineHeight: 1.55,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    border: msg.role === 'assistant' ? '1px solid var(--border)' : 'none',
                  }}
                >
                  {msg.content}
                </div>
              </div>

              {/* Inline paper cards */}
              {msg.papers && msg.papers.length > 0 && (
                <div
                  style={{
                    marginTop: 10,
                    display: 'grid',
                    gap: 8,
                    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                  }}
                >
                  {msg.papers.map((p) => (
                    <ChatPaperCard
                      key={p.id}
                      paper={p}
                      saved={savedIds.includes(p.id)}
                      onOpen={onOpen}
                      onToggleSave={onToggleSave}
                    />
                  ))}
                </div>
              )}
            </div>
          ))}

          {/* Loading indicators */}
          {agentLoading && (
            <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
              <div
                style={{
                  background: 'var(--surface-2)',
                  border: '1px solid var(--border)',
                  borderRadius: '14px 14px 14px 4px',
                }}
              >
                <TypingIndicator />
              </div>
            </div>
          )}
          {searchLoading && (
            <div style={{ paddingLeft: 4 }}>
              <SearchingIndicator />
            </div>
          )}

          {/* Filter warning */}
          {filterWarning && (
            <div
              style={{
                fontSize: 12.5,
                color: 'oklch(0.55 0.1 40)',
                background: 'oklch(0.98 0.015 40)',
                border: '1px solid oklch(0.82 0.06 40)',
                borderRadius: 8,
                padding: '8px 12px',
              }}
            >
              {filterWarning}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input area */}
        <div
          className="card"
          style={{
            padding: 6,
            margin: '12px 0 20px',
            boxShadow: 'var(--shadow)',
            borderColor: 'var(--border-strong)',
          }}
        >
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Nhập yêu cầu… (Enter để gửi, Shift+Enter xuống dòng)"
            rows={2}
            disabled={isLoading}
            className="w-full resize-none outline-none"
            style={{
              border: 0,
              background: 'transparent',
              fontSize: 15,
              lineHeight: 1.5,
              color: 'var(--ink)',
              padding: '12px 14px 6px',
              opacity: isLoading ? 0.5 : 1,
            }}
          />
          <div
            className="flex items-center gap-2"
            style={{ padding: '6px 8px 8px', justifyContent: 'flex-end' }}
          >
            <span className="muted" style={{ fontSize: 12, marginRight: 'auto' }}>
              Enter để gửi · Shift+Enter xuống dòng
            </span>
            <button
              className="btn btn-accent"
              style={{ paddingInline: 18 }}
              disabled={isLoading || !inputValue.trim()}
              onClick={() => sendMessage(inputValue)}
            >
              {isLoading ? (
                <Icon name="loader" size={15} style={{ animation: 'spin 1s linear infinite' }} />
              ) : (
                <Icon name="arrowR" size={15} />
              )}
              Gửi
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
