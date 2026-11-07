import React, { useEffect, useState } from 'react'
import { createClient } from './client'
import EntryScreen from './EntryScreen'

export default function AccountSession({ children }) {
  const [user, setUser] = useState(null)
  const [busy, setBusy] = useState(true)
  const [notice, setNotice] = useState(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [sessionAttempt, setSessionAttempt] = useState(0)
  const [returnToSignIn, setReturnToSignIn] = useState(false)
  const [api] = useState(() => createClient({ base: import.meta.env.VITE_API_BASE_URL || '', onExpired: () => { setReturnToSignIn(true); setUser(null); setPassword(''); setNotice({ text: 'Your session expired. Sign in again to continue.', error: true }) } }))
  useEffect(() => {
    let active = true
    setBusy(true)
    api.session().then(value => { if (active) { setUser(value); setNotice(null) } }).catch(e => { if (active) setNotice(e.status === 401 ? null : { text: e.message, error: true }) }).finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [api, sessionAttempt])
  const login = async event => {
    event.preventDefault()
    setBusy(true); setNotice(null)
    try { setUser(await api.login(username, password)); setUsername('') }
    catch (e) { setNotice({ text: e.message || 'Unable to sign in. Check your connection.', error: true }) }
    finally { setPassword(''); setBusy(false) }
  }
  const logout = async () => {
    setReturnToSignIn(true)
    setUser(null); setPassword(''); setUsername(''); setBusy(true); setNotice({ text: 'Signing out…' })
    try { await api.logout(); setNotice({ text: 'Signed out. Private case data cleared.' }) }
    catch (e) { setNotice({ text: `Private case data cleared. Server sign-out could not be confirmed: ${e.message}. Retry session to sign out again.`, error: true }) }
    finally { setBusy(false) }
  }
  if (user) return children({ api, user, logout })
  return <EntryScreen focusSignIn={returnToSignIn}>
    <form onSubmit={login} className="login-form" aria-busy={busy}>
      <label>Username<input name="username" autoComplete="username" required maxLength={128} value={username} onChange={e => setUsername(e.target.value)} disabled={busy} /></label>
      <label>Password<input name="password" type="password" autoComplete="current-password" required maxLength={128} value={password} onChange={e => setPassword(e.target.value)} disabled={busy} /></label>
      <button className="primary-btn" disabled={busy}>{busy ? 'Connecting…' : 'Sign in'}</button>
    </form>
    {notice && <p className={notice.error ? 'inline-error' : undefined} role={notice.error ? 'alert' : 'status'}>{notice.text}</p>}
    <button className="ghost-btn" disabled={busy} onClick={() => setSessionAttempt(n => n + 1)}>Retry session</button>
  </EntryScreen>
}

export function CaseList({ api, refreshKey, onSelect, disabled }) {
  const [jobs, setJobs] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let active = true
    setBusy(true); setError('')
    api.request('/api/jobs').then(data => { if (active) setJobs(data.jobs || []) }).catch(e => { if (active && e.name !== 'AbortError') setError(e.message) }).finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [api, refreshKey, attempt])
  return <section className="card cases-panel" aria-busy={busy}>
    <div className="section-heading"><div><h2>Your cases</h2><p>Cases available to your account and reviewer role.</p></div><button className="secondary-btn" disabled={busy} onClick={() => setAttempt(n => n + 1)}>Refresh cases</button></div>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {!busy && !jobs.length && <p>No cases yet. Generate an appeal package to begin.</p>}
    <div className="case-list">{jobs.map(job => <button type="button" className="mode-card" disabled={disabled} key={job.job_id} onClick={() => onSelect(job.job_id)}><strong>{job.case_label || job.case_id || job.job_id}</strong><span>{job.status} · {job.mode}</span><span>{job.job_id}</span></button>)}</div>
  </section>
}
