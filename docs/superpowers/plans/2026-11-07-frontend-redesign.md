# InsureClear frontend redesign

The public entry combines the paper wordmark and dark scroll transition from Davide Carusio with the typographic vortex and split composition from The Content Architecture. The private workspace uses the same visual system with compact feedback for case actions.

## Phase 1 — Public entry

- [x] Create a React presentation shell for the current sign-in form and keep native anchor navigation to sign-in and the workflow.
- [x] Build the textured wordmark, scroll-driven dark transition, and concentric type animation with local CSS and SVG. Keep every statement visible in a static layout when reduced motion is requested.
- [x] Keep the preview generic and put all private case reads behind the existing session gate.

## Phase 2 — Private workspace

- [x] Replace the gradient surfaces with paper, ink, ruled panels, and restrained status colors. Retain case setup, status polling, evidence tabs, and review controls.
- [x] Preserve clear focus, disabled controls, readable feedback, and responsive layouts at narrow widths.

## Phase 3 — Verification

- [x] Use verification-before-completion to run the frontend tests and production build.
- [x] Use redesign-existing-projects and emil-design-eng to compare the rendered desktop and mobile entry, exercise the sign-in anchor and keyboard flow, and inspect a synthetic workspace if available.

## Verification record

- The frontend suite passed 16 tests. The new regression test reproduced overlapping anonymous session checks cancelling one another before the fix.
- The Vite production build passed.
- Browser checks covered desktop and narrow phone layouts, the sign-in anchor, the scroll reveal, pause and resume, sign-in and sign-out focus, and the draft review screen with a synthetic reviewer and case. The reduced-motion stylesheet provides the static fallback.
- The visual treatment uses native CSS and SVG within the existing React frontend. Browser workflow checks used a local synthetic API fixture.
