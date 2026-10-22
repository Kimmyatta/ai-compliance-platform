# Termination Review: First Milestone

Update: new focused reports use the [atomic-claim workflow](atomic_claim_evaluations.md).
The paragraph-format live observations below are historical. General Analysis is paused;
existing reports remain readable. A separate fallible [semantic verifier](claim_verifier.md)
now adds model assessments; it does not certify legal conclusions.

## Scope

One issue only: termination, written notice and opportunity to remedy. This is a
reviewable research draft, not a finding that termination is valid or invalid.
Contract clauses are selected and confirmed by the reviewer. The system does not
claim to extract or interpret the complete agreement automatically.

The evidence endpoint searches the selected matter separately from the legal library.
It includes adjacent chunks from the same document so the reviewer can inspect context.
Keyword ranking does not establish relevance or distinguish submissions from holdings.
The reviewer must select actual court reasoning or statutory text, not allegations.

The comparison endpoint checks each quotation against its original passage and checks
the document role. It rejects another matter's evidence, private files used as law,
paraphrased quotations, unreviewed citation IDs and missing confirmations. The exact
reviewed quotations and confirmed facts are preserved in the saved report. Surrounding
passages are for human review; only the two chosen quotations go to the model.

## Fictional Sample

The fixed evidence fixture is `tests/fixtures/termination_review.json`. Its case facts
are synthetic. The authority quotation was matched to the locally imported Royal
Magma judgment, Page 8. This is an evidence fixture, not an expert-approved legal answer.

Run the local fixture check from the legal app directory:

```powershell
..\venv\Scripts\python.exe scripts/check_termination_sample.py
```

An explicit provider-backed, unsaved diagnostic is available:

```powershell
..\venv\Scripts\python.exe scripts/check_termination_sample.py --live
```

Neither command changes the case documents or saves a report. The live command sends
only this fictional fixture and its public authority quotation to the configured provider.
It consumes provider tokens. It does not certify the generated answer.

## Manual Review Checklist

- Recognise Clause 9's express notice, remedy, access and termination wording.
- Preserve the stated cure period: fourteen days **after receipt**, not dispatch.
- Do not invent a definition of material breach or reasonable access.
- Keep disputed access and alleged defects disputed.
- Distinguish a general statement about termination clauses from a ruling that this
  particular clause is valid, enforceable or complied with.
- Refer to what the selected quotation covers, not what an entire judgment or all
  Ghanaian law does or does not address.
- Do not calculate a binding deadline, decide validity of termination or promise a remedy.
- Treat notice content, service evidence, access and proof of breach as separate
  evidence questions. Do not treat an express quoted condition as missing information.

## Verification And Remaining Limits

Automated tests cover source isolation, adjacent context, exact quotes, review gates,
saved evidence, invalid output and insufficient-authority abstention. Browser tests
cover confirmation reset, quotation rendering, citation inspection and responsive layout.
They do not establish substantive legal accuracy.

Live sample checks no longer omitted the termination clause, but still produced
overbroad statements about express clauses and some confused notice/receipt questions.
A larger-model diagnostic did not eliminate those issues. The configured model was
not changed. The comparison therefore remains an **unverified draft**. A Ghana-qualified
lawyer must review legal support and applicable current law before reliance. Do not
expand to automated remedies or case outcomes on the strength of these tests alone.
