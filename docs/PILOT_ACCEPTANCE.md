# Private pilot acceptance record

Status: **NOT ACCEPTED**. This checklist records release evidence, not a readiness claim. Local code and deterministic tests do not establish clinical/legal correctness, production capacity, secure hosting or consent. Blank fields and unchecked gates are blockers until their evidence and responsible human are recorded.

## Candidate and evidence

| Record | Value |
|---|---|
| Candidate commit / clean tree identifier | Pending final integration |
| Candidate review owner / date | Pending |
| Offline Linux Python 3.11 and 3.13 CI run IDs / results | Pending execution of candidate workflow |
| Frontend npm ci / test / build evidence | Pending candidate verification |
| Dependency audit / unresolved findings | Pending |
| Independent security review / resolved regressions | Pending |
| Fresh synthetic run A / manifest digest / strict result | Not run for this candidate |
| Fresh synthetic run B / manifest digest / strict result | Not run for this candidate |
| Qualified legal and semantic reviewer / date / evidence | Not appointed / not signed |
| Hosting region / operator / budget | Not selected |
| Pilot users / peak arrivals / review turnaround objective | Not agreed |
| Capacity and crash-recovery report | Not measured for this candidate |
| Deployment authorization / environment / date | Not granted by this document |
| Final operator and expert acceptance signatures | Pending |

## Reproducible offline gate

- [ ] Candidate commit and generation-source hashes identify exactly the reviewed code; no dirty generation files are hidden by an older commit ID.
- [ ] GitHub Actions runs full `python -m pytest -q` on Linux Python 3.11 and 3.13, plus `npm ci`, `npm test`, `npm run build` in `web/frontend`, without provider secrets. Record run IDs and failures above.
- [ ] Independent review covers session/Origin/CSRF, cross-user and cross-org access, legacy rows, source/version approval races, deletion fences, cancellation, private errors and budget boundaries. Important findings have RED/GREEN regressions and an integrated suite pass.
- [ ] Record dependency audit findings and dispositions, whitespace checks and explicit staged-path/private-artifact inspection.
- [ ] Build API/frontend Docker images; smoke-test both fresh and upgraded temporary volumes. Record unavailable tooling as an open blocker.

## Separate operator-run synthetic live gate

Live runs incur provider usage and require the operator's authorization and configured credentials. They are never part of PR CI. Use only fictional repository fixtures and pinned public regulatory sources. Do not submit real patient documents under this gate.

On the final candidate, run the following **twice as separate fresh runs** with the same model/reasoning/budget configuration, without `--resume`, copied reports or checkpoint reuse:

```text
python eval/run_eval.py --min-verdict-accuracy 1 --max-unsupported-claim-rate 0
```

- [ ] Record distinct fresh run IDs, candidate commit, model/reasoning/config, per-report manifests, errors, latency, per-case usage and current-invocation usage for both runs. Preserve failed runs unchanged; never change the gold answer key to pass.
- [ ] Both strict deterministic gates pass; failures remain visible and are triaged. A keyword/verdict pass does not replace expert review.
- [ ] A qualified reviewer compares conclusions and cited evidence across runs rather than requiring identical prose. Check exact policy quotes, offsets, negation, accident exceptions, governing dates/versions, citation applicability, already-supplied documents, supported deadlines, fair valid-denial advice and uncertainty.
- [ ] Record the expert rubric, each case decision, disagreements, corrections and sign-off separately from keyword scores. See [regulatory review checklist](REGULATORY_REVIEW_CHECKLIST.md).

Each newly generated case stores a canonical manifest binding exact denial/policy text hashes, case and answer-key hashes, generation/prompt/source-file hashes, the verified registry fingerprint, model/reasoning and effective generation configuration. `--resume` preflights all selected saved reports before scoring or provider dispatch and refuses missing/changed manifests. Historical reports without manifests remain historical evidence; do not retrofit manifests or overwrite them to qualify a candidate. A correctly matching manifest permits deterministic rescoring with `score_history`; summaries distinguish reused/new cases and usage from this invocation only. These integrity hashes are provenance checks, not digital signatures or legal approval.

## Representative data and capacity gate

- [ ] Obtain appropriate authorization, consent, redaction and provider/data-handling decisions before any real representative input is used externally.
- [ ] Qualified humans review representative long documents with late clauses, scans/OCR, multilingual wording and ambiguous/contradictory evidence. Record failures and coverage limits; short synthetic fixtures cannot satisfy this gate.
- [ ] Agree peak users/arrival rates and provider quotas; measure queue-to-result p95, errors, retries, stage latency/tokens and human-review turnaround under that load.
- [ ] Demonstrate burst admission, worker crashes/recovery, duplicate-effect prevention, cooperative cancellation and retention/deletion races with synthetic temporary fixtures.
- [ ] Meet agreed pilot thresholds. Plan targets are p95 queue-to-result below 90 seconds, execution failures below 1%, and no duplicate effects; unmet or unmeasured targets remain open. In-flight synchronous calls may finish before cancellation is observed.

## Environment and human sign-off gate

- [ ] Operator selects hosting region/budget, retention, account/reviewer roles, expected load and support/incident owners.
- [ ] Qualified reviewers sign governing legal applicability, data/consent/provider handling and scope limitations; coding agents cannot supply these signatures.
- [ ] Establish and verify actual encrypted storage/backups, restricted filesystem permissions, least-privilege secrets, HTTPS, restore drill, alerts and incident/rollback runbook. Private local paths alone do not establish encryption.
- [ ] Provision named accounts through the hidden-prompt CLI; verify HTTPS Secure cookies, exact Origin/CSRF, cross-account denial and exact current approved export. Keep legacy/local Streamlit and CLI inaccessible publicly.
- [ ] Receive explicit authorization before provisioning or public/private deployment, then run environment smoke tests and a limited monitored pilot.
- [ ] Operator and qualified reviewer sign this record against the final candidate and archived evidence. Any failed gate blocks acceptance; no automatic insurer submission is authorized.
