# Focused Case Application

Production termination reports now use `focused_references_v2`. This remains a narrow
termination review, not general case analysis, an automated legal opinion or a remedies
recommendation. General Analysis stays paused. Earlier saved reports are not rewritten.

## Source Observations

The generator selects observation IDs and scope, not observation wording or quotations.
The server copies the entire selected source unit into the statement and supporting span.
This retains words such as "in general" and "would typically", receipt triggers and the
original punctuation. A comma cannot silently become a full stop in a copied fact quote.
Fact observations cite the user-confirmed factual premise, not independent documentary
proof. That premise can still contain an extraction error, omission or disputed allegation.

Evidence units partition the complete whitespace/NFC-normalized inputs using punctuation
boundaries. They are citation aids, not a linguistic/legal parser or proof of atomicity.
Abbreviations and compound sentences can still yield imperfect units. Nothing is silently
removed from the model input. Invalid, duplicate, overlong or wrong-role observation IDs
reject generation; invalid application references are retained with visible flags.

## Required Application Topics

The response schema requires all three named records: notice and cure, remedial access,
and material breach. Each record selects evidence-unit IDs and a topic-specific question
code, and labels the selection `aligned_sources` or `evidence_gap`. It cannot write a free
application answer, date calculation or legal conclusion. The server supplies versioned
question wording; quotation text is resolved from the actual evidence, not generated.

An aligned-source record needs contract, confirmed-fact and authority references. These
role/text checks do not establish semantic relevance, compliance, binding effect or
entitlement to relief. A record may remain an evidence gap even with all three roles when
the excerpts do not address the question. The model can still choose a poor question or
align irrelevant passages; the displayed excerpts make that decision inspectable.

All application questions are stored as `not_established`, with `wording_origin:
review_question`. The existing evidence gate marks them insufficient for an affirmative
conclusion; they are not scored as model-verified legal answers. The eligible descriptive
observations still run through the separate AI verifier. A "complete" verifier pass refers
to those eligible observations, not resolution of the application questions. Historical
affirmative cross-source claims still have positive support withheld for lawyer review.

The readable report shows the three topic headings under How They Relate to Your Case,
with the question, inline status and exact contract/facts/authority excerpts. Each item
still belongs to one claim. The report generates no connecting narrative. Possible
Arguments and Next Steps remains explicitly empty when no such claim exists. Verifier
unavailability/partial coverage is visible above the report, not just inside the detailed
supporting-evidence panel.

## Persistence And Verification

Reports retain `claim_format`, source-wording origin, topic, alignment and question code.
A verifier-only retry preserves these fields and invalid-reference flags without model
regeneration. Source observations and question wording are checked again for consistency.
Older atomic reports without this format keep their original text and number of claims;
verification does not add new application topics to historical work.

Generation is still one bounded provider call, followed by the existing verifier, not an
extra narrative or per-topic generation call. Whole-input token limits, provider cooldowns,
draft retention on verifier failure, and the saved-evidence/matter checks remain in place.

## Observed Pilot

The first two-fixture development pilot used a free-text application design labelled
`focused_references_v1`. Its mechanical screens reported zero forbidden patterns, but
inspection exposed a bad inference: the model turned date arithmetic into a conclusion
that the cure period was satisfied. It also produced a receipt-period question with the
wrong direction. One verifier pass was partial after a provider formatting failure.
That design was not enabled in the running app and its artifact is preserved:
`evals/runs/focused-20261021T034621Z-09f0821b.json` (UTC filename).

The revised two-fixture pilot used ID-selected source observations and constrained
review questions. Both fixtures returned all three topics with no reference flags, and
both completed AI assessment of their four descriptive observations. All three questions
per case remained non-conclusions. Its separate artifact is
`evals/runs/focused-20261021T035210Z-ebf80e63.json`. These are development fixtures, not
held-out validation; the earlier failures motivated the redesign. Later question wording
was made more contract-relative rather than assuming receipt is always the trigger.

A bounded read-only run using the existing fictional EHL-ECS report inputs also produced
all three source-linked review topics and completed AI checks for four copied observations.
It preserved the authority's "would typically" wording and did not alter the saved report.
These checks demonstrate the format path, not legal correctness or model reliability.

The eval runner supports `--workflow focused`; older legacy/atomic runs are unchanged.
Every artifact retains its model, prompt and source hash. Mechanical screening and AI
assessment coverage must not be reported as a rate of legally correct case analyses.
