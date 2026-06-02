import { Icon } from './atoms'
import type { Screen } from '../types/paper'

interface Props {
  screen: Screen
  savedCount: number
  query: string
  onHome: () => void
  onSaved: () => void
  onChat: () => void
}

export default function NavBar({ screen, savedCount, query, onHome, onSaved, onChat }: Props) {
  const onInner = screen !== 'home'

  return (
    <nav
      className="sticky top-0 z-40 border-b"
      style={{
        background: 'oklch(0.984 0.004 85 / 0.86)',
        backdropFilter: 'saturate(1.4) blur(12px)',
        borderColor: 'var(--border)',
      }}
    >
      <div
        className="w-full mx-auto px-7 flex items-center gap-5"
        style={{ maxWidth: 'var(--maxw)', height: 60 }}
      >
        {/* Wordmark */}
        <button
          className="flex items-center gap-2 select-none flex-none"
          onClick={onHome}
          style={{ cursor: 'pointer' }}
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
        </button>

        {/* Compact search bar on inner pages */}
        {onInner && (
          <button
            onClick={onHome}
            className="flex items-center gap-2"
            style={{
              maxWidth: 360, flex: 1,
              border: '1px solid var(--border-strong)', borderRadius: 8,
              padding: '8px 12px', background: 'var(--surface)',
              cursor: 'text', color: 'var(--ink-2)', fontSize: 13.5,
            }}
          >
            <Icon name="search" size={15} style={{ color: 'var(--ink-3)', flexShrink: 0 }} />
            <span className="overflow-hidden text-ellipsis whitespace-nowrap flex-1 text-left">
              {query || 'Tìm paper…'}
            </span>
          </button>
        )}

        <div className="flex-1" />

        {/* Nav links */}
        <div className="flex items-center gap-1">
          <button
            className={`btn btn-ghost btn-sm${screen === 'home' ? ' bg-s3 text-ink' : ''}`}
            onClick={onHome}
          >
            <Icon name="search" size={15} /> Tìm kiếm
          </button>
          <button
            className={`btn btn-ghost btn-sm${screen === 'chat' ? ' bg-s3 text-ink' : ''}`}
            onClick={onChat}
          >
            <Icon name="chat" size={15} /> Chat AI
          </button>
          <button
            className={`btn btn-ghost btn-sm relative${screen === 'saved' ? ' bg-s3 text-ink' : ''}`}
            onClick={onSaved}
          >
            <Icon name="bookmark" size={15} /> Đã lưu
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
          </button>
        </div>
      </div>
    </nav>
  )
}
