# Retrospective — Contract Module Sprint 4 (admin FE + quiz refactor + Word import)

**Date:** 2026-07-18
**Plan:** `docs/plans/2026-07-18-contract-module-plan.md` (gained the "Stitch
approval" + "Word import" sections after Sprint 3).
**Branch:** `feat/contract-module` (NOT pushed; single deploy at Sprint 5).
**Scope:** Admin FE per the approved Stitch (with the owner's two corrections),
the quiz FE refactor, and the Word import (BE + FE). Behind
`BURSARY_AGREEMENT_ENABLED` (OFF); NO deploy; no migration.

## What Was Built

- **Admin FE** — Contracts card in Administration → Organisation; `admin/contracts`
  list; `admin/contracts/[id]` six-tab editor (`components/contracts/`: ConfigForm,
  ClauseEditor, QuizEditor, ScheduleEditor, TemplatePreview, DeployPanel) + a shared
  `shared.tsx`. Real admin layout ("Administration" active); the schedule editor uses
  real data (RM200, 17-month Jul→Nov two-year grid, total vs award). Client fns in
  `lib/admin-api.ts`.
- **Quiz refactor** — `AwardComprehensionQuiz` fetches from the API, records the pass
  pinned to `template_version`, re-takes on a 409. Static `CHECKPOINTS` deleted (kept
  only the UI chrome); slim component test replaces the guardrail.
- **Word import** — `import-docx` endpoint (`contracts.segment_docx`: python-docx +
  Gemini, mocked in tests) + the FE review-before-accept in ClauseEditor.
- **i18n** — `admin.contracts.*` en/ms/ta (98 leaves) + `admin.administration.contracts`
  + a new parity guard test.

## What Went Well

- **The API-first Sprints 1–3 made the FE thin.** Every page/component is a wrapper
  over an existing, tested endpoint; the Deploy super-only rule the FE enforces is
  the same rule the backend already tested, so the FE gate is belt to the backend's
  braces, not the only line of defence.
- **CHECKPOINTS deletion was verified, not assumed.** A Node one-liner compared the
  8 fixture `quiz_en` questions against the live `CHECKPOINTS.en` before deleting —
  0 missing — so the static content genuinely lives on in the seed fixture.
- **The i18n injection enforced parity at write time.** The Python injector asserts
  `en == ms == ta` key sets before writing, so the three files can't drift; the new
  guard test then pins it in CI.

## What Went Wrong

1. **The environment wiped `node_modules` mid-sprint (twice).** Symptom: jest
   suddenly reported "Module ts-jest not found", then `@babel/types/lib/index.js`
   missing; `ls node_modules` returned 0 entries. Root cause: a disk-cleanup process
   on the low-disk box (the "Pending cleanup" note in MEMORY.md) races long editing
   sessions and prunes `node_modules`. Fix: `npm ci`, and crucially **chain the
   verification into the same command** (`npm ci && npx jest`) so the tests run in
   the window before the cleaner strikes again — a standalone `npx jest` after a
   separate install failed because packages were pruned in between. **System change
   (lesson):** on this box, run FE `npm ci && <jest|next build>` as one chained
   command; a clean `tsc --noEmit` + the chained jest/build is the reliable signal.
2. **The IDE silently reverted an appended block in an open file.** The first
   `cat >> admin-api.ts` of the contract client fns landed (file grew to 1607 lines),
   but a later edit round found the block gone (file back to ~1476) — the IDE had the
   file open with a stale buffer and autosaved over the append. tsc caught it (every
   contract fn "has no exported member"). Fix: re-added via the Edit tool (which the
   IDE respects). **Lesson:** append to a possibly-open file with Edit, not `cat >>`;
   and always tsc after bulk client-fn additions.
3. **`tsc --noEmit` with default flags reported 15 pre-existing test-file errors**
   (Set iteration, index-signature casts) that made my real error hard to spot. Root
   cause: the project needs `--target es2018 --downlevelIteration` (already noted in
   `docs/lessons.md`); plain tsc uses a stricter target. Re-running with the project
   flags gave 0 errors project-wide. Applied the existing lesson rather than adding a
   new one.

## Design Decisions

- **Editor tabs as horizontal tabs in the real admin layout** — the approved Stitch
  mocks drew a full app sidebar; the owner's correction was to drop it and use the
  real admin chrome with "Administration" active. So the six tabs are a horizontal
  bar inside the page, and the layout's `isActive('/admin/administration')` now also
  matches `/admin/contracts` (mirrors the Payments sub-page pattern).
- **Quiz edits save via the clauses PUT, not a per-quiz endpoint** — the quiz payload
  is a field on the clause, so QuizEditor edits the in-memory clause list and saves
  the whole list; `generate-quiz` persists server-side, edits are local until Save.
  No new endpoint for what `replace_clauses` already round-trips.
- **Word import returns a proposal, never mutates** — `import-docx` extracts +
  segments and returns `[{heading, body}]`; the actual replace happens through the
  existing clauses PUT only on the author's confirm. One import path, one write path,
  the reviewed structured clauses stay the single source of truth (brief challenge #1).

## Numbers

- +5 backend tests (import-docx) → **2846 scholarship pytest**; **593 jest** (35
  suites; new i18n guard + quiz component test); `next build` clean; tsc 0 errors;
  org-fence guard green; 0 migration drift. Files: ~14 web (2 pages + 7 components +
  admin-api + api + quiz + i18n×3 + layout + administration) + 4 api (contracts.py,
  views_admin, urls, test) + requirements + the plan doc.
