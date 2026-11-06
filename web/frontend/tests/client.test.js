import test from 'node:test'
import assert from 'node:assert/strict'
const m = await import('../src/client.js').catch(() => ({}))
const json = (data, status = 200) => new Response(JSON.stringify(data), { status })

test('same-origin requests include cookies; CSRF is session-bound and mutation-only', async () => {
  assert.equal(typeof m.createClient, 'function', 'account client exists')
  const calls = []
  const c = m.createClient({ fetchImpl: async (url, options) => {
    calls.push({ url, options })
    return json(url.endsWith('/session') ? { user: { user_id: 'alice', role: 'claimant' }, csrf_token: 'csrf' } : { jobs: [] })
  } })
  await c.session()
  await c.request('/api/jobs')
  await c.request('/api/analyze', { method: 'POST', body: new FormData() })
  assert.equal(calls[0].url, '/api/auth/session')
  calls.forEach(({ options }) => assert.equal(options.credentials, 'include'))
  assert.equal(new Headers(calls[1].options.headers).get('X-CSRF-Token'), null)
  assert.equal(new Headers(calls[2].options.headers).get('X-CSRF-Token'), 'csrf')
  assert.equal(new Headers(calls[2].options.headers).get('Content-Type'), null)
  assert.equal(new Headers(calls[2].options.headers).get('X-API-Key'), null)
})

test('login refreshes session; logout uses then clears CSRF', async () => {
  assert.equal(typeof m.createClient, 'function')
  const calls = []
  const c = m.createClient({ fetchImpl: async (url, options) => {
    calls.push({ url, options }); return json({ user: { user_id: 'alice' }, csrf_token: 'fresh' })
  } })
  await c.login('alice', 'a secure password')
  assert.equal(calls[0].url, '/api/auth/login')
  assert.deepEqual(JSON.parse(calls[0].options.body), { username: 'alice', password: 'a secure password' })
  assert.equal(calls[1].url, '/api/auth/session')
  await c.logout()
  assert.equal(calls[2].url, '/api/auth/logout')
  assert.equal(new Headers(calls[2].options.headers).get('X-CSRF-Token'), 'fresh')
  await assert.rejects(c.request('/api/analyze', { method: 'POST' }), /session/i)
})

test('expired sessions notify UI; cleared clients reject late private data', async () => {
  assert.equal(typeof m.createClient, 'function')
  let expired = 0
  const c = m.createClient({ onExpired: () => expired++, fetchImpl: async () => json({ detail: 'Authentication required' }, 401) })
  await assert.rejects(c.request('/api/jobs'), e => e.status === 401 && /expired/i.test(e.message))
  assert.equal(expired, 1)
  let finish
  const delayed = m.createClient({ fetchImpl: () => new Promise(resolve => { finish = resolve }) })
  const request = delayed.request('/api/jobs')
  delayed.clear()
  finish(json({ jobs: [{ id: 'private' }] }))
  await assert.rejects(request, { name: 'AbortError' })
})

test('stale versions and structured validation issues reach the UI', async () => {
  assert.equal(typeof m.createClient, 'function')
  const c = m.createClient({ fetchImpl: async () => json({ detail: { message: 'Correct evidence', validation: { issues: [{ code: 'unsupported_fact', message: 'Check amount' }] } } }, 422) })
  await assert.rejects(c.request('/api/jobs/x/review'), e => e.status === 422 && /unsupported_fact/.test(e.message) && /Check amount/.test(e.message))
  const stale = m.createClient({ fetchImpl: async () => json({ detail: 'Version changed' }, 409) })
  await assert.rejects(stale.request('/api/jobs/x/review'), e => e.status === 409 && /reload/i.test(e.message))
})

test('edits and decisions send the current server version, never a cached initial version', async () => {
  assert.equal(typeof m.createClient, 'function')
  const calls = []
  const c = m.createClient({ fetchImpl: async (url, options) => {
    if (url.endsWith('/session')) return json({ user: { user_id: 'r', role: 'reviewer' }, csrf_token: 'c' })
    calls.push({ url, method: options.method, body: JSON.parse(options.body) })
    return json({ version: calls.length + 4, letter: 'edited', status: calls.length === 1 ? 'draft' : 'approved' })
  } })
  await c.session()
  const edited = await c.saveReview('job/a', { version: 4 }, 'edited', 'correction')
  assert.equal(edited.version, 5)
  const decided = await c.decideReview('job/a', edited, 'approved', 'checked', { facts_checked: true, coverage_checked: true, legal_checked: true })
  assert.equal(decided.version, 6)
  assert.deepEqual(calls[0], { url: '/api/jobs/job%2Fa/review', method: 'PUT', body: { expected_version: 4, letter: 'edited', note: 'correction' } })
  assert.deepEqual(calls[1].body, { expected_version: 5, decision: 'approved', note: 'checked', checks: { facts_checked: true, coverage_checked: true, legal_checked: true } })
})

test('approved export requires current version/hash and unchanged text', () => {
  assert.equal(typeof m.canExportApproved, 'function')
  const r = { version: 3, status: 'approved', letter: 'Approved', letter_sha256: 'abc', approval: { version: 3, letter_sha256: 'abc' } }
  assert.equal(m.canExportApproved(r, 'Approved'), true)
  assert.equal(m.canExportApproved(r, 'Edited'), false)
  assert.equal(m.canExportApproved({ ...r, version: 4 }, r.letter), false)
  assert.equal(m.canExportApproved({ ...r, status: 'draft' }, r.letter), false)
  assert.equal(m.canExportApproved({ ...r, letter_sha256: 'def' }, r.letter), false)
})

test('approved download uses the server endpoint with exact untouched bytes', async () => {
  assert.equal(typeof m.createClient, 'function')
  const urls = []
  const c = m.createClient({ fetchImpl: async (url, options) => {
    urls.push(url); assert.equal(options.credentials, 'include')
    return new Response('Approved\r\nUnicode: ₹')
  } })
  assert.equal(await (await c.approvedLetter('job-a')).text(), 'Approved\r\nUnicode: ₹')
  assert.deepEqual(urls, ['/api/jobs/job-a/download/approved-letter'])
})

test('poll failures stop visibly after bounded backoff; cancelled jobs never poll again', async () => {
  assert.equal(typeof m.startJobPolling, 'function')
  const pending = [], delays = [], errors = []
  let requests = 0
  const stop = m.startJobPolling({ load: async () => { requests++; throw new Error('Offline') }, onJob: () => {}, onError: msg => errors.push(msg), schedule: (fn, delay) => { pending.push(fn); delays.push(delay); return pending.length }, cancel: () => {} })
  await new Promise(resolve => setImmediate(resolve))
  while (pending.length) { pending.shift()(); await new Promise(resolve => setImmediate(resolve)) }
  assert.equal(requests, 4)
  assert.deepEqual(delays, [2000, 4000, 8000])
  assert.match(errors.at(-1), /stopped/i)
  stop()
  let count = 0
  m.startJobPolling({ load: async () => ({ status: 'cancelled' }), onJob: () => count++, onError: msg => assert.equal(msg, ''), schedule: assert.fail, cancel: () => {} })
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(count, 1)
})


test('failed login displays invalid credentials rather than claiming an expired session', async () => {
  assert.equal(typeof m.createClient, 'function')
  const c = m.createClient({ fetchImpl: async () => json({ detail: 'Invalid username or password' }, 401) })
  await assert.rejects(c.login('alice', 'wrong'), e => /Invalid username or password/.test(e.message) && !/expired/.test(e.message))
})

test('stopping a poll before a late response prevents private updates and scheduling', async () => {
  assert.equal(typeof m.startJobPolling, 'function')
  let finish
  const stop = m.startJobPolling({ load: () => new Promise(resolve => { finish = resolve }), onJob: assert.fail, onError: assert.fail, schedule: assert.fail, cancel: () => {} })
  stop()
  finish({ status: 'running', result: 'private' })
  await new Promise(resolve => setImmediate(resolve))
})

test('timed-out jobs terminate polling without scheduling another request', async () => {
  const delays = []
  const stop = m.startJobPolling({ load: async () => ({ status: 'timed_out' }), onJob: () => {}, onError: () => {}, schedule: (fn, delay) => { delays.push(delay) }, cancel: () => {} })
  await new Promise(resolve => setImmediate(resolve))
  stop()
  assert.deepEqual(delays, [])
})
