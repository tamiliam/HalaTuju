# Retrospective — TD-403: an STR counts as income proof only if it is from this year (2026-10-26)

Commits `32a847f1` (the ruling), `cafcfc43` (review 1), `85921925` (review 2), `b67dd4f5` (the submission
year), with the lead's `ed342354` (rebase fix-up: `VERDICT_ENGINE_VERSION` became 2026-10-26.2 because
corpus C1 took .1, and one old history comment was tightened to keep `verdict_engine.py` at 1004 lines).
Pushed to main and live 2026-10-26 (web-00989-vf5; the api build was then superseded by C3's
api-01147-9gw). Built in the worktree `td403-str-year`, with three review rounds and two owner rulings.
CHANGELOG: "TD-403 — an STR counts as income proof only if it is from this year". Decision:
`docs/decisions.md` 2026-10-26 (with its addendum). Register: TD-403 closed.

## What Was Built

- **The rule (owner ruling 2026-10-26, strict all year, no January–March grace).** An STR counts as
  income proof only if its stored year (`fields.year`) is THIS year. `_str_currency` asks the year of
  every recognised format, the dashboard included, BEFORE the approval and rejection words:
  - an earlier year → `stale`, whatever its status says (approved, unread or rejected);
  - a later year → the new neutral state `future` (live: a 2027 'semakan_status' page, 'berjaya' —
    almost certainly next year's application status);
  - no year read → `unconfirmed`, as before (passes, Probable — the officer checks).
- **The gate, both routes.** `str_not_breached` treats `stale` and `future` as breached, so neither
  carries a cluster or a member's income. A stale STR asks plainly with `str_stale:<year>` ("Your STR is
  from {year}. Please upload this year's STR."); a `future` page asks neutrally with `str_not_this_year`.
  Income shown another way (a payslip, EPF, a declared amount with a letter) still carries the household.
- **Every other reader.** The request verdict (`future` → `insufficient`: it closes no ask and is not a
  mismatch); the keep-the-better upload ranking (another year's page ranks below an unreadable one); the
  verdict (`future` bands Unsure — a 2027 "Lulus" had read Certain); the student and officer chips (no
  "Lulus" claimed for another year's page); the coach (`future` coaches, and a gentle "we may have misread
  it" line); the officer cockpit's "salary documents are supportive" mirror. Copy in en/ms/ta (Malay and
  Tamil first drafts).
- **The submission year (owner ruling, second part).** `str_route.str_this_year(application)` is the one
  seam: today in Malaysia before submission; the Malaysian year of `profile_completed_at` once submitted
  (cleared and re-stamped if the case goes back to the wizard; a decision reopen keeps it); the intake year
  for a legacy submitted row with no stamp. An STR uploaded after submission is judged against the
  submission year. A static test refuses any other module computing the STR currency or its year.
- **The suite pins the STR year to 2026** (`conftest.STR_TEST_YEAR`; `real_str_clock` opts out), so the
  2026-dated fixtures — and the Cloud Build deploy gate — do not turn red on 1 January 2027.

## What Went Well

- **Every fix was bitten** — each reverted, its test seen red, the file restored byte-exact (`cmp`) —
  across all four commits, including the seam itself (made "today only", and "stamp ignored").
- **The clock tests are real.** The Malaysian-midnight cases (31 Dec 23:59 / 1 Jan 00:01 MYT) caught a
  UTC-based `str_this_year` in a bite-check, and the 2027-01-05 frozen clock covers every reader of a
  submitted case: chips, gate, coach, request, re-notify, band.
- **The frozen matrix stayed frozen.** The TD-285 whose-STR matrix gained a third, separately pinned
  layer (six salary-route gate rows) rather than an edit to its record.

## What Went Wrong

1. **The first cut let an unreadable status dodge the year rule.** `_str_currency` asked "did an approval
   word read?" before "which year is this?", so a 2025 page whose status did not read answered
   `unreadable` — which `str_not_breached` counts — and passed the gate on both routes, even resolving an
   STR request, while the same page saying "Lulus" was blocked. *Root cause:* the year check was added as
   one more rung at the bottom of an existing ladder, and the rungs above it return states that readers
   act on; the builder kept `stale` meaning "approved but old" to keep a chip truthful, and accepted the
   gap as "unreadable's own question". *System change:* the year is asked first for every recognised
   format; the ladder test has a row for each rung it must pre-empt (unread, "Dalam proses", letter,
   dashboard); lesson recorded (a disqualifying rule runs above every rung that can answer first).
2. **The keep-the-better ranking still assumed "stale = approved".** After review 1 widened `stale` to any
   earlier year, `_STR_CURRENCY_RANK` still placed it above `unreadable`. Probe: a live 2025 STR (blocked)
   plus a new 2026 upload with a blurred status (unreadable — it would pass) — the guard kept the new one
   out and the student stayed blocked. *Root cause:* when a state's meaning changed, its readers were
   re-checked for gates and chips but not for the ranking that encoded the old meaning. *System change:*
   another year's page ranks below `unreadable` (with `future`); tests pin that scenario and that a current
   or unconfirmed STR is never replaced by another year's page; the same lesson's second half.
3. **An old rejection replaced a current approval.** A 2024 "Ditolak" read `rejected` (the rejection
   words ran before the year), and `str_proof_quality` treats `rejected` as news that always replaces — so
   it promoted over a live 2026 Lulus and blocked the family. *Root cause:* "a rejection is news" was true
   only for this year's rejection, and nothing tied the rule to the year. *System change:* an earlier
   year's rejection is `stale` (not news, never replaces); `rejected` stays for this year's or a dateless
   one; both pinned, and the promotion decision is tested through the upload path's own
   `should_promote` + `doc_match_verdict`.

**How the owner's submission-year ruling reshaped the 1 January problem.** The first cut judged every case
by TODAY, so on 1 January 2027 every submitted case resting on a 2026 STR would have turned stale at once:
a Check-2 `str_not_current` request and a re-notify email to each, a band drop from Certain, and red chips
for officers mid-review — a mass action the coordinator held for the owner. The owner went further than
"don't send the request": *"If the STR was current at the point of submission, we let it be."* So the
question stopped being "suppress what fires on 1 January" and became "which year does this case answer
to?" — one seam (`str_this_year(application)`), with the submission stamp as the reference, and nothing
fires at all. A suppression would have needed a guard in every reader (request, email, verdict, chips,
coach); the seam needed none, and the static test keeps a future reader from using plain today.

## Review (sprint-close step 4b)

No `/code-review` run, by the coordinator's instruction: three adversarial review rounds, each answered in
full in the worktree —
- **Round 1 (on `0d32b712` → `cafcfc43`):** BLOCKER — the unread-status dodge (item 1); a stale STR blocked
  under "doesn't match" copy → its own `str_stale:<year>` ask. Held: the 1 January question.
- **Round 2 (on `5454063c` → `85921925`):** the ranking (item 2); the old rejection (item 3); the officer's
  "approved, prior cycle" gloss reworded; a gentle "we may have misread it" coach line.
- **Owner ruling (→ `b67dd4f5`):** judge a submitted case by its submission year.
- Gates confirmed by the lead on each commit; combined gates on the rebased tree 8894 (+1 fixed) / web 4552.

## Numbers

- API (`python -m pytest -q -n auto -p no:cacheprovider`, worktree): baseline 8,824 → 8,854 passed /
  3 skipped; 8,894 (+1 fixed by the lead) on the rebased tree.
- Web: 4,548 → 4,552 jest / 288 suites, gates green (typecheck, lint, i18n).
- No migration. `VERDICT_ENGINE_VERSION` 2026-10-26.2 (after the rebase). Register: TD-403 closed.
- Live exposure at the ruling (lead's count): STRs of year 2026: 44; 2025: 1; no year: 47; 2027: 1.
