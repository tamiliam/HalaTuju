# Retrospective — Resolved bank-details "Done" card fix (2026-06-29)

Small web-only bugfix from live-testing the bank-details flow on test account #16. One commit
(`51ce03e6`); 2 files; no migration; web build only.

## What Was Built

After a student adds their bank account, the Action Centre now shows a clear green **Done** card —
a struck-through "Add your bank account for payment" + DONE pill, attributed to "our review
assistant" — instead of the confusing "From your reviewer" card with a blank title.

## What Went Wrong (the bug)

- **Symptom:** the resolved bank task rendered as a green card labelled "From your reviewer" with no
  title — no clear "task completed" indication.
- **Root cause:** `bank_details_missing` was never added to `KNOWN_CODES` in `lib/actionCentre.ts`.
  `titleSourceFor`/`isOfficerItem` classify any *unknown* code as a free-text officer ticket, so the
  resolved bank item got the officer attribution ("From your reviewer") and used `item.prompt` (empty)
  as its title. The OPEN bank task was fine only because it's special-cased to a dedicated
  `BankDetailsTask` component; the **resolved** state falls through to the generic Done card, which was
  never exercised when S7 shipped.
- **Why it was missed at S7:** the bank feature was tested in its open/upload/confirm states, but the
  *post-resolution* card — a different render path — wasn't checked. A status-gated task has more than
  one visual state, and the terminal (resolved/done) state is the easy one to forget.
- **System change (prevents recurrence):** added `bank_details_missing` to `KNOWN_CODES` + a special
  case in `titleSourceFor`, and **two jest regressions** pinning (a) the bank title source and (b) that
  the bank task attributes to the assistant, never the reviewer. The existing `KNOWN_CODES`-iteration
  test also now covers it. Lesson generalised in `docs/lessons.md`.

## Design Decision

Reused the existing `scholarship.actionCentre.bank.title` for the resolved card rather than minting a
new "bank account added" string — the struck-through-task + DONE-pill convention (shared by every Done
card) already communicates completion, and reusing the open card's heading keeps the two states
consistent and avoids a duplicate i18n key in three languages.

## Numbers

- 1 commit (`51ce03e6`), 2 files (`lib/actionCentre.ts` + its test).
- No migration; web build only (api correctly did not trigger).
- 27 actionCentre jest tests green (+2 new); `next build` clean.
- Verified the data on #16: bank account saved (holder verdict OK), task resolved — the defect was
  purely in the resolved-card render path.
