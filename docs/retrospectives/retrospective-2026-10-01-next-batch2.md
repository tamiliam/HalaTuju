# Retrospective — Next-tier batch 2 (2026-10-01)

**Scope (owner: "proceed with batch 2"; "allow" on TD-319):** eleven web-console fixes from the
debt register's Next tier and the TD-319 ruling on the api. Built by one agent; an adversarial
reviewer who did not build it reads the diff before the lead commits, pushes or deploys anything.
The owner reads the new Tamil and the TD-297 manual sentence before the push.

## What was built

| Item | Change | Guard |
|---|---|---|
| TD-312 | `/search` eligibility toggle may shrink (`min-w-0 max-w-full`); only the switch `shrink-0`; its text wraps | `navLayout.test.ts` (+1); measured in Chromium at 360 px (below) |
| TD-288 | `Pills` / `Question` lifted to module scope in `IncomeWizard.tsx` | `IncomeWizard.focus.test.tsx` (2) — written first, red, then green |
| TD-297 | the manual's grouping sentence puts Payments and Spending in the programme | `manual.test.ts` (+4), read against `NAV_ITEMS` scopes |
| TD-299 | New run only for a gift of the caller's own organisation; one line otherwise | `payments/page.newRun.test.tsx` (3), through the real `AppShell` |
| TD-303 | the scope's new `unconfirmed`; no New run when the address names a gift an empty/failed list cannot confirm | same file (4: failed, empty, each with and without a gift) |
| TD-301 | the Overview's `load` takes the TD-298 ticket | `overview/page.order.test.tsx` (3) |
| TD-220 | the payslip/EPF IC chip: "does not match the IC on file" / "could not be read" | `officerCockpit.test.ts` (+6), `view.docFacts.test.tsx` (2) |
| TD-158 | BC row: `cap ? 'not' : …` and the Genuine chip | `officerCockpit.test.ts` (+3), `view.docFacts.test.tsx` (1) |
| TD-157 | `sgd_conversion` on the officer's document payload only; the drawer's note | `test_sgd_conversion.py` (10), `view.docFacts.test.tsx` (2) |
| TD-057 | the dashboard clears the apply-return marker; the helpers moved to the leaf `applyReturn.ts` | `dashboard/page.applyReturn.test.tsx` (2, the whole path rendered) |
| TD-313 | a TVET row with no general-key label shows the served Malay label alone | `RequirementsCard.tvet.test.tsx` (9) |
| TD-319 | an `unknown` EPF table asks Gemini for the contribution fields only | `test_epf_contribution_fallback.py` (10) |

## What bit

Twenty mutations turned their guards red — at least one per item — each from a byte backup with the
SHA-256 equal on restore, plus two comment-only changes that stayed green (the table is in the
build report). The TD-288 bite re-declares `Pills` inside the wizard as a wrapper around the
module one — the exact shape of the defect — and the focus test goes red on it.

## What was learnt

- **An import is a bundle decision.** The first cut of TD-057 imported `clearApplyReturn` from
  `@/lib/scholarship` into the dashboard: one `removeItem`, and `/dashboard` grew 251,395 ->
  257,480 gz bytes. Nothing failed — `/dashboard` is not ledgered and sits above the median — so
  only reading the bytes showed it. The helpers moved to a leaf; the route now costs 238 bytes.
  Already the rule in lessons.md (TD-300's constructor lesson is the same family), so no new lesson.
- **"A suspect BC shows no green tick" and "the same pattern as str/salary/epf" are two different
  specs.** The pattern (owner 2026-07-07) caps only a WRONG-TYPE document; a suspect one keeps its
  reads beside an amber chip. Built to the pattern; the difference is reported to the lead.
- **The payslip "could not be read" red did not exist on the payslip chip.** For a slip the number
  is either read (and then matched) or the chip was hidden. TD-220's split therefore shows the
  unread case only when the slip itself read nothing (`student_verdict` unreadable / wrong_doc),
  the state `doc_match_verdict` calls `unreadable`.

## The adversarial review (no HIGH or MEDIUM; four LOW, all fixed, red first)

- **F1 (TD-158):** an unreadable BC returned before the cap, so a selfie in the BC slot showed only
  the amber unreadable chip; it now carries the red Wrong type chip too.
- **F2 (TD-220):** the comment claimed the chip used both of `doc_match_verdict`'s verdicts; it
  now says what the code does (`incomplete` with no number shows no IC chip). No behaviour change.
- **F3 (TD-157):** the note re-wrote the engine's gate; it now asks `amounts._to_myr` (one home).
  Its meaning is "this slip converts to RM Y at this rate", not "was counted": the engine counts
  the first slip per earner, and a second Singapore slip carries the note too (pinned by a test).
- **F4 (TD-303):** a genuinely EMPTY gift list read "could not be loaded"; the shell now passes a
  `failed` flag, and the line shows only on a failed fetch.
- **Manual:** Billing is money and stays in the organisation menu — the sentence now names it.
- **TD-319, what it costs beyond the upload path:** the bulk `reextract_documents` command and
  `eval_doc_recognition` reach the same extraction, so each now spends one Gemini call per
  `unknown` EPF statement — a cohort-wide re-read is the owner's separate ask. And a statement
  whose figures came from Gemini is labelled `capture='ai'` though its identity read exactly:
  raised as **TD-320** (LOW, Later tier).
- **TD-299, left as it was:** a DRAFT gift of the caller's own organisation still shows New run
  when no live gift exists — the server refuses, and `useGiftGate` asks only beside a live gift.

## Measurements

- `/search` at 360 px (Chromium, `next dev`): toggle right edge 304 px in Tamil (375 with the old
  classes restored in the page), 269 English, 304 Malay; document 345 px = viewport less scrollbar.
- Bundle: see the CHANGELOG and the build report; every ledgered line keeps at least 0.9 kB.
