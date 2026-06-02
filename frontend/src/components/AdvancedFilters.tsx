import { useState } from 'react'
import { Icon } from './atoms'
import type { Conference, Filters } from '../types/paper'
import { MIN_YEAR, CURRENT_YEAR } from '../types/paper'

interface Props {
  filters: Filters
  setFilters: (f: Filters) => void
  conferences: Conference[]
  onClose: () => void
}

const INPUT_STYLE: React.CSSProperties = {
  width: '100%',
  border: '1px solid var(--border-strong)',
  borderRadius: 7,
  padding: '10px 12px',
  fontSize: 14,
  background: 'var(--surface)',
  outline: 'none',
  color: 'var(--ink)',
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 22 }}>
      <div className="flex justify-between items-baseline mb-2">
        <label className="eyebrow">{label}</label>
        {hint && <span className="muted" style={{ fontSize: 12 }}>{hint}</span>}
      </div>
      {children}
    </div>
  )
}

export default function AdvancedFilters({ filters, setFilters, conferences, onClose }: Props) {
  const [local, setLocal] = useState<Filters>(filters)
  const set = (patch: Partial<Filters>) => setLocal((f) => ({ ...f, ...patch }))

  const toggleConf = (id: string) =>
    set({ confs: local.confs.includes(id) ? local.confs.filter((x) => x !== id) : [...local.confs, id] })

  const apply = () => { setFilters(local); onClose() }

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <div
        role="dialog"
        aria-modal
        style={{
          position: 'fixed', top: '50%', left: '50%',
          transform: 'translate(-50%,-50%)', zIndex: 70,
          width: 'min(620px, calc(100vw - 40px))',
          maxHeight: 'calc(100vh - 60px)', overflowY: 'auto',
          background: 'var(--surface)',
          borderRadius: 'var(--r-lg)',
          boxShadow: 'var(--shadow-lg)',
          border: '1px solid var(--border)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between sticky top-0 z-10"
          style={{ padding: '20px 24px', borderBottom: '1px solid var(--border)', background: 'var(--surface)' }}
        >
          <div>
            <div className="eyebrow mb-1">Tinh chỉnh tìm kiếm</div>
            <h2 style={{ margin: 0, fontSize: 19, fontWeight: 600 }}>Bộ lọc nâng cao</h2>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose} style={{ width: 34, padding: 0 }}>
            <Icon name="close" size={16} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: 24 }}>
          <Field label="Hội nghị">
            <div className="flex flex-wrap gap-2">
              {conferences.map((c) => (
                <button
                  key={c.id}
                  className={`chip${local.confs.includes(c.id) ? ' active' : ''}`}
                  onClick={() => toggleConf(c.id)}
                >
                  {local.confs.includes(c.id) && <Icon name="check" size={13} />} {c.name}
                </button>
              ))}
            </div>
          </Field>

          <Field label="Khoảng năm" hint={`${local.years[0]} – ${local.years[1]}`}>
            <div className="flex items-center gap-3">
              <input
                type="range" min={MIN_YEAR} max={CURRENT_YEAR}
                value={local.years[0]}
                onChange={(e) => set({ years: [Math.min(+e.target.value, local.years[1]), local.years[1]] })}
                className="flex-1" style={{ accentColor: 'var(--ink)' }}
              />
              <input
                type="range" min={MIN_YEAR} max={CURRENT_YEAR}
                value={local.years[1]}
                onChange={(e) => set({ years: [local.years[0], Math.max(+e.target.value, local.years[0])] })}
                className="flex-1" style={{ accentColor: 'var(--ink)' }}
              />
            </div>
          </Field>

          <Field label="Số trích dẫn tối thiểu" hint={`${local.minCite}+`}>
            <input
              type="range" min={0} max={300} step={10}
              value={local.minCite}
              onChange={(e) => set({ minCite: +e.target.value })}
              className="w-full" style={{ accentColor: 'var(--ink)' }}
            />
          </Field>

          <Field label="Tác giả chứa">
            <input
              style={INPUT_STYLE}
              placeholder="vd: Zhao, Mehta…"
              value={local.author}
              onChange={(e) => set({ author: e.target.value })}
            />
          </Field>

          <Field label="Loại trừ từ khóa" hint="phân tách bằng dấu phẩy">
            <input
              style={INPUT_STYLE}
              placeholder="vd: survey, benchmark"
              value={local.exclude}
              onChange={(e) => set({ exclude: e.target.value })}
            />
          </Field>

          <Field label="Ngưỡng độ liên quan tối thiểu" hint={`${local.minRel}%`}>
            <input
              type="range" min={0} max={95} step={5}
              value={local.minRel}
              onChange={(e) => set({ minRel: +e.target.value })}
              className="w-full" style={{ accentColor: 'var(--ink)' }}
            />
          </Field>

          <div className="flex gap-4 flex-wrap">
            <label className="flex items-center gap-2 cursor-pointer" style={{ fontSize: 14 }}>
              <input type="checkbox" checked={local.hasPdf} onChange={(e) => set({ hasPdf: e.target.checked })} />
              Chỉ paper có PDF
            </label>
            <label className="flex items-center gap-2 cursor-pointer" style={{ fontSize: 14 }}>
              <input type="checkbox" checked={local.oralOnly} onChange={(e) => set({ oralOnly: e.target.checked })} />
              Chỉ Oral / Highlight
            </label>
          </div>
        </div>

        {/* Footer */}
        <div
          className="flex gap-2 justify-end sticky bottom-0"
          style={{ padding: '16px 24px', borderTop: '1px solid var(--border)', background: 'var(--surface)' }}
        >
          <button className="btn btn-ghost" onClick={onClose}>Hủy</button>
          <button className="btn btn-accent" onClick={apply}>
            <Icon name="check" size={16} /> Áp dụng bộ lọc
          </button>
        </div>
      </div>
    </>
  )
}
