# Live regression baseline, 2026-11-05

Run: `eval/results/sp_base_20261105`  
Source: local working tree on `443d837`, before retrieval/registry implementation.  
Provider: `groq:openai/gpt-oss-120b`; reasoning effort `medium`.  
Exit status: **0**, configured strict gates passed.

| Measure | Result |
|---|---:|
| Cases completed | 10/10 |
| Extraction accuracy | 100.0% |
| Verdict accuracy | 100.0% |
| Letter-fact accuracy | 97.5% |
| Detected unsupported-claim rate | 0.0% |
| Expected key arguments found | 5/7 |
| Failed cases | 0 |
| Mean Judge score | 0.8 |
| Mean runtime per case | 37.4 s |
| Sample nearest-rank p95 | 59.94 s |
| Provider calls | 88 |
| Reported total tokens | 312,888 |
| Retry events / 429s | 7 / 7 |

Command:

```powershell
.\.venv\Scripts\python.exe -B -u eval\run_eval.py --resume sp_base_20261105 --min-verdict-accuracy 1.0 --max-unsupported-claim-rate 0
```

## Gaps the passing gates do not cover

The configured gates enforce verdict accuracy, unsupported-claim rate and
execution success. They do not enforce perfect letter facts, key argument recall,
Judge approval or production latency. The current run has these remaining gaps:

- Letter-fact misses: `{"c07_cosmetic_valid": ["policyholder"]}`.
- Key-argument misses: `c04_day_care, c05_accident_waiting`.
- Four cases have final Judge scores below 0.75. A completed job is not necessarily
  an approved appeal.
- Ten short synthetic cases are not representative of long/OCR-heavy policies,
  adversarial input, current legal applicability, concurrency or load bursts.
- The p95 figure is a small-sample description, not a production service guarantee.

Keep the answer key independent. Validate whether the detected misses are true
omissions, alternative wording, or a stale legal assumption before changing
prompts or tests. Broader release gates should cover extraction, letter facts,
key-argument recall, coverage and source verification in addition to existing gates.

Full reports and the source digest manifest remain under the ignored evaluation
results directory. This document contains synthetic-case aggregate results only.
