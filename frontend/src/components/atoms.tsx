import type { SVGProps } from 'react'
import type { Paper } from '../types/paper'

// ── Icons ────────────────────────────────────────
const IC: Record<string, React.ReactElement> = {
  search:   <path d="M11 11l4 4M7.5 13a5.5 5.5 0 100-11 5.5 5.5 0 000 11z" />,
  arrowR:   <path d="M3.5 8h9M9 4.5L12.5 8 9 11.5" />,
  arrowL:   <path d="M12.5 8h-9M7 4.5L3.5 8 7 11.5" />,
  bookmark: <path d="M4 2.5h8v11l-4-2.6-4 2.6v-11z" />,
  download: <path d="M8 2.5v7.5M5 7l3 3 3-3M3.5 13h9" />,
  ext:      <path d="M6 3.5H3.5v9h9V10M9.5 3.5H13V7M13 3.5L7.5 9" />,
  filter:   <path d="M2.5 3.5h11M4.5 8h7M6.5 12.5h3" />,
  sort:     <path d="M4 3v10M4 13l-2-2M4 13l2-2M12 13V3M12 3l-2 2M12 3l2 2" />,
  cite:     <path d="M5.5 4.5C4 5 3 6.2 3 8c0 .9.7 1.6 1.6 1.6S6 8.9 6 8 5.3 6.4 4.4 6.4M11 4.5C9.5 5 8.5 6.2 8.5 8c0 .9.7 1.6 1.6 1.6s1.4-.7 1.4-1.6-.7-1.6-1.6-1.6" />,
  user:     <path d="M8 8a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM3.5 13c.6-2.2 2.3-3.3 4.5-3.3s3.9 1.1 4.5 3.3" />,
  close:    <path d="M4 4l8 8M12 4l-8 8" />,
  check:    <path d="M3 8.5l3.2 3L13 5" />,
  globe:    <path d="M8 14A6 6 0 108 2a6 6 0 000 12zM2 8h12M8 2c1.7 1.6 2.6 3.7 2.6 6S9.7 12.4 8 14M8 2C6.3 3.6 5.4 5.7 5.4 8S6.3 12.4 8 14" />,
  spark:    <path d="M8 2.5l1.3 3.4L12.7 7 9.3 8.1 8 11.5 6.7 8.1 3.3 7l3.4-1.1L8 2.5z" />,
  layers:   <path d="M8 2.5l5.5 3L8 8.5 2.5 5.5 8 2.5zM2.5 8.5L8 11.5l5.5-3M2.5 11L8 14l5.5-3" />,
  clock:    <path d="M8 14A6 6 0 108 2a6 6 0 000 12zM8 5v3.2l2 1.3" />,
  trash:    <path d="M3.5 4.5h9M6 4.5V3h4v1.5M5 4.5l.6 8.5h4.8l.6-8.5" />,
  loader:   <path d="M8 2v2M8 12v2M2 8h2M12 8h2M3.8 3.8l1.4 1.4M10.8 10.8l1.4 1.4M3.8 12.2l1.4-1.4M10.8 5.2l1.4-1.4" />,
  warning:  <path d="M8 3L14 13H2L8 3zM8 8v2.5M8 12h.01" />,
  chat:     <path d="M2.5 3h11a1 1 0 011 1v6a1 1 0 01-1 1H9l-3 2.5V11H3.5a1 1 0 01-1-1V4a1 1 0 011-1z" />,
  menu:     <path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11" />,
}

interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'stroke'> {
  name: string
  size?: number
  stroke?: number
}

export function Icon({ name, size = 16, stroke = 1.6, className, ...rest }: IconProps) {
  return (
    <svg
      viewBox="0 0 16 16"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
      {...rest}
    >
      {IC[name] ?? null}
    </svg>
  )
}

// ── Conference tag ───────────────────────────────
export function ConfTag({ conf, year, solid }: { conf?: string; year?: number; solid?: boolean }) {
  return (
    <span className={`conf-tag${solid ? ' solid' : ''}`}>
      {conf}
      {year != null && <span style={{ opacity: 0.65 }}>· {year}</span>}
    </span>
  )
}

// ── Relevance meter ──────────────────────────────
export function Relevance({ value, showLabel }: { value: number; showLabel?: boolean }) {
  return (
    <div className="flex items-center gap-2" title={`Độ liên quan ${value}%`}>
      {showLabel && (
        <span className="eyebrow" style={{ fontSize: 10.5, letterSpacing: '.1em' }}>
          liên quan
        </span>
      )}
      <div className="rel-bar">
        <div className="rel-fill" style={{ width: `${value}%` }} />
      </div>
      <span className="rel-num">{value}%</span>
    </div>
  )
}

// ── Citation count ───────────────────────────────
export function CiteCount({ n }: { n: number | null | undefined }) {
  if (!n) return null
  return (
    <span className="inline-flex items-center gap-1 mono muted" style={{ fontSize: 12.5 }}>
      <Icon name="cite" size={13} />
      {n.toLocaleString('vi-VN')}
    </span>
  )
}

// ── Bookmark button ──────────────────────────────
interface SaveBtnProps {
  saved: boolean
  onClick: () => void
  label?: boolean
  size?: 'sm' | 'lg'
}

export function SaveBtn({ saved, onClick, label, size = 'sm' }: SaveBtnProps) {
  return (
    <button
      className={`btn ${size === 'sm' ? 'btn-sm ' : ''}${saved ? 'btn-primary' : 'btn-outline'} w-full`}
      onClick={(e) => { e.stopPropagation(); onClick() }}
      title={saved ? 'Bỏ lưu' : 'Lưu paper'}
    >
      <Icon name="bookmark" size={size === 'sm' ? 14 : 16} style={{ fill: saved ? 'currentColor' : 'none' }} />
      {label && (saved ? 'Đã lưu' : 'Lưu')}
    </button>
  )
}

// ── Authors line ─────────────────────────────────
export function Authors({ list, max = 4 }: { list: string[]; max?: number }) {
  const shown = list.slice(0, max)
  const extra = list.length - shown.length
  return (
    <span style={{ color: 'var(--ink-2)', fontSize: 13.5 }}>
      {shown.join(', ')}
      {extra > 0 && <span className="muted"> +{extra} tác giả</span>}
    </span>
  )
}

// ── Result card skeleton ─────────────────────────
export function CardSkeleton() {
  return (
    <div className="card" style={{ padding: '20px 22px' }}>
      <div className="flex items-center gap-3 mb-3">
        <div className="skeleton" style={{ width: 60, height: 20 }} />
        <div className="skeleton" style={{ width: 40, height: 20 }} />
        <div className="ml-auto skeleton" style={{ width: 80, height: 16 }} />
      </div>
      <div className="skeleton mb-2" style={{ height: 22, width: '75%' }} />
      <div className="skeleton mb-3" style={{ height: 18, width: '55%' }} />
      <div className="skeleton mb-3" style={{ height: 16, width: '45%' }} />
      <div className="flex gap-2">
        {[60, 80, 70].map((w, i) => (
          <div key={i} className="skeleton" style={{ width: w, height: 24 }} />
        ))}
      </div>
    </div>
  )
}

// ── Error banner ─────────────────────────────────
export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      className="card flex items-start gap-3"
      style={{ padding: '16px 18px', borderColor: 'oklch(0.75 0.08 30)', background: 'oklch(0.98 0.012 30)' }}
    >
      <Icon name="warning" size={18} style={{ color: 'oklch(0.6 0.1 30)', flexShrink: 0, marginTop: 1 }} />
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4, color: 'var(--ink)' }}>
          Không thể kết nối backend
        </div>
        <div style={{ fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.5 }}>{message}</div>
      </div>
      {onRetry && (
        <button className="btn btn-outline btn-sm" onClick={onRetry}>
          Thử lại
        </button>
      )}
    </div>
  )
}

// Re-export Paper type for convenience
export type { Paper }
