import test from 'node:test'
import assert from 'node:assert/strict'
import { buildSync } from 'esbuild'
import { createRequire } from 'node:module'
let render
try {
  const result = buildSync({ stdin: { contents: `import React from 'react'; import { renderToStaticMarkup } from 'react-dom/server'; import { ReviewView } from './src/ReviewEditor.jsx'; export const render = props => renderToStaticMarkup(React.createElement(ReviewView, props));`, resolveDir: process.cwd(), loader: 'jsx' }, bundle: true, platform: 'node', format: 'cjs', write: false, logLevel: 'silent' })
  const module = { exports: {} }
  new Function('module', 'exports', 'require', result.outputFiles[0].text)(module, module.exports, createRequire(import.meta.url))
  render = module.exports.render
} catch {}
const base = { review: { version: 2, status: 'draft', letter: 'Draft', letter_sha256: 'fixture-hash', approval: null, validation: { valid: true }, history: [] }, text: 'Draft', note: '', checks: {}, busy: false, stale: false, user: { role: 'claimant' } }

test('claimants can edit their draft and see validation without reviewer confirmations', () => {
  assert.equal(typeof render, 'function', 'review UI is implemented')
  const html = render({ ...base, review: { ...base.review, validation: { valid: false, errors: [{ category: 'unsupported_amount', value: '₹100', message: 'Verify claim amount' }] } } })
  assert.match(html, /Save draft/)
  assert.match(html, /Verify claim amount/)
  assert.match(html, /unsupported_amount/)
  assert.match(html, /₹100/)
  assert.doesNotMatch(html, /Facts checked|Approve current revision|Request changes/)
})

test('reviewers see three explicit confirmations and disabled approval before checks', () => {
  assert.equal(typeof render, 'function')
  const html = render({ ...base, user: { role: 'reviewer' } })
  assert.match(html, /Facts checked/)
  assert.match(html, /Coverage checked/)
  assert.match(html, /Legal applicability checked/)
  assert.match(html, /disabled=""[^>]*>Approve current revision/)
})

test('stale editor blocks mutations and offers reload; history identifies actor and version', () => {
  assert.equal(typeof render, 'function')
  const html = render({ ...base, text: 'Changed draft', stale: true, review: { ...base.review, history: [{ version: 2, action: 'edit', actor_id: 'alice', created_at: '2026-11-06', note: 'Corrected amount' }] } })
  assert.match(html, /Reload current revision/)
  assert.match(html, /disabled=""[^>]*>Save draft/)
  assert.match(html, /alice/)
  assert.match(html, /Corrected amount/)
})


test('a clean validated reviewer revision enables approval only after all confirmations', () => {
  const checks = { facts_checked: true, coverage_checked: true, legal_checked: true }
  const html = render({ ...base, user: { role: 'reviewer' }, checks })
  assert.doesNotMatch(html, /disabled=""[^>]*>Approve current revision/)
  assert.match(html, />Approve current revision/)
  const invalid = render({ ...base, user: { role: 'reviewer' }, checks, review: { ...base.review, validation: { valid: false, errors: [] } } })
  assert.match(invalid, /disabled=""[^>]*>Approve current revision/)
})
