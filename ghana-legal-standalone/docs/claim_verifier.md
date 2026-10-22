# Separate Claim Verifier

## Contract

The drafting call and verification call use different prompts. The verifier receives
only the exact claims, their scope and selected spans, and the complete reviewed
contract, authority and confirmed factual premise. It does not receive the generator's
reasoning, confidence or a proposed support verdict. Both calls use the configured
model; this is not independent-model or independent-lawyer validation.

The rubric distinguishes:

- `supported`: the reviewed evidence establishes the complete proposition and scope.
- `contradicted`: the relevant evidence expressly states an incompatible proposition.
- `insufficient_evidence`: missing proof, unstated assumptions, outside law, disputed
  allegations, an unsupported scope or any unsupported part of a compound assertion.
- `not_checked`: no usable model assessment was completed or accepted.

An unresolved question is assigned insufficient evidence by an explicit evidence gate,
not attributed to the model. A claim with failed span/role checks is blocked from the
verifier and remains unchecked. All text, including rejected claims, remains visible.

## Validation And Bounds

**Conservative policy:** a model-proposed `supported` verdict on a cross-source
comparison is never accepted automatically. It is retained as an unaccepted proposal,
with `semantic_status: not_checked`, `origin: policy_gate`, and lawyer-review wording.
The raw model verdict and reason remain available for audit and evaluation. This gate
was added after an actual saved draft exposed a false acceptance missed by the initial
synthetic set. It is not a claim that the model learned to reason correctly.

Eligible claims are batched, at most four per call and three logical calls per pass.
Each batch includes the complete reviewed evidence and must fit the configured input
budget; evidence and claims are never silently truncated. The response budget is capped
at 1,800 completion tokens, or the lower configured completion budget.

The response must contain exactly one assessment for each requested claim ID, with no
missing, duplicate or unknown IDs. Supported/contradicted assessments need exact evidence
spans in the appropriate roles; supported comparisons need both contract and authority.
Invented quotes, invalid roles or malformed responses cannot create positive labels.

Provider failures and rate limits leave remaining claims unchecked. No automatic retry
of rate limits occurs; the existing one-retry policy for classified structured-generation
failures remains bounded inside each logical call. The UI distinguishes text matching,
model assessment and unavailable checks, and shows the provider cooldown before retry.

## Saved Reports

### Readable Presentation

Atomic reports now open as an ordinary-headings report. The frontend groups existing
claims by scope: case facts and contract terms under Case Summary, authority principles
and case-specific statements under Relevant Judgments, comparisons under How They Relate
to Your Case, and unresolved points under Uncertainties. The current schema has no
argument or next-step claim scope, so that section explicitly reports no available claims.
No model writes connecting prose, and no claims are rewritten or split into new assertions.
Each displayed statement retains its claim ID internally and exposes the linked source
passages and a direct link to its detailed evidence checks.

Evidence failures, unavailable assessments, insufficient evidence, AI contradiction
assessments and withheld comparisons are marked beside the statement, even when the
supporting-evidence details are closed. Positive labels explicitly remain advisory AI
assessments, not lawyer approval. Historical supported comparisons also remain withheld.
The full claim list, reviewed quotations, confirmed premises and verifier controls are
under Review supporting evidence. Atomic reports never render legacy narrative findings.
Older paragraph-format reports retain their warning and original findings.

This is a deterministic frontend projection, so existing saved atomic reports receive
the presentation without database migration, a server grouping endpoint, regeneration,
or provider calls. Downloaded JSON and stored records remain unchanged. Passage selection,
generation, verification, and the paused general-analysis route are unchanged.

New focused drafts run the verifier after generation. A verifier failure does not erase
the draft or pass it as supported. Saved atomic reports can be checked with **Verify
claims**, without repeating generation. The server revalidates quoted source text and
private-matter scope and recomputes the original span checks before making any model call.

A rerun saves a new report with `verified_from_report_id`; the old record is unchanged.
Stale assessment labels are not carried forward if the new pass fails. Metadata retains
the verifier version, model, rubric hash, evidence/claim input hash, timestamp, coverage,
blocked and unresolved counts, batch attempts, errors/cooldown and cautionary warning.

This is not a lawyer-approval workflow. Neither a supported label nor a complete pass
establishes applicable current law, binding effect, subsequent treatment, valid termination
or entitlement to a remedy. The user must review those questions independently.

## Annotated-Probe Evaluation

The same 12 synthetic fixtures contain 24 engineering-annotated probes, split into
8 development fixtures and 4 previously held-out fixtures. Each has a supported and an
unsupported/contradicted claim. Expected labels are never included in verifier input.
The rubric is fixed before this run; it is not tuned against the held-out results.

From the legal app directory:

```powershell
..\venv\Scripts\python.exe scripts/run_termination_evals.py --live --workflow verifier --split all --interval 60
```

This uses synthetic evidence only, consumes provider tokens and saves an artifact under
ignored `evals/runs/`. The artifact records prompts, fixture and verifier-code hashes,
model, budgets, exact assessments and expected labels. No real client matter is sent by
the evaluation command. Provider errors remain visible, not counted as correct results.

Metrics separately report annotation agreement, assessment coverage, unsupported claims
incorrectly accepted, supported claims flagged/abstained and the confusion matrix.
False-acceptance rates use assessed negative probes and explicitly retain coverage and
unchecked counts, so outages do not masquerade as safety. Lexical screening is not used
to judge these verdicts. These labels test source comprehension, not Ghanaian law.

## Residual Risks

The verifier may repeat the drafter's mistake, misread scope, mistake allegations for
findings, accept an unsupported implication or reject a valid paraphrase. Even exact
verifier evidence does not prove entailment. Synthetic probes are small and deliberately
limited; their results cannot establish production or expert-level legal accuracy.
No content is automatically deleted, accepted as legal advice or lawyer-approved.

## Recorded Results

The frozen first verifier run assessed all 24 probes in the original 12 fixtures,
including the four held-out fixtures. It matched 20/24 exact labels, accepted 0/12
unsupported probes and correctly supported 12/12 supported probes. Four insufficient-
evidence cases were overconfidently called contradicted (disputed access, payment
enforceability, unproven receipt and loss classification). These are errors, not passes.

Artifact: `evals/runs/verifier-20261020T030818Z-19946e37.json`. This result describes
the initial verifier before the cross-source policy gate, not a validated legal system.

A subsequent check of the saved EHL-ECS draft falsely supported claim C5, asserting
that a fourteen-day cure period was consistent with a general statement about termination
clauses. Neither supplied quotation established that legal inference. The original
assessment record was retained, not silently corrected or deleted.

That failure became the post-run regression in `evals/verifier_regressions.json`:

```powershell
..\venv\Scripts\python.exe scripts/run_termination_evals.py --live --workflow verifier --split regression
```

The two-probe regression assessed both claims. The model again accepted the unsupported
comparison (1/1 negative falsely accepted), but the new policy withheld that positive
proposal (0 pipeline acceptances). The correct literal contract claim remained supported.
Artifact: `evals/runs/verifier-20261020T152859Z-dcd0e0e1.json`.

This regression is development evidence from an observed failure, not held-out testing.
It shows why the clean false-acceptance count on the small original set must not be
generalised. Metrics now retain raw-model false acceptances separately from pipeline
outcomes, so the policy gate cannot hide the model's mistakes. Broader lawyer-reviewed
evaluation remains necessary. No further rubric tuning was performed against the held-out run.
