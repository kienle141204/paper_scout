import { useEffect } from 'react'
import { Icon } from './atoms'
import { FilterSidebarContent } from './FilterSidebar'
import type { Conference, Filters } from '../types/paper'

interface Props {
  open: boolean
  onClose: () => void
  filters: Filters
  setFilters: (f: Filters) => void
  conferences: Conference[]
  paperCounts: Record<string, number>
  onOpenAdvanced: () => void
  activeAdvCount: number
}

export default function FilterDrawer({ open, onClose, ...sidebarProps }: Props) {
  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, zIndex: 60,
          background: 'oklch(0.3 0.01 75 / 0.32)',
          backdropFilter: 'blur(2px)',
          opacity: open ? 1 : 0,
          pointerEvents: open ? 'auto' : 'none',
          transition: 'opacity 0.24s',
        }}
      />
      <aside className={`drawer drawer-right${open ? ' open' : ''}`}>
        <div
          className="flex items-center justify-between"
          style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}
        >
          <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--ink)' }}>Bộ lọc</span>
          <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Đóng bộ lọc">
            <Icon name="close" size={16} />
          </button>
        </div>
        <div style={{ padding: '16px' }}>
          <FilterSidebarContent {...sidebarProps} />
        </div>
      </aside>
    </>
  )
}
