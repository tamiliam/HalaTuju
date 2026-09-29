# Retrospective — `has_valid_str` asks whose STR it is (TD-285)

**2026-09-29. API only. Built by a subagent; NOT committed, pushed or deployed — the lead and an
adversarial reviewer own that.** Owner's ruling: TD-285 option 1, *"close it now, the F8 way."*
The lead's production count the same day: 60 applications hold an STR, 3 carry a typed amount,
**0** typed amounts rest on an STR whose recipient NRIC matches no household IC. No live answer
moves. The adversarial review returned SHIP AFTER FIXES; F2–F4 are fixed below, F5 is recorded,
and F1 went to the owner, who ruled the same day: **"we cannot judge" is NOT "stranger"** — see
*The F1 ruling, built* below, which supersedes the moved-row counts in the sections before it.

## What Was Built

- **The predicate.** `income_engine/evidence.py::has_valid_str` is now
  `currency in (current, unconfirmed) AND NOT str_check_names_a_stranger(sc)`. The ownership rule
  is F8's, split out of `income_str_ownership.str_recipient_is_stranger` into
  `str_check_names_a_stranger(sc)` so there is one copy, and applied to the `student_str_check`
  reading `has_valid_str` has already taken. A POSITIVE mismatch refuses; `no_ref` (a recipient that
  did not read, or no household IC to compare against) still vouches.
- **The characterisation** (`tests/test_income_whose_str_vouches.py`). 208 households: 2 routes ×
  13 STR states (own STR matched by name / NRIC / both; own STR whose recipient did not read; a
  stranger's STR with ICs on file — current, dashboard-unconfirmed, name-only, **NRIC-only**; a
  stranger's STR with no IC on file; a stranger's stale STR; own stale; own unreadable; none) ×
  typed amount or not × nothing / payslip / EPF / a letter that read. Each household is asked all
  four callers plus the live gate — ten readings. `BEFORE` was read off the untouched tree and is
  never edited; `MOVED` holds `(before, after)` for the readings that changed; the tests assert
  every other row is byte-identical, every `before` half equals `BEFORE`, and the moved set is
  exactly the stranger's-STR-with-ICs rows. The frozen gate is pinned across all thirteen states.
- **The student's Check-2 asks** (review F2): the three codes `on_str` and the declared-wage ask
  decide, per route and state, before and after (section 5); and the swap end to end — an open
  `_str` clarify, the next sync, and the email the hourly sweep sends (section 6).
- **`VERDICT_ENGINE_VERSION` → `2026-09-29.1`**, with a test that fails if the bump is dropped.
- **A query budget for the predicate itself** (`TestHasValidStrQueryBudget`, 8 / 6 / 6 / 1).
- §11 rows in `test_income_evidence_homes.py` updated (they pinned the defect as "NOT fixed by this
  change" and said so), one row ADDED there showing why the audit's gate must stay, and one F8 gate
  row added for the NRIC-only stranger on both routes.

## What moved — exactly 64 rows, all a stranger's STR with a household IC on file

| household | what changed |
|---|---|
| every one of the 64 | `has_valid_str` True → False; `on_str` True → False (student-facing — see below) |
| salary route, typed amount, nothing else (4) | the figure is unproven (per-capita → unknown, profile line → "none on file", reconciliation can no longer total); **Check 2 now asks for the letter**; **band Certain → Unsure** (`income_declared_needs_evidence`) |
| STR route, typed amount, nothing else (4) | the figure is unproven (per-capita, headroom, profile line). No chase (cash door is salary-only) and **no band move** — the audit's gate had already refused to let this figure raise the fall-through |
| typed amount + a letter that read (8) | still a real number, now `declared_evidenced`; the card reads `income_declared_accepted_evidenced` instead of `_str` (except the STR-route dashboard STR, which bands on `str_not_current` before any evidence code is rendered) |

**The student's Check-2 codes** (submitted household, typed amount, bills reading high):

| route | before, every stranger-with-IC state | after |
|---|---|---|
| salary | `high_utility_expense_str` | `high_utility_expense` + `declared_income_evidence_missing` |
| str | `high_utility_expense_str` | `high_utility_expense` |

Every other state's codes are unchanged (own STR and `no_ref` stay `_str`; stale / unreadable /
none already read `high_utility_expense`, plus the letter on the salary route).

**What such a household is SENT.** The next Check-2 sync resolves the open
`high_utility_expense_str` clarify itself (`resolved_by='system'`) — the student's Action Centre
shows it done without an answer. `high_utility_expense` is raised in its place **when a clarify
slot is free** (it is the lowest-priority clarify and capped; it quotes the household income the
student REPORTED at apply, `profile.household_income`), and on the salary route the uncapped
`declared_income_evidence_missing` letter request is raised at once. Any new item re-arms the
one-time notice, and the hourly `send_due_query_emails` sends the existing
**`send_query_raised_email`** — subject *"A few things we need for your {programme} application"*,
a body giving the COUNT of open items and a link. No new email text; the branding golden is
byte-identical. From `interviewing` onward the `_str` clarify is still closed but nothing replaces
it and no email is sent.

**Did not move, anywhere:** the submission gate and every blocker code, the frozen gate, any row of
the family's own STR, any row of an STR whose recipient did not read, any row of a stranger's STR
with no IC on file, and every recorded query budget.

## What Went Well

- **The ruling fitted one place.** The four callers all read `has_valid_str`, so one predicate
  change moved them together and the matrix could prove that nothing else did.
- **Zero queries.** `has_valid_str` already calls `student_str_check`, which has already matched the
  recipient against every household IC; the ownership rule reads those two statuses. Measured 8 / 6 /
  6 / 6 / 1 queries before and after across own / stranger / unread / no-IC / none.
- **The revert bite reddened exactly the moved rows and nothing else**, which is also the proof that
  the rest of `BEFORE` was transcribed faithfully from the untouched tree.

## What Went Wrong

- **No budget watched the predicate.** *Symptom:* bite (d) put one extra query inside
  `has_valid_str` and all five recorded budgets stayed green. *Root cause:* every budget is keyed on a
  request fixture, and none of those fixtures reaches `has_valid_str` with an approved STR on file.
  The obvious implementation — call `str_recipient_is_stranger(application)` — doubles the
  predicate's cost (8 → 16, bite d2) and would have shipped silently. *Fix:*
  `TestHasValidStrQueryBudget`; a lesson in `docs/lessons.md`.
- **I called `on_str` "officer-facing" and it is not** (review F2). *Symptom:* the retro, the
  decisions entry and the matrix pinned `on_str` as a boolean for an officer's follow-up context; in
  fact `check2_queries._gap_sets` uses it to choose the STUDENT's high-utility clarify, so the change
  closes an open student question, raises a different one and triggers the query email. *Root
  cause:* I took TD-285's four-caller table as the surface map ("officer-facing copy") instead of
  grepping every reader of the RETURN value (`high_utility_expense_context` → `_gap_sets` →
  `sync_check2_queries` → `send_due_query_emails`). *Fix:* sections 5 and 6 pin the codes and the
  email; a caller's consumers are now listed by grep in this retro, not by the table.
- **The matrix could not tell an "OR" rule from a name-only one** (review F3). *Symptom:* changing
  the ownership rule to read the name alone turned nothing red. *Root cause:* every stranger state
  carried a NAME mismatch; none had the name unread and the NRIC mismatched. *Fix:* the
  `stranger_nric_only` state (16 matrix rows, two Check-2 rows) and an F8 gate row on both routes;
  the name-only bite now reddens all of them.
- **Two docstrings still said `has_valid_str` "never asks whose STR it is"** (review F4) —
  `verdict_income_salary.salary_evidence_stands_without_the_str` and `evidence.str_not_breached`.
  Reworded; the first now also says why its gate stays.
- **The audit's §11 said "if this row ever goes red, re-read this section" — and two rows went red,
  one of them unforeseen.** `test_the_salary_reading_still_carries_income_proof_present` pinned the
  salary reading's own marker on the stranger's-STR arm; the ruling legitimately removes it. *Fix:*
  the row now asserts the new truth and says what it read before.
- **A scratch diff script was refused by the workspace security hook** (a false positive on a
  standard-library parsing helper). Not reworded around: the diff was computed by importing the
  pinned `BEFORE` table from the test module instead, which needs no text parsing.

## Design Decisions

- **Apply the rule to the reading in hand, not to the application.** One rule, no second read. The
  gate's function now calls the same helper, so the two can never disagree about whose STR it is;
  `test_the_predicate_and_the_gate_ask_one_ownership_question` pins it across every state.
- **Keep the audit's fall-through gate.** An STR whose recipient did NOT read still vouches, so on
  the incomplete-cluster arm the salary reading can still carry `income_proof_present` off the STR
  alone. Bite (f) — delete the gate — reddens
  `test_the_gate_still_bites_where_absence_keeps_the_str_vouching`.
- **The cash-door ruling is honoured, not reversed** (decisions.md 2026-09-29).
- **The end-to-end fixture reaches the old state honestly.** It runs the Check-2 sync with
  `has_valid_str` answering as the old tree did and lets the student answer each clarify in turn
  until the lowest-priority `_str` one is open — rather than inserting that item by hand, which
  would have skipped the clarify cap that decides whether its replacement is raised at once.
- **Version bump, three lines.** `verdict_engine.py` sits at 1165 against an allowance of 1166.

## Bite-checks (original bytes restored in a `finally`, verified by SHA-256; every needle matched exactly once)

| Bite | Result |
|---|---|
| (a) revert the tightening | red — exactly the moved matrix rows, plus the words-rows and the §11 pair |
| (b) tighten too far: the recipient must positively MATCH | red — 32 matrix rows (`own_unread`, `stranger_no_ic`), the two absence rows, and the `test_income_declared_gaps` short-circuit row |
| (c) drop the version bump | red — `test_the_verdict_engine_version_records_the_move` |
| (d) one extra query inside `has_valid_str` | **SILENT on every existing budget** → finding; `TestHasValidStrQueryBudget` written; now red: "costs 9 queries; the budget is 8" |
| (d2) the naive implementation, `not str_recipient_is_stranger(application)` | red — 16 > 8, 12 > 6, 12 > 6 |
| (e) comment only | green |
| (f) delete the audit's fall-through gate | red — the new absence row |
| (g) review F3: the ownership rule reads the NAME alone | first **SILENT** (the reviewer's run) → finding; now red — 16 `stranger_nric_only` matrix rows, both Check-2 rows, the words-row and the F8 gate row on both routes |
| (h) review F2: Check 2 always asks the income variant, ignoring `on_str` | red — 10 Check-2 rows (every `_str` state) and all three end-to-end rows |

## Numbers

- pytest **7,117 / 3 skipped → 7,194 / 3 skipped** (after the re-review) (after the review fixes; one earlier full run
  failed `test_org_requests_endpoints::test_the_ai_split_is_exact` under xdist, which passed alone
  and on the re-run — unrelated to income, noted as a possible flake); jest
  **3,118 / 176 → 3,118 / 176** (API only; no web mirror of `has_valid_str` exists).
- Query budgets, before → after: officer detail **38 → 38** (bare) and **38 → 38** (three
  documents); student read **7 / 13 / 20 → 7 / 13 / 20**; STR fall-through **27 / 39 → 27 / 39**;
  `has_valid_str` itself **8 / 6 / 6 / 1** (new, identical on the untouched tree).
- `verdict_engine.py` 1163 → 1165 (allowance 1166).

## Web mirror

`halatuju-web/src/lib/incomeWizard.ts` and `incomeShown.ts` do not mirror `has_valid_str` or the
STR arm. `officerCockpit.ts`'s `strNotBreached` mirrors `str_not_breached`, which this ruling does
not touch. The `unguarded_mirrors` ledger is unchanged.

## The F1 ruling, built (2026-09-29)

**The finding.** As first built, a mother's STR with only the father's IC on file read as a
stranger's: it mismatched the one IC we could compare. The owner: *"we cannot judge" is NOT
"stranger"* — the STR counts, the missing IC is asked for, and only a household whose every member's
IC is on file and none matches is refused. One shared rule, so the F8 gate softens with it.

**What changed.**
- `income_str_ownership.str_roster` — recorded father/mother (not `deceased`/`no_contact`), a
  guardian, the STR earner, the working members — and `str_check_names_a_stranger(sc, application)`
  now needs a COMPLETE comparison set. The set travels on the reading (`ic_read_members`, collected
  in `_str_recipient_household_match`'s one loop, stripped from the student payload): **no budget
  moved** (`has_valid_str` 8/6/6/1; officer 38/38; student 7/13/20; fall-through 27/39).
- **The gate** (`str_gate_reading`): `parent_ic_missing:<member>` in place of `str_not_household`
  for a cannot-judge STR — exactly the households the old gate blocked, so no one newly blocked and
  no one freed (`test_the_gate_never_blocks_a_row_it_did_not_block`). A true stranger: unchanged.
- **Check 2**: new uncapped, member-tagged doc requests `<member>_ic_for_str_missing` with en/ms/ta
  student copy (officer strings later removed — see the re-review); the existing query email
  carries them.
- **The matrix**: 18 states, 288 rows. **64 move fully** (the four true-stranger states); **36 move
  at the gate only** (six cannot-judge states, incl. the stale one — it never vouched, but it was
  blocked as a stranger); every other reading of a cannot-judge row is the untouched tree's.

**What went wrong.** *Symptom:* the first build called the owner's commonest case — the mother's STR
before her IC is uploaded — somebody else's, and blocked her with an accusation. *Root cause:* F8's
field rule treats "mismatched every IC we have" as "mismatched the household", and TD-285 inherited
it without asking who was MISSING from the comparison. *Fix:* the roster and the completeness test,
with a state per shape; the review caught it before any student did.

**Bites (F1).** (a) an incomplete roster counts as a stranger → red: 86 matrix rows across all six
cannot-judge states, the gate rows on both routes, the Check-2 rows, the §11 rows, the end-to-end
ask; (b) a complete-roster stranger counts as `no_ref` → red: 64 matrix rows, exactly the four
true-stranger states; (c1) drop the Check-2 ask → red, 15 tests; (c2) drop the gate's ask → red,
18 matrix rows + gate rows; (d) comment only → green.

## The re-review, fixed (2026-09-29) — supersedes the F1 section's gate and counts

Verdict SHIP AFTER FIXES; two HIGHs, a MEDIUM, two LOWs.

- **F-A (HIGH) — "read" was per IC, it must be per FIELD.** *Symptom:* the mother's IC read only
  her NRIC, the STR showed only her name — and the STR was refused, though she was never compared
  on the one field it offers (and the mirror case). *Root cause:* the comparison set was "members
  whose IC read ANYTHING". *Fix:* `ic_read_members` is now `{on_file, name, nric}`; a mismatch
  refuses only if COMPLETE on a field the STR offers. Two cannot-judge states and one
  complete-on-one-field true-stranger state added (48 rows).
- **F-B/F-D (HIGH) — the gate asked for an upload the page cannot take.** *Symptom:* the owner's
  own example was blocked with "upload your mother's IC", and the Documents page has no slot for a
  non-working mother. *Root cause:* I placed the ask where the old block was without checking the
  surface could answer it — the dead-end pattern this week had already closed twice. *Fix:* the
  lead's reading (decisions.md): a cannot-judge STR does not block; the ask is raised after
  submission in Check 2. `blockers.py` is back to its committed logic (+2 comment lines); 48 rows
  are freed, and `test_the_gate_never_blocks_a_row_it_did_not_block` now checks EVERY row's
  blockers are a subset of the untouched tree's. TD-309 is the real gap.
- **F-C (MEDIUM) — an IC on file that read nothing was called "missing".** *Fix:*
  `<member>_ic_for_str_unreadable` — "the IC on file for her could not be read…". The existing
  `earner_ic_unreadable` could not be reused: verdict-derived, earner-only, untagged.
- **The officer copy I first added was dead weight — and it broke the bundle budget.** *Symptom:*
  `npm run bundle-budget` failed `/scholarship/apply` and `/scholarship/application` by 1.0 kB each.
  *Root cause:* ten `admin.scholarship.verdict.item.<code>` strings per locale, in the one message
  file every route loads — and nothing renders that namespace for a Check-2 code: the officer's
  Outstanding list shows the student's own wording. I had copied the house convention without
  checking it was read. *Fix:* removed; measured with and without (only those strings made the
  difference); the officer render is pinned by `view.strIc.test.tsx`. Median 227 → 228 kB, under 229.
- **F-F (LOW)** — the mother variant rendered with the real en and ta catalogues
  (`ActionCentre.strIc.test.tsx`), and in the officer's Outstanding list (`view.strIc.test.tsx`).
- **F-G (LOW)** — not done; `_gap_sets` would need a wider signature in the oversize-ledgered
  `check2_queries.py`. TD-308.
- **F-E** — recorded for the owner in TD-285 and decisions.md, no change.

**Bites (re-review).** (a) "read" per IC → red: 32 matrix rows (both F-A states) + 9 more;
(b) no complete comparison ever suffices → **first SILENT**: no state had a mismatch complete on
one field and incomplete on the other, so the early return was untested. `true_stranger_complete_on_
name` added; now red, 16 rows; (c) the gate blocks a cannot-judge STR again → red: 48 matrix rows
across all eight cannot-judge states + gate rows; (d) an unreadable IC called missing → red, 9
tests; (e) comment only → green.

## What Is Still Open

- The lead's reading of the gate is on record for the owner to overrule (decisions.md).
- **F5, known edge, no fix (LOW):** an adult STUDENT's own STR reads as a stranger's, because
  `_MEMBER_ORDER` holds no student — F8's existing rule, now carried into the amount. Live count to
  be run by the lead.
- **TD-307:** the possible xdist flake in `test_org_requests_endpoints`.
- **TD-306, pre-existing:** the `high_utility_expense` clarify's `income` param is omitted when
  the student reported no household income, and the web's `interpolateMessage` then leaves the
  literal `RM {income}` in the student's copy. TD-285 can route a stranger's-STR household into that
  variant; it did not create the edge.
- TD-286 — its trigger ("the third post-H4 budget") is reached.
- The read-only production screen is with the lead; its NAME comparison is exact where the
  Python's is fuzzy, so it can only over-report.
