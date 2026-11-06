# Evidence foundations implementation result

Date: 2026-11-06. Branch: `codex/evidence-foundations`.
Existing local HEAD: `14ee15f`; final corrections and this report remain in the
working tree. No push, merge or deployment was performed in this completion pass.

## Implemented behavior

- Deterministic document chunks preserve exact source offsets. Conservative
  UTF-8 byte bounds include scaffolding, output, JSON instructions and provider
  reasoning reserves. Omitted coverage is visible; complete inputs remain
  available for case evidence checks.
- Three official public regulatory artifacts are pinned outside mutable data in
  `resources/regulatory`. Nine health-circular excerpts are currently curated;
  the other two documents are catalogued and integrity checked, not fully curated.
- Writer, Judge and final validator share selected primary evidence. Provenance
  links require exact curated quotes and a compatible instrument type; citation
  identity/page/hash are assigned by code rather than a model.
- Source provenance never automatically approves a legal interpretation.
  Incomplete coverage or legal applicability requires review. Failed final
  evidence produces `VALIDATION_ERROR`; otherwise applicable approval is capped
  at `REVIEW_REQUIRED`, preserving `REVISE`.
- CLI, FastAPI and active Streamlit use the shared pipeline. Real Streamlit app
  tests verify the effective review/error result instead of raw Judge approval.
- Checkpoints bind input text, context budgets and registry versions. Direct agent
  calls also bind facts/evidence; revised and sanitized drafts retain cache identity.
- Immutable corpus updates remain visible with an existing Docker data volume.
  Build contexts exclude environment files, host dependencies and private outputs.
- The bounded official-source importer creates candidates without automatic rule
  activation. Evaluation reconstructs support from pinned excerpts and re-scores
  saved reports without provider calls, preserving prior scores and usage scope.

## Automated verification

**120 tests passed** with:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --tb=short --show-capture=no
```

Coverage includes source integrity, long/Unicode inputs, clause aliases and dates,
provider budgets/retry bounds, cache identity, worker ownership/takeover,
Docker-volume simulation, active Streamlit and evaluation resume behavior.
Provider calls are mocked in automated tests. The frontend production build also
passed after the review UI changes; frontend source did not change afterward.

The final three scorer/fixture regressions were observed failing, then all eleven
scorer tests and the full 120-test suite passed. No full Docker image build,
cloud load test or production traffic test was performed. Registry checks verify
publisher-host provenance, file headers and pinned bytes, not PDF digital signatures.

## Live results and provenance

| Result set | Verdicts | Extraction | Tracked letter facts | Keyword argument hits | Detected unsupported claims | Mean runtime |
|---|---|---|---|---|---|---|
| Historical `sp_base_20261105` | 10/10 | 100% | 97.5% | 5/7 | 0/10 | 37.4s |
| Final cohort `sp_release_20261106` | 10/10 | 100% | 100% | 7/7 | 0/10 | 73.75s |

The final cohort passed the configured strict verdict/evidence gates with no
execution failures. **It is nine unchanged live reports from
`sp_verified_20261106`, reverified and rescored, plus one new live c08 run.**
It is not a second independent ten-case batch or a reproducibility demonstration.
All ten short inputs fit completely; long-input omissions are covered by automated
fixtures rather than these live cases. Effective outcomes: nine `REVIEW_REQUIRED`
and one `REVISE`; none is automatically approved for sending.

The original fresh ten-case run completed with 9/10 verdicts and 6/7 keyword hits.
Its c08 answer expected all required documents to have been submitted, but its
acknowledgment explicitly listed only the claim form and final bill. The missing
summary made the model's original verdict defensible. We preserved that run and
its exact original fixtures, corrected the acknowledgment to include discharge
summary and investigation reports, and reran only c08. **No answer key changed.**
The c04 keyword miss was a Unicode nonbreaking-hyphen formatting mismatch; the
matcher now normalizes equivalent hyphens without changing the gold terms.

The manifests verify byte-identical inputs for the other nine cases, identical
pipeline source hashes and the same registry fingerprint. Copied report bodies
were checked against their originals. Saved scores are rebuilt using the actual
pinned registry rather than generated regulatory text.

Earlier failures remain available: `sp_found_20261105` hit prompt bounds before
compact prompts; `sp_final_20261105` had six DNS failures and normalization/scoring
flags in its four completed cases. They are not passing release baselines.

## Cost and latency

| Scope | Successful provider calls | Reported tokens | Retries | 429s |
|---|---|---|---|---|
| Historical ten-case baseline | 88 | 312888 | 7 | 7 |
| Final ten-report cohort | 83 | 281879 | 5 | 0 |
| New c08 invocation only | 8 | 27799 | 0 | 0 |

Cohort totals difference sequential original cumulative counters per case, exclude
original c08 and add its new run. `summary.json` explicitly counts current-invocation
usage only; `cohort-audit.json` contains full-set totals. Provider usage can omit
unreported failed-attempt tokens, so this is not a billing reconciliation.

Mean cohort runtime is 73.75s; nearest-rank sample p95 is **147.48s** (the maximum
of ten observations). The below-90s target is **not met**. Provider conditions,
revisions and corrected input differ, so these runs do not isolate retrieval's
performance effect. No sustained capacity or cost-saving claim follows.

## Remaining quality and release limits

The scorer checks verdicts, six extraction fields, four letter identifiers,
keyword presence and deterministic evidence errors. It does not grade every
statement or prove a persuasive appeal. Manual inspection found concrete gaps:

- c04 asks for day-care wording already present in the policy; its keyword hit
  does not establish that the main contractual argument was made well.
- c08's intermediate waiting-period explanation reverses the accident exception.
  Its final letter also contains generic sanitized references and legal assertions
  needing review. Correct verdict and identifiers do not make that reasoning correct.
- Generated letters still request 15-day responses despite removal of fixed legal
  deadlines from prompts; the scorer does not establish that these are valid legal
  deadlines. Requested response times must not be presented as verified entitlements.

These remain production quality work under the approved mandatory-human-review
boundary. The initial registry is not comprehensive; governing dates and versions
need qualified review. There is no curated case-law corpus or automatic legal
rules engine. Real/OCR/long-document, multilingual, burst and repeat-run evaluations
remain necessary before release. Human review must precede sending an appeal.

## Implementation decisions and risks

These are the implementation ledger's rulings, in order:

1. Preserve earlier review fixes in the existing checkout and use a local Codex
   branch. Cost if wrong: scopes are harder to disentangle; the patch stays reviewable.
2. Treat source provenance separately from case-specific legal applicability.
   Cost: expert review effort remains necessary for every legal interpretation.
3. Give the full-12k-character inclusion test an explicit 32k budget. Cost: that
   fixture does not promise full inclusion under the default 16k bound.
4. Keep caller `regulatory_text` only as an unverified lead/cache input. Cost:
   legitimate unregistered material needs trusted curation before authoritative use.
5. Require an exact curated quote and compatible instrument type to link source
   provenance. Cost: valid paraphrases may remain unverified; semantic truth is unproven.
6. Store immutable corpus under `resources/regulatory`, outside mutable data.
   Cost: operators must rebuild/restart to activate a bundled registry update.
7. Curate printed parent/subclause aliases. Cost: a bad alias could misattribute a
   clause; pinned offset and alias tests help but expert review remains necessary.
8. Correct the internally contradictory c08 fixture and normalize equivalent
   Unicode hyphens, preserving gold answers and old results. Cost: final results
   use a corrected fixture revision and nine reused reports, limiting comparability.
9. Retain the approved human-review boundary rather than claim semantic/legal
   correctness from string-based gates. Cost: unresolved reasoning and drafting
   weaknesses need reviewer edits and a broader expert-scored evaluation.

Independent reviews found trust, prompt-budget, cache, Streamlit and deployment
issues. Important findings were reproduced and fixed with regressions. The first
review stopped at a usage limit; no clean independent approval is claimed. No
separate deferred-minor list was returned. Detailed fixes and rulings are in
`docs/superpowers/implementation-ledger.md`.

## Next scaling work

Start with accounts and case ownership, an actual reviewer approval/edit workflow,
retention/deletion controls and per-case cost/latency telemetry. Then use measured
pilot demand to choose independent workers, PostgreSQL and private object storage.
See `SCALING_ROADMAP.md`. No daily volume, cloud budget or deployment is assumed.

## Local artifacts

- `eval/results/sp_release_20261106/summary.json` and `summary.md`.
- `eval/results/sp_release_20261106/run-context.json` and `cohort-audit.json`.
- `eval/results/sp_verified_20261106/fixture-inputs-original.json` and original reports.

Evaluation outputs remain ignored by Git; this report records the auditable metrics.
