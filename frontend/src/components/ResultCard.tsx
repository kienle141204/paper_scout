import { ConfTag, CiteCount, Relevance, Authors, Icon } from './atoms'
import type { Paper } from '../types/paper'

interface Props {
  paper: Paper
  saved: boolean
  rank?: number
  onOpen: () => void
  onToggleSave: () => void
}

export default function ResultCard({ paper, saved, rank, onOpen, onToggleSave }: Props) {
  return (
    <article
      className="card fade-in"
      onClick={onOpen}
      style={{ padding: '20px 22px', cursor: 'pointer', position: 'relative', transition: 'border-color .14s, box-shadow .14s' }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = 'var(--border-strong)'
        e.currentTarget.style.boxShadow = 'var(--shadow)'
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--border)'
        e.currentTarget.style.boxShadow = 'var(--shadow-sm)'
      }}
    >
      {/* Meta row */}
      <div className="flex items-center gap-3 mb-3">
        {rank != null && (
          <span className="mono muted" style={{ fontSize: 12, width: 22 }}>
            {String(rank).padStart(2, '0')}
          </span>
        )}
        <ConfTag conf={paper.conf} year={paper.year} />
        <CiteCount n={paper.citations} />
        <div className="flex-1" />
        <Relevance value={paper.relevance} showLabel />
      </div>

      {/* English title */}
      <h3
        className="serif"
        style={{
          fontSize: 21, lineHeight: 1.25, fontWeight: 500,
          margin: '0 0 5px', color: 'var(--ink)',
          letterSpacing: '-0.01em', paddingRight: 36,
        }}
      >
        {paper.titleEn}
      </h3>

      {/* Vietnamese title */}
      {paper.titleVi && (
        <div style={{ fontSize: 14.5, color: 'var(--ink-2)', marginBottom: 12, lineHeight: 1.4 }}>
          {paper.titleVi}
        </div>
      )}

      {/* Authors */}
      <div className="mb-3">
        <Authors list={paper.authors} />
      </div>

      {/* Keywords */}
      <div className="flex items-center gap-2 flex-wrap">
        {paper.keywords.slice(0, 4).map((k) => (
          <span key={k} className="kw">{k}</span>
        ))}
      </div>

      {/* Floating save button */}
      <button
        onClick={(e) => { e.stopPropagation(); onToggleSave() }}
        title={saved ? 'Bỏ lưu' : 'Lưu paper'}
        style={{
          position: 'absolute', top: 16, right: 16,
          width: 32, height: 32, borderRadius: 7,
          border: `1px solid ${saved ? 'var(--ink)' : 'var(--border)'}`,
          background: saved ? 'var(--ink)' : 'var(--surface)',
          color: saved ? 'var(--bg)' : 'var(--ink-3)',
          display: 'grid', placeItems: 'center', transition: 'all .14s',
        }}
      >
        <Icon name="bookmark" size={15} style={{ fill: saved ? 'currentColor' : 'none' }} />
      </button>
    </article>
  )
}
