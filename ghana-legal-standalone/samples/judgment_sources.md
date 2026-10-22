# Judgment Candidates for the Sample Contract Dispute

These are real judgment sources identified for research, not a conclusion that any
particular decision governs the fictional cold-storage dispute. Read the full judgments
and check their status and applicability before relying on them.

The three original PDFs were manually downloaded by the user and **imported into the
local test library on 18 October 2026**. They contain 84 PDF pages and produced 127
searchable passages. Case names, dates and courts were checked against the PDFs;
stored-original hashes were checked against the downloaded files. The duplicate Tessu
download was not imported a second time.

The initial direct download had encountered GhaLII's browser-verification page. No
attempt was made to bypass it, and no source snippets were substituted for complete
judgments. Page-cited searches were verified for all three imported decisions.

## 1. Blackchild Co. Ltd v Sekondi-Takoradi Metropolitan Assembly

- Court: High Court, Sekondi
- Date: 23 March 2023
- Suit: E2/15/18
- GhaLII identifier: [2023] GHAHC 557
- Source PDF: https://ghalii.org/akn/gh/judgment/ghahc/2023/557/eng%402023-03-23/source
- Suggested filename: `Blackchild_v_STMA_2023.pdf`
- Research connection: contractual termination, notice and an opportunity to rectify defaults.

## 2. Prophet Emmanuel Tessu v Kodzo Sakah

- Court: District Court, Dzodze
- Date: 13 January 2023
- Suit: A11/07/22
- GhaLII identifier: [2023] GHADC 549
- Source PDF: https://ghalii.org/akn/gh/judgment/ghadc/2023/549/eng%402023-01-13/source
- Suggested filename: `Tessu_v_Sakah_2023.pdf`
- Research connection: disputed repair performance, delay and continuation of a contract.

## 3. Royal Magma Ghana Ltd v Comexas Ltd

- Court: High Court, Commercial Division, Accra
- Date: 15 October 2024
- Suit: CM/RPC/0155/2023
- GhaLII identifier: [2024] GHAHC 472
- Source PDF: https://ghalii.org/akn/gh/judgment/ghahc/2024/472/eng%402024-10-15/source
- Suggested filename: `Royal_Magma_v_Comexas_2024.pdf`
- Research connection: equipment rental, disputed payment terms and termination.

## Getting the Originals

Open the source links in a normal browser and download the complete PDFs where
access and use are permitted. Save the files in Downloads or upload them through
the app as **Legal library / Judgment**, entering the metadata above.

Keep `Sample_Contract_Dispute_Ghana.pdf` in a private matter, not in the judgment
collection. The fictional file is a case to analyse; it is not an authority.

For a fresh local workspace, the verified Downloads copies can be imported again
with the legal API running. From the parent repository root:

```powershell
.\venv\Scripts\python.exe ghana-legal-standalone/scripts/import_downloaded_judgments.py C:\Users\USER\Downloads
```

This imports only the three files described in `judgment_import_manifest.json`,
verifies their hashes/page counts, preserves metadata, and uses the API's existing
duplicate detection. It does not download from or crawl GhaLII. The script requires
`httpx` and `PyMuPDF`, available in the current parent environment.

## Attribution and Use

Provider: Ghana Legal Information Institute (GhaLII), https://ghalii.org/.

Terms: https://ghalii.org/terms-of-use/.

The published general terms describe CC BY-NC 4.0 reuse with attribution, possible
collection-specific/additional conditions, and restrictions on scraping/bulk downloads.
These notes are not commercial-use clearance. Confirm the applicable conditions for
the intended use before importing or distributing the documents. Preserve original
source text and source links; record the basis of permitted use in the upload form.
