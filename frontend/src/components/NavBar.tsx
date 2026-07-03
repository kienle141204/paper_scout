import { useState, useRef } from 'react'
import { Icon } from './atoms'
import type { Screen } from '../types/paper'
import MobileMenu from './MobileMenu'
import { useLanguage } from '../contexts/LanguageContext'

interface Props {
  screen: Screen
  savedCount: number
  query: string
  onHome: () => void
  onSaved: () => void
  onChat: () => void
  onSearch?: (query: string) => void
  onSettings: () => void
}

function navLink(_href: string, handler: () => void, e: React.MouseEvent) {
  e.preventDefault()
  handler()
}

export default function NavBar({ screen, savedCount, query, onHome, onSaved, onChat, onSearch, onSettings }: Props) {
  const onInner = screen !== 'home'
  const [menuOpen, setMenuOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const { t } = useLanguage()

  const nt = t.nav

  return (
    <>
      <nav
        className="sticky top-0 z-40 border-b"
        style={{
          background: 'oklch(0.984 0.004 85 / 0.86)',
          backdropFilter: 'saturate(1.4) blur(12px)',
          borderColor: 'var(--border)',
        }}
      >
        <div className="w-full mx-auto px-4 sm:px-7 flex items-center gap-3 sm:gap-5 h-[60px] max-w-page">
          {/* Wordmark */}
          <a
            href="/"
            onClick={(e) => navLink('/', onHome, e)}
            className="flex items-center gap-2 select-none flex-none"
            style={{ cursor: 'pointer', textDecoration: 'none' }}
          >
            <span
              className="grid place-items-center flex-none"
              style={{
                width: 26, height: 26, borderRadius: 7,
                background: 'var(--ink)', color: 'var(--bg)',
              }}
            >
              <Icon name="search" size={15} stroke={1.9} />
            </span>
            <span style={{ fontWeight: 600, fontSize: 16.5, letterSpacing: '-0.01em', color: 'var(--ink)' }}>
              Paper<b>Scout</b>
            </span>
          </a>

          {/* Compact search bar on inner pages */}
          {onInner && (
            <form
              className="flex items-center gap-2 flex-1 sm:max-w-[360px]"
              style={{
                border: '1px solid var(--border-strong)', borderRadius: 8,
                padding: '6px 12px', background: 'var(--surface)',
              }}
              onSubmit={(e) => {
                e.preventDefault()
                const val = inputRef.current?.value.trim()
                if (val && onSearch) onSearch(val)
              }}
            >
              <Icon name="search" size={15} style={{ color: 'var(--ink-3)', flexShrink: 0 }} />
              <input
                ref={inputRef}
                type="text"
                defaultValue={query}
                key={query}
                placeholder={nt.searchPlaceholder}
                style={{
                  flex: 1, border: 'none', outline: 'none', background: 'transparent',
                  fontSize: 13.5, color: 'var(--ink)', minWidth: 0,
                }}
              />
            </form>
          )}

          {/* Spacer */}
          <div className={onInner ? 'hidden sm:block sm:flex-1' : 'flex-1'} />

          {/* Nav links — desktop only */}
          <div className="hidden sm:flex items-center gap-1">
            <a
              href="/"
              onClick={(e) => navLink('/', onHome, e)}
              className={`btn btn-ghost btn-sm${screen === 'home' || screen === 'results' ? ' text-ink' : ''}`}
              style={{ textDecoration: 'none' }}
            >
              <Icon name="search" size={15} /> {nt.search}
            </a>
            <a
              href="/chat"
              onClick={(e) => navLink('/chat', onChat, e)}
              className={`btn btn-ghost btn-sm${screen === 'chat' ? ' text-ink' : ''}`}
              style={{ textDecoration: 'none' }}
            >
              <Icon name="chat" size={15} /> {nt.chatAi}
            </a>
            <a
              href="/saved"
              onClick={(e) => navLink('/saved', onSaved, e)}
              className={`btn btn-ghost btn-sm relative${screen === 'saved' ? ' text-ink' : ''}`}
              style={{ textDecoration: 'none' }}
            >
              <Icon name="bookmark" size={15} /> {nt.saved}
              {savedCount > 0 && (
                <span
                  className="mono inline-grid place-items-center"
                  style={{
                    fontSize: 11, fontWeight: 500,
                    background: 'var(--ink)', color: 'var(--bg)',
                    borderRadius: 20, minWidth: 18, height: 18, padding: '0 5px',
                  }}
                >
                  {savedCount}
                </span>
              )}
            </a>

            {/* Settings button */}
            <button
              className="btn btn-ghost btn-sm"
              onClick={onSettings}
              aria-label={nt.settings}
              title={nt.settings}
            >
              <Icon name="settings" size={15} />
            </button>
          </div>

          {/* Hamburger — mobile only */}
          <button
            className="flex sm:hidden btn btn-ghost btn-sm"
            onClick={() => setMenuOpen(true)}
            aria-label={nt.menuOpen}
          >
            <Icon name="menu" size={18} />
          </button>
        </div>
      </nav>

      <MobileMenu
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
        screen={screen}
        savedCount={savedCount}
        onHome={() => { setMenuOpen(false); onHome() }}
        onSaved={() => { setMenuOpen(false); onSaved() }}
        onChat={() => { setMenuOpen(false); onChat() }}
        onSettings={() => { setMenuOpen(false); onSettings() }}
      />
    </>
  )
}
