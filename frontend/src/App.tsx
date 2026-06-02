import { useState, useEffect, useCallback, useMemo } from 'react'
import NavBar from './components/NavBar'
import AdvancedFilters from './components/AdvancedFilters'
import HomeScreen from './screens/HomeScreen'
import ResultsScreen from './screens/ResultsScreen'
import DetailScreen from './screens/DetailScreen'
import SavedScreen from './screens/SavedScreen'
import ChatScreen from './screens/ChatScreen'
import type { Paper, Conference, Filters, SortKey, Screen } from './types/paper'
import { DEFAULT_FILTERS } from './types/paper'
import { getConferences, searchPapers, parseQuery } from './services/api'
import type { SearchParams } from './services/api'

export default function App() {
  const [screen, setScreen] = useState<Screen>('home')
  const [prevScreen, setPrevScreen] = useState<Screen>('results')
  const [query, setQuery] = useState('')
  const [papers, setPapers] = useState<Paper[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const [sort, setSort] = useState<SortKey>('relevance')
  const [savedMap, setSavedMap] = useState<Record<string, Paper>>(() => {
    try { return JSON.parse(localStorage.getItem('ps_saved_papers') ?? '{}') } catch { return {} }
  })
  const savedIds = useMemo(() => Object.keys(savedMap), [savedMap])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [chatPapersMap, setChatPapersMap] = useState<Record<string, Paper>>({})
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [conferences, setConferences] = useState<Conference[]>([])
  const [lastSearchParams, setLastSearchParams] = useState<SearchParams | null>(null)

  // Load conferences on mount
  useEffect(() => {
    getConferences()
      .then(setConferences)
      .catch(() => { /* fail silently — UI still works without conf metadata */ })
  }, [])

  // Scroll to top on screen / paper change
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior })
  }, [screen, selectedId])

  const runSearch = useCallback(async (params: SearchParams) => {
    setLastSearchParams(params)
    setQuery(params.query)
    setLoading(true)
    setError(null)
    setPapers([])
    setScreen('results')
    try {
      const result = await searchPapers(params)
      setPapers(result.papers)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đã xảy ra lỗi không xác định.')
    } finally {
      setLoading(false)
    }
  }, [])

  const handleSearch = useCallback(
    async (args: { query: string; confs: string[]; yearFrom: number; yearTo: number }) => {
      // Parse natural language query to extract keywords, venues, year
      const parsed = await parseQuery(args.query).catch(() => null)

      const keywords = parsed?.keywords ?? args.query
      // Merge LLM-detected venues with manually selected conferences (deduplicated)
      const detectedVenues = parsed?.venues ?? []
      const mergedConfs = [...new Set([...args.confs, ...detectedVenues])]

      const yearFrom = parsed?.year_from ?? args.yearFrom
      const yearTo = parsed?.year_to ?? args.yearTo

      setFilters((f) => ({ ...f, confs: mergedConfs, years: [yearFrom, yearTo] }))
      runSearch({
        query: keywords,
        conferences: mergedConfs,
        yearFrom,
        yearTo,
      })
    },
    [runSearch],
  )

  const handleRetry = useCallback(() => {
    if (lastSearchParams) runSearch(lastSearchParams)
  }, [lastSearchParams, runSearch])

  const toggleSave = useCallback((id: string) => {
    setSavedMap((prev) => {
      let next: Record<string, Paper>
      if (id in prev) {
        const { [id]: _removed, ...rest } = prev
        next = rest
      } else {
        const paper = papers.find((p) => p.id === id) ?? chatPapersMap[id]
        if (!paper) return prev
        next = { ...prev, [id]: paper }
      }
      localStorage.setItem('ps_saved_papers', JSON.stringify(next))
      return next
    })
  }, [papers, chatPapersMap])

  const openPaper = useCallback((id: string) => {
    setPrevScreen(screen)
    setSelectedId(id)
    setScreen('detail')
  }, [screen])

  const openPaperObj = useCallback((paper: Paper) => {
    setChatPapersMap((prev) => (paper.id in prev ? prev : { ...prev, [paper.id]: paper }))
    openPaper(paper.id)
  }, [openPaper])

  const handleBack = useCallback(() => {
    setScreen(prevScreen)
  }, [prevScreen])

  const selected = useMemo(
    () => papers.find((p) => p.id === selectedId) ?? (selectedId ? chatPapersMap[selectedId] ?? null : null),
    [papers, selectedId, chatPapersMap],
  )

  const related = useMemo(() => {
    if (!selected) return []
    const kws = new Set(selected.keywords.map((k) => k.toLowerCase()))
    return papers
      .filter((p) => p.id !== selected.id && p.keywords.some((k) => kws.has(k.toLowerCase())))
      .sort((a, b) => b.relevance - a.relevance)
      .slice(0, 3)
  }, [selected, papers])

  const savedPapers = useMemo(() => Object.values(savedMap), [savedMap])

  const activeAdvCount = useMemo(() => {
    let n = 0
    if (filters.author) n++
    if (filters.exclude) n++
    if (filters.minCite > 0) n++
    if (filters.minRel > 0) n++
    if (filters.hasPdf) n++
    if (filters.oralOnly) n++
    return n
  }, [filters])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg)' }}>
      <NavBar
        screen={screen}
        query={query}
        savedCount={savedIds.length}
        onHome={() => setScreen('home')}
        onSaved={() => setScreen('saved')}
        onChat={() => setScreen('chat')}
      />

      {screen === 'home' && (
        <HomeScreen conferences={conferences} onSearch={handleSearch} onOpenChat={() => setScreen('chat')} />
      )}

      {screen === 'results' && (
        <ResultsScreen
          query={query}
          papers={papers}
          loading={loading}
          error={error}
          savedIds={savedIds}
          conferences={conferences}
          filters={filters}
          setFilters={setFilters}
          sort={sort}
          setSort={setSort}
          onOpen={openPaper}
          onToggleSave={toggleSave}
          onOpenAdvanced={() => setAdvancedOpen(true)}
          activeAdvCount={activeAdvCount}
          onRetry={handleRetry}
        />
      )}

      {screen === 'detail' && selected && (
        <DetailScreen
          paper={selected}
          saved={savedIds.includes(selected.id)}
          related={related}
          conferences={conferences}
          onToggleSave={() => toggleSave(selected.id)}
          onBack={handleBack}
          onOpen={openPaper}
        />
      )}

      {screen === 'saved' && (
        <SavedScreen
          savedPapers={savedPapers}
          onOpen={openPaper}
          onToggleSave={toggleSave}
          onGoSearch={() => setScreen('home')}
        />
      )}

      {screen === 'chat' && (
        <ChatScreen
          conferences={conferences}
          savedIds={savedIds}
          onOpen={openPaperObj}
          onToggleSave={toggleSave}
          onGoSearch={() => setScreen('home')}
        />
      )}

      {advancedOpen && (
        <AdvancedFilters
          filters={filters}
          setFilters={setFilters}
          conferences={conferences}
          onClose={() => setAdvancedOpen(false)}
        />
      )}

      <footer style={{
        borderTop: '1px solid var(--border)',
        padding: '18px 28px',
        marginTop: 'auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 8,
      }}>
        <span className="mono muted" style={{ fontSize: 12 }}>
          PaperScout · prototype
        </span>
        <span className="mono muted" style={{ fontSize: 12 }}>
          {conferences.map((c) => c.name).join(' · ')}
        </span>
      </footer>
    </div>
  )
}
