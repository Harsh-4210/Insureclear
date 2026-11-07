import React, { useEffect, useId, useRef, useState } from 'react'
import './entry.css'

const WORKFLOW = [
  ['Bring the documents.', 'Start with a denial letter and the relevant policy. Upload PDFs, paste text, or open a demo case in the workspace.'],
  ['Trace the evidence.', 'Inspect the policy excerpts and regulatory references alongside the analysis. Check where the case needs more evidence.'],
  ['Review the draft.', 'Edit the appeal and record the review decision before exporting an approved version.'],
]

const RING_LABELS = ['CLAIM DENIAL', 'POLICY TEXT', 'CITED EVIDENCE', 'HUMAN REVIEW']
const RINGS = Array.from({ length: 24 }, (_, index) => {
  const radius = 23 + index * 18
  const label = RING_LABELS[index % RING_LABELS.length]
  const text = (label + ' · ').repeat(Math.max(1, Math.floor(2 * Math.PI * radius / ((label.length + 3) * 8))))
  return { radius, text, track: index % 3 }
})

function Orbit() {
  const id = useId()
  const [paused, setPaused] = useState(false)
  const graphic = useRef(null)

  function setOrbitSpeed(rate) {
    graphic.current?.getAnimations?.({ subtree: true }).forEach(animation => animation.updatePlaybackRate?.(rate))
  }

  return (
    <div className={`entry-orbit${paused ? ' is-paused' : ''}`}>
      <svg ref={graphic} viewBox="-320 -320 640 640" aria-hidden="true" focusable="false">
        <defs>
          {RINGS.map(({ radius }) => (
            <path key={radius} id={`${id}-${radius}`} d={`M ${-radius},0 a ${radius},${radius} 0 1,1 ${2 * radius},0 a ${radius},${radius} 0 1,1 ${-2 * radius},0`} />
          ))}
        </defs>
        {RINGS.map(({ radius }) => <circle key={radius} r={radius} className="orbit-grid" />)}
        {[0, 1, 2].map(track => (
          <g key={track} className={`orbit-track orbit-track-${track}`}>
            {RINGS.filter(ring => ring.track === track).map(({ radius, text }) => (
              <text key={radius}>
                <textPath href={`#${id}-${radius}`} startOffset={`${radius % 36}%`}>{text}</textPath>
              </text>
            ))}
          </g>
        ))}
      </svg>
      <span className="orbit-caption">Fig. 01 / Anatomy of an appeal</span>
      <button className="orbit-toggle" type="button" onClick={() => setPaused(value => !value)}>
        {paused ? 'Play animation' : 'Pause animation'}
      </button>
      <button
        className="orbit-hold"
        type="button"
        disabled={paused}
        onPointerDown={event => {
          if (event.button !== 0) return
          event.currentTarget.setPointerCapture(event.pointerId)
          setOrbitSpeed(5)
        }}
        onLostPointerCapture={() => setOrbitSpeed(1)}
        onKeyDown={event => {
          if (event.key === ' ' || event.key === 'Enter') setOrbitSpeed(5)
        }}
        onKeyUp={() => setOrbitSpeed(1)}
        onBlur={() => setOrbitSpeed(1)}
      >
        Hold to accelerate
      </button>
    </div>
  )
}

export default function EntryScreen({ children, focusSignIn }) {
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
        <a className="entry-button" href="#sign-in">Sign in <span aria-hidden="true">↗</span></a>
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
            <svg className="entry-wordmark" viewBox="0 0 1000 153" preserveAspectRatio="none" aria-hidden="true" focusable="false">
              <text x="0" y="137" textLength="1000" lengthAdjust="spacingAndGlyphs">insureclear</text>
            </svg>
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
            <span className="entry-kicker">02 / Private pilot</span>
            <h2 id="sign-in-title">Sign in to your cases.</h2>
            <p>Use the account provided by your pilot operator.</p>
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
