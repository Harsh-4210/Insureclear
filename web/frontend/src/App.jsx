import { useEffect, useMemo, useState } from 'react'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')
const API_KEY = import.meta.env.VITE_API_KEY || ''

const apiFetch = (url, options = {}) => fetch(url, {
  ...options,
  headers: {
    ...(options.headers || {}),
    ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
  },
})

const MODES = [
  {
    id: 'demo',
    label: 'Demo case',
    description: 'Run the polished Star Health sample immediately.',
  },
  {
    id: 'text',
    label: 'Paste text',
    description: 'Use copied denial and policy text without OCR.',
  },
  {
    id: 'pdf',
    label: 'Upload PDFs',
    description: 'Submit actual denial and policy PDFs.',
  },
]

const STAGES = [
  { id: 'starting', label: 'Start' },
  { id: 'extracting', label: 'Extract' },
  { id: 'auditor', label: 'Auditor' },
  { id: 'policy_analyst', label: 'Policy' },
  { id: 'irdai_checker', label: 'IRDAI' },
  { id: 'appeal_writer', label: 'Letter' },
  { id: 'judge', label: 'Judge' },
  { id: 'revision', label: 'Revise' },
  { id: 'revision_review', label: 'Re-check' },
  { id: 'complete', label: 'Complete' },
]

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'letter', label: 'Appeal Letter' },
  { id: 'analysis', label: 'Case Analysis' },
  { id: 'irdai', label: 'IRDAI Findings' },
  { id: 'review', label: 'Quality Review' },
  { id: 'report', label: 'Full Report' },
]

function App() {
  const [mode, setMode] = useState('demo')
  const [caseId, setCaseId] = useState('')
  const [freshRun, setFreshRun] = useState(false)
  const [denialText, setDenialText] = useState('')
  const [policyText, setPolicyText] = useState('')
  const [denialFile, setDenialFile] = useState(null)
  const [policyFile, setPolicyFile] = useState(null)
  const [job, setJob] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const result = job?.result ?? null
  const status = job?.status ?? 'idle'
  const progress = typeof job?.progress === 'number' ? job.progress : 0
  const currentStage = job?.stage ?? 'starting'

  const score = result?.pipeline_stats?.final_score ?? null
  const recommendation = result?.pipeline_stats?.final_recommendation ?? null
  const successProbability = result?.irdai_checker?.appeal_pathway?.estimated_success_probability ?? 'unknown'
  const violations = result?.irdai_checker?.potential_insurer_violations ?? []
  const letter = result?.appeal_letter ?? ''
  const reportJson = useMemo(() => JSON.stringify(result ?? {}, null, 2), [result])

  useEffect(() => {
    if (!job?.job_id || ['completed', 'failed'].includes(job.status)) {
      return undefined
    }

    let cancelled = false
    const pollJob = async () => {
      try {
        const response = await apiFetch(`${API_BASE}/api/jobs/${job.job_id}`)
        if (!response.ok) {
          return
        }
        const data = await response.json()
        if (!cancelled) {
          setJob(data)
        }
      } catch {
        // Keep polling silently. The UI should not flicker on transient network failures.
      }
    }

    pollJob()
    const timer = window.setInterval(pollJob, 2000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [job?.job_id, job?.status])

  const visibleStageIndex = STAGES.findIndex((stage) => stage.id === currentStage)

  const submitAnalysis = async () => {
    setError('')
    setIsSubmitting(true)

    try {
      if (mode === 'text' && (!denialText.trim() || !policyText.trim())) {
        throw new Error('Paste both denial and policy text before running the analysis.')
      }

      if (mode === 'pdf' && (!denialFile || !policyFile)) {
        throw new Error('Upload both denial and policy PDFs before running the analysis.')
      }

      const formData = new FormData()
      formData.append('mode', mode)
      formData.append('case_id', caseId.trim())
      formData.append('fresh_run', String(freshRun))

      if (mode === 'text') {
        formData.append('denial_text', denialText)
        formData.append('policy_text', policyText)
      }

      if (mode === 'pdf') {
        formData.append('denial_pdf', denialFile)
        formData.append('policy_pdf', policyFile)
      }

      const response = await apiFetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        body: formData,
      })

      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload.detail || 'Unable to start the analysis job.')
      }

      setJob({
        ...payload,
        progress: 0,
        stage: 'queued',
        message: 'Job queued',
        status: 'queued',
      })
      setActiveTab('overview')
    } catch (submitError) {
      setError(submitError.message || 'Unable to start the analysis job.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const downloadBlob = (filename, content, mimeType) => {
    const blob = new Blob([content], { type: mimeType })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    window.URL.revokeObjectURL(url)
  }

  const renderMetric = (label, value, tone = 'neutral') => (
    <div className={`metric-card ${tone}`}>
      <span>{label}</span>
      <strong>{value ?? '—'}</strong>
    </div>
  )

  const isCompleted = status === 'completed' && result
  const isRunning = ['queued', 'running'].includes(status)
  const stageMessage = job?.message || 'Ready to analyse'

  return (
    <div className="app-shell">
      <div className="aurora aurora-left" />
      <div className="aurora aurora-right" />

      <main className="page-wrap">
        <section className="hero card">
          <div className="hero-copy">
            <div className="eyebrow">InsureClear</div>
            <h1>Premium claim appeal intelligence for Indian health insurance cases.</h1>
            <p>
              Upload denial documents, inspect policy risk, and generate a legally grounded appeal with live pipeline visibility.
            </p>
            <div className="hero-badges">
              <span>IRDAI-cited</span>
              <span>Revision loop</span>
              <span>PDF + text + demo</span>
            </div>
          </div>

          <div className="hero-stats">
            {renderMetric('Pipeline', status.toUpperCase(), status === 'completed' ? 'success' : isRunning ? 'warning' : 'neutral')}
            {renderMetric('Score', score !== null ? `${Math.round(score * 100)}%` : '—', score !== null && score >= 0.75 ? 'success' : 'warning')}
            {renderMetric('Probability', typeof successProbability === 'string' ? successProbability.toUpperCase() : '—', 'neutral')}
          </div>
        </section>

        <section className="layout-grid">
          <section className="card input-panel">
            <div className="section-heading">
              <div>
                <h2>Case setup</h2>
                <p>Choose a mode, then submit the cleanest source material you have.</p>
              </div>
              <span className="pill">API: {API_BASE}</span>
            </div>

            <div className="mode-grid">
              {MODES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`mode-card ${mode === item.id ? 'active' : ''}`}
                  onClick={() => setMode(item.id)}
                >
                  <strong>{item.label}</strong>
                  <span>{item.description}</span>
                </button>
              ))}
            </div>

            <div className="form-grid">
              <label>
                Case ID
                <input
                  type="text"
                  value={caseId}
                  onChange={(event) => setCaseId(event.target.value)}
                  placeholder="Optional: case_001, client-name, etc."
                />
              </label>

              <label className="checkbox-row">
                <input type="checkbox" checked={freshRun} onChange={(event) => setFreshRun(event.target.checked)} />
                <span>Fresh run, ignore existing checkpoints</span>
              </label>
            </div>

            {mode === 'text' && (
              <div className="text-grid">
                <label>
                  Denial text
                  <textarea
                    value={denialText}
                    onChange={(event) => setDenialText(event.target.value)}
                    placeholder="Paste the rejection letter text here"
                  />
                </label>
                <label>
                  Policy text
                  <textarea
                    value={policyText}
                    onChange={(event) => setPolicyText(event.target.value)}
                    placeholder="Paste the relevant policy text here"
                  />
                </label>
              </div>
            )}

            {mode === 'pdf' && (
              <div className="upload-grid">
                <label className="upload-card">
                  <span>Denial PDF</span>
                  <strong>{denialFile ? denialFile.name : 'Choose file'}</strong>
                  <input
                    type="file"
                    accept="application/pdf"
                    onChange={(event) => setDenialFile(event.target.files?.[0] ?? null)}
                  />
                </label>
                <label className="upload-card">
                  <span>Policy PDF</span>
                  <strong>{policyFile ? policyFile.name : 'Choose file'}</strong>
                  <input
                    type="file"
                    accept="application/pdf"
                    onChange={(event) => setPolicyFile(event.target.files?.[0] ?? null)}
                  />
                </label>
              </div>
            )}

            <div className="action-row">
              <button type="button" className="primary-btn" onClick={submitAnalysis} disabled={isSubmitting}>
                {isSubmitting ? 'Submitting…' : 'Generate appeal package'}
              </button>
              <button
                type="button"
                className="secondary-btn"
                onClick={() => {
                  setMode('demo')
                  setCaseId('')
                  setFreshRun(false)
                  setDenialText('')
                  setPolicyText('')
                  setDenialFile(null)
                  setPolicyFile(null)
                  setJob(null)
                  setError('')
                  setActiveTab('overview')
                }}
              >
                Reset
              </button>
            </div>

            {error && <div className="inline-error">{error}</div>}

            <div className="workflow-card">
              <div className="workflow-header">
                <h3>Pipeline status</h3>
                <span>{stageMessage}</span>
              </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${Math.min(Math.max(progress, 0), 100)}%` }} />
              </div>
              <div className="workflow-rail">
                {STAGES.map((stage, index) => {
                  const isActive = stage.id === currentStage
                  const isDone = visibleStageIndex > index || status === 'completed'
                  return (
                    <div key={stage.id} className={`workflow-step ${isActive ? 'active' : ''} ${isDone ? 'done' : ''}`}>
                      <span>{index + 1}</span>
                      <strong>{stage.label}</strong>
                    </div>
                  )
                })}
              </div>
            </div>
          </section>

          <section className="card output-panel">
            <div className="section-heading">
              <div>
                <h2>Live result</h2>
                <p>The interface updates as soon as the backend advances through the pipeline.</p>
              </div>
              <span className={`pill ${status}`}>{status}</span>
            </div>

            {job && (
              <div className="job-summary">
                <div>
                  <span>Job</span>
                  <strong>{job.job_id}</strong>
                </div>
                <div>
                  <span>Case</span>
                  <strong>{job.case_id}</strong>
                </div>
                <div>
                  <span>Mode</span>
                  <strong>{job.mode}</strong>
                </div>
              </div>
            )}

            <div className="tab-row">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {activeTab === 'overview' && (
              <div className="overview-grid">
                <div className="summary-card spotlight">
                  <span>Recommendation</span>
                  <strong>{recommendation ?? 'Awaiting judge output'}</strong>
                </div>
                <div className="summary-card">
                  <span>Quality score</span>
                  <strong>{score !== null ? `${Math.round(score * 100)}%` : '—'}</strong>
                </div>
                <div className="summary-card">
                  <span>Violations found</span>
                  <strong>{violations.length}</strong>
                </div>
                <div className="summary-card">
                  <span>Success probability</span>
                  <strong>{typeof successProbability === 'string' ? successProbability : '—'}</strong>
                </div>

                {result && (
                  <div className="detail-card wide">
                    <h3>Case snapshot</h3>
                    <div className="case-snapshot">
                      <div>
                        <span>Insurer</span>
                        <strong>{result?.auditor?.insurer_name || '—'}</strong>
                      </div>
                      <div>
                        <span>Treatment</span>
                        <strong>{result?.auditor?.treatment_or_procedure || '—'}</strong>
                      </div>
                      <div>
                        <span>Denial reason</span>
                        <strong>{result?.auditor?.denial_reason_category || '—'}</strong>
                      </div>
                      <div>
                        <span>Claim amount</span>
                        <strong>{result?.auditor?.claim_amount || '—'}</strong>
                      </div>
                    </div>
                  </div>
                )}

                {!result && (
                  <div className="empty-state wide">
                    Start a job to see the live pipeline output, scorecard, and download actions here.
                  </div>
                )}
              </div>
            )}

            {activeTab === 'letter' && (
              <div className="detail-card">
                <div className="detail-header">
                  <h3>Appeal letter</h3>
                  {result && (
                    <div className="inline-actions">
                      <button type="button" className="ghost-btn" onClick={() => downloadBlob('appeal_letter.txt', letter, 'text/plain')}>
                        Download TXT
                      </button>
                      <button type="button" className="ghost-btn" onClick={() => downloadBlob('appeal_report.json', reportJson, 'application/json')}>
                        Download JSON
                      </button>
                    </div>
                  )}
                </div>
                <pre className="letter-block">{letter || 'Your generated appeal letter will appear here.'}</pre>
              </div>
            )}

            {activeTab === 'analysis' && (
              <div className="detail-stack">
                <div className="detail-card">
                  <h3>Auditor findings</h3>
                  <div className="key-value-grid">
                    <div><span>Insurer</span><strong>{result?.auditor?.insurer_name || '—'}</strong></div>
                    <div><span>Policy number</span><strong>{result?.auditor?.policy_number || '—'}</strong></div>
                    <div><span>Claim number</span><strong>{result?.auditor?.claim_number || '—'}</strong></div>
                    <div><span>Hospital</span><strong>{result?.auditor?.hospital_name || '—'}</strong></div>
                    <div><span>Claim amount</span><strong>{result?.auditor?.claim_amount || '—'}</strong></div>
                    <div><span>Denial category</span><strong>{result?.auditor?.denial_reason_category || '—'}</strong></div>
                  </div>
                </div>

                <div className="detail-card">
                  <h3>Policy analyst</h3>
                  <p>{result?.policy_analyst?.rejection_validity_explanation || 'Waiting for policy analysis.'}</p>
                  <div className="bullet-list">
                    {(result?.policy_analyst?.strongest_counter_arguments ?? []).map((item) => (
                      <div key={item} className="bullet-item">{item}</div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'irdai' && (
              <div className="detail-stack">
                <div className="detail-card">
                  <h3>Appeal pathway</h3>
                  <div className="key-value-grid">
                    <div><span>First step</span><strong>{result?.irdai_checker?.appeal_pathway?.recommended_first_step || '—'}</strong></div>
                    <div><span>Eligibility</span><strong>{result?.irdai_checker?.appeal_pathway?.ombudsman_eligible ? 'Yes' : 'No'}</strong></div>
                    <div><span>Probability</span><strong>{result?.irdai_checker?.appeal_pathway?.estimated_success_probability || '—'}</strong></div>
                  </div>
                </div>

                <div className="detail-card">
                  <h3>Potential violations</h3>
                  <div className="bullet-list">
                    {violations.length > 0 ? (
                      violations.map((item) => (
                        <div key={item.violation} className="bullet-item">
                          <strong>{item.violation}</strong>
                          <span>{item.regulation_breached}</span>
                        </div>
                      ))
                    ) : (
                      <div className="empty-state">No violations captured yet.</div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'review' && (
              <div className="detail-stack">
                <div className="score-grid">
                  {[
                    ['factual_accuracy', 'Factual accuracy'],
                    ['irdai_citation_quality', 'IRDAI citation quality'],
                    ['argument_strength', 'Argument strength'],
                    ['structure_integrity', 'Structure integrity'],
                  ].map(([key, label]) => {
                    const value = result?.judge?.[key] ?? 0
                    return (
                      <div key={key} className="score-card">
                        <span>{label}</span>
                        <strong>{Math.round(value * 100)}%</strong>
                        <div className="progress-bar small">
                          <div className="progress-fill" style={{ width: `${value * 100}%` }} />
                        </div>
                      </div>
                    )
                  })}
                </div>

                <div className="detail-card">
                  <h3>Judge notes</h3>
                  <div className="bullet-list">
                    {(result?.judge?.missing_elements ?? []).map((item) => (
                      <div key={item} className="bullet-item">Missing: {item}</div>
                    ))}
                    {(result?.judge?.weak_arguments ?? []).map((item) => (
                      <div key={item} className="bullet-item">Weak: {item}</div>
                    ))}
                    {(result?.judge?.hallucination_flags ?? []).map((item) => (
                      <div key={item} className="bullet-item danger">Hallucination: {item}</div>
                    ))}
                    {!result?.judge && <div className="empty-state">Waiting for judge output.</div>}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'report' && (
              <div className="detail-card">
                <h3>Full JSON report</h3>
                <pre className="json-block">{reportJson}</pre>
              </div>
            )}

            {status === 'failed' && (
              <div className="inline-error" style={{ marginTop: 16 }}>
                {job?.error || 'The pipeline failed.'}
                {job?.traceback && <pre className="traceback">{job.traceback}</pre>}
              </div>
            )}

            {isCompleted && (
              <div className="completion-banner">
                <strong>Pipeline complete.</strong>
                <span>Output saved in the backend and ready for download.</span>
              </div>
            )}
          </section>
        </section>
      </main>
    </div>
  )
}

export default App
