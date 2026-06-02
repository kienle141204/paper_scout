import { useState, useEffect } from 'react'
import { Icon, ConfTag, CiteCount, Relevance, SaveBtn } from '../components/atoms'
import RichText from '../components/RichText'
import { viewPaper, analyzePaper } from '../services/api'
import type { Paper, Conference } from '../types/paper'

interface Props {
  paper: Paper
  saved: boolean
  related: Paper[]
  conferences: Conference[]
  onToggleSave: () => void
  onBack: () => void
  onOpen: (id: string) => void
}

export default function DetailScreen({ paper, saved, related, conferences, onToggleSave, onBack, onOpen }: Props) {
  const [lang, setLang] = useState<'vi' | 'en'>('vi')
  const [abstractVi, setAbstractVi] = useState<string | null>(paper.abstractVi ?? null)
  const [translating, setTranslating] = useState(false)
  const [translateError, setTranslateError] = useState(false)
  const [copied, setCopied] = useState(false)
  const [analyzeState, setAnalyzeState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [analysisHtml, setAnalysisHtml] = useState<string | null>(null)
  const [analyzeError, setAnalyzeError] = useState<string | null>(null)

  useEffect(() => {
    setAbstractVi(paper.abstractVi ?? null)
    setTranslating(false)
    setTranslateError(false)
    setAnalyzeError(null)

    // Check localStorage for cached analysis first
    try {
      const cached = localStorage.getItem(`ps_analysis_${paper.id}`)
      if (cached) {
        const data = JSON.parse(cached) as { html?: string }
        if (data.html) {
          setAnalysisHtml(data.html)
          setAnalyzeState('done')
        } else {
          setAnalysisHtml(null)
          setAnalyzeState('idle')
        }
      } else {
        setAnalysisHtml(null)
        setAnalyzeState('idle')
      }
    } catch {
      setAnalysisHtml(null)
      setAnalyzeState('idle')
    }

    viewPaper({
      paper_id: paper.id,
      title: paper.titleEn,
      abstract: paper.abstractEn,
      authors: paper.authors,
      keywords: paper.keywords,
      venue: paper.venue,
      year: paper.year,
      url: paper.url,
      conference: paper.conf,
    }).then((res) => {
      if (res.abstract_vi) setAbstractVi(res.abstract_vi)
    }).catch(() => setTranslateError(true)).finally(() => setTranslating(false))
    if (!paper.abstractVi) setTranslating(true)
  }, [paper.id])

  const handleAnalyze = async () => {
    setAnalyzeState('loading')
    setAnalyzeError(null)
    try {
      const result = await analyzePaper({
        paper_id: paper.id,
        title: paper.titleEn,
        abstract: paper.abstractEn,
        authors: paper.authors,
        keywords: paper.keywords,
        venue: paper.venue,
        year: paper.year,
        url: paper.url,
        conference: paper.conf,
      })
      setAnalysisHtml(result.html)
      setAnalyzeState('done')
      // Save to localStorage so next open skips LLM entirely
      try {
        localStorage.setItem(`ps_analysis_${paper.id}`, JSON.stringify({ html: result.html, ts: Date.now() }))
      } catch { /* localStorage full — skip */ }
    } catch (err) {
      setAnalyzeError(err instanceof Error ? err.message : 'Đã xảy ra lỗi.')
      setAnalyzeState('error')
    }
  }

  const openAnalysis = () => {
    if (!analysisHtml) return
    const blob = new Blob([analysisHtml], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
  }

  const downloadAnalysis = () => {
    if (!analysisHtml) return
    const blob = new Blob([analysisHtml], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${paper.titleEn.slice(0, 60).replace(/[^a-zA-Z0-9\s-]/g, '')}.html`
    a.click()
    URL.revokeObjectURL(url)
  }

  const copyCitation = () => {
    const authors = paper.authors.length > 0
      ? (paper.authors.length > 3 ? `${paper.authors[0]} et al.` : paper.authors.join(', '))
      : 'Unknown'
    const citation = `${authors} (${paper.year ?? '?'}). ${paper.titleEn}. ${paper.conf ?? paper.venue ?? ''}`.trim()
    navigator.clipboard.writeText(citation).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const confMeta = conferences.find((c) => c.id === paper.conf)

  return (
    <div className="fade-in flex-1">
      <div className="w-full mx-auto px-7" style={{ maxWidth: 1080, paddingTop: 22, paddingBottom: 72 }}>

        {/* Back */}
        <button className="btn btn-ghost btn-sm mb-5" onClick={onBack} style={{ paddingLeft: 8 }}>
          <Icon name="arrowL" size={15} /> Quay lại kết quả
        </button>

        <div className="flex gap-11 items-start">

          {/* ── Main ───────────────────────────────── */}
          <div className="flex-1 min-w-0">

            {/* Meta row */}
            <div className="flex items-center gap-3.5 mb-4 flex-wrap">
              <ConfTag conf={paper.conf} year={paper.year} solid />
              <CiteCount n={paper.citations} />
              <Relevance value={paper.relevance} showLabel />
            </div>

            {/* English title */}
            <h1
              className="serif"
              style={{
                fontSize: 34, lineHeight: 1.2, fontWeight: 500,
                letterSpacing: '-0.015em', margin: '0 0 10px', color: 'var(--ink)',
              }}
            >
              {paper.titleEn}
            </h1>

            {/* Vietnamese title */}
            {paper.titleVi && (
              <p style={{ fontSize: 18, color: 'var(--ink-2)', margin: '0 0 18px', lineHeight: 1.42, fontStyle: 'italic' }}>
                {paper.titleVi}
              </p>
            )}

            {/* Authors */}
            <div className="flex items-center gap-2 mb-6" style={{ color: 'var(--ink-2)', fontSize: 14.5 }}>
              <Icon name="user" size={15} style={{ color: 'var(--ink-3)' }} />
              {paper.authors.join(' · ')}
            </div>

            {/* Why relevant */}
            <div
              className="flex gap-3 mb-7"
              style={{
                padding: '13px 15px',
                background: 'var(--accent-soft)',
                border: '1px solid var(--accent-border)',
                borderRadius: 'var(--r)',
              }}
            >
              <Icon name="spark" size={16} style={{ color: 'var(--accent)', marginTop: 1, flexShrink: 0 }} />
              <div style={{ fontSize: 13.5, color: 'var(--ink)', lineHeight: 1.5 }}>
                <b style={{ fontWeight: 600 }}>Vì sao liên quan:</b> khớp{' '}
                <b className="mono" style={{ color: 'var(--accent)' }}>{paper.relevance}%</b>{' '}
                với truy vấn của bạn — trùng các khái niệm{' '}
                <i>{paper.keywords.slice(0, 2).join(', ')}</i>.
              </div>
            </div>

            {/* Key contributions */}
            {paper.keyContributions && paper.keyContributions.length > 0 && (
              <div className="mb-7">
                <div className="eyebrow mb-3">Đóng góp chính</div>
                <ul style={{ margin: 0, paddingLeft: 20, display: 'grid', gap: 8 }}>
                  {paper.keyContributions.map((c, i) => (
                    <li key={i} style={{ fontSize: 14.5, lineHeight: 1.55, color: 'var(--ink)' }}>{c}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Abstract section */}
            <div className="flex items-center justify-between mb-3.5">
              <h2 className="eyebrow" style={{ fontSize: 12, margin: 0 }}>Tóm tắt</h2>
              <div
                className="inline-flex"
                style={{ background: 'var(--surface-3)', borderRadius: 7, padding: 3, gap: 2 }}
              >
                {(['vi', 'en'] as const).map((v) => (
                  <button
                    key={v}
                    onClick={() => setLang(v)}
                    style={{
                      border: 0, borderRadius: 5, padding: '5px 11px',
                      fontSize: 12.5, fontWeight: 500,
                      background: lang === v ? 'var(--surface)' : 'transparent',
                      color: lang === v ? 'var(--ink)' : 'var(--ink-3)',
                      boxShadow: lang === v ? 'var(--shadow-sm)' : 'none',
                      cursor: 'pointer',
                    }}
                  >
                    {v === 'vi' ? 'Tiếng Việt' : 'English (gốc)'}
                  </button>
                ))}
              </div>
            </div>

            {lang === 'vi' && translateError && (
              <div className="flex items-center gap-2 mb-3" style={{
                fontSize: 13, color: 'oklch(0.5 0.1 40)',
                background: 'oklch(0.97 0.015 40)',
                border: '1px solid oklch(0.85 0.06 40)',
                borderRadius: 8, padding: '8px 12px',
              }}>
                <Icon name="globe" size={14} />
                Không thể dịch tự động. Đang hiển thị bản gốc tiếng Anh.
              </div>
            )}

            {lang === 'vi' && translating ? (
              <div className="flex items-center gap-2 muted" style={{ fontSize: 14, margin: '0 0 14px' }}>
                <span className="skeleton inline-block" style={{ width: 18, height: 18, borderRadius: '50%' }} />
                Đang dịch sang tiếng Việt…
              </div>
            ) : (
              <RichText
                text={lang === 'vi' ? (abstractVi ?? paper.abstractEn ?? '—') : (paper.abstractEn ?? '—')}
                style={{ fontSize: 16, lineHeight: 1.78, color: 'var(--ink)', marginBottom: 14 }}
              />
            )}

            {lang === 'vi' && abstractVi && !translating && !translateError && (
              <div className="muted flex items-center gap-1.5" style={{ fontSize: 12 }}>
                <Icon name="globe" size={13} />
                Dịch tự động từ tiếng Anh — bấm "English (gốc)" để xem nguyên văn.
              </div>
            )}

            {/* Paper analysis section */}
            <div style={{ marginTop: 28 }}>
              {analyzeState === 'idle' && (
                <button
                  onClick={handleAnalyze}
                  style={{
                    width: '100%',
                    minHeight: 180,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 10,
                    padding: '28px 24px',
                    border: '1.5px dashed var(--border-strong)',
                    borderRadius: 'var(--r)',
                    background: 'var(--surface)',
                    cursor: 'pointer',
                    transition: 'border-color 0.14s, background 0.14s',
                    fontFamily: 'inherit',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'var(--accent)'
                    e.currentTarget.style.background = 'var(--accent-soft)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--border-strong)'
                    e.currentTarget.style.background = 'var(--surface)'
                  }}
                >
                  <Icon name="spark" size={26} style={{ color: 'var(--ink-4)' }} />
                  <div style={{ fontSize: 14.5, fontWeight: 600, color: 'var(--ink-2)' }}>
                    Phân tích paper với AI
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--ink-3)', maxWidth: 360, lineHeight: 1.5, textAlign: 'center' }}>
                    Tạo báo cáo về động lực nghiên cứu, trực quan hóa phương pháp và kết quả đạt được
                  </div>
                </button>
              )}

              {analyzeState === 'loading' && (
                <div
                  className="card flex items-center justify-center gap-3"
                  style={{ minHeight: 180, color: 'var(--ink-2)', fontSize: 14.5 }}
                >
                  <Icon name="loader" size={18} style={{ animation: 'spin 1s linear infinite', color: 'var(--accent)' }} />
                  Đang phân tích paper… (có thể mất 20–40 giây)
                </div>
              )}

              {analyzeState === 'error' && (
                <div
                  className="card flex items-center gap-3"
                  style={{
                    minHeight: 100, padding: '18px 20px',
                    color: 'oklch(0.5 0.1 40)',
                    background: 'oklch(0.97 0.015 40)',
                    border: '1px solid oklch(0.85 0.06 40)',
                  }}
                >
                  <Icon name="globe" size={16} />
                  <span className="flex-1" style={{ fontSize: 13.5 }}>
                    {analyzeError || 'Không thể phân tích paper. Vui lòng thử lại.'}
                  </span>
                  <button
                    className="btn btn-outline btn-sm"
                    onClick={handleAnalyze}
                    style={{ fontSize: 13 }}
                  >
                    Thử lại
                  </button>
                </div>
              )}

              {analyzeState === 'done' && analysisHtml && (
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="eyebrow" style={{ fontSize: 11 }}>Phân tích AI</span>
                    <div className="flex gap-2">
                      <button className="btn btn-outline btn-sm" onClick={openAnalysis}>
                        <Icon name="ext" size={13} /> Mở đầy đủ
                      </button>
                      <button className="btn btn-outline btn-sm" onClick={downloadAnalysis}>
                        <Icon name="download" size={13} /> Tải xuống
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ color: 'var(--ink-3)', fontSize: 12 }}
                        onClick={() => {
                          localStorage.removeItem(`ps_analysis_${paper.id}`)
                          setAnalyzeState('idle')
                          setAnalysisHtml(null)
                        }}
                      >
                        Tạo lại
                      </button>
                    </div>
                  </div>
                  <iframe
                    srcDoc={analysisHtml}
                    sandbox="allow-same-origin"
                    title="Phân tích paper"
                    style={{
                      width: '100%', height: 620,
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--r)',
                    }}
                  />
                </div>
              )}
            </div>

            {/* Keywords */}
            <div style={{ marginTop: 28 }}>
              <div className="eyebrow mb-3">Từ khóa</div>
              <div className="flex flex-wrap gap-2">
                {paper.keywords.map((k) => (
                  <span key={k} className="kw" style={{ fontSize: 13, padding: '5px 10px' }}>{k}</span>
                ))}
              </div>
            </div>

            {/* Related papers */}
            {related.length > 0 && (
              <div style={{ marginTop: 40, paddingTop: 28, borderTop: '1px solid var(--border)' }}>
                <div className="eyebrow mb-4">Paper liên quan</div>
                <div className="grid gap-2.5">
                  {related.map((r) => (
                    <button
                      key={r.id}
                      onClick={() => onOpen(r.id)}
                      className="flex items-center gap-3.5 text-left w-full card"
                      style={{ padding: '13px 15px', transition: 'all .14s', cursor: 'pointer' }}
                      onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--ink-3)' }}
                      onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
                    >
                      <ConfTag conf={r.conf} year={r.year} />
                      <span className="flex-1 min-w-0">
                        <span
                          className="serif block"
                          style={{
                            fontSize: 15.5, color: 'var(--ink)', fontWeight: 500,
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          }}
                        >
                          {r.titleEn}
                        </span>
                        {r.titleVi && <span className="muted" style={{ fontSize: 12.5 }}>{r.titleVi}</span>}
                      </span>
                      <span className="rel-num flex-none">{r.relevance}%</span>
                      <Icon name="arrowR" size={15} style={{ color: 'var(--ink-4)', flexShrink: 0 }} />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* ── Side panel ────────────────────────── */}
          <aside style={{ width: 268, flexShrink: 0 }}>
            <div className="sticky" style={{ top: 76 }}>
              <div className="card" style={{ padding: 18 }}>
                {paper.url && (
                  <a
                    href={paper.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-accent btn-block mb-2"
                  >
                    <Icon name="download" size={16} /> Tải PDF / Xem paper
                  </a>
                )}

                <SaveBtn saved={saved} onClick={onToggleSave} label size="lg" />

                <button
                  className="btn btn-outline btn-block mt-2"
                  onClick={copyCitation}
                  style={{ fontSize: 13 }}
                >
                  <Icon name={copied ? 'check' : 'ext'} size={14} />
                  {copied ? 'Đã copy!' : 'Copy citation (APA)'}
                </button>

                {confMeta?.url && (
                  <div className="mt-2">
                    <a href={confMeta.url} target="_blank" rel="noopener noreferrer" className="btn btn-outline btn-block">
                      <Icon name="ext" size={15} /> Trang gốc hội nghị
                    </a>
                  </div>
                )}

                {/* Metadata */}
                <div style={{ borderTop: '1px solid var(--border)', marginTop: 16, paddingTop: 16, display: 'grid', gap: 13 }}>
                  {([
                    ['Hội nghị', paper.conf ? `${paper.conf} ${paper.year ?? ''}`.trim() : '—'],
                    ['Trích dẫn', paper.citations != null ? paper.citations.toLocaleString('vi-VN') : '—'],
                    ['Độ liên quan', `${paper.relevance}%`],
                    ['Số tác giả', String(paper.authors.length)],
                    ['PDF', paper.url ? 'Có sẵn' : 'Không rõ'],
                  ] as [string, string][]).map(([k, v]) => (
                    <div key={k} className="flex justify-between items-baseline gap-2" style={{ fontSize: 13 }}>
                      <span className="muted whitespace-nowrap">{k}</span>
                      <span className="mono whitespace-nowrap" style={{ color: 'var(--ink)', fontWeight: 500 }}>{v}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="muted" style={{ fontSize: 11.5, marginTop: 14, lineHeight: 1.5, padding: '0 4px' }}>
                Trích dẫn cập nhật từ chỉ mục công khai. Bản dịch tạo tự động, có thể chưa chính xác hoàn toàn.
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}
