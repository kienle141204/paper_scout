import { Icon, ConfTag, Relevance } from './atoms'
import type { Paper } from '../types/paper'

interface Props {
  paper: Paper
  saved: boolean
  onOpen: (paper: Paper) => void
  onToggleSave: (id: string) => void
}

export default function ChatPaperCard({ paper, saved, onOpen, onToggleSave }: Props) {
  return (
    <div
      className="card"
      style={{
        padding: '12px 14px',
        cursor: 'pointer',
        transition: 'border-color .12s',
      }}
      onClick={() => onOpen(paper)}
      onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--ink-3)' }}
      onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
    >
      {/* Top row: conf tag + year + relevance */}
      <div className="flex items-center gap-2 mb-1.5" style={{ flexWrap: 'wrap' }}>
        {paper.conf && <ConfTag conf={paper.conf} year={paper.year} />}
        {paper.relevance > 0 && <Relevance value={paper.relevance} />}
        <div className="flex-1" />
        <button
          className={`btn btn-sm ${saved ? 'btn-primary' : 'btn-ghost'}`}
          style={{ padding: '2px 8px', minHeight: 26 }}
          onClick={(e) => { e.stopPropagation(); onToggleSave(paper.id) }}
          title={saved ? 'Bỏ lưu' : 'Lưu paper'}
        >
          <Icon
            name="bookmark"
            size={13}
            style={{ fill: saved ? 'currentColor' : 'none' }}
          />
        </button>
      </div>

      {/* Title */}
      <div
        style={{
          fontWeight: 600,
          fontSize: 13.5,
          color: 'var(--ink)',
          lineHeight: 1.4,
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
          marginBottom: 4,
        }}
      >
        {paper.titleEn}
      </div>

      {/* Authors */}
      {paper.authors.length > 0 && (
        <div
          style={{
            fontSize: 12,
            color: 'var(--ink-3)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {paper.authors.slice(0, 3).join(', ')}
          {paper.authors.length > 3 && ` +${paper.authors.length - 3}`}
        </div>
      )}

      {/* "Xem chi tiết" link */}
      <div className="flex items-center gap-1 mt-2" style={{ fontSize: 12, color: 'var(--ink-3)' }}>
        <Icon name="ext" size={12} />
        <span>Xem chi tiết</span>
      </div>
    </div>
  )
}
