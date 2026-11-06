import React, { useEffect, useState } from 'react'
import { createClient } from './client'

export default function AccountSession({ children }) {
  const [user, setUser] = useState(null)
  const [busy, setBusy] = useState(true)
  const [notice, setNotice] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [sessionAttempt, setSessionAttempt] = useState(0)
  const [api] = useState(() => createClient({ base: import.meta.env.VITE_API_BASE_URL || '', onExpired: () => { setUser(null); setPassword(''); setNotice('Your session expired. Sign in again to continue.') } }))
  useEffect(() => {
    let active = true
    setBusy(true)
    api.session().then(value => { if (active) { setUser(value); setNotice('') } }).catch(e => { if (active) setNotice(e.status === 401 ? '' : e.message) }).finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [api, sessionAttempt])
  const login = async event => {
    event.preventDefault()
    setBusy(true); setNotice('')
    try { setUser(await api.login(username, password)); setUsername('') }
    catch (e) { setNotice(e.message || 'Unable to sign in. Check your connection.') }
    finally { setPassword(''); setBusy(false) }
  }
  const logout = async () => {
    setUser(null); setPassword(''); setUsername(''); setBusy(true); setNotice('Signing out…')
    try { await api.logout(); setNotice('Signed out. Private case data cleared.') }
    catch (e) { setNotice(`Private case data cleared. Server sign-out could not be confirmed: ${e.message}. Retry session to sign out again.`) }
    finally { setBusy(false) }
  }
  if (user) return children({ api, user, logout })
  return <div className="app-shell"><main className="page-wrap login-wrap"><section className="card input-panel" aria-busy={busy}>
    <div className="eyebrow">InsureClear · Private pilot</div><h1>Sign in to your cases</h1><p>Use the account provided by your pilot operator.</p>
    <form onSubmit={login} className="login-form">
      <label>Username<input name="username" autoComplete="username" required maxLength={128} value={username} onChange={e => setUsername(e.target.value)} disabled={busy} /></label>
      <label>Password<input name="password" type="password" autoComplete="current-password" required maxLength={128} value={password} onChange={e => setPassword(e.target.value)} disabled={busy} /></label>
      <button className="primary-btn" disabled={busy}>{busy ? 'Connecting…' : 'Sign in'}</button>
    </form>
    {notice && <p className="inline-error" role="alert">{notice}</p>}
    <button className="ghost-btn" disabled={busy} onClick={() => setSessionAttempt(n => n + 1)}>Retry session</button>
  </section></main></div>
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
