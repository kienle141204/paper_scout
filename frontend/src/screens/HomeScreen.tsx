import { useState } from 'react'
import { Icon } from '../components/atoms'
import type { Conference } from '../types/paper'
import { SAMPLE_QUERIES, MIN_YEAR, CURRENT_YEAR } from '../types/paper'

interface SearchArgs {
  query: string
  confs: string[]
  yearFrom: number
  yearTo: number
}

interface Props {
  conferences: Conference[]
  onSearch: (args: SearchArgs) => void
  onOpenChat: () => void
}

const HISTORY_KEY = 'ps_search_history'
const MAX_HISTORY = 8

function loadHistory(): string[] {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) ?? '[]') } catch { return [] }
}

function saveHistory(query: string) {
  const prev = loadHistory().filter((q) => q !== query)
  localStorage.setItem(HISTORY_KEY, JSON.stringify([query, ...prev].slice(0, MAX_HISTORY)))
}

export default function HomeScreen({ conferences, onSearch, onOpenChat }: Props) {
  const [q, setQ] = useState('')
  const [confs, setConfs] = useState<string[]>([])
  const [yearFrom, setYearFrom] = useState(2022)
  const [yearTo, setYearTo] = useState(CURRENT_YEAR)
  const [history, setHistory] = useState<string[]>(loadHistory)

  const toggleConf = (id: string) =>
    setConfs((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]))

  const submit = (query?: string) => {
    const text = (query ?? q).trim()
    if (!text) return
    saveHistory(text)
    setHistory(loadHistory())
    onSearch({ query: text, confs, yearFrom, yearTo })
  }

  return (
    <div className="fade-in flex-1">
      <div className="w-full mx-auto px-4 sm:px-7 pt-10 sm:pt-[76px] pb-16 sm:pb-[80px]" style={{ maxWidth: 880 }}>

        {/* Hero */}
        <div className="text-center mb-9">
          <div className="eyebrow mb-4">Tra cứu paper hội nghị · AI</div>
          <h1 className="hero-title">
            Tìm đúng paper bạn cần,<br />không phải dịch từng abstract.
          </h1>
          <p style={{ fontSize: 17, color: 'var(--ink-2)', margin: '0 auto', maxWidth: 560, lineHeight: 1.55 }}>
            Mô tả chủ đề bằng tiếng Việt. PaperScout tìm khắp các hội nghị lớn,
            xếp hạng theo độ liên quan và{' '}
            <b style={{ fontWeight: 600, color: 'var(--ink)' }}>dịch sẵn tiêu đề & tóm tắt</b>.
          </p>
        </div>

        {/* Search box */}
        <div className="card" style={{ padding: 6, boxShadow: 'var(--shadow)', borderColor: 'var(--border-strong)' }}>
          <textarea
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit() }}
            placeholder="Ví dụ: mô hình khuếch tán tạo ảnh y tế độ phân giải cao…"
            rows={2}
            className="w-full resize-none outline-none"
            style={{
              border: 0, background: 'transparent',
              fontSize: 16.5, lineHeight: 1.5, color: 'var(--ink)',
              padding: '16px 16px 6px',
            }}
          />
          <div className="flex items-center flex-wrap gap-2" style={{ padding: '8px 10px 9px' }}>
            <button className="chip" style={{ height: 34, flexShrink: 0 }}>
              <Icon name="layers" size={14} />
              {confs.length ? `${confs.length} hội nghị` : 'Tất cả hội nghị'}
            </button>
            <div className="flex items-center gap-1.5 mono muted" style={{ fontSize: 13 }}>
              <Icon name="clock" size={14} /> {yearFrom}–{yearTo}
            </div>
            <div className="flex-1" />
            <button
              className="btn btn-ghost btn-sm"
              onClick={onOpenChat}
              style={{ fontSize: 13, color: 'var(--ink-2)' }}
              title="Tìm kiếm bằng hội thoại AI"
            >
              <Icon name="chat" size={14} /> Chat AI
            </button>
            <button className="btn btn-accent" onClick={() => submit()} style={{ paddingInline: 20 }}>
              <Icon name="search" size={16} /> Tìm kiếm
            </button>
          </div>
        </div>

        {/* Conference chips */}
        <div className="mt-7">
          <div className="eyebrow mb-3">Lọc theo hội nghị</div>
          <div className="flex flex-wrap gap-2">
            {conferences.map((c) => (
              <button
                key={c.id}
                className={`chip${confs.includes(c.id) ? ' active' : ''}`}
                onClick={() => toggleConf(c.id)}
                title={c.full}
              >
                {confs.includes(c.id) && <Icon name="check" size={13} />}
                {c.name}
              </button>
            ))}
          </div>
        </div>

        {/* Year range */}
        <div className="mt-7">
          <div className="eyebrow mb-3">Khoảng năm</div>
          <div className="flex items-center gap-3 max-w-[420px]">
            <span className="mono" style={{ fontSize: 13, color: 'var(--ink-2)', width: 40 }}>{yearFrom}</span>
            <input
              type="range" min={MIN_YEAR} max={CURRENT_YEAR} value={yearFrom}
              onChange={(e) => setYearFrom(Math.min(+e.target.value, yearTo))}
              className="flex-1" style={{ accentColor: 'var(--ink)' }}
            />
            <span className="mono muted">→</span>
            <input
              type="range" min={MIN_YEAR} max={CURRENT_YEAR} value={yearTo}
              onChange={(e) => setYearTo(Math.max(+e.target.value, yearFrom))}
              className="flex-1" style={{ accentColor: 'var(--ink)' }}
            />
            <span className="mono text-right" style={{ fontSize: 13, color: 'var(--ink-2)', width: 40 }}>{yearTo}</span>
          </div>
        </div>

        {/* Search history */}
        {history.length > 0 && (
          <div className="mt-8">
            <div className="flex items-center justify-between mb-3">
              <div className="eyebrow">Tìm kiếm gần đây</div>
              <button
                className="btn btn-ghost btn-sm"
                style={{ fontSize: 12, color: 'var(--ink-3)' }}
                onClick={() => { localStorage.removeItem(HISTORY_KEY); setHistory([]) }}
              >
                Xóa lịch sử
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {history.map((h, i) => (
                <button
                  key={i}
                  className="chip"
                  onClick={() => { setQ(h); submit(h) }}
                  style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                >
                  <Icon name="clock" size={13} /> {h}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Sample queries */}
        <div className="mt-10">
          <div className="eyebrow mb-3">Hoặc thử một truy vấn mẫu</div>
          <div className="grid gap-2">
            {SAMPLE_QUERIES.map((s, i) => (
              <button
                key={i}
                onClick={() => { setQ(s); submit(s) }}
                className="flex items-center gap-3 text-left card"
                style={{
                  padding: '13px 15px', cursor: 'pointer',
                  fontSize: 14.5, transition: 'all .14s', color: 'var(--ink)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--ink-3)'
                  e.currentTarget.style.background = 'var(--surface-2)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border)'
                  e.currentTarget.style.background = 'var(--surface)'
                }}
              >
                <Icon name="search" size={15} style={{ color: 'var(--ink-3)', flexShrink: 0 }} />
                <span className="flex-1">{s}</span>
                <Icon name="arrowR" size={15} style={{ color: 'var(--ink-4)', flexShrink: 0 }} />
              </button>
            ))}
          </div>
        </div>

        {/* Stat strip */}
        <div
          className="flex gap-10 justify-center flex-wrap"
          style={{ marginTop: 44, paddingTop: 26, borderTop: '1px solid var(--border)' }}
        >
          {[
            [String(conferences.length || 15), 'hội nghị được lập chỉ mục'],
            ['48.200+', 'papers'],
            ['tiếng Việt', 'dịch tự động tiêu đề + abstract'],
          ].map(([n, l], i) => (
            <div key={i} className="text-center">
              <div style={{ fontSize: 25, fontWeight: 600, color: 'var(--ink)', letterSpacing: '-0.02em' }}>{n}</div>
              <div className="muted" style={{ fontSize: 12.5, marginTop: 2 }}>{l}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
