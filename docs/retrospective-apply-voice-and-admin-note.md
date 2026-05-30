# Retrospective — Apply-form first-person voice + admin "Student's note" merge (v2.16.5)

**Date:** 2026-05-30
**Scope:** frontend polish, no migration. Continues the 2.16.x admin/apply pass.

## What Was Built

- **First-person voice across /apply.** Unified the section titles and ownership labels to the student's
  own voice (My Plans, My SPM / STPM Results, Support I'd Like From Us, "…in my household", "Scholarships I
  have applied for or hold") in en/ms/ta. Direct questions still address "you"; the org stays "us".
- **Context-aware Results title.** New `resultsSpm` / `resultsStpm` i18n keys + a `sectionKey()` helper in
  `apply/page.tsx` that swaps the generic "My SPM / STPM Results" for the exam the student actually sat,
  wired into all three render sites (sidebar nav, progress subtitle, card heading).
- **Admin "Student's note" merge.** The two free-text memos (uncertainty_note from Plans + anything_else from
  Support) now share one labelled box on the applicant detail page; the Plans block is nested into the
  Academic card under a divider rather than a standalone card.

## What Went Well

- Caught a pronoun-referent collision *before* implementing: the literal request "Support I'd Like From You"
  would have made "you" mean the org in the title while the questions on the same step use "you" = student.
  Chose "From Us" to keep one referent per pronoun on a single screen, and flagged the alternative to the user
  rather than silently overriding.
- The i18n change was applied with a raw-substring script that preserved CRLF + Tamil UTF-8, and parity was
  re-asserted (1498 × en/ms/ta) immediately after — no drift.

## What Went Wrong

1. **A prior instance crashed mid-task on a thinking-block API error, leaving the page.tsx wiring unfinished
   while the i18n edits were already on disk.**
   - *Why:* the crash was a harness/transport error (`thinking blocks in the latest assistant message cannot
     be modified`), unrelated to the work — but it left the working tree in a half-applied state (i18n keys
     added, `sectionKey()` not yet wired), which could read as "done" to a careless resumer.
   - *Fix:* on resume, re-derive state from disk (parity check + grep for the new keys' usage) before
     assuming anything is finished — done here, and it surfaced the unfinished wiring + an unrelated
     uncommitted admin-page change that belonged to the same sprint.

2. **Windows console (cp1252) repeatedly choked when printing Tamil from inline `python -c`.**
   - *Why:* default stdout encoding is cp1252; Tamil code points have no mapping → `UnicodeEncodeError`,
     and one attempt to write `/tmp/...` silently failed (no `/tmp` on Windows).
   - *Fix:* set `PYTHONIOENCODING=utf-8` for any script that prints non-Latin text; for file dumps use a
     real workspace path, never `/tmp`. (Recurring enough to be worth a lesson.)

## Design Decisions

- **"Support I'd Like From Us", not "From You".** One referent per pronoun on a screen beats a literal match
  to the request. (See lessons.md.)
- **A `sectionKey()` indirection rather than three inline ternaries.** One helper, used in all three render
  sites, keeps the SPM/STPM branch in one place and self-documents via the comment.

## Numbers

- i18n parity: 1498 × en/ms/ta
- jest: 160 passed
- `tsc --noEmit`: clean on both touched pages (pre-existing test-file errors unrelated)
- `next build`: clean (exit 0)
- Files touched: 5 (apply/page.tsx, admin/[id]/page.tsx, en/ms/ta.json)
