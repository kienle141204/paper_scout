import { useState } from 'react'
import { Icon } from './atoms'
import { authLogin, authRegister } from '../services/api'
import { useLanguage } from '../contexts/LanguageContext'
import { useAuth } from '../contexts/AuthContext'

interface Props {
  onClose: () => void
  initialMode?: 'login' | 'register'
}

export default function AuthModal({ onClose, initialMode = 'login' }: Props) {
  const { t } = useLanguage()
  const auth = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>(initialMode)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const at = t.auth
  const et = t.error

  const validate = () => {
    if (!email.includes('@') || email.length < 5) return et.invalidEmail
    if (password.length < 8) return et.weakPassword
    return null
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const err = validate()
    if (err) { setError(err); return }
    setLoading(true)
    setError(null)
    try {
      if (mode === 'login') {
        const res = await authLogin({ email, password })
        auth.login(res.token, res.user)
      } else {
        const res = await authRegister({ email, password, display_name: name || undefined })
        auth.login(res.token, res.user)
      }
      onClose()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : ''
      if (msg.includes('already') || msg.includes('registered') || msg.includes('exists') || msg.includes('409')) {
        setError(et.emailTaken)
      } else if (msg.includes('invalid') || msg.includes('password') || msg.includes('credentials') || msg.includes('401')) {
        setError(et.auth)
      } else {
        setError(et.unknown)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="card w-full"
        style={{ maxWidth: 400, padding: 32, position: 'relative', boxShadow: '0 20px 60px rgba(0,0,0,0.15)' }}
      >
        <button
          onClick={onClose}
          className="btn btn-ghost btn-sm absolute"
          style={{ top: 16, right: 16, padding: '6px 8px' }}
          aria-label="Close"
        >
          <Icon name="close" size={16} />
        </button>

        <h2 style={{ fontSize: 22, fontWeight: 600, marginBottom: 24, letterSpacing: '-0.01em' }}>
          {mode === 'login' ? at.loginTitle : at.registerTitle}
        </h2>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {mode === 'register' && (
            <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink-2)' }}>{at.nameLabel}</span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={at.namePlaceholder}
                style={{
                  border: '1px solid var(--border-strong)', borderRadius: 7, padding: '9px 12px',
                  fontSize: 14, background: 'var(--surface)', outline: 'none',
                  color: 'var(--ink)',
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--ink-3)' }}
                onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border-strong)' }}
              />
            </label>
          )}

          <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink-2)' }}>{at.emailLabel}</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={at.emailPlaceholder}
              required
              autoComplete="email"
              style={{
                border: '1px solid var(--border-strong)', borderRadius: 7, padding: '9px 12px',
                fontSize: 14, background: 'var(--surface)', outline: 'none', color: 'var(--ink)',
              }}
              onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--ink-3)' }}
              onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border-strong)' }}
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink-2)' }}>{at.passwordLabel}</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={at.passwordPlaceholder}
              required
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              style={{
                border: '1px solid var(--border-strong)', borderRadius: 7, padding: '9px 12px',
                fontSize: 14, background: 'var(--surface)', outline: 'none', color: 'var(--ink)',
              }}
              onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--ink-3)' }}
              onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border-strong)' }}
            />
          </label>

          {error && (
            <div style={{
              background: '#fff5f5', border: '1px solid #fca5a5', borderRadius: 7,
              padding: '9px 12px', fontSize: 13, color: '#dc2626',
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn btn-accent"
            disabled={loading}
            style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}
          >
            {loading
              ? (mode === 'login' ? at.loggingIn : at.registering)
              : (mode === 'login' ? at.loginBtn : at.registerBtn)
            }
          </button>
        </form>

        <div style={{ textAlign: 'center', marginTop: 18 }}>
          <button
            className="btn btn-ghost btn-sm"
            style={{ fontSize: 13, color: 'var(--ink-2)' }}
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null) }}
          >
            {mode === 'login' ? at.switchToRegister : at.switchToLogin}
          </button>
        </div>
      </div>
    </div>
  )
}
