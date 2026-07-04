import { useState } from 'react'
import type { RagCitation, RagPlan, RagVerification } from '../../types/rag'

// ── Citation inline renderer ─────────────────────────────────────────────────

export function CitationChip({
  refNum,
  active,
  onClick,
}: { refNum: number; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      title={`Trích dẫn [${refNum}]`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 17, height: 17,
        fontSize: 10, fontWeight: 700,
        background: active ? 'var(--accent)' : 'var(--accent-soft)',
        border: `1px solid ${active ? 'var(--accent)' : 'var(--accent-border)'}`,
        borderRadius: 4,
        color: active ? '#fff' : 'var(--accent)',
        cursor: 'pointer',
        margin: '0 1px',
        verticalAlign: 'super',
        lineHeight: 1,
        flexShrink: 0,
      }}
    >
      {refNum}
    </button>
  )
}

// ── Confidence + coverage badges ─────────────────────────────────────────────

export const CONFIDENCE_STYLE = {
  high:   { bg: 'var(--s1-bg)',   border: 'var(--s1-bdr)',   color: 'var(--s1-clr)',  label: 'Cao' },
  medium: { bg: 'var(--s2-bg)',   border: 'var(--s2-bdr)',   color: 'var(--s2-clr)',  label: 'Trung bình' },
  low:    { bg: 'oklch(0.97 0.015 40)', border: 'oklch(0.85 0.06 40)', color: 'oklch(0.5 0.1 40)', label: 'Thấp' },
}
export const COVERAGE_STYLE = {
  full:         { label: 'Đầy đủ',     color: 'var(--s1-clr)' },
  partial:      { label: 'Một phần',   color: 'var(--s2-clr)' },
  insufficient: { label: 'Thiếu',      color: 'oklch(0.5 0.1 40)' },
}

export function ReasoningBlock({ plan }: { plan: RagPlan }) {
  const [open, setOpen] = useState(false)
  // Plan shape varies by lane (skill/fast/deliberate) — arrays may be absent.
  const subQuestions = plan?.sub_questions ?? []
  const sectionsSearched = plan?.sections_searched ?? []
  if (!subQuestions.length && !sectionsSearched.length) return null
  return (
    <div style={{ marginBottom: 8 }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: 5,
          background: 'none', border: 'none', padding: 0,
          cursor: 'pointer', fontSize: 11, color: 'var(--ink-3)', fontWeight: 600,
          letterSpacing: '.03em',
        }}
      >
        <span style={{ fontSize: 9 }}>{open ? '▼' : '▶'}</span>
        Phân tích câu hỏi
        {subQuestions.length > 0 && (
          <span style={{ fontWeight: 400, marginLeft: 4 }}>
            · {subQuestions.length} khía cạnh
          </span>
        )}
      </button>
      {open && (
        <div
          style={{
            marginTop: 6,
            padding: '8px 10px',
            background: 'var(--accent-soft)',
            border: '1px solid var(--accent-border)',
            borderRadius: 7,
            fontSize: 11.5,
          }}
        >
          {subQuestions.length > 0 && (
            <>
              <div style={{ fontWeight: 700, color: 'var(--ink-2)', marginBottom: 4, fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '.05em' }}>Khía cạnh</div>
              <ul style={{ margin: '0 0 6px', paddingLeft: 16 }}>
                {subQuestions.map((q, i) => (
                  <li key={i} style={{ color: 'var(--ink-2)', lineHeight: 1.6 }}>{q}</li>
                ))}
              </ul>
            </>
          )}
          {sectionsSearched.length > 0 && (
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '.05em' }}>Tìm trong:</span>
              {sectionsSearched.map((s) => (
                <span key={s} style={{ fontSize: 10.5, padding: '1px 6px', borderRadius: 4, background: 'var(--accent)', color: '#fff' }}>{s}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function VerificationBadge({ v }: { v: RagVerification }) {
  if (v.hallucination_risk === 'none' || v.hallucination_risk === 'low') return null
  const isHigh = v.hallucination_risk === 'high'
  return (
    <div
      style={{
        marginTop: 8,
        padding: '7px 10px',
        background: isHigh ? 'oklch(0.97 0.02 40)' : 'oklch(0.98 0.02 85)',
        border: `1px solid ${isHigh ? 'oklch(0.85 0.07 40)' : 'oklch(0.88 0.07 85)'}`,
        borderRadius: 6,
        fontSize: 11.5,
        color: isHigh ? 'oklch(0.45 0.12 40)' : 'oklch(0.5 0.1 85)',
        display: 'flex', gap: 6, alignItems: 'flex-start',
      }}
    >
      <span style={{ fontSize: 13 }}>{isHigh ? '⚠️' : '💡'}</span>
      <div>
        <strong style={{ fontSize: 11 }}>Rủi ro hallucination: {v.hallucination_risk}</strong>
        {(v.issues?.length ?? 0) > 0 && (
          <ul style={{ margin: '3px 0 0', paddingLeft: 14 }}>
            {v.issues!.map((issue, i) => <li key={i}>{issue}</li>)}
          </ul>
        )}
      </div>
    </div>
  )
}

export function AnswerMeta({
  confidence,
  coverage,
}: {
  confidence?: 'high' | 'medium' | 'low'
  coverage?: 'full' | 'partial' | 'insufficient'
}) {
  if (!confidence && !coverage) return null
  const cs = confidence ? CONFIDENCE_STYLE[confidence] : null
  const cv = coverage ? COVERAGE_STYLE[coverage] : null
  return (
    <div style={{ display: 'flex', gap: 6, marginTop: 7, flexWrap: 'wrap' }}>
      {cs && (
        <span style={{
          fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4,
          background: cs.bg, border: `1px solid ${cs.border}`, color: cs.color,
        }}>
          Độ tin cậy: {cs.label}
        </span>
      )}
      {cv && (
        <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: 'var(--surface-3, #f0f0ee)', color: cv.color }}>
          Phủ: {cv.label}
        </span>
      )}
    </div>
  )
}

export function MessageContent({
  content,
  citations = [],
}: { content: string; citations?: RagCitation[] }) {
  const [activeCite, setActiveCite] = useState<number | null>(null)

  const parts = (content ?? '').split(/(\[\d+\])/g)
  const activeCitation = citations.find((c) => c.ref === activeCite)

  return (
    <div>
      <p style={{ margin: 0, lineHeight: 1.65, whiteSpace: 'pre-wrap' }}>
        {parts.map((part, i) => {
          const m = part.match(/^\[(\d+)\]$/)
          if (m) {
            const n = parseInt(m[1])
            const hasCite = citations.some((c) => c.ref === n)
            if (hasCite) {
              return (
                <CitationChip
                  key={i}
                  refNum={n}
                  active={activeCite === n}
                  onClick={() => setActiveCite(activeCite === n ? null : n)}
                />
              )
            }
          }
          return <span key={i}>{part}</span>
        })}
      </p>

      {activeCitation && (
        <div
          style={{
            marginTop: 8,
            padding: '8px 11px',
            background: 'var(--accent-soft)',
            border: '1px solid var(--accent-border)',
            borderRadius: 6,
            fontSize: 11.5,
            lineHeight: 1.55,
            color: 'var(--ink-2)',
          }}
        >
          <span
            className="mono"
            style={{ fontSize: 10, fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '.05em' }}
          >
            [{activeCitation.ref}] {activeCitation.section}
            {activeCitation.page != null ? ` · tr.${activeCitation.page + 1}` : ''}
          </span>
          <p style={{ margin: '4px 0 0', fontStyle: 'italic' }}>
            "{activeCitation.quote}"
          </p>
        </div>
      )}
    </div>
  )
}
