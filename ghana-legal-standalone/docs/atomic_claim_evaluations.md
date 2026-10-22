# Atomic Claims And Evaluation Protocol

Update: the separate [claim verifier](claim_verifier.md) is now implemented. The
first-milestone observations below describe the original span-only workflow and pilot;
they are not evidence of the new verifier's accuracy.

## What Changed

The focused termination endpoint now produces a list of short claims rather than
similarity/difference paragraphs. Each claim has a scope and selected evidence spans.
The server assigns claim IDs and document IDs, computes character offsets and checks
whether the selected text occurs in the corresponding reviewed evidence.

Scopes are contract term, confirmed factual premise, general principle in the reviewed
authority, authority's own case, cross-source comparison and unresolved point. A
comparison requires contract and authority spans. Other factual/legal scopes require
the appropriate source role. Model-selected scope and claim atomicity still need review.

Reports preserve canonical evidence texts and Unicode code-point offsets. The browser
highlights the matched words and opens their original source passages. Confirmed facts
are a working premise, not independently verified document evidence.

`evidence_check` is `matched`, `flagged` or `no_evidence`. Invented spans and missing or
wrong roles create flags. Flagged claims are not silently deleted. All claims have
`semantic_status: not_checked`. A real span can accompany an unsupported conclusion.
No claim is labelled legally supported, lawyer-approved or verified by a second model.

General Analysis is paused for new case reports; the API returns 409. Old paragraph
reports remain readable with a warning. Existing documents and reports are not migrated
or rewritten. The research/search workflows are outside this focused milestone.

## Fixtures And Labels

`evals/termination_cases.json` contains 12 synthetic evidence-comprehension cases:
8 development cases and 4 held-out cases. They test receipt versus dispatch, seven versus
fourteen days, written notice, disputed access, undefined materiality, payment conditions,
generality versus approval, allegations versus holdings, unproven receipt, case-specific
outcomes, unrelated authority and unproven loss classification.

Each includes required/forbidden pattern screens and two engineering-annotated probes:
one supported by its supplied evidence and one contradicted or insufficiently evidenced.
These labels are manually authored source-comprehension expectations, not independent
expert validation of Ghanaian law. Future semantic assessment needs lawyer-reviewed labels.

The 24 fixed probes demonstrate a known limitation: all 12 unsupported/contradicted probes
can carry real, correctly role-labelled spans. This is an adversarial construction showing
why matching cannot establish support, not a measured production hallucination rate.

## Running Checks

From `ghana-legal-standalone/`, validate all fixtures offline:

```powershell
..\venv\Scripts\python.exe scripts/run_termination_evals.py --split all
```

Opt-in live runs use only synthetic fixtures and consume provider tokens. By default they
pause 60 seconds between requests. A failed generation is recorded separately from a
screening result. Rate-limit delays are respected; missing outputs are not counted as passes.

```powershell
..\venv\Scripts\python.exe scripts/run_termination_evals.py --live --workflow legacy --limit 2
..\venv\Scripts\python.exe scripts/run_termination_evals.py --live --workflow atomic --limit 2
```

Omit `--limit` to run the full development split. Use `--split holdout` only after freezing
the prompt and evaluation rules; do not tune on held-out results. No live holdout run was
performed in this milestone.

Artifacts are saved under ignored `evals/runs/`. They include fixture hashes, selected IDs,
model, prompts, budgets, output, mechanical screens and generation failures. The previous
paragraph task is frozen in `evals/legacy_termination_prompt.txt` for baseline comparison.
The actual system prompt is retained in each run so changes are auditable.

Rescreen a saved run offline without overwriting it or making provider calls:

```powershell
..\venv\Scripts\python.exe scripts/run_termination_evals.py --rescore evals/runs/RUN.json
```

The rescored artifact preserves prior/current fixture hashes and the original run path.
Use the same fixture revision and case IDs when comparing workflows.

## Initial Pilot: Two Development Cases

Both workflows completed T01 and T02 on the configured GPT-OSS 20B model. After correcting
a screen that mishandled "seven-day", the legacy run missed one required-pattern screen;
the atomic run missed none. Neither run triggered a forbidden-pattern screen. The full
12-case suite was validated offline, not generated live.

This is not evidence of a reliable improvement in legal accuracy: the sample is tiny,
synthetic and unreplicated. The legacy T01 answer abstained, so a missing detail there is
not automatically an incorrect legal assertion. The legacy T02 answer made an inference
towards enforceability that the supplied excerpt did not establish; the lexical screens
did not detect that leap. The atomic T01 output still combined multiple facts in some
claims. Meaning, atomicity and scope remain review tasks.

Original live artifacts:
- `legacy-20261019T161251Z-a4a2a47f.json`
- `atomic-20261019T161417Z-69337883.json`

Corrected offline screen artifacts:
- `legacy-rescore-20261019T161531Z-0b6975ab.json`
- `atomic-rescore-20261019T161533Z-79f24074.json`

## Metrics And Next Gate

Pattern flags and missing required patterns are lexical screens with false positives and
false negatives, including negation, conditional language and paraphrases. They are not
an entailment score. The reports intentionally leave `semantic_accuracy` null.

The separate batched verifier now supplies supported, contradicted and insufficient-evidence
assessments without changing or deleting draft claims. Its annotated-probe evaluation is
documented separately; it does not turn the original lexical screens into semantic scores.
Measure unsupported claims incorrectly accepted, supported claims incorrectly flagged,
abstention and coverage. Generated outputs need additional human labels before those
rates can be calculated. Claim-by-claim lawyer approval and persisted review decisions
are later work, not implied by the existing pre-generation quotation confirmations.
