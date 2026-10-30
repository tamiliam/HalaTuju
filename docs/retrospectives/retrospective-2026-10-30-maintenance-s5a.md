# Retrospective: Student maintenance Sprint 5a, the scholar file's Money and Contract tabs (2026-10-30)

Roadmap: `docs/plans/2026-10-29-student-maintenance-roadmap.md` (Sprint 5, admin half; 5b is the student's Funds
and Contract tabs).

- **Shipped:** `3d636795` (the feature) and `cebc9850` (fixes for the 6 adversarial review findings).
- **Live:** main `cebc9850`, api-01201-dhs, about 02:34 UTC on 2026-10-30.
- **No migration.**

## What Was Built

- **The Money tab** (`GET admin/scholarship/scholars/<id>/money/`, `scholar_money.py`).
  - Award, paid and remaining come from the Payments rules: `payments.paid_to_date` counts released
    disbursements, and `payments._remaining` floors at 0 and reads 0 with no award.
  - It lists her last 3 released payments. Every amount goes over the wire as a string.
  - Spending this term, by category, appears only for a viewer with the `spending` permission. Without it, the
    key is missing from the reply rather than set to null.
  - "This term" is the S4b result term she is in (stored start ≤ today ≤ stored end), otherwise since the day she
    was funded. Every category is listed, unfolded, sent by code and translated on screen.
- **The Contract tab** (`.../contract/`).
  - It shows a platform-signed agreement: the student and guarantor have signed, the organisation has
    countersigned, and the PDF exists. The witness is optional.
  - The wording matches the Overview card: "Countersigned by the organisation", then "Signed and executed" once the
    witness signs.
  - The parties are listed by name, role and date. No IC number is ever sent, and the witness row appears only once
    the witness has signed.
  - The PDF opens through a 300-second signed link, minted only on click. The link is refused unless the file path
    belongs to this application (`<org>/<app>/…`).
  - The tab does not depend on the signing feature flag.
- **The fence** is the scholar-file rule: finance and an unassigned reviewer are refused, another organisation
  gets 404, and a closed file can still be read.
- **One invariant test** holds five readers to the same paid and remaining: the Overview card, her My Bursary
  summary, the Money tab, the Payments funding summary and the sponsor card's "released".
- **Acceptance** was the lead's read-only SQL on live apps #4, #6 and #8. Award 2000, paid 800 / 800 / 600 and
  remaining 1200 / 1200 / 1400, which matches the Payments rules.

## What Went Well

- **Every reader and the five screens that had to agree were listed before building** (the step 3b list). That
  turned "totals match the Payments page" into one test spanning five screens rather than a manual check.
- **The pre-flight measured the worktree's own baselines** (10,442 pytest and 5,035 jest) instead of carrying
  numbers forward from the last sprint.
- **The owner was asked the one real question** (what spending the student sees) before 5b, not after.

## What Went Wrong: the 6 adversarial review findings

1. **HIGH: every contract would have read "No contract on file".**
   - What happened: the reader used `BursaryAgreement.is_executed`, which requires a witness signature. The
     platform's own rule (`bursary._maybe_activate`, and decisions.md) treats the witness as optional. Today
     `bursary_agreements` has 0 rows live; the first countersigned contract without a witness would have been
     hidden.
   - Root cause: a model property with the right-sounding name ("executed") was trusted, and nobody checked it
     against the rule the platform actually acts on.
   - System change: the tab now uses `platform_signed` (binds AND foundation_signed_at AND a PDF), the same
     condition activation uses. Tests cover the countersigned-without-witness case and the "before the
     organisation signs" case.
2. **MED: categories were folded and printed in English.**
   - What happened: the sponsor card's top-six-plus-"Other" fold, and the server's English labels, were reused for
     an officer screen whose model is the Spending page.
   - Root cause: a helper was reused without checking whose presentation it encodes.
   - System change: `category_rows(fold=False)`; categories are sent by code only, with
     `admin.scholars.moneyTab.category.*` keys (including an explicit "other"). The category drift test now covers
     this screen in all three languages.
3. **LOW: the tenant check never fired for real agreement paths.**
   - What happened: real paths have 3 segments, and `resolve_org_for_path` only reads an organisation from a
     4-segment document key. The test used a made-up 4-segment path, so it passed.
   - System change: the check now requires the first two segments to be this application's organisation id and
     application id, and the test uses the real `build_doc_key` shape.
4. **LOW: the witness could be named after the recording officer.** `witness_signed_by` is the staff member who
   recorded the witness, not the witness. It is now `witness_name`, else the witness organisation's name.
5. **LOW: a term that had already ended still counted as "this term".** The rule now needs start ≤ today ≤ end;
   otherwise it falls back to "since funded".
6. **LOW: PDF link handling.**
   - What happened: the first load minted a link nobody had asked for. The button was disabled when there was no
     link, so a failure could not be retried, and an earlier failure was never cleared.
   - System change: a link is minted only on click (`?link=1`), the button stays enabled, and a success clears the
     failure.

**Shared root cause (1, 3, 4):** a field or helper was trusted for its NAME (`is_executed`, `resolve_org_for_path`,
`witness_signed_by`) rather than for what it actually checks on real data. **Main lesson (lessons.md):** a
"signed/executed" reader must use the platform's own activation rule, with the witness optional, not a model
property with a stricter meaning.

## Design Decisions

- Money is the Payments rules and nothing else; the screens format strings and do no sums of their own.
- Spending detail is the Spending page's rule (the `spending` permission), not the scholar-file rule. Finance never
  reaches the file.
- Contract means platform-signed only (owner, 2026-10-29). No scan uploads.
- **Owner ruling (2026-10-30), for 5b:** the student's Funds tab shows totals plus categories, the same card her
  sponsor sees, with no merchants and no dates.

## Numbers

- Lead's run on the rebased tip: **10,525 pytest** passed (3 skipped); **5,061 jest in 326 suites**; i18n ALL
  PASSED; bundle ok (median 146.662 kB); `makemigrations --check` clean.
- Adversarial review: 1 HIGH, 1 MED and 4 LOW, all fixed, each with a regression test.
- Commits: the feature (22 files) and the fixes (15 files). No migration.
