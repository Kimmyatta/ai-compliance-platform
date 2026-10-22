# Source-Linked Case Facts

New focused reports use `case_evidence.version = document_facts_v1`. The entered
summary is retained for the audit trail, but is not sent to the claim generator or
verifier as factual proof. Historical reports are not rewritten.

## Proposed Brief

The model selects excerpt IDs, not replacement factual prose. The server resolves
each ID to continuous normalized source text, retains attribution and qualifications,
and returns source links. Unknown or duplicate IDs reject the brief. The model can
still select poorly or omit context. Editing the returned brief does not turn the
edited text into documentary evidence.

## Focused Reports

The server scans up to 40 matter-scoped passages for notice/receipt/cure,
repair/access, material breach, and document-status terms. It selects complete
excerpts round-robin across those groups, capped at 4,500 characters. Excerpts
longer than 700 characters are excluded rather than cut. Exact duplicates on the
same document page are removed; overlapping fragments are replaced only when an
available containing excerpt on that same page preserves the text. Coverage counts
and an incompleteness warning are saved.
This is keyword retrieval, not a legal relevance or completeness assessment.

The claim generator receives that documentary corpus and issue-specific candidate
references. Each facts-role span resolves back to a source passage and source
offsets. A purported alignment using no topic-matching factual reference is flagged.
Each issue also displays its selected documentary excerpts independently of the
model's choices. This exposes receipt dates and disputed repair-access evidence
instead of depending on a lossy entered summary.

Verification still assesses wording and scope, not the underlying truth of an
allegation. The UI distinguishes checking against document wording from checking
against an entered summary. Frozen documentary snapshots are validated against
the current matter before verification-only retries; no new evidence is silently
substituted. Both facts-role evidence and its original source are retained.

## Boundaries

- Source-exact excerpts can still be misleading without context or accurate uploads.
- Punctuation-based units are citation aids, not a linguistic or legal parser.
- Keyword matches cannot establish relevance, chronology, credibility or materiality.
- Dates and access disputes are not automatically resolved into valid termination.
- User-supplied facts absent from the selected documents remain unverified context.
- Substantive arguments and whole-case analysis are not implemented by this change.
