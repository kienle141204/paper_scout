import { useState, useRef, useEffect, useCallback } from 'react'
import type { Paper } from '../types/paper'
import { usePaperRagChat } from '../hooks/usePaperRagChat'
import { Icon } from './atoms'
import { ReasoningBlock, VerificationBadge, AnswerMeta, MessageContent } from './rag/MessageParts'

interface Props {
  paper: Paper
  onSizeChange?: (isFull: boolean) => void
}

type PanelSize = 'closed' | 'mini' | 'full'

// ── Main component ───────────────────────────────────────────────────────────

export default function PaperAgentBubble({ paper, onSizeChange }: Props) {
  const [size, setSize] = useState<PanelSize>('closed')
  const {
    ingestStatus, ingestSource, messages, input, setInput, askLoading, doIngest, handleSend,
  } = usePaperRagChat(paper)

  const messagesRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Notify parent when full-panel state changes
  useEffect(() => {
    onSizeChange?.(size === 'full')
  }, [size, onSizeChange])

  // Collapse panel when paper changes
  useEffect(() => {
    setSize('closed')
  }, [paper.id])

  // Auto-scroll messages
  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    }
  }, [messages])

  // Focus input when ready
  useEffect(() => {
    if (size !== 'closed' && ingestStatus === 'ready') {
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [size, ingestStatus])

  const handleOpen = useCallback(() => {
    setSize('mini')
    if (ingestStatus === 'idle') doIngest()
  }, [ingestStatus, doIngest])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // ── Shared styles ────────────────────────────────────────────────────────

  const BUBBLE_SIZE = 52

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <>
      {/* ── Floating bubble button ─────────────────────── */}
      {size === 'closed' && (
        <button
          onClick={handleOpen}
          title="Hỏi AI về bài báo này"
          style={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            zIndex: 100,
            width: BUBBLE_SIZE,
            height: BUBBLE_SIZE,
            borderRadius: '50%',
            background: 'var(--accent)',
            border: 'none',
            color: '#fff',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 16px rgba(37,99,235,0.40)',
            transition: 'transform 0.15s, box-shadow 0.15s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'scale(1.08)'
            e.currentTarget.style.boxShadow = '0 6px 20px rgba(37,99,235,0.55)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'scale(1)'
            e.currentTarget.style.boxShadow = '0 4px 16px rgba(37,99,235,0.40)'
          }}
        >
          <Icon name="chat" size={22} stroke={1.8} style={{ color: '#fff' }} />
        </button>
      )}

      {/* ── Expanded panel ─────────────────────────────── */}
      {size !== 'closed' && (
        <>
          <div
            style={
              size === 'full'
                ? {
                    // Right-side panel: 40% of viewport width, full height
                    position: 'fixed',
                    top: 0,
                    right: 0,
                    bottom: 0,
                    width: '40vw',
                    minWidth: 360,
                    zIndex: 99,
                    display: 'flex',
                    flexDirection: 'column',
                    background: 'var(--surface)',
                    borderLeft: '1px solid var(--border)',
                    borderRadius: 0,
                    boxShadow: '-6px 0 32px rgba(0,0,0,0.13)',
                    overflow: 'hidden',
                  }
                : {
                    // Mini floating panel above bubble
                    position: 'fixed',
                    right: 24,
                    bottom: BUBBLE_SIZE + 16 + 24,
                    width: 370,
                    height: 520,
                    zIndex: 99,
                    display: 'flex',
                    flexDirection: 'column',
                    background: 'var(--surface)',
                    border: '1px solid var(--border)',
                    borderRadius: 14,
                    boxShadow: '0 8px 40px rgba(0,0,0,0.18)',
                    overflow: 'hidden',
                  }
            }
          >
            {/* Header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 9,
                padding: '11px 14px',
                borderBottom: '1px solid var(--border)',
                background: 'var(--surface)',
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  width: 28, height: 28, borderRadius: 8,
                  background: 'var(--accent)', flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}
              >
                <Icon name="spark" size={15} stroke={1.8} style={{ color: '#fff' }} />
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--ink)', lineHeight: 1.2 }}>
                  Paper AI
                </div>
                <div
                  className="muted"
                  style={{
                    fontSize: 11, lineHeight: 1.3,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}
                >
                  {paper.titleEn.slice(0, 55)}{paper.titleEn.length > 55 ? '…' : ''}
                </div>
              </div>

              {/* Source badge */}
              {ingestSource && (
                <span
                  style={{
                    fontSize: 10, fontWeight: 600, padding: '2px 7px',
                    borderRadius: 4, flexShrink: 0,
                    background: ingestSource === 'pdf' ? 'var(--s1-bg)' : 'var(--s2-bg)',
                    color: ingestSource === 'pdf' ? 'var(--s1-clr)' : 'var(--s2-clr)',
                    border: `1px solid ${ingestSource === 'pdf' ? 'var(--s1-bdr)' : 'var(--s2-bdr)'}`,
                  }}
                >
                  {ingestSource === 'pdf' ? 'Full PDF' : ingestSource === 'cached' ? 'Cached' : 'Abstract'}
                </span>
              )}

              {/* Controls */}
              <div style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
                <button
                  onClick={() => setSize(size === 'full' ? 'mini' : 'full')}
                  title={size === 'full' ? 'Thu nhỏ' : 'Phóng to'}
                  style={{
                    width: 26, height: 26, borderRadius: 6,
                    border: 0, background: 'transparent', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'var(--ink-3)',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--surface-3)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                >
                  <Icon name={size === 'full' ? 'arrowL' : 'ext'} size={14} />
                </button>
                <button
                  onClick={() => setSize('closed')}
                  title="Đóng"
                  style={{
                    width: 26, height: 26, borderRadius: 6,
                    border: 0, background: 'transparent', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'var(--ink-3)',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--surface-3)' }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
                >
                  <Icon name="close" size={14} />
                </button>
              </div>
            </div>

            {/* Messages */}
            <div
              ref={messagesRef}
              style={{
                flex: 1,
                overflowY: 'auto',
                padding: '14px 14px 6px',
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
              }}
            >
              {/* Ingesting state */}
              {ingestStatus === 'ingesting' && (
                <div
                  style={{
                    display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center',
                    flex: 1, gap: 12, padding: '24px 0',
                  }}
                >
                  <div
                    style={{
                      width: 40, height: 40, borderRadius: 12,
                      background: 'var(--accent-soft)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                  >
                    <Icon
                      name="loader"
                      size={20}
                      style={{ color: 'var(--accent)', animation: 'spin 1s linear infinite' }}
                    />
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--ink)', marginBottom: 4 }}>
                      Đang đọc bài báo…
                    </div>
                    <div className="muted" style={{ fontSize: 12, lineHeight: 1.5 }}>
                      Tải PDF, phân tích nội dung và tạo vector index.
                      <br />Lần đầu có thể mất 15–30 giây.
                    </div>
                  </div>
                </div>
              )}

              {/* Messages list */}
              {messages.map((msg, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                    gap: 8,
                    alignItems: 'flex-start',
                  }}
                >
                  {/* Avatar */}
                  {msg.role === 'assistant' && (
                    <div
                      style={{
                        width: 26, height: 26, borderRadius: 8, flexShrink: 0,
                        background: 'var(--accent)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        marginTop: 2,
                      }}
                    >
                      <Icon name="spark" size={13} stroke={1.8} style={{ color: '#fff' }} />
                    </div>
                  )}

                  <div
                    style={{
                      maxWidth: '82%',
                      padding: '9px 12px',
                      borderRadius: msg.role === 'user'
                        ? '12px 4px 12px 12px'
                        : '4px 12px 12px 12px',
                      background: msg.role === 'user' ? 'var(--accent)' : 'var(--surface-2, #f5f5f4)',
                      color: msg.role === 'user' ? '#fff' : 'var(--ink)',
                      fontSize: 13.5,
                      lineHeight: 1.6,
                    }}
                  >
                    {msg.loading ? (
                      <div>
                        <div style={{ display: 'flex', gap: 4, alignItems: 'center', padding: '2px 0' }}>
                          {[0, 1, 2].map((j) => (
                            <span
                              key={j}
                              style={{
                                width: 6, height: 6, borderRadius: '50%',
                                background: 'var(--ink-3)',
                                animation: `bounce 1.2s ease-in-out ${j * 0.2}s infinite`,
                              }}
                            />
                          ))}
                        </div>
                        <div className="muted" style={{ fontSize: 10.5, marginTop: 5 }}>
                          Phân tích → Tìm kiếm → Tổng hợp → Kiểm tra…
                        </div>
                      </div>
                    ) : (
                      <div>
                        {msg.plan && <ReasoningBlock plan={msg.plan} />}
                        <MessageContent content={msg.content} citations={msg.citations} />
                        <AnswerMeta confidence={msg.confidence} coverage={msg.coverage} />
                        {msg.verification && <VerificationBadge v={msg.verification} />}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              <div style={{ height: 4 }} />
            </div>

            {/* Input area */}
            <div
              style={{
                padding: '10px 12px',
                borderTop: '1px solid var(--border)',
                background: 'var(--surface)',
                flexShrink: 0,
              }}
            >
              {ingestStatus === 'error' && (
                <div
                  style={{
                    marginBottom: 8,
                    padding: '7px 10px',
                    background: 'oklch(0.97 0.015 40)',
                    border: '1px solid oklch(0.85 0.06 40)',
                    borderRadius: 7,
                    fontSize: 12,
                    color: 'oklch(0.5 0.1 40)',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
                  }}
                >
                  <span>Không thể khởi tạo. Kiểm tra cấu hình Supabase.</span>
                  <button
                    className="btn btn-sm btn-outline"
                    style={{ fontSize: 11, padding: '3px 8px' }}
                    onClick={doIngest}
                  >
                    Thử lại
                  </button>
                </div>
              )}

              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    ingestStatus === 'ingesting' ? 'Đang khởi tạo…'
                    : ingestStatus === 'error' ? 'Cần khắc phục lỗi trước…'
                    : 'Hỏi về phương pháp, kết quả… (Enter để gửi)'
                  }
                  disabled={ingestStatus !== 'ready' || askLoading}
                  rows={1}
                  style={{
                    flex: 1,
                    resize: 'none',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    padding: '8px 11px',
                    fontSize: 13,
                    lineHeight: 1.5,
                    fontFamily: 'inherit',
                    background: ingestStatus !== 'ready' ? 'var(--surface-3, #f5f5f4)' : 'var(--surface)',
                    color: 'var(--ink)',
                    outline: 'none',
                    maxHeight: 100,
                    overflowY: 'auto',
                    transition: 'border-color 0.12s',
                  }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--accent)' }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
                  onInput={(e) => {
                    const el = e.currentTarget
                    el.style.height = 'auto'
                    el.style.height = `${Math.min(el.scrollHeight, 100)}px`
                  }}
                />
                <button
                  onClick={() => handleSend()}
                  disabled={!input.trim() || ingestStatus !== 'ready' || askLoading}
                  style={{
                    width: 36, height: 36, borderRadius: 8, flexShrink: 0,
                    border: 0,
                    background: (!input.trim() || ingestStatus !== 'ready' || askLoading)
                      ? 'var(--surface-3, #e5e5e2)'
                      : 'var(--accent)',
                    color: (!input.trim() || ingestStatus !== 'ready' || askLoading)
                      ? 'var(--ink-4, #aaa)'
                      : '#fff',
                    cursor: (!input.trim() || ingestStatus !== 'ready' || askLoading)
                      ? 'not-allowed' : 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: 'background 0.12s',
                  }}
                >
                  {askLoading
                    ? <Icon name="loader" size={15} style={{ animation: 'spin 1s linear infinite' }} />
                    : <Icon name="arrowR" size={15} stroke={2} />
                  }
                </button>
              </div>

              <div className="muted" style={{ fontSize: 10.5, marginTop: 5, textAlign: 'center' }}>
                Trả lời dựa trên nội dung paper · Nhấn citation [1] để xem trích dẫn
              </div>
            </div>
          </div>

          {/* Re-open bubble when panel is mini (show below panel) */}
          {size === 'mini' && (
            <button
              onClick={() => setSize('closed')}
              title="Ẩn"
              style={{
                position: 'fixed',
                bottom: 24,
                right: 24,
                zIndex: 100,
                width: BUBBLE_SIZE,
                height: BUBBLE_SIZE,
                borderRadius: '50%',
                background: 'var(--accent)',
                border: 'none',
                color: '#fff',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 4px 16px rgba(37,99,235,0.40)',
              }}
            >
              <Icon name="close" size={18} stroke={2} style={{ color: '#fff' }} />
            </button>
          )}
        </>
      )}

      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: scale(0); opacity: 0.4; }
          40% { transform: scale(1); opacity: 1; }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </>
  )
}
