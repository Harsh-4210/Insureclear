import React, { useEffect, useState } from 'react'
import { canExportApproved } from './client'

const confirmations = [ ['facts_checked', 'Facts checked'], ['coverage_checked', 'Coverage checked'], ['legal_checked', 'Legal applicability checked'] ]

export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function ReviewView({ review, text, note, checks, user, busy, stale, error, message, onText, onNote, onCheck, onSave, onDecision, onReload, onDownload }) {
  const reviewer = ['reviewer', 'admin'].includes(user.role)
  const dirty = text !== review.letter
  const ready = !busy && !stale && !dirty
  const allChecked = confirmations.every(([key]) => checks[key] === true)
  return <div className="detail-card review-editor" aria-busy={busy}>
    <div className="detail-header"><h3>Human review</h3><span className="pill">Version {review.version} · {dirty ? 'unsaved draft' : review.status.replaceAll('_', ' ')}</span></div>
    <p>Generated letters are drafts. Human approval applies only to one saved revision and its source evidence.</p>
    {error && <div className="inline-error" role="alert">{error}</div>}
    {message && <p role="status">{message}</p>}
    <label>Current appeal draft<textarea value={text} maxLength={50000} onChange={e => onText?.(e.target.value)} disabled={busy} /></label>
    <label>Revision or decision note<textarea className="review-note" value={note} maxLength={2000} onChange={e => onNote?.(e.target.value)} disabled={busy} /></label>
    {review.validation && <div className="validation-panel" role="status">
      <strong>{review.validation.valid ? 'Saved revision passes deterministic evidence checks.' : 'Evidence issues require correction.'}</strong>
      {dirty && <p>Save to validate your changes. Checks below describe the saved revision.</p>}
      {(review.validation.errors || []).map((issue, index) => <p key={index}>{typeof issue === 'string' ? issue : `${issue.category || 'issue'}: ${issue.message || JSON.stringify(issue)}${issue.value ? ` (${issue.value})` : ''}`}</p>)}
    </div>}
    <div className="action-row">
      <button type="button" className="primary-btn" onClick={onSave} disabled={busy || stale || !text.trim() || !dirty}>Save draft</button>
      <button type="button" className="secondary-btn" onClick={onReload} disabled={busy}>Reload current revision</button>
      {!stale && canExportApproved(review, text) && <button type="button" className="primary-btn" onClick={onDownload} disabled={busy}>Download approved letter</button>}
    </div>
    {stale && <p role="alert">This revision is stale. Copy any unsaved work before reloading. Reload replaces the editor with the current server revision.</p>}
    {reviewer && <fieldset disabled={busy || stale || dirty} className="review-confirmations">
      <legend>Reviewer confirmations for version {review.version}</legend>
      {confirmations.map(([key, label]) => <label key={key} className="checkbox-row"><input type="checkbox" checked={checks[key] || false} onChange={e => onCheck?.(key, e.target.checked)} />{label}</label>)}
      <div className="action-row">
        <button type="button" className="primary-btn" onClick={() => onDecision?.('approved')} disabled={!ready || !allChecked || !review.validation?.valid}>Approve current revision</button>
        <button type="button" className="secondary-btn" onClick={() => onDecision?.('changes_requested')} disabled={!ready}>Request changes</button>
      </div>
    </fieldset>}
    <details><summary>Revision history ({review.history?.length || 0})</summary>
      {(review.history || []).map(event => <div className="review-event" key={event.version}><strong>Version {event.version} · {event.action}</strong><p>{event.actor_id || 'Generated draft'} · {event.created_at}</p><p>{event.note || 'No note'}</p></div>)}
    </details>
  </div>
}

export default function ReviewEditor({ api, jobId, user }) {
  const [review, setReview] = useState(null)
  const [text, setText] = useState('')
  const [note, setNote] = useState('')
  const [checks, setChecks] = useState({})
  const [busy, setBusy] = useState(false)
  const [stale, setStale] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [reload, setReload] = useState(0)
  const accept = data => { setReview(data); setText(data.letter); setNote(''); setChecks({}); setStale(false) }
  useEffect(() => {
    let active = true
    setBusy(true); setError(''); setMessage('')
    api.request(`/api/jobs/${encodeURIComponent(jobId)}/review`).then(data => { if (active) accept(data) }).catch(e => { if (active && e.name !== 'AbortError') setError(e.message) }).finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [api, jobId, reload])
  const mutate = async operation => {
    setBusy(true); setError(''); setMessage('')
    try { const data = await operation(); accept(data); setMessage(`Saved version ${data.version}: ${data.status.replaceAll('_', ' ')}.`) }
    catch (e) { if (e.name !== 'AbortError') { setError(e.message); if (e.status === 409) { setStale(true); setChecks({}) } } }
    finally { setBusy(false) }
  }
  const download = async () => {
    setBusy(true); setError('')
    try { saveBlob(await api.approvedLetter(jobId), `approved-letter-v${review.version}.txt`) }
    catch (e) { if (e.name !== 'AbortError') { setError(e.message); if (e.status === 409) setStale(true) } }
    finally { setBusy(false) }
  }
  if (!review) return <div className="detail-card"><p role="status">{busy ? 'Loading human review…' : 'Human review unavailable.'}</p>{error && <p role="alert" className="inline-error">{error}</p>}<button className="secondary-btn" disabled={busy} onClick={() => setReload(n => n + 1)}>Retry review</button></div>
  return <ReviewView {...{ review, text, note, checks, user, busy, stale, error, message }} onText={value => { setText(value); setChecks({}); setMessage('') }} onNote={setNote} onCheck={(key, value) => setChecks(current => ({ ...current, [key]: value }))} onSave={() => mutate(() => api.saveReview(jobId, review, text, note))} onDecision={decision => mutate(() => api.decideReview(jobId, review, decision, note, checks))} onReload={() => setReload(n => n + 1)} onDownload={download} />
}
