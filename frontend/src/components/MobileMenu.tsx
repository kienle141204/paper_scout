import { useEffect } from 'react'
import { Icon } from './atoms'
import type { Screen } from '../types/paper'

interface Props {
  open: boolean
  onClose: () => void
  screen: Screen
  savedCount: number
  onHome: () => void
  onSaved: () => void
  onChat: () => void
}

export default function MobileMenu({ open, onClose, screen, savedCount, onHome, onSaved, onChat }: Props) {
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
      <nav className={`drawer${open ? ' open' : ''}`}>
        <div
          className="flex items-center justify-between"
          style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}
        >
          <span style={{ fontWeight: 600, fontSize: 15, color: 'var(--ink)' }}>
            Paper<b>Scout</b>
          </span>
          <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Đóng menu">
            <Icon name="close" size={16} />
          </button>
        </div>

        <div style={{ padding: '12px 8px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          <a
            href="/"
            onClick={(e) => { e.preventDefault(); onHome() }}
            className={`btn btn-ghost btn-block${screen === 'home' || screen === 'results' ? ' text-ink' : ''}`}
            style={{ justifyContent: 'flex-start', height: 52, fontSize: 15, textDecoration: 'none' }}
          >
            <Icon name="search" size={17} /> Tìm kiếm
          </a>
          <a
            href="/chat"
            onClick={(e) => { e.preventDefault(); onChat() }}
            className={`btn btn-ghost btn-block${screen === 'chat' ? ' text-ink' : ''}`}
            style={{ justifyContent: 'flex-start', height: 52, fontSize: 15, textDecoration: 'none' }}
          >
            <Icon name="chat" size={17} /> Chat AI
          </a>
          <a
            href="/saved"
            onClick={(e) => { e.preventDefault(); onSaved() }}
            className={`btn btn-ghost btn-block${screen === 'saved' ? ' text-ink' : ''}`}
            style={{ justifyContent: 'flex-start', height: 52, fontSize: 15, textDecoration: 'none' }}
          >
            <Icon name="bookmark" size={17} />
            Đã lưu
            {savedCount > 0 && (
              <span
                className="mono inline-grid place-items-center"
                style={{
                  fontSize: 11, fontWeight: 500,
                  background: 'var(--ink)', color: 'var(--bg)',
                  borderRadius: 20, minWidth: 18, height: 18, padding: '0 5px',
                  marginLeft: 2,
                }}
              >
                {savedCount}
              </span>
            )}
          </a>
        </div>
      </nav>
    </>
  )
}
