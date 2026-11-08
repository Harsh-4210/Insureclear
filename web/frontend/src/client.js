export class ApiError extends Error {
  constructor(status, detail) {
    const message = typeof detail === 'string' ? detail : JSON.stringify(detail)
    super(status === 401 ? 'Your session expired. Sign in again.' : status === 409 ? `${message || 'Review changed'}. Reload the current revision before trying again.` : message || `Request failed (${status}).`)
    this.status = status
    this.detail = detail
  }
}

export function createClient({ base = '', fetchImpl = (...args) => fetch(...args), onExpired = () => {} } = {}) {
  let csrf = '', generation = 0
  const pending = new Set()
  const clear = () => {
    csrf = ''
    generation++
    for (const controller of pending) controller.abort()
    pending.clear()
  }
  const request = async (path, options = {}) => {
    const epoch = generation
    const { responseType = 'json', ...init } = options
    const method = (init.method || 'GET').toUpperCase()
    const headers = new Headers(init.headers)
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && path !== '/api/auth/login') {
      if (!csrf) throw new ApiError(401, 'Session required')
      headers.set('X-CSRF-Token', csrf)
    }
    const controller = new AbortController()
    pending.add(controller)
    try {
      const response = await fetchImpl(`${base.replace(/\/$/, '')}${path}`, { ...init, method, headers, credentials: 'include', cache: 'no-store', signal: controller.signal })
      if (epoch !== generation) throw new DOMException('Session cleared', 'AbortError')
      if (!response.ok) {
        const body = await response.json().catch(() => ({}))
        if (epoch !== generation) throw new DOMException('Session cleared', 'AbortError')
        const anonymousProbe = path === '/api/auth/session' && !csrf
        if (response.status === 401 && path !== '/api/auth/login' && !anonymousProbe) { clear(); onExpired() }
        if (response.status === 401 && path === '/api/auth/login') throw Object.assign(new Error(body.detail || 'Invalid username or password'), { status: 401 })
        throw new ApiError(response.status, body.detail || 'Unable to complete request')
      }
      const data = await (responseType === 'blob' ? response.blob() : response.json())
      if (epoch !== generation) throw new DOMException('Session cleared', 'AbortError')
      return data
    } finally {
      pending.delete(controller)
    }
  }
  const jsonRequest = (path, method, body) => request(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  const session = async () => {
    const data = await request('/api/auth/session')
    csrf = data.csrf_token
    return data.user
  }
  return {
    request, clear, session,
    async login(username, password) { await jsonRequest('/api/auth/login', 'POST', { username, password }); return session() },
    async logout() { try { await request('/api/auth/logout', { method: 'POST' }) } finally { clear() } },
    saveReview: (id, review, letter, note) => jsonRequest(`/api/jobs/${encodeURIComponent(id)}/review`, 'PUT', { letter, expected_version: review.version, note }),
    decideReview: (id, review, decision, note, checks) => jsonRequest(`/api/jobs/${encodeURIComponent(id)}/review/decision`, 'POST', { expected_version: review.version, decision, note, checks }),
    approvedLetter: id => request(`/api/jobs/${encodeURIComponent(id)}/download/approved-letter`, { responseType: 'blob' }),
  }
}

export function canExportApproved(review, text) {
  return Boolean(review?.status === 'approved' && review.letter === text && review.approval?.version === review.version && review.approval?.letter_sha256 === review.letter_sha256)
}

export function startJobPolling({ load, onJob, onError, schedule = setTimeout, cancel = clearTimeout }) {
  let stopped = false, timer, failures = 0
  const poll = async () => {
    try {
      const job = await load()
      if (stopped) return
      failures = 0
      onError('')
      onJob(job)
      if (['completed', 'failed', 'cancelled', 'timed_out'].includes(job.status)) return
      timer = schedule(poll, 2000)
    } catch (error) {
      if (stopped || error.name === 'AbortError') return
      failures++
      const stop = failures > 3 || (error.status && error.status < 500 && error.status !== 429)
      onError(`${error.message || 'Network unavailable'}. ${stop ? 'Polling stopped. Use Retry updates to reconnect.' : `Retrying updates (${failures}/3).`}`)
      if (!stop) timer = schedule(poll, 2000 * 2 ** (failures - 1))
    }
  }
  poll()
  return () => { stopped = true; cancel(timer) }
}
