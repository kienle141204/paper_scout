import { useRef, useEffect } from 'react'
import { Icon } from './atoms'
import { useLanguage } from '../contexts/LanguageContext'
import { useAuth } from '../contexts/AuthContext'
import { updateLanguagePref } from '../services/api'

interface Props {
  onClose: () => void
  onOpenAuth: () => void
}

export default function SettingsPanel({ onClose, onOpenAuth }: Props) {
  const { lang, setLang, t } = useLanguage()
  const auth = useAuth()
  const panelRef = useRef<HTMLDivElement>(null)
  const st = t.settings

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  const handleLangChange = async (newLang: 'en' | 'vi') => {
    setLang(newLang)
    if (auth.isLoggedIn && auth.token) {
      try { await updateLanguagePref(auth.token, newLang) } catch { /* silently ignore */ }
    }
  }

  return (
    <div
      className="fixed inset-0 z-50"
      style={{ background: 'rgba(0,0,0,0.2)' }}
    >
      <div
        ref={panelRef}
        className="absolute right-0 top-0 h-full card"
        style={{
          width: 300, borderRadius: '0 0 0 12px', borderRight: 'none', borderTop: 'none',
          padding: '24px 20px', boxShadow: '-8px 0 32px rgba(0,0,0,0.08)',
          display: 'flex', flexDirection: 'column', gap: 24,
          background: 'var(--surface)', overflowY: 'auto',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 16, fontWeight: 600, letterSpacing: '-0.01em' }}>{st.title}</span>
          <button className="btn btn-ghost btn-sm" onClick={onClose} style={{ padding: '6px 8px' }}>
            <Icon name="close" size={16} />
          </button>
        </div>

        {/* Language section */}
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--ink-3)', marginBottom: 10 }}>
            {st.language}
          </div>
          <p style={{ fontSize: 12.5, color: 'var(--ink-3)', marginBottom: 12 }}>{st.languageDesc}</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(['en', 'vi'] as const).map((l) => (
              <button
                key={l}
                onClick={() => handleLangChange(l)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
                  borderRadius: 8, border: '1.5px solid', cursor: 'pointer', textAlign: 'left',
                  background: lang === l ? 'var(--accent-soft)' : 'var(--surface)',
                  borderColor: lang === l ? 'var(--accent-border)' : 'var(--border)',
                  color: lang === l ? 'var(--accent)' : 'var(--ink)',
                  fontWeight: lang === l ? 600 : 400, fontSize: 14,
                  transition: 'all .12s',
                }}
              >
                <span style={{ fontSize: 18 }}>{l === 'en' ? '🇺🇸' : '🇻🇳'}</span>
                <span>{l === 'en' ? st.english : st.vietnamese}</span>
                {lang === l && <Icon name="check" size={14} style={{ marginLeft: 'auto', color: 'var(--accent)' }} />}
              </button>
            ))}
          </div>
        </div>

        {/* Divider */}
        <div style={{ borderTop: '1px solid var(--border)' }} />

        {/* Account section */}
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--ink-3)', marginBottom: 10 }}>
            {st.account}
          </div>
          {auth.isLoggedIn && auth.user ? (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                <div style={{
                  width: 36, height: 36, borderRadius: '50%',
                  background: 'var(--ink)', color: 'var(--bg)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 15, fontWeight: 700, flexShrink: 0,
                }}>
                  {(auth.user.display_name ?? auth.user.email)[0].toUpperCase()}
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {auth.user.display_name ?? auth.user.email}
                  </div>
                  {auth.user.display_name && (
                    <div style={{ fontSize: 12, color: 'var(--ink-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {auth.user.email}
                    </div>
                  )}
                </div>
              </div>
              <button
                className="btn btn-outline btn-sm"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => { auth.logout(); onClose() }}
              >
                {st.logout}
              </button>
            </div>
          ) : (
            <div>
              <p style={{ fontSize: 12.5, color: 'var(--ink-3)', marginBottom: 12, lineHeight: 1.5 }}>{st.loginPrompt}</p>
              <button
                className="btn btn-primary"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={() => { onClose(); onOpenAuth() }}
              >
                <Icon name="user" size={15} /> {st.loginBtn}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
