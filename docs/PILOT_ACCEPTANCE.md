# Private pilot acceptance record

Status: **NOT ACCEPTED**. This checklist records release evidence, not a readiness claim. Local code and deterministic tests do not establish clinical/legal correctness, production capacity, secure hosting or consent. Blank fields and unchecked gates are blockers until their evidence and responsible human are recorded.

## Candidate and evidence

| Record | Value |
|---|---|
| Candidate commit / clean tree identifier | `9cbb2e32ee796430c23d64f1f9ecf4431361ddb7`; candidate source files matched the commit. Two separate draft operations/planning documents were outside the candidate changes. |
| Candidate review owner / date | Local implementation review, 2026-11-07. Operator and expert owners pending. |
| Offline Linux Python 3.11 and 3.13 CI run IDs / results | Local network-disabled Docker runs passed 270 tests on each version. Windows passed 269 with one platform skip. GitHub Actions run IDs remain pending. |
| Frontend npm ci / test / build evidence | 16 tests passed. Connected and Vercel preview builds passed. The preview rendered locally with zero forms, password fields, or file inputs. Node.js 22 image built from the npm lockfile. |
| Dependency audit / unresolved findings | npm audit reported zero vulnerabilities. pip-audit against the Python lockfile reported no known vulnerabilities. Gemini SDK maintenance remains a separate provider gate. |
| Independent security review / resolved regressions | Targeted review covered pre-parse authorization, streamed request limits, error redaction, model role separation, and preview isolation. Found stale review checkpoint reuse; fixed with failing-then-passing regressions. |
| Fresh synthetic run A / manifest digest / strict result | `20261107_201221`, 9/10 verdicts, 0/10 cases with detected unsupported claims, zero execution failures. Strict gate failed. Manifest-set SHA-256 `a72a502fc7048976c61573889e1fc9f0457c2564fe55b9e15d5f1ebb79863ea2`. |
| Fresh synthetic run B / manifest digest / strict result | `20261107_201935`, 9/10 verdicts, 1/10 cases with detected unsupported claims, zero execution failures. Strict gate failed. Manifest-set SHA-256 `a72a502fc7048976c61573889e1fc9f0457c2564fe55b9e15d5f1ebb79863ea2`. |
| Qualified legal and semantic reviewer / date / evidence | Not appointed / not signed |
| Hosting region / operator / budget | Not selected |
| Pilot users / peak arrivals / review turnaround objective | Not agreed |
| Capacity and crash-recovery report | In an isolated no-provider burst, 24 requests yielded 7 unique queued jobs and 17 rate-limited responses. Per-user limits held, a running job was reclaimed, and local admission p95 was 95 ms. Provider-backed concurrent load and queue-to-result capacity remain unmeasured. |
| Deployment authorization / environment / date | Frontend preview requested. Vercel CLI authentication pending. Connected environment, operator decisions, and expert sign-off remain open. |
| Final operator and expert acceptance signatures | Pending |

## Reproducible offline gate

- [x] The candidate commit identifies the reviewed source. Model evaluations record per-case generation source and fixture hashes.
- [ ] GitHub Actions runs full `python -m pytest -q` on Linux Python 3.11 and 3.13, plus `npm ci`, `npm test`, `npm run build` in `web/frontend`, without provider secrets. Record run IDs and failures above.
- [ ] Independent review covers session/Origin/CSRF, cross-user and cross-org access, legacy rows, source/version approval races, deletion fences, cancellation, private errors and budget boundaries. Important findings have RED/GREEN regressions and an integrated suite pass.
- [ ] Record dependency audit findings and dispositions, whitespace checks and explicit staged-path/private-artifact inspection.
- [x] Built both images and passed isolated fresh and upgraded synthetic volume smoke checks, including reopening volumes and reading the approved export. The localhost nginx/FastAPI HTTP smoke also verified anonymous and missing-CSRF denial before upload parsing, authorized multipart intake, no-store case responses, and logout. API image `sha256:9055b1c677a9fc8c218439e5341c818ece71a232e21629d02366b7c923d0759c`. Frontend image `sha256:86ffbe1e64d359ae13ed067f35ca721bfc991713a2e1e94166939553020c8205`.

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

### Current candidate findings

Run A used Groq `openai/gpt-oss-120b` at medium reasoning. It made 84 calls and
reported 300,594 tokens. Mean case time was 41.0 seconds and sequential case
p95 was 58.78 seconds. This is fixture latency. Queue capacity remains unmeasured.

The `c06_hernia_valid` report stated that the cited specific-disease waiting
period was unsatisfied, then imported a hypothetical accident exception from a
different clause and set the verdict to challengeable. The original report and
gold answer remain archived. The earlier run interrupted before this candidate
was finalized is excluded from both strict gates.

Run B used the same model, settings, and manifest set. It made 79 calls and
reported 281,707 tokens. Mean case time was 35.0 seconds and sequential case p95
was 55.37 seconds. The `c08_documents_submitted` policy stage did not receive
the original denial's receipt acknowledgment and treated the document as
missing. The `c03_room_rent` generated draft contained unsupported clause
references and was marked `VALIDATION_ERROR`. Its final sanitizer also
misidentified a wrapped rate comparison as a case-law citation.

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
