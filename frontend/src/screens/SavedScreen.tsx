import { Icon, ConfTag, CiteCount, Authors } from '../components/atoms'
import type { Paper } from '../types/paper'

interface Props {
  savedPapers: Paper[]
  onOpen: (id: string) => void
  onToggleSave: (id: string) => void
  onGoSearch: () => void
}

export default function SavedScreen({ savedPapers, onOpen, onToggleSave, onGoSearch }: Props) {
  const confCount = new Set(savedPapers.map((p) => p.conf).filter(Boolean)).size

  return (
    <div className="fade-in flex-1">
      <div className="w-full mx-auto px-7" style={{ maxWidth: 880, paddingTop: 30, paddingBottom: 72 }}>

        <div className="flex items-end justify-between mb-7 flex-wrap gap-3">
          <div>
            <div className="eyebrow mb-2">Thư viện của bạn</div>
            <h1 style={{ fontSize: 29, fontWeight: 600, margin: 0, letterSpacing: '-0.02em' }}>
              Paper đã lưu
            </h1>
          </div>
          {savedPapers.length > 0 && (
            <span className="mono muted" style={{ fontSize: 13 }}>
              {savedPapers.length} paper · {confCount} hội nghị
            </span>
          )}
        </div>

        {savedPapers.length === 0 ? (
          <div className="card text-center" style={{ padding: '60px 40px' }}>
            <div
              className="grid place-items-center mx-auto mb-5"
              style={{
                width: 52, height: 52, borderRadius: 13,
                background: 'var(--surface-3)', color: 'var(--ink-3)',
              }}
            >
              <Icon name="bookmark" size={22} />
            </div>
            <h3 style={{ fontSize: 20, fontWeight: 600, margin: '0 0 8px', color: 'var(--ink)', letterSpacing: '-0.01em' }}>
              Chưa có paper nào được lưu
            </h3>
            <p className="muted mx-auto" style={{ fontSize: 14.5, margin: '0 auto 22px', maxWidth: 360, lineHeight: 1.55 }}>
              Bấm biểu tượng <Icon name="bookmark" size={13} style={{ verticalAlign: '-1px' }} /> trên mỗi kết
              quả để lưu lại đọc sau. Paper đã lưu sẽ xuất hiện ở đây.
            </p>
            <button className="btn btn-primary mx-auto" onClick={onGoSearch}>
              <Icon name="search" size={16} /> Bắt đầu tìm kiếm
            </button>
          </div>
        ) : (
          <div className="grid gap-3.5">
            {savedPapers.map((p) => (
              <article
                key={p.id}
                className="card flex gap-4 items-start"
                onClick={() => onOpen(p.id)}
                style={{ padding: '18px 20px', cursor: 'pointer', transition: 'border-color .14s' }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--border-strong)' }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    <ConfTag conf={p.conf} year={p.year} />
                    <CiteCount n={p.citations} />
                  </div>
                  <h3
                    className="serif"
                    style={{ fontSize: 19, lineHeight: 1.25, fontWeight: 500, margin: '0 0 4px', color: 'var(--ink)' }}
                  >
                    {p.titleEn}
                  </h3>
                  {p.titleVi && (
                    <div className="muted" style={{ fontSize: 13.5, marginBottom: 10 }}>{p.titleVi}</div>
                  )}
                  <Authors list={p.authors} max={3} />
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); onToggleSave(p.id) }}
                  title="Bỏ lưu"
                  className="btn btn-outline btn-sm flex-none"
                  style={{ width: 34, padding: 0 }}
                >
                  <Icon name="trash" size={15} />
                </button>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
