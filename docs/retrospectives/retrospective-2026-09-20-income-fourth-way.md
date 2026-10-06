# Retrospective — TD-262 F2 + W1: the fourth way gets a real door

**Date:** 2026-09-20 · **Ticket:** TD-262 (F2, and W1 examined) · **Owner ruling:** `docs/decisions.md`, 2026-09-20
**Built by:** an Opus 5 agent to a written brief and the standing hard rules. The lead reads the
report, runs the blast-radius SQL against production, and pushes.
**Outcome: a family paid in cash can find the way in, and the trap that stood behind it is gone.**
**No eligibility answer moved.** No submission blocker added or removed, `application_completeness`
untouched, `VERDICT_ENGINE_VERSION` and `results_doc.MODEL_VERSION` both unbumped. No migration.

## What Was Built

- **Three doorways of equal weight**, inside a ticked earner's Income box on the student's
  Documents tab: their salary slip, their EPF (KWSP) statement, and **"Paid in cash or works
  informally?"** — now a card beside the other two instead of a text link below them. Closed until
  tapped; opens in place to the amount field and, once an amount is typed, the supporting-letter
  card. Every string was already in the catalogues.
- **One new line, en / ms / ta:** *"One letter is enough for the whole family."*
- **The lockout is gone.** The cash door was hidden whenever any salary or EPF **file** existed for
  that earner. It now reads the **served** per-earner answer (`income_shown`), which the api serves
  to the student's own payload for the first time.
- **The dead-end chase is gone.** `declared_income_gaps` — moved to its own module — raises no gap
  for a member whose income is already shown another way.

## The Finding — two defects that were actually one trap

This is the part worth carrying forward, and it is not a fact about income.

Each half read as a minor display defect in isolation. `declared_income_gaps` chasing a family who
had already uploaded a payslip is a slightly noisy Action Centre. `memberHasProof` counting files
rather than evidence is the same presence-vs-readability slip this arc has been deleting since
chunk 2.

**Together they are a room with the door locked from outside.** A household whose only payslip is
a photograph of the wrong thing is judged *income not shown* by the server; Check 2 asks them for
a supporting letter; and the one screen that could produce that letter has closed the cash panel —
**because of the same unusable document**. They cannot answer the chase. They cannot retract the
figure. The only escape is to delete their own payslip first, which nobody would think to do.

So: **a bad ASK and a bad AFFORDANCE that share an input are not two bugs of size one.** Whenever
a rule decides both *what we demand* and *what we offer*, the two must be checked together, at the
same reading of the same fact. The general lesson is now in `docs/lessons.md`.

## What Went Well

- **The served answer already existed, and cost almost nothing to reuse.** `income_shown.py` (chunk
  2+3), `src/lib/incomeShown.ts` and its defensive `answerFor` were all built for the officer's
  cockpit. Serving the same map on the student's payload was nine lines in `serializers.py`; the
  web side needed no new reader, no new type shape, and inherited the not-atomic-deploy fallback
  already written and reasoned about. **One rule, one home, two screens** — and the two are now
  asserted identical by a test.
- **Characterising first made the review trivial.** Eighteen rows were written against the
  untouched tree. Fourteen went green immediately — those are today's behaviour, pinned and
  unmoved. Four went **red**, and those four *are* the defect: the diff is readable as "these four
  answers were wrong, here is the line that fixes them."
- **The standing rule's escape hatch worked exactly as designed, twice.** `income_engine.py`
  3,201 → **3,188** and `ScholarshipDocuments.tsx` 1,957 → **1,914**, both by moving the affected
  code into a new module rather than adding to the big file. No split sprint had to be pulled
  forward, and the web budget ratcheted down 1,942 → 1,914 as a by-product.
- **Five bite-checks, all five behaved.** Both directions (revert item 2, revert item 3), the
  over-broad direction (never raise a gap at all), the affordance (hide the third door — seven rows
  red), and a cosmetic comment edit that stayed green. No silent bite this time.

## What Went Wrong

1. **The brief said the student's payload "already carries" `income_shown`. It did not.** Only
   `serializers_admin.py` served it. Discovered by reading the serializer rather than trusting the
   sentence — which is the `feedback_absence_is_a_query` habit pointing the other way: *a claim
   that something IS there is also a query.* Cost: a small api change the brief had not scoped, and
   a serializer that is now nine lines from its budget.

2. **`src/lib/api.ts` stopped the obvious implementation dead, and only the gate said so.** The
   natural home for the new field is `ScholarshipApplication`. That file sits at **2,488 lines —
   exactly its recorded 2,468 plus the 20-line allowance** — so a *one-line* type field failed the
   ratchet. The standing rule was checked at sprint start for `income_engine.py` and
   `ScholarshipDocuments.tsx`, the two files the brief named; `api.ts` was not on the list to check
   because nobody expected a type declaration to count as growth. **It does.**
   *Fix:* the field is declared as `ServesIncomeShown` beside its only reader, with the reason at
   the declaration and a note for H13 to fold it in when that file is split.
   *Carried forward:* at sprint start, list every file the change will touch **including type
   declarations and test fixtures**, and read each one's remaining allowance — not just the ones
   the brief names.

3. **The first cut added a suppression, and the ratchet caught it.** `declared_income_gaps` was
   re-exported from `income_engine` behind `# noqa: E402,F401`, which is the reflex move for a
   function that has moved. The noqa count went red. The right answer was better anyway: the two
   importers now name the new module directly, so the name has **one home** and no linter is
   silenced. A shim would have quietly recreated the twelfth home of the income rule.

4. **Five old tests had to move, not be deleted, and the distinction needed saying out loud.**
   `test_income_engine.py`'s `declared_income_gaps` rows are built on `SimpleNamespace` fakes. The
   gap now asks a question about real documents, so the rows moved to factory fixtures in the new
   file. Deleting test rows in the same commit as a behaviour change looks exactly like gaming the
   count, so each one is named at the site it left and at the file it joined.

## What Was Deliberately NOT Built

- **The STR route's cash door — and it was RULED OUT the same day, not deferred.** The owner:
  *"If STR has been fulfilled, there is no need for the student to complete the cash door. It is
  there primarily for those without STR or salary slip."* So `declared_income_gaps` keeps its STR
  short-circuit **by decision**, and its two early returns are rulings rather than unfinished
  edges. The fourth way is for households with neither a current STR nor a payslip.
  *Reported, not built:* a household whose STR is stale, unreadable or in a stranger's name can
  only reach the cash door by changing its answer to Q1 — *"Do you have an STR document?"* — which
  they would answer "Yes" truthfully. The switch itself is safe (pre-submit it loses nothing at
  all), so the gap is the QUESTION's wording, which asks about possession where the route needs
  usability. Details in the TD-262 entry; no nudge was built.
- **Option 4 — `income_support_doc` in the requirement engines.** Listing the letter as a
  requirement puts a third upload slot in front of every salary-route family, including the many
  who never declare anything. The screen offers it when there is an amount to support.
- **W1's mononym mirror parity.** It did not fall out for free: the third door is a screen
  affordance and never touches `incomeRequirements` / `salary_member_blocks`.
- **A guard for the three parked `unguarded_mirrors` entries.** They describe the requirement
  engines and the patronymic connector — precisely what option 4 and W1 are still deciding. A guard
  written today would **bless a shape under review**, which is the exact failure the ledger note
  was written to prevent.
- **Any change to `memberIncomeShown`, the green tick.** The owner ruled on it in chunk 1. The door
  and the tick answer different questions; only the door was wrong.

## Numbers

| | before | after |
|---|---|---|
| pytest | 7,003 / 3 skipped | **7,019** / 3 skipped |
| jest | 2,904 / 159 suites | **2,913** / 159 suites |
| `income_engine.py` | 3,201 | **3,188** |
| `ScholarshipDocuments.tsx` | 1,957 | **1,914** (budget 1,942 → 1,914) |
| `serializers.py` | 1,203 | **1,212** (budget 1,195 — nine lines left) |
| `src/lib/api.ts` | 2,488 | **2,488** (byte-untouched, at its ceiling) |

`manage.py check` 0 issues · `makemigrations --check --dry-run` clean · tsc 0 · lint 0 errors ·
i18n parity ok (5,389 keys × 3) · `next build` exit 0 · `code_health` 0 FAIL, `std` ok, no reading
worse. No suppression added; no budget raised; no test skipped.
