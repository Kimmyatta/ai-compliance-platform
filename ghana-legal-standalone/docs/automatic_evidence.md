# Automatic Evidence Selection

The default Termination & Cure path now accepts case facts, finds candidate evidence,
shows the selected quotations, and asks for one confirmation of the factual premise.
It does not ask the user to select chunk IDs or silently claim they reviewed reasoning.
Manual evidence review remains available with the original explicit confirmations.
General Analysis remains paused; this does not implement whole-case analysis.

## Selection And Gates

`POST /api/case-analysis/termination/prepare` accepts the selected matter and facts.
It uses the existing scoped keyword retrieval and same-document neighbouring chunks.
Two separate bounded AI calls select a continuous contract quotation and an authority
quotation. Whole candidate passages are budgeted using the existing tokenizer helper;
the preview discloses how many candidates were actually supplied. Facts are not clipped.
The model may abstain. Unknown source IDs, wrong collections, other private matters,
nonmatching quotations and allegation/background/uncertain classifications stop selection.
Statutory text must come from the statute collection, not a quoted statute in a judgment.

A third call assesses the selected quotations' roles in their source passages and
immediate same-document neighbours without
the selectors' reasoning. It must identify an operative agreement term and agree on
court reasoning or statutory text, referencing exact server-supplied excerpts from each quotation.
Disagreement, unclear attribution, invalid structure or invented evidence blocks the
preview. This role-check context is never clipped to fit: an over-budget check stops.
Provider failures do not create a selection or trigger a fallback to unchecked
generation. Existing bounded retry handling remains unchanged; rate limits are not retried.

### Resuming After Rate Limits

Validated contract/authority selections are checkpointed in `evidence_preparations`,
separately from completed previews and reports. On HTTP 429 the server retains completed
stages and the retry deadline. A manual retry after the deadline resumes only unfinished
stages, including after an API restart. A checkpoint is never a usable evidence preview;
the separate role check must still complete before generation is enabled.

Checkpoints expire after 30 minutes and are keyed by matter, exact facts, relevant document
collection, model, input/output budgets, prompts and selection schemas. Selected sources and
same-document context are checked again before reuse. Changed facts, sources, context or
configuration prevent stale reuse. Non-rate-limit validation failures discard the active
checkpoint, except a role-check rejection, which is retained as a blocked review.
Preparations are serialized within this local API process to avoid duplicate concurrent
stage calls. This is not a distributed queue or multi-worker coordination mechanism.

The provider client also honours a process-wide cooldown for all AI tasks after a 429.
`Retry-After` is exposed through CORS; the default analysis UI displays a countdown and
disables its AI buttons until the deadline. It makes no automatic rate-limit retries and
preserves facts and any completed preview. A successful earlier brief does not need to be
extracted again. Rate limits can still recur: checkpointing reduces duplicate work rather
than increasing the account quota. Provider failure bodies are never stored in checkpoints.

This role check uses the same configured model, not an independent legal reviewer.
It can miss allegations, omitted qualifications or prompt injection. Exact quotations
and matching role assessments do not establish applicability, binding authority or
current law. The preview and generated report explicitly carry that limitation.

### Blocked Role Reviews

A role-check rejection now returns structured HTTP 422 detail with the exact selected
quotations and deterministic issue codes. It distinguishes a contract classified as a
party description/uncertain, disagreement about authority attribution, and missing or
nonmatching supporting words. These are AI role/selection failures, not findings that
the library contains no applicable law. The code neither relaxes the checks nor treats
a model failure as proof that an original judgment is defective.

The selected evidence and classification are retained in `evidence_reviews`, not in
completed previews or successful reports. Identical retries return that blocked review
without another provider call, rather than sampling until the model approves. Matter,
source/context, expiry and configuration invalidation still apply. Earlier failures
that predate this change did not retain their individual rejection conditions, so their
exact cause cannot be reconstructed from the old generic error alone.

The UI shows the specific issue and both source quotations. **Review selected passages**
opens the existing manual form with those quotations populated and both confirmations
unchecked. Opening the form calls no AI and approves nothing. Users can inspect original
passages or retrieve alternative candidates through the existing keyword-only controls.
Proceeding still requires explicit facts/contract and authority-reasoning confirmations,
fresh source-scope/quotation checks, atomic generation and the unchanged claim verifier.

The manual request includes `role_review_id`. The server checks the saved review belongs
to that matter, has not expired, and its source/context/collection remains unchanged.
Corrected facts or quotations are recorded explicitly, not falsely attributed to the
original automatic selection. Reports retain original role assessments, flagged evidence,
and `mode: manual_after_role_flag`; earlier flags stay visible and survive verifier-only
retries. A user's confirmation is not independently verified professional identity or
lawyer validation. No role-review ID can be used as an automatic-generation preview ID.

### Exact Excerpt References

The role-check response now selects IDs from server-supplied `quote_parts` instead of
writing its own supporting quotations. Each part is a continuous span of the normalized
selected quotation with code-point offsets and a role-specific ID. Parts partition the
whole quotation in order; surrounding source passages remain available to the classifier.
This is text wrapping, not sentence parsing or a legal interpretation. Selected IDs are
resolved to source text by the server and retained as `role_evidence`. Empty, duplicate,
unknown or wrong-role IDs fail the same evidence gate. Classifying roles as allegations,
background or uncertain still blocks automatic generation.

This change follows an observed formatting failure on the fictional EHL-ECS sample:
both roles were accepted by the model, but its contract basis was the keyword list
`shall investigate, give written notice, allow fourteen days, remedy, termination`,
which was not a continuous quotation. That failed the old text-match check; it did not
establish that the contract or judgment was unsuitable. Returning references avoids
asking the model to reproduce text already held by the server, without accepting that
old keyword list or removing source/role checks. Payloads identify the new format as
`server_quote_parts_v1`; historical blocked records remain unchanged.

On 20 October 2026 a single live recheck of those saved fictional-case quotations
returned `operative_term` and `court_reasoning`, with two contract and three authority
parts resolved correctly and no role-check issues. It generated no report and changed
no existing record. This validates that sample's formatting path, not model reliability,
authority applicability, claim support or legal accuracy. Later claim verification and
positive-comparison withholding remain required.

## Preview And Generation

Selections are stored in a separate additive SQLite table, not as successful reports.
Each record retains exact source snapshots, quotations, role assessments, candidate
coverage, model, version, timestamp, facts/collection fingerprints and a 30-minute expiry.
The preview ID is an opaque record ID, not authentication or an access-control boundary.
The application remains a local single-workspace prototype without user authentication.

`POST /api/case-analysis/termination/automatic` requires that saved ID, the same matter,
unchanged facts and a facts confirmation. Client-supplied quote/role overrides are rejected.
The server checks expiry, current collections, full selected-source snapshots, source roles
and exact quotation membership again. Changed neighbouring context also invalidates it.
A new matter/library document invalidates selection;
uploads to unrelated private matters do not become candidates or invalidate it.

Generation uses the existing atomic-claim and verifier machinery. No automatic selection
is recorded as a human authority confirmation. Report provenance says `mode: ai_selected`
and `human_confirmed: [facts]`. The role-check warning survives verifier-only retries.
Claim-level failures and positive comparison withholding remain unchanged, and readable
reports are still deterministic projections of claims rather than generated narratives.
Existing saved reports are not edited. The original manual API still requires both
human confirmations, and the general-analysis API still returns HTTP 409.

## Verification

Backend tests cover scoped and persistent previews, role disagreement, abstention,
invented quotations/bases, blank facts, expiry, changed documents/facts, client overrides,
provider and budget failure, unchanged history and verifier-only provenance retention.
Browser tests cover one visible confirmation, no passage dropdowns on the default path,
selected-source inspection, role failure, expired previews, facts/matter invalidation,
mobile layout, report warnings, and the unchanged manual workflow.
Additional tests simulate provider 429s to cover cooldown enforcement, browser CORS headers,
manual retries, checkpoint resumption after restart, and refusal to bypass role checks.
Blocked-review tests additionally cover specific reasons, retained candidates without
provider reruns, explicit manual confirmations, source/matter/expiry gates, edited facts
and quotations, report provenance, mobile layout and preserved flags after verification.

The unit and browser tests mock AI responses; they do not measure model accuracy.
`scripts/check_automatic_evidence.py --live` optionally runs a bounded synthetic provider
smoke test in a temporary store: select usable evidence in the presence of an allegation
and separately classify an explicitly attributed counsel submission. It uses no uploaded
private matter documents. Even success is not a reliability estimate or lawyer validation.

The 20 October 2026 smoke check with the configured `openai/gpt-oss-20b` model completed
selection of the usable synthetic reasoning rather than the competing allegation, and
classified the isolated counsel submission as `party_allegation`. This was one tiny
positive/negative pair, not a held-out benchmark or a legal-accuracy measurement.
