# Retrospective — Contract authoring & polish — 2026-07-21

One session, one arc: make the contract module's **authoring** experience real against a genuine
donor agreement (`2026 June - Donor Student Conditional Agreement v3.docx`). Five increments; the
module stayed behind both OFF flags throughout (`BURSARY_AGREEMENT_ENABLED`,
`AWARD_ACCEPTANCE_ENABLED`) — authoring tools only, nothing user-facing went live.

## What was built

1. **Import fidelity + insert-between + bold/variables** (deployed `4aa67529`)
   - `.docx` import now parses the document's OWN heading/list numbering deterministically
     (`_docx_structure`) instead of flattening to text and letting Gemini guess (which merged
     separate definition items). Gemini kept as the fallback for unstyled docs. Title + preamble
     captured (fill-if-blank).
   - Insert-a-clause-between (`＋`); `**bold**` → `<b>`; `{{variable}}` merge tokens
     (`CONTRACT_VARS` + `substitute_vars`, resolved per student at render, template keeps the token).

2. **Preview / Open-PDF fix — TD-163** (deployed with #3)
   - Root cause: `?format=pdf` collided with DRF's reserved `format` content-negotiation param →
     `Http404` before the view ran. Selector → `?output=pdf`; popup-blocker fix; preview render
     aligned to the signed agreement; distinct `pdfFailed` message. TD-163 RESOLVED.

3. **Import 500 / empty-upload fix + org-code prefill** (deployed `95d3727b`)
   - `DataError: value too long for varchar(255)` — authors style full sub-clauses as a Word
     Heading (256–539 chars); `_docx_structure` routed them into `heading_*`. Fix: long Heading →
     body at parse time + a `replace_clauses` fold-guard for every write path. Org_admins see their
     org prefilled + locked.

4. **Render polish + counterparty auto-fill + address field** (deployed `e9609e82`)
   - One shared renderer (`render_clauses_html`) for the agreement AND preview; import pre-fills
     counterparty name/NRIC/address from the recital; new `counterparty_address` field (migration
     **0107**, applied migrate-first).

5. **Word-style numbering + hanging indent + editor tidy-up** (**HELD** on
   `fix/contract-authoring-polish2`, `9edaccca` — owner deferred the deploy)
   - Numbering `1.` / `1.1.` / `I.` (Word style); hanging-indent table render; import swaps the
     literal donor name → `{{donor_name}}`; editor: note folded into the hint, B/＋Variable moved to
     the bottom row, empty heading/body collapse to `＋ Heading` / `＋ Body` chips.

## What went well

- **Diagnosis before code paid off twice.** TD-163 and the import-500 were both diagnosed to a
  precise root cause (DRF param collision; varchar overflow) using **prod logs + a local repro
  against the real prod data** before touching code — no guessing, no wasted deploys.
- **Worktree isolation held the whole way.** Every increment was built in its own git worktree off
  `origin/main` (node_modules via a junction), so the concurrent agent's parallel sponsor-pool work
  was never disturbed; only `CHANGELOG.md` ever conflicted (trivially).
- **Migrate-first worked cleanly** for `0107`: column + `django_migrations` row applied to prod via
  Supabase and verified BEFORE the code push.

## What went wrong

1. **Open-PDF had never worked in production — and looked like a render bug.**
   - *Symptom:* "Could not render the preview" + Open-PDF wouldn't open; parked as TD-163 blaming
     the font/render.
   - *Root cause:* `?format=pdf` — `format` is DRF's reserved content-negotiation query param, so
     the request 404'd during content negotiation, before the view ran. The PDF branch was dead code.
     The real cause was invisible because the endpoint returned 200 for HTML and only 404 for the PDF
     variant, and no test exercised `?format=pdf`.
   - *Fix / prevention:* renamed to `?output=pdf`; added a regression test asserting `?output=pdf`
     streams a PDF AND `?format=pdf` 404s; captured the trap in `lessons.md`.

2. **The importer 500'd on the first real document (empty upload was worse — it looked like nothing
   happened).**
   - *Symptom:* "Accept and replace clauses" → 500; the create-form upload silently produced an
     EMPTY draft.
   - *Root cause:* `heading_*` is `varchar(255)`, but real authors style full sub-clauses as a Word
     Heading (up to 539 chars); the parser trusted the source to fit, and the create-form path
     swallowed the write error as a soft-fail.
   - *Fix / prevention:* classify long Headings as body + a hard fold-guard at the `replace_clauses`
     choke-point (covers hand-typed / Gemini / copy-from too); lesson recorded (external text
     overflows CharField limits; a soft-failing populate path must surface the error).

3. **The `render_preview_html` shipped in the first pass diverged from the signed agreement.**
   - *Symptom:* the preview didn't escape author text, used flat numbering, and ignored bold/vars —
     so it could corrupt on `&`/`<`/`>` and didn't represent the real document.
   - *Root cause:* it was a separate, simpler renderer written before the hierarchy/bold/variable
     work — a second source of truth for "how a clause looks".
   - *Fix / prevention:* collapsed both onto ONE `render_clauses_html`; the preview is now literally
     the same renderer as the signed doc.

## Design decisions (see `docs/decisions.md`)

- `.docx` import reads Word's own numbering; AI is the fallback, not the parser.
- Merge variables resolve at render time; the template keeps the token.
- Open-PDF selector is `?output=pdf`, never `?format=pdf` (reserved by DRF).
- One shared clause renderer for the agreement + preview; bold only at level 0; Word-style numbering.

## Numbers

- **Increments:** 5 (4 deployed, 1 held pending owner deploy).
- **Migrations:** 1 (`0107_contracttemplate_counterparty_address`, migrate-first).
- **Tests:** 4217 backend (pytest) + jest suite green; new contract tests cover the docx parser +
  fallback, heading-overflow guard, variable substitution + bold, the `?output=pdf` regression, the
  Word numbering, the hanging-indent render, counterparty extraction, and donor→variable on import.
- **Deploys:** 4 (each a single api+web Cloud Build, both SUCCESS); 0 wasted deploys.
- **Flags:** unchanged (OFF) throughout.
