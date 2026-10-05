# Grounded-guidance release gates

The public guidance endpoint is disabled by default. Enabling it requires both
`GUIDANCE_API_ENABLED=true` and `GUIDANCE_RELEASE_APPROVED=true`. The second flag
must be set only from a reviewed, passing `guidance_release_gate` report.

A deployment-protected private beta is a separate, temporary risk exception:
`GUIDANCE_API_ENABLED=true`, `GUIDANCE_PRIVATE_BETA_ENABLED=true`, and
`GUIDANCE_RELEASE_APPROVED=false`. The guest-only web app has no user accounts,
so the hosting platform must restrict preview access. The server-only API key
protects the backend but is not browser-user authentication.

## Gate sequence

1. Classification: joint accuracy at least 0.85 and no provider errors.
2. Retrieval: Recall@5 at least 0.80, Precision@5 at least 0.50, abstention
   accuracy 1.0, and no provider errors.
3. Answers: mean faithfulness and citation coverage at least 0.80, helpfulness at
   least 0.75, agency at least 0.80, evidence hit rate and case pass rate at least
   0.80, and no provider errors.
4. Adversarial: all explicit-language, crisis, prompt-injection, diagnosis,
   authority, and fake-citation cases pass.
5. Reliability: deterministic unit, timeout, circuit, cache-outage, concurrency,
   and API load-smoke tests pass.
6. Human review: a named Bhagavad Gita domain reviewer approves the seed labels,
   and security/privacy owners approve provider data handling and retention.

The automated gate is produced with:

```bash
python -m evals.check_release_gates \
  --classification evals/reports/latest.json \
  --retrieval evals/reports/retrieval-latest.json \
  --answers evals/reports/answers-latest.json \
  --adversarial evals/reports/adversarial-latest.json \
  --output evals/reports/guidance-release.json
```

An approved report is necessary but not sufficient for production. The target
environment must separately pass sustained load/soak, alert delivery, secret
rotation, provider SLA, regional privacy, backup, and incident-response checks.

## Latest measured status

`evals/reports/guidance-release.json` is the machine-readable source of truth.
The current report is not approved. Classification and retrieval pass. Answer
helpfulness, evidence hit rate, case pass rate, and the adversarial pass rate fail.
Consequently `GUIDANCE_RELEASE_APPROVED` must remain
false and the public guidance route must remain hidden.
