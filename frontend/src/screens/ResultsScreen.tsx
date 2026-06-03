import { useMemo, useState } from 'react'
import { Icon, CardSkeleton, ErrorBanner } from '../components/atoms'
import ResultCard from '../components/ResultCard'
import FilterSidebar from '../components/FilterSidebar'
import FilterDrawer from '../components/FilterDrawer'
import type { Paper, Conference, Filters, SortKey } from '../types/paper'

interface Props {
  query: string
  papers: Paper[]
  loading: boolean
  error: string | null
  savedIds: string[]
  conferences: Conference[]
  confError?: boolean
  filters: Filters
  setFilters: (f: Filters) => void
  sort: SortKey
  setSort: (s: SortKey) => void
  onOpen: (id: string) => void
  onToggleSave: (id: string) => void
  onOpenAdvanced: () => void
  activeAdvCount: number
  onRetry: () => void
  hasMore?: boolean
  currentPage?: number
  onGoToPage?: (page: number) => void
  correctedQuery?: string | null
}

export default function ResultsScreen({
  query, papers, loading, error, savedIds, conferences, confError,
  filters, setFilters, sort, setSort,
  onOpen, onToggleSave, onOpenAdvanced, activeAdvCount, onRetry,
  hasMore, currentPage, onGoToPage, correctedQuery,
}: Props) {

  const [filterOpen, setFilterOpen] = useState(false)

  const filtered = useMemo(() => {
    let list = papers.filter((p) => {
      if (filters.confs.length && !filters.confs.includes(p.conf ?? '')) return false
      if (p.year != null && (p.year < filters.years[0] || p.year > filters.years[1])) return false
      if ((p.citations ?? 0) < filters.minCite) return false
      if (p.relevance < (filters.minRel ?? 0)) return false
      if (filters.hasPdf && !p.url) return false
      if (filters.author) {
        const q = filters.author.toLowerCase()
        if (!p.authors.join(' ').toLowerCase().includes(q)) return false
      }
      if (filters.exclude) {
        const ex = filters.exclude.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean)
        if (ex.some((e) => p.keywords.join(' ').toLowerCase().includes(e))) return false
      }
      return true
    })
    list = [...list].sort((a, b) => {
      if (sort === 'citations') return (b.citations ?? 0) - (a.citations ?? 0)
      if (sort === 'year') return (b.year ?? 0) - (a.year ?? 0)
      return b.relevance - a.relevance
    })
    return list
  }, [papers, filters, sort])

  const paperCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    papers.forEach((p) => { if (p.conf) counts[p.conf] = (counts[p.conf] ?? 0) + 1 })
    return counts
  }, [papers])

  return (
    <div className="fade-in flex-1">
      <div className="w-full mx-auto px-4 sm:px-7" style={{ maxWidth: 'var(--maxw)', paddingTop: 26, paddingBottom: 60 }}>

        {/* Query header */}
        <div className="mb-6">
          <div className="eyebrow mb-2">Kết quả cho</div>
          <h1 style={{ fontSize: 27, fontWeight: 600, margin: 0, letterSpacing: '-0.02em', color: 'var(--ink)' }}>
            "{query}"
          </h1>
          {correctedQuery && (
            <div
              className="flex items-start gap-2 mt-3"
              style={{
                fontSize: 13, lineHeight: 1.5,
                color: 'var(--accent)',
                background: 'var(--accent-soft)',
                border: '1px solid var(--accent-border)',
                borderRadius: 8, padding: '8px 12px',
                maxWidth: 600,
              }}
            >
              <Icon name="spark" size={14} style={{ marginTop: 1, flexShrink: 0 }} />
              <span>
                <b style={{ fontWeight: 600 }}>Đã hiểu ý bạn:</b>{' '}
                {correctedQuery}
              </span>
            </div>
          )}
        </div>

        <div className="flex gap-9 items-start">
          <div className="hidden md:block">
            <FilterSidebar
              filters={filters} setFilters={setFilters}
              conferences={conferences} paperCounts={paperCounts}
              onOpenAdvanced={onOpenAdvanced} activeAdvCount={activeAdvCount}
            />
          </div>
          <FilterDrawer
            open={filterOpen}
            onClose={() => setFilterOpen(false)}
            filters={filters} setFilters={setFilters}
            conferences={conferences} paperCounts={paperCounts}
            onOpenAdvanced={onOpenAdvanced} activeAdvCount={activeAdvCount}
          />

          {/* Results column */}
          <div className="flex-1 min-w-0">
            {/* Sort bar */}
            <div className="flex items-center gap-2 mb-4">
              <button
                className="btn btn-outline btn-sm flex md:hidden items-center gap-2"
                onClick={() => setFilterOpen(true)}
              >
                <Icon name="filter" size={14} /> Bộ lọc
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
              <div className="hidden md:block" style={{ fontSize: 13.5, color: 'var(--ink-2)' }}>
                {loading
                  ? <span className="skeleton inline-block" style={{ width: 100, height: 16 }} />
                  : <><b style={{ color: 'var(--ink)', fontWeight: 600 }}>{filtered.length}</b> paper liên quan</>
                }
              </div>
              <div className="flex-1" />
              <label className="flex items-center gap-2" style={{ fontSize: 13, color: 'var(--ink-2)' }}>
                <Icon name="sort" size={14} /> Sắp xếp:
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value as SortKey)}
                  style={{
                    fontFamily: 'inherit', fontSize: 13, fontWeight: 500, color: 'var(--ink)',
                    border: '1px solid var(--border-strong)', borderRadius: 6, padding: '6px 9px',
                    background: 'var(--surface)', cursor: 'pointer',
                  }}
                >
                  <option value="relevance">Độ liên quan</option>
                  <option value="citations">Trích dẫn</option>
                  <option value="year">Mới nhất</option>
                </select>
              </label>
            </div>

            {/* Error */}
            {error && <ErrorBanner message={error} onRetry={onRetry} />}

            {/* Skeletons */}
            {loading && !error && (
              <div className="grid gap-3.5">
                {[1, 2, 3, 4].map((i) => <CardSkeleton key={i} />)}
              </div>
            )}

            {/* Empty */}
            {!loading && !error && filtered.length === 0 && (
              <div className="card text-center" style={{ padding: 48, color: 'var(--ink-3)' }}>
                <Icon name="search" size={28} style={{ color: 'var(--ink-4)' }} />
                <div className="mt-3" style={{ fontSize: 15 }}>
                  Không có paper nào khớp bộ lọc hiện tại.
                </div>
              </div>
            )}

            {/* Conf load error */}
            {confError && (
              <div className="mb-4" style={{ fontSize: 13, color: 'var(--ink-3)', padding: '8px 12px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }}>
                Không tải được danh sách hội nghị — bộ lọc hội nghị tạm thời không khả dụng.
              </div>
            )}

            {/* Results */}
            {!loading && !error && filtered.length > 0 && (
              <div className="grid gap-3.5">
                {filtered.map((p, i) => (
                  <ResultCard
                    key={p.id} paper={p} rank={i + 1}
                    saved={savedIds.includes(p.id)}
                    onOpen={() => onOpen(p.id)}
                    onToggleSave={() => onToggleSave(p.id)}
                  />
                ))}
              </div>
            )}

            {/* Pagination */}
            {!loading && !error && (filtered.length > 0 || (currentPage ?? 1) > 1) && (
              <div className="flex items-center justify-center gap-3 mt-6">
                <button
                  className="btn btn-outline btn-sm"
                  disabled={(currentPage ?? 1) <= 1}
                  onClick={() => onGoToPage?.((currentPage ?? 1) - 1)}
                >
                  ← Trang trước
                </button>
                <span style={{ fontSize: 13.5, color: 'var(--ink-2)', minWidth: 64, textAlign: 'center' }}>
                  Trang {currentPage ?? 1}
                </span>
                <button
                  className="btn btn-outline btn-sm"
                  disabled={!hasMore}
                  onClick={() => onGoToPage?.((currentPage ?? 1) + 1)}
                >
                  Trang sau →
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
