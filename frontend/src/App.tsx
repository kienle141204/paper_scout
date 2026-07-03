import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import NavBar from './components/NavBar'
import AdvancedFilters from './components/AdvancedFilters'
import AuthModal from './components/AuthModal'
import SettingsPanel from './components/SettingsPanel'
import HomeScreen from './screens/HomeScreen'
import ResultsScreen from './screens/ResultsScreen'
import DetailScreen from './screens/DetailScreen'
import ReaderScreen from './screens/ReaderScreen'
import SavedScreen from './screens/SavedScreen'
import ChatScreen from './screens/ChatScreen'
import type { Paper, Conference, Filters, SortKey, Screen } from './types/paper'
import { DEFAULT_FILTERS } from './types/paper'
import { getConferences, searchPapers, parseQuery } from './services/api'
import type { SearchParams } from './services/api'
import { LanguageProvider } from './contexts/LanguageContext'
import { AuthProvider, useAuth } from './contexts/AuthContext'

function screenToUrl(screen: Screen, selectedId: string | null, query: string): string {
  if (screen === 'detail' && selectedId) return `/detail/${encodeURIComponent(selectedId)}`
  if (screen === 'reader' && selectedId) return `/reader/${encodeURIComponent(selectedId)}`
  if (screen === 'results') return query ? `/results?q=${encodeURIComponent(query)}` : '/results'
  if (screen === 'saved') return '/saved'
  if (screen === 'chat') return '/chat'
  return '/'
}

function parseInitialUrl(): { screen: Screen; selectedId: string | null } {
  const path = window.location.pathname
  if (path.startsWith('/detail/')) {
    const id = decodeURIComponent(path.slice('/detail/'.length))
    return { screen: 'detail', selectedId: id || null }
  }
  if (path.startsWith('/reader/')) {
    const id = decodeURIComponent(path.slice('/reader/'.length))
    return { screen: 'reader', selectedId: id || null }
  }
  if (path === '/saved') return { screen: 'saved', selectedId: null }
  if (path === '/chat') return { screen: 'chat', selectedId: null }
  return { screen: 'home', selectedId: null }
}

// Parse URL once before component mounts (not inside render loop)
const _INIT = parseInitialUrl()

function AppInner() {
  const { isLoggedIn } = useAuth()
  const [screen, setScreen] = useState<Screen>(_INIT.screen)
  const [prevScreen, setPrevScreen] = useState<Screen>('results')
  const [query, setQuery] = useState('')
  const [papers, setPapers] = useState<Paper[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const [sort, setSort] = useState<SortKey>('relevance')
  const [savedMap, setSavedMap] = useState<Record<string, Paper>>(() => {
    if (!localStorage.getItem('ps_token')) return {}
    try { return JSON.parse(localStorage.getItem('ps_saved_papers') ?? '{}') } catch { return {} }
  })
  const savedIds = useMemo(() => Object.keys(savedMap), [savedMap])
  const [selectedId, setSelectedId] = useState<string | null>(_INIT.selectedId)
  const [chatPapersMap, setChatPapersMap] = useState<Record<string, Paper>>({})
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [conferences, setConferences] = useState<Conference[]>([])
  const [confError, setConfError] = useState(false)
  const [lastSearchParams, setLastSearchParams] = useState<SearchParams | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [correctedQuery, setCorrectedQuery] = useState<string | null>(null)
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)

  // When user logs out, clear savedMap
  useEffect(() => {
    if (!isLoggedIn) {
      setSavedMap({})
    }
  }, [isLoggedIn])

  // ── URL / History routing ────────────────────────────────────────────────
  const isPopping = useRef(false)
  const isMounted = useRef(false)

  // Sync URL when navigating
  useEffect(() => {
    if (isPopping.current) { isPopping.current = false; return }
    const url = screenToUrl(screen, selectedId, query)
    if (!isMounted.current) {
      isMounted.current = true
      window.history.replaceState({ screen, selectedId, query }, '', url)
    } else {
      window.history.pushState({ screen, selectedId, query }, '', url)
    }
    // query intentionally excluded: only push on navigation events (screen/selectedId change)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screen, selectedId])

  // Handle browser back / forward
  useEffect(() => {
    const onPop = (e: PopStateEvent) => {
      const s = e.state as { screen?: Screen; selectedId?: string | null; query?: string } | null
      if (!s?.screen) return
      isPopping.current = true
      setScreen(s.screen)
      setSelectedId(s.selectedId ?? null)
      if (s.query !== undefined) setQuery(s.query)
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  // Load conferences on mount
  useEffect(() => {
    getConferences()
      .then(setConferences)
      .catch(() => setConfError(true))
  }, [])

  // Scroll to top on screen / paper change
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior })
  }, [screen, selectedId])

  const PAGE_SIZE = 10

  const runSearch = useCallback(async (params: SearchParams) => {
    setLastSearchParams(params)
    setQuery(params.query)
    setLoading(true)
    setError(null)
    setPapers([])
    setHasMore(false)
    setCorrectedQuery(null)
    setCurrentPage(1)
    setScreen('results')
    try {
      const result = await searchPapers({ ...params, offset: 0, limit: PAGE_SIZE })
      setPapers(result.papers)
      setHasMore(result.hasMore)
      setCorrectedQuery(result.correctedQuery)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred.')
    } finally {
      setLoading(false)
    }
  }, [PAGE_SIZE])

  const goToPage = useCallback(async (page: number) => {
    if (!lastSearchParams) return
    setLoading(true)
    setError(null)
    setPapers([])
    setHasMore(false)
    window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior })
    try {
      const result = await searchPapers({ ...lastSearchParams, offset: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE })
      setPapers(result.papers)
      setHasMore(result.hasMore)
      setCurrentPage(page)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred.')
    } finally {
      setLoading(false)
    }
  }, [lastSearchParams, PAGE_SIZE])

  const handleSearch = useCallback(
    async (args: { query: string; confs: string[]; yearFrom: number; yearTo: number }) => {
      const parsed = await parseQuery(args.query).catch(() => null)

      const keywords = parsed?.keywords ?? args.query
      const keywordVariants = parsed?.keyword_variants ?? []
      const detectedVenues = parsed?.venues ?? []
      const mergedConfs = [...new Set([...args.confs, ...detectedVenues])]
      const yearFrom = parsed?.year_from ?? args.yearFrom
      const yearTo = parsed?.year_to ?? args.yearTo

      setFilters((f) => ({ ...f, confs: mergedConfs, years: [yearFrom, yearTo] }))
      runSearch({
        query: keywords,
        keywordVariants,
        conferences: mergedConfs,
        yearFrom,
        yearTo,
        correctedQuery: parsed?.corrected_query ?? null,
      })
    },
    [runSearch],
  )

  const handleRetry = useCallback(() => {
    if (lastSearchParams) goToPage(currentPage)
  }, [lastSearchParams, currentPage, goToPage])

  const toggleSave = useCallback((id: string) => {
    if (!isLoggedIn) {
      setAuthModalOpen(true)
      return
    }
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
  }, [papers, chatPapersMap, isLoggedIn])

  const openPaper = useCallback((id: string) => {
    setPrevScreen(screen)
    setSelectedId(id)
    setScreen('detail')
  }, [screen])

  const openPaperObj = useCallback((paper: Paper) => {
    setChatPapersMap((prev) => (paper.id in prev ? prev : { ...prev, [paper.id]: paper }))
    openPaper(paper.id)
  }, [openPaper])

  const openReader = useCallback((id: string) => {
    setPrevScreen('detail')
    setSelectedId(id)
    setScreen('reader')
  }, [])

  const handleBack = useCallback(() => {
    setScreen(prevScreen)
  }, [prevScreen])

  const selected = useMemo(
    () => papers.find((p) => p.id === selectedId)
      ?? (selectedId ? chatPapersMap[selectedId] ?? savedMap[selectedId] ?? null : null),
    [papers, selectedId, chatPapersMap, savedMap],
  )

  const related = useMemo(() => {
    if (!selected) return []
    const kws = new Set(selected.keywords.map((k) => k.toLowerCase()))
    const pool = papers.length > 0 ? papers : Object.values(chatPapersMap)
    return pool
      .filter((p) => p.id !== selected.id && p.keywords.some((k) => kws.has(k.toLowerCase())))
      .sort((a, b) => b.relevance - a.relevance)
      .slice(0, 3)
  }, [selected, papers, chatPapersMap])

  const savedPapers = useMemo(() => Object.values(savedMap), [savedMap])

  const activeAdvCount = useMemo(() => {
    let n = 0
    if (filters.author) n++
    if (filters.exclude) n++
    if (filters.minCite > 0) n++
    if (filters.minRel > 0) n++
    if (filters.hasPdf) n++
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
        onSearch={(q) => handleSearch({ query: q, confs: filters.confs, yearFrom: filters.years[0], yearTo: filters.years[1] })}
        onSettings={() => setSettingsOpen(true)}
        onLogin={() => setAuthModalOpen(true)}
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
          confError={confError}
          filters={filters}
          setFilters={setFilters}
          sort={sort}
          setSort={setSort}
          onOpen={openPaper}
          onToggleSave={toggleSave}
          onOpenAdvanced={() => setAdvancedOpen(true)}
          activeAdvCount={activeAdvCount}
          onRetry={handleRetry}
          hasMore={hasMore}
          currentPage={currentPage}
          onGoToPage={goToPage}
          correctedQuery={correctedQuery}
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
          onOpenReader={openReader}
          onNeedAuth={() => setAuthModalOpen(true)}
        />
      )}

      {screen === 'reader' && selected && (
        <ReaderScreen
          paper={selected}
          saved={savedIds.includes(selected.id)}
          onToggleSave={() => toggleSave(selected.id)}
          onBack={handleBack}
          onNeedAuth={() => setAuthModalOpen(true)}
        />
      )}

      {screen === 'saved' && (
        <SavedScreen
          savedPapers={savedPapers}
          onOpen={openPaper}
          onToggleSave={toggleSave}
          onGoSearch={() => setScreen('home')}
          onOpenAuth={() => setAuthModalOpen(true)}
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

      {authModalOpen && (
        <AuthModal onClose={() => setAuthModalOpen(false)} />
      )}

      {settingsOpen && (
        <SettingsPanel
          onClose={() => setSettingsOpen(false)}
          onOpenAuth={() => setAuthModalOpen(true)}
        />
      )}

      {screen !== 'reader' && (
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
      )}
    </div>
  )
}

export default function App() {
  return (
    <LanguageProvider>
      <AuthProvider>
        <AppInner />
      </AuthProvider>
    </LanguageProvider>
  )
}
