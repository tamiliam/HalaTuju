# Retrospective — org-timing Sprint 1: student message timing becomes an organisation setting (2026-10-07)

Roadmap: `docs/plans/2026-10-07-org-timing-settings-roadmap.md`. Decision: `docs/decisions.md`
2026-10-07. Shipped `5fd333e6` (api `halatuju-api-01112-nbv`, web `halatuju-web-00965-xbg`).

## What Was Built

- **13 new organisation settings** for every scheduled student message: the shortlisted and
  not-shortlisted email delays, the four completion reminders and the auto-close, the time to answer
  questions and its reminder, the reviewer and QC decline holds, the award-email delay and the
  funding-confirmed hold. **10 existing timing ranges narrowed** (5 student, 5 staff).
- **Narrow ranges** near each default (owner: "closer to the default but the org is given some
  flexibility"), never finer than the job that acts on the value, never past the public "within 48
  hours".
- **Rules between timings** (`org_config_rules.RULES`): the interview window plus R1–R7, checked on the
  merged settings; the tab shows the reason under the box to fix.
- **Every read site** follows the application's organisation; the award-email release is a
  per-organisation SQL window (`award_timing.py`).
- **The final reminder keeps its promise** (review F1): reminder 4 stamps the number it stated
  (`final_reminder_close_days`, migration 0170) and the close waits the longer of that and the setting.
- **The defect that started it is gone:** Sabah no longer waits 48 hours by accident; BrightPath stores
  55 minutes for both gifts.
- Refactor first, moves only: `org_config.py` split into registry and rules.

## What Went Well

- The owner's question ("why 48 hours?") was answered from the data (the round row) and the code (the
  create endpoint never set the field) before anything was proposed.
- The design converged in three short owner rounds (organisation not gift; narrow ranges; rules), each
  reflected in the plan before any code.
- The split-first rule kept `sponsorship.py` at 1018 of 1019 lines and `org_config.py` under 600; the
  cross-app import count fell 25 → 20.
- The adversarial review found a real student harm (F1) before the push, and its fix was bite-checked
  three ways.

## What Went Wrong

1. **I told the owner a false rule about when changes take effect.** Symptom: "a new value only affects
   new cases" — the review showed four timings re-read on every sweep, so lowering the auto-close could
   close a student sooner than reminder 4 had promised. Root cause: I generalised from the stamped
   values (decision, decline and award due times) without sorting every read site into "stamped at the
   event" vs "re-read per sweep". System change: lesson added (`docs/lessons.md` 2026-10-07); the
   promised close is now stamped; the manual and the hints say which timings reach those already waiting.
2. **The English message file sits at the bundle line, and the sprint's copy had to be trimmed twice.**
   Symptom: the first build failed the 0.15 kB near-line margin; the review's copy fix had to pay for
   itself by shortening another hint. Root cause: every en.json string ships to every route (TD-360 —
   no per-route catalogue split yet). System change: none new; TD-360 stays the fix, and the CLAUDE.md
   Next Sprint block now warns that the next string needs weight taken off first.
3. **The Sabah 48 hours came from a model default nobody could see.** Symptom: one gift shortlisted in
   55 minutes, the other in 48 hours, by accident, for weeks. Root cause: a behaviour-deciding value
   lived as a column the create endpoint never wrote and no screen showed; the 55 for the flagship was
   set by hand in SQL. System change: the value is now an organisation setting on a screen, with a
   guard test that every default lies in range and passes every rule.

## Design Decisions

- Organisation-level, not gift-level (owner); platform value only as the default behind a blank box.
- Narrow ranges; undo windows never zero; the interview reminders stay fixed (wording and the
  Meta-approved WhatsApp templates state the time).
- Keep the final reminder's promise with a stamped column rather than only warning in copy (owner
  option 1).
- The three intake-round columns are left in place, unread, and dropped in Sprint 2 (expand-contract).

## Review findings and how each was answered

- F1 (lowering a sweep-read timing reaches students already waiting) — fixed (`c1da7f4d`, `2e6c6614`).
- L1 (stale "5-day" assignment hint) — fixed. L2 (missing `select_related` in three sweeps) — fixed.
- L3 (a manual rescore re-times waiting decisions) — not fixed; **TD-369**; a gotcha in CLAUDE.md.
- The query-reminder dry run uses the submit clock (pre-existing) — **TD-370**.
- The `| Q(isnull=True)` arm of the award window: its bite was SILENT (Django already guards a negated
  `__in` on a local column). Kept as the house spelling and documented in `award_timing.py`; the test
  pins the outcome.

## Numbers

| | Before | After |
|---|---|---|
| pytest (`-n auto`, the deploy gate's line) | 8084 passed / 3 skipped | 8117 passed / 3 skipped |
| jest | 4146 / 252 suites | 4149 / 252 suites |
| i18n keys per locale | 5409 | 5447 |
| Bundle median | — | 228.729 kB (line 229) |
| `/scholarship/application` | — | 273.753 kB (line 274) |
| `courses_to_scholarship_imports` | 25 | 20 |
| Migrations | ledger 0169 | 0170 (migrate-first, verified) |
| Deploys | | 1 (api + web) |
