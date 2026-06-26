import { useEffect, useRef } from 'react'
import { Icon, ConfTag, SaveBtn } from '../components/atoms'
import RichText from '../components/RichText'
import { usePaperRagChat } from '../hooks/usePaperRagChat'
import { ReasoningBlock, VerificationBadge, AnswerMeta, MessageContent } from '../components/rag/MessageParts'
import type { Paper } from '../types/paper'
import { useLanguage } from '../contexts/LanguageContext'
import { useAuth } from '../contexts/AuthContext'

interface Props {
  paper: Paper
  saved: boolean
  onToggleSave: () => void
  onBack: () => void
  onNeedAuth: () => void
}

const SUGGESTED = [
  'Đóng góp chính của paper là gì?',
  'Phương pháp hoạt động như thế nào?',
  'Kết quả thực nghiệm ra sao?',
  'Hạn chế và hướng phát triển?',
]

export default function ReaderScreen({ paper, saved, onToggleSave, onBack, onNeedAuth }: Props) {
  const { t } = useLanguage()
  const { isLoggedIn } = useAuth()
  const dr = t.reader
  const handleToggleSave = () => {
    if (!isLoggedIn) { onNeedAuth(); return }
    onToggleSave()
  }
  const {
    ingestStatus, ingestSource, messages, input, setInput, askLoading, doIngest, handleSend,
  } = usePaperRagChat(paper)

  const messagesRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Start reading the paper as soon as the Reader screen opens.
  useEffect(() => {
    if (ingestStatus === 'idle') doIngest()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paper.id])

  useEffect(() => {
    if (messagesRef.current) messagesRef.current.scrollTop = messagesRef.current.scrollHeight
  }, [messages])

  useEffect(() => {
    if (ingestStatus === 'ready') setTimeout(() => inputRef.current?.focus(), 50)
  }, [ingestStatus])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="fade-in" style={{ flex: 1, display: 'flex', flexDirection: 'column', height: 'calc(100vh - 60px)', minHeight: 0, overflow: 'hidden' }}>
      {/* sub-header */}
      <div style={{ flex: 'none', height: 50, borderBottom: '1px solid var(--border)', background: 'var(--surface)', display: 'flex', alignItems: 'center', gap: 14, padding: '0 16px' }}>
        <button className="btn btn-ghost btn-sm" onClick={onBack} style={{ paddingLeft: 8, flex: 'none' }}>
          <Icon name="arrowL" size={15} /> {dr.back}
        </button>
        <div style={{ width: 1, height: 22, background: 'var(--border)', flex: 'none' }} />
        <ConfTag conf={paper.conf} year={paper.year} />
        <span className="serif" style={{ fontSize: 14.5, fontWeight: 500, color: 'var(--ink)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>
          {paper.titleEn}
        </span>
        <div style={{ flex: 1 }} />
        <div style={{ width: 120, flex: 'none' }}>
          <SaveBtn saved={saved} onClick={handleToggleSave} label />
        </div>
        {paper.pdfUrl && (
          <a href={paper.pdfUrl} target="_blank" rel="noopener noreferrer" className="btn btn-accent btn-sm" style={{ flex: 'none' }}>
            <Icon name="download" size={14} /> {dr.downloadPdf}
          </a>
        )}
      </div>

      {/* split */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'minmax(0, 1.32fr) minmax(380px, 1fr)', minHeight: 0 }}>
        {/* left: PDF */}
        <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0, minHeight: 0, borderRight: '1px solid var(--border)', background: 'var(--surface-3)' }}>
          {paper.pdfUrl ? (
            <>
              <div style={{ flex: 'none', height: 42, borderBottom: '1px solid var(--border)', background: 'var(--surface)', display: 'flex', alignItems: 'center', gap: 10, padding: '0 14px' }}>
                <Icon name="doc" size={14} style={{ color: 'var(--ink-3)' }} />
                <span className="mono" style={{ fontSize: 11.5, color: 'var(--ink-2)' }}>paper.pdf</span>
                <div style={{ flex: 1 }} />
                <a href={paper.pdfUrl} target="_blank" rel="noopener noreferrer" className="btn btn-ghost btn-sm" title={dr.viewSource}>
                  <Icon name="ext" size={14} />
                </a>
              </div>
              <iframe
                src={paper.pdfUrl}
                title={paper.titleEn}
                style={{ flex: 1, border: 0, background: 'white' }}
              />
            </>
          ) : (
            <div style={{ flex: 1, overflowY: 'auto', padding: '32px 28px' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 18, padding: '12px 14px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--r)' }}>
                <Icon name="doc" size={18} style={{ color: 'var(--ink-4)', flexShrink: 0, marginTop: 1 }} />
                <div>
                  <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--ink)', marginBottom: 3 }}>{dr.noPdfTitle}</div>
                  <div className="muted" style={{ fontSize: 12.5, lineHeight: 1.5 }}>{dr.noPdfDesc}</div>
                  {paper.url && (
                    <a href={paper.url} target="_blank" rel="noopener noreferrer" className="btn btn-outline btn-sm" style={{ marginTop: 10, fontSize: 12 }}>
                      <Icon name="ext" size={13} /> {dr.viewSource}
                    </a>
                  )}
                </div>
              </div>
              <h1 className="serif" style={{ fontSize: 19, lineHeight: 1.3, margin: '0 0 12px', color: 'var(--ink)' }}>{paper.titleEn}</h1>
              <div className="muted" style={{ fontSize: 12.5, marginBottom: 16 }}>{paper.authors.join(' · ')}</div>
              <RichText
                text={paper.abstractVi ?? paper.abstractEn ?? '—'}
                style={{ fontSize: 15, lineHeight: 1.75, color: 'var(--ink)' }}
              />
            </div>
          )}
        </div>

        {/* right: chat */}
        <div style={{ minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column', background: 'var(--surface)' }}>
          <div style={{ flex: 'none', padding: '14px 18px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 11 }}>
            <span style={{ width: 30, height: 30, borderRadius: 8, background: 'var(--accent-soft)', border: '1px solid var(--accent-border)', display: 'grid', placeItems: 'center', color: 'var(--accent)', flex: 'none' }}>
              <Icon name="spark" size={16} />
            </span>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>Hỏi đáp về paper</div>
              <div className="muted" style={{ fontSize: 11.5 }}>Trả lời dựa trên nội dung bài báo</div>
            </div>
            {ingestSource && (
              <span style={{
                fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 4, flexShrink: 0,
                background: ingestSource === 'pdf' ? 'var(--s1-bg)' : 'var(--s2-bg)',
                color: ingestSource === 'pdf' ? 'var(--s1-clr)' : 'var(--s2-clr)',
                border: `1px solid ${ingestSource === 'pdf' ? 'var(--s1-bdr)' : 'var(--s2-bdr)'}`,
              }}>
                {ingestSource === 'pdf' ? 'Full PDF' : ingestSource === 'cached' ? 'Cached' : 'Abstract'}
              </span>
            )}
          </div>

          <div ref={messagesRef} style={{ flex: 1, overflowY: 'auto', padding: '20px 18px', display: 'flex', flexDirection: 'column', gap: 16 }}>
            {ingestStatus === 'ingesting' && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, gap: 12, padding: '24px 0' }}>
                <div style={{ width: 40, height: 40, borderRadius: 12, background: 'var(--accent-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Icon name="loader" size={20} style={{ color: 'var(--accent)', animation: 'spin 1s linear infinite' }} />
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--ink)', marginBottom: 4 }}>Đang đọc bài báo…</div>
                  <div className="muted" style={{ fontSize: 12, lineHeight: 1.5 }}>
                    Tải PDF, phân tích nội dung và tạo vector index.<br />Lần đầu có thể mất 15–30 giây.
                  </div>
                </div>
              </div>
            )}

            {ingestStatus === 'error' && (
              <div style={{ margin: 'auto 0', padding: '12px 14px', background: 'oklch(0.97 0.015 40)', border: '1px solid oklch(0.85 0.06 40)', borderRadius: 8, fontSize: 12.5, color: 'oklch(0.5 0.1 40)' }}>
                <div style={{ marginBottom: 8 }}>Không thể khởi tạo. Kiểm tra cấu hình Supabase.</div>
                <button className="btn btn-sm btn-outline" onClick={doIngest}>Thử lại</button>
              </div>
            )}

            {ingestStatus === 'ready' && messages.length <= 1 && (
              <div style={{ display: 'grid', gap: 8 }}>
                {SUGGESTED.map((s) => (
                  <button
                    key={s}
                    onClick={() => handleSend(s)}
                    style={{
                      textAlign: 'left', padding: '11px 13px', borderRadius: 'var(--r)',
                      border: '1px solid var(--border-strong)', background: 'var(--surface)',
                      fontSize: 13.5, color: 'var(--ink)', display: 'flex', alignItems: 'center', gap: 10,
                    }}
                  >
                    <Icon name="spark" size={14} style={{ color: 'var(--accent)', flex: 'none' }} />
                    <span style={{ flex: 1 }}>{s}</span>
                    <Icon name="arrowR" size={14} style={{ color: 'var(--ink-4)', flex: 'none' }} />
                  </button>
                ))}
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} style={{ display: 'flex', flexDirection: msg.role === 'user' ? 'row-reverse' : 'row', gap: 8, alignItems: 'flex-start' }}>
                {msg.role === 'assistant' && (
                  <div style={{ width: 26, height: 26, borderRadius: 8, flexShrink: 0, background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 2 }}>
                    <Icon name="spark" size={13} stroke={1.8} style={{ color: '#fff' }} />
                  </div>
                )}
                <div style={{
                  maxWidth: '86%', padding: '9px 13px',
                  borderRadius: msg.role === 'user' ? '13px 13px 4px 13px' : '4px 13px 13px 13px',
                  background: msg.role === 'user' ? 'var(--ink)' : 'var(--surface-2)',
                  color: msg.role === 'user' ? 'var(--bg)' : 'var(--ink)',
                  fontSize: 13.5, lineHeight: 1.6,
                }}>
                  {msg.loading ? (
                    <div style={{ display: 'flex', gap: 4, alignItems: 'center', padding: '2px 0' }}>
                      {[0, 1, 2].map((j) => (
                        <span key={j} style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--ink-4)', animation: `dotPulse 1.1s infinite ${j * 0.16}s` }} />
                      ))}
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
          </div>

          <div style={{ flex: 'none', padding: '12px 14px 14px', borderTop: '1px solid var(--border)', background: 'var(--surface)' }}>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, border: '1px solid var(--border-strong)', borderRadius: 12, padding: '7px 8px 7px 13px', background: 'var(--surface)' }}>
              <textarea
                ref={inputRef}
                rows={1}
                value={input}
                placeholder={dr.askPlaceholder}
                disabled={ingestStatus !== 'ready' || askLoading}
                onChange={(e) => {
                  setInput(e.target.value)
                  e.target.style.height = 'auto'
                  e.target.style.height = Math.min(e.target.scrollHeight, 110) + 'px'
                }}
                onKeyDown={handleKeyDown}
                style={{ flex: 1, border: 0, outline: 'none', resize: 'none', background: 'transparent', fontSize: 13.5, lineHeight: 1.5, color: 'var(--ink)', maxHeight: 110, padding: '4px 0' }}
              />
              <button
                onClick={() => handleSend()}
                disabled={!input.trim() || ingestStatus !== 'ready' || askLoading}
                className="btn btn-accent btn-sm"
                style={{ width: 34, height: 34, padding: 0, borderRadius: 9, flex: 'none', opacity: !input.trim() || ingestStatus !== 'ready' || askLoading ? 0.4 : 1 }}
              >
                {askLoading ? <Icon name="loader" size={16} style={{ animation: 'spin 1s linear infinite' }} /> : <Icon name="arrowR" size={16} />}
              </button>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes dotPulse { 0%,60%,100% { opacity: .25; transform: translateY(0); } 30% { opacity: 1; transform: translateY(-3px); } }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}
