import { Icon } from './atoms'
import type { Conference, Filters } from '../types/paper'
import { MIN_YEAR, CURRENT_YEAR } from '../types/paper'

interface Props {
  filters: Filters
  setFilters: (f: Filters) => void
  conferences: Conference[]
  paperCounts: Record<string, number>
  onOpenAdvanced: () => void
  activeAdvCount: number
}

export default function FilterSidebar({
  filters, setFilters, conferences, paperCounts, onOpenAdvanced, activeAdvCount,
}: Props) {
  const set = (patch: Partial<Filters>) => setFilters({ ...filters, ...patch })

  const toggleConf = (id: string) =>
    set({ confs: filters.confs.includes(id) ? filters.confs.filter((x) => x !== id) : [...filters.confs, id] })

  const reset = () => setFilters({ ...filters, confs: [], years: [MIN_YEAR, CURRENT_YEAR], hasPdf: false, minCite: 0 })

  return (
    <aside style={{ width: 248, flexShrink: 0 }}>
      <div className="sticky" style={{ top: 76 }}>
        {/* Header */}
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2" style={{ fontWeight: 600, fontSize: 14, color: 'var(--ink)' }}>
            <Icon name="filter" size={15} /> Bộ lọc
          </div>
          <button className="btn btn-ghost btn-sm" style={{ height: 28, paddingInline: 8 }} onClick={reset}>
            Đặt lại
          </button>
        </div>

        {/* Conferences */}
        <div style={{ padding: '16px 0', borderTop: '1px solid var(--border)' }}>
          <div className="eyebrow mb-3">Hội nghị</div>
          <div className="grid gap-2">
            {conferences.map((c) => (
              <label
                key={c.id}
                className="flex items-center gap-2 cursor-pointer"
                style={{ fontSize: 13.5, color: 'var(--ink-2)' }}
              >
                <input
                  type="checkbox"
                  checked={filters.confs.includes(c.id)}
                  onChange={() => toggleConf(c.id)}
                />
                <span style={{ fontWeight: 500, color: 'var(--ink)', flex: 1 }}>{c.name}</span>
                <span className="mono muted" style={{ fontSize: 11 }}>
                  {paperCounts[c.id] ?? 0}
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Year range */}
        <div style={{ padding: '16px 0', borderTop: '1px solid var(--border)' }}>
          <div className="eyebrow mb-3">Năm · {filters.years[0]}–{filters.years[1]}</div>
          <input
            type="range" min={MIN_YEAR} max={CURRENT_YEAR}
            value={filters.years[0]}
            onChange={(e) => set({ years: [Math.min(+e.target.value, filters.years[1]), filters.years[1]] })}
            className="w-full" style={{ accentColor: 'var(--ink)' }}
          />
          <input
            type="range" min={MIN_YEAR} max={CURRENT_YEAR}
            value={filters.years[1]}
            onChange={(e) => set({ years: [filters.years[0], Math.max(+e.target.value, filters.years[0])] })}
            className="w-full mt-1.5" style={{ accentColor: 'var(--ink)' }}
          />
        </div>

        {/* Quick filters */}
        <div style={{ padding: '16px 0', borderTop: '1px solid var(--border)' }}>
          <div className="eyebrow mb-3">Nhanh</div>
          <label className="flex items-center gap-2 cursor-pointer mb-2.5" style={{ fontSize: 13.5 }}>
            <input type="checkbox" checked={filters.hasPdf} onChange={(e) => set({ hasPdf: e.target.checked })} />
            <span>Có sẵn PDF</span>
          </label>
          <div className="mb-1.5" style={{ fontSize: 13, color: 'var(--ink-2)' }}>
            Trích dẫn tối thiểu: <b className="mono">{filters.minCite}</b>
          </div>
          <input
            type="range" min={0} max={300} step={10}
            value={filters.minCite}
            onChange={(e) => set({ minCite: +e.target.value })}
            className="w-full" style={{ accentColor: 'var(--ink)' }}
          />
        </div>

        {/* Advanced */}
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16 }}>
          <button className="btn btn-outline btn-block" onClick={onOpenAdvanced}>
            <Icon name="sort" size={15} /> Bộ lọc nâng cao
            {activeAdvCount > 0 && (
              <span
                className="mono inline-grid place-items-center"
                style={{
                  fontSize: 11, fontWeight: 500,
                  background: 'var(--ink)', color: 'var(--bg)',
                  borderRadius: 20, minWidth: 18, height: 18, padding: '0 5px',
                }}
              >
                {activeAdvCount}
              </span>
            )}
          </button>
        </div>
      </div>
    </aside>
  )
}
