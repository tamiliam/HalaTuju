# Retrospective — Contract clause hierarchy + upload-at-create

**Date:** 2026-07-19 · Owner-approved (mockup signed off) · Contract module behind the OFF flags
**Plan:** `docs/plans/2026-07-19-clause-hierarchy-plan.md`

## What Was Built
A 3-level clause hierarchy for contract templates + the docx importer surfaced as a create option.
- `ContractClause.level` (0/1/2, migration `0105`, applied migrate-first). Numbering **computed**
  from the `(order, level)` run (`1.` / `1.1` / `i)`), never stored.
- `contracts.clause_numbers` + `normalise_levels` (no-skip rule) as the single source of truth,
  mirrored by `lib/clauseNumbering.ts` (paired jest test).
- Editor: Indent/Outdent + move + live numbers; quiz only on top-level clauses; the quiz prompt now
  covers the whole subtree (clause + descendants).
- Create form "Upload a document" → import (`segment_docx` returns a level per segment) → editor.
- `render_agreement_html` uses computed numbering + indent (preview + signed PDF).

## What Went Well
- **The importer already existed** — this reused `segment_docx`/`import-docx` end-to-end; the new work
  was a `level` field on each segment + surfacing it at create time. Small delta, big UX win.
- **Numbers-are-computed, not stored** avoided a whole class of renumber-on-reorder bugs; the
  no-skip normaliser keeps the tree valid at every edit + save.
- Backend-first with the pure numbering functions unit-tested before wiring meant the FE mirror was a
  1:1 transcription pinned by a shared-fixture test.

## What Went Wrong
- **Stitch failed to generate the editor mockup twice** (~9 min lost across attempts). Root cause:
  Stitch has been unreliable all session (needed retries every prior time too). Fix this time: fell
  back to a **hand-built HTML Artifact mockup** in the real admin style — more precise for a
  numbering-heavy UI anyway, and instant. Systemic note: for exact/precise UI (tables, numbering,
  dense controls) an HTML mockup Artifact is often a better approval vehicle than Stitch's AI
  interpretation; keep it as the standard fallback when Stitch stalls.
- **Left throwaway cruft in two appended tests** (a dead `if False` line + an unused
  `make_deployable`). Root cause: appending a test block via a shell heredoc instead of the editor.
  Caught on read-back before running. Reinforces the existing lesson: write scripted test blocks with
  the editor, not a heredoc.

## Design Decisions
- **Roman at level 3, decimal above** (`1` / `1.1` / `i)`) per the owner — standard legal drafting.
- **Compute numbering in Python and render explicit prefixes** instead of nested `<ol>` — xhtml2pdf
  handles mixed decimal/roman list numbering poorly, so an `<ol>` would have rendered wrong in the PDF.
- **Quiz stays at level 0 and covers the subtree** — the comprehension check is about the whole
  clause's obligations, not a fragment; a sub-clause carrying a quiz flag is dropped at save.

## Numbers
- Tests: scholarship pytest **2907** (+10), jest **611** (+6); `next build` clean.
- Migration `0105` applied migrate-first + verified (16 existing clause rows → level 0).
- One deploy (api + web).
