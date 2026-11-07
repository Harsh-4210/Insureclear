import React, { useEffect, useId, useRef, useState } from 'react'
import './entry.css'

const WORKFLOW = [
  ['Bring the documents.', 'Start with a denial letter and the relevant policy. Upload PDFs, paste text, or open a demo case in the workspace.'],
  ['Trace the evidence.', 'Inspect the policy excerpts and regulatory references alongside the analysis. Check where the case needs more evidence.'],
  ['Review the draft.', 'Edit the appeal and record the review decision before exporting an approved version.'],
]

const RING_LABELS = ['CLAIM DENIAL', 'POLICY TEXT', 'CITED EVIDENCE', 'HUMAN REVIEW']
const RINGS = Array.from({ length: 18 }, (_, index) => {
  const radius = 28 + index * 24
  const label = RING_LABELS[index % RING_LABELS.length]
  const text = (label + ' · ').repeat(Math.max(1, Math.floor(2 * Math.PI * radius / ((label.length + 3) * 8))))
  return { radius, text, track: index % 2 }
})

function Orbit() {
  const id = useId()
  const [paused, setPaused] = useState(false)
  const [boosted, setBoosted] = useState(false)
  const [visible, setVisible] = useState(false)
  const panel = useRef(null)

  useEffect(() => {
    if (!window.IntersectionObserver) {
      setVisible(true)
      return
    }
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting))
    observer.observe(panel.current)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    for (const layer of panel.current.querySelectorAll('.orbit-layer')) {
      for (const animation of layer.getAnimations?.() ?? []) {
        animation.updatePlaybackRate?.(boosted ? 2.5 : 1)
      }
    }
  }, [boosted, visible, paused])

  return (
    <div ref={panel} className={`entry-orbit${visible && !paused ? ' is-running' : ''}`}>
      <svg className="orbit-grid" viewBox="-440 -440 880 880" aria-hidden="true" focusable="false">
        {RINGS.map(({ radius }) => <circle key={radius} r={radius} />)}
      </svg>
      {[0, 1].map(track => (
        <div key={track} className={`orbit-layer orbit-layer-${track}`} aria-hidden="true">
          <svg viewBox="-440 -440 880 880" focusable="false">
            {RINGS.filter(ring => ring.track === track).map(({ radius, text }) => (
              <g key={radius}>
                <path id={`${id}-${radius}`} fill="none" d={`M ${-radius},0 a ${radius},${radius} 0 1,1 ${2 * radius},0 a ${radius},${radius} 0 1,1 ${-2 * radius},0`} />
                <text><textPath href={`#${id}-${radius}`} startOffset={`${radius % 36}%`}>{text}</textPath></text>
              </g>
            ))}
          </svg>
        </div>
      ))}
      <span className="orbit-caption">Fig. 01 / Anatomy of an appeal</span>
      <button className="orbit-toggle" type="button" onClick={() => setPaused(value => !value)}>
        {paused ? 'Play animation' : 'Pause animation'}
      </button>
      <button
        className="orbit-boost"
        type="button"
        aria-pressed={boosted}
        disabled={paused}
        onClick={() => setBoosted(value => !value)}
      >
        Boost rotation
      </button>
    </div>
  )
}

export default function EntryScreen({ children, focusSignIn, preview = false }) {
  const signIn = useRef(null)

  useEffect(() => {
    if (!focusSignIn) return
    signIn.current.focus({ preventScroll: true })
    signIn.current.scrollIntoView({ behavior: 'instant' })
  }, [focusSignIn])
  return (
    <div className="entry">
      <header className="entry-nav">
        <a className="entry-brand" href="#top">insureclear</a>
        <a className="entry-workflow-link" href="#workflow">How it works</a>
        <a className="entry-button" href="#sign-in">{preview ? 'Preview status' : 'Sign in'} <span aria-hidden="true">↗</span></a>
      </header>

      <main id="top">
        <section className="entry-hero">
          <div className="entry-intro">
            <h1>When a health claim is denied.</h1>
            <p>Read the denial against your policy. Follow the evidence. Prepare an appeal for human review.</p>
          </div>
          <div className="entry-masthead">
            <div className="entry-meta">
              <span>Health insurance appeals / India</span>
              <a href="#workflow">Explore the workflow <span aria-hidden="true">↓</span></a>
            </div>
            <div className="entry-wordmark-mask">
              <svg className="entry-wordmark" viewBox="0 0 1000 153" preserveAspectRatio="none" aria-hidden="true" focusable="false">
                <text x="0" y="137" textLength="1000" lengthAdjust="spacingAndGlyphs">insureclear</text>
              </svg>
            </div>
          </div>
        </section>

        <section id="workflow" className="entry-story" aria-labelledby="entry-story-title">
          <div className="entry-shutter" aria-hidden="true">
            {[0, 1, 2, 3, 4].map(index => <span key={index} style={{ '--stripe': index }} />)}
          </div>
          <div className="entry-story-lead">
            <span className="entry-kicker">01 / The review workflow</span>
            <h2 id="entry-story-title">What does your policy say about the denial?</h2>
          </div>
          <ol className="entry-steps">
            {WORKFLOW.map(([title, description], index) => (
              <li key={title}>
                <span className="entry-kicker" aria-hidden="true">0{index + 1}</span>
                <h3>{title}</h3>
                <p>{description}</p>
              </li>
            ))}
          </ol>
        </section>

        <section ref={signIn} id="sign-in" className="entry-access" aria-labelledby="sign-in-title" tabIndex={-1}>
          <div className="entry-access-copy">
            <span className="entry-kicker">{preview ? '02 / Frontend preview' : '02 / Private pilot'}</span>
            <h2 id="sign-in-title">{preview ? 'Explore the pilot interface.' : 'Sign in to your cases.'}</h2>
            <p>{preview
              ? 'This preview shows the public interface. Sign-in and document uploads require a connected private pilot environment.'
              : 'Use the account provided by your pilot operator.'}</p>
            {children}
          </div>
          <Orbit />
        </section>
      </main>
      <footer className="entry-footer">
        <span>InsureClear / Private pilot</span>
        <a href="#top">Back to top <span aria-hidden="true">↑</span></a>
      </footer>
    </div>
  )
}
