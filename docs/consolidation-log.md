# Small-Change Consolidation Log

Tracks one-off small-lane changes between full sprints. Every ~10 pending entries triggers a
Consolidation Review (see `Settings/_workflows/small-change-lane.md` Part B).

## Pending

_(cleared at the 2026-10-06 review — counter reset; the 13 reviewed entries are listed in that review)_

## Reviews

### 2026-10-06 — thirteen changes, 18 Sep → 6 Oct: the lane carried three sprints, and one budget line took five fights

**The thirteen** (commit · files): the type check made a real gate, TD-221 (`a22b1d89` · 12); the
code-health baseline, docs only (`2e3cd2bb` · 4); the stuck banner per ROAD, BrightPath #24
(`7cc65ddb` · 7); the Overview attention card and one-round picker (`ba8d423a` · 5); the three fonts
self-hosted, TD-305 (`7435fa90` · 12, three of them font files); no student reads "RM {income}",
TD-306 (`4583a83d` · 17); TD-306's route back under budget (`40887efb` · 11); the sponsor 404 made
reachable, #25 follow-up (`3faa3450` · 4); the Requests analysis wording (`29c47c9a` · 9); a confirmed
offer refreshes the profile pathway, TD-210 (`a5d12fb2` · 16); and requests #27 (`c56a8546` · 3), #29
(`43997738` · 8) and #28 (`ccceb5ad` · 14).

**Reflect.** Most were genuine fixes, and three of them carried their own guard and have held: the
type check (tsc reads 0 at every `--full` reading since, today's included, and it is in `npm run
gates`); the fonts (a deploy needs nothing from Google; TD-310 followed as its own sprint); and the
sponsor 404, whose pair test pins the sink, the boundary AND the way out. Three were symptoms. The
**route rescue** (`40887efb`) existed only because TD-306's copy tipped `/scholarship/application`
over its line — the first of five weight fights in a week, below. The **stuck banner** existed
because #144's fix of 7 Sep had a test asserting the pre-July shape, which could never reach the
branch it named; the same shape as five of request #26's tests after the one-application rebase
(2026-10-05), which assumed the old rule and went red only in the full suite. And **#28** needed a
near-miss caught by its builder: the Overview chart held its own list of category codes and dropped
any it did not know, so the new category's money would have vanished from the chart silently — the
fourth review running to meet "something that looks armed and does nothing" (2026-08-19, 2026-09-08,
2026-09-18), this time as a list that discards rather than a button that does nothing. One process
miss is on the record in its own entry: the stuck-banner fix was built UNASKED, before the owner had
triaged it.

**Cohere — two clusters, both promoted.**

- **One budget line, five fights (2026-09-30 → 10-06).** TD-306's copy (gate refused `4583a83d`;
  `40887efb` made the post-award cards lazy); TD-309 (the Form 6 list made lazy, 30 dead keys
  deleted); apply-gift-clarity (five strings, 86 gz bytes, took `/profile` over — the gate refused
  `552cf494` at 310.007 with 0.055 kB showing locally); request #26 (cut its own en.json footprint to
  land); and the one-application sprint (TD-354's 28-byte fix built and backed out). Each was a lazy
  boundary or a deletion — room borrowed once. The common mode is not any page: it is **one English
  message file, ~97 kB gzipped, on 74–82 of 89 routes**, so every string anywhere moves every
  budgeted line. **Promoted to TD-360** (split it by audience). TD-344 is re-scoped to the two routes
  that are thin today (`/scholarship/apply` 0.189 kB of room, `/scholarship/application` 0.179;
  `/profile` has 0.988 since request #26).
- **Mirrors the guard cannot see (#28; the 404 pair, the TD-349 reopen offer in their own changes).**
  The web mirror guard reads only `src/lib/` and only a comment that says "mirror"; #28's list lived
  in `components/` and called itself "the codes the server always sends". **Promoted to TD-362**: the
  structural half (a served choice set listed by hand in the web is imported from one module or
  drift-tested) is a ledger triage over ~33 files, so a sprint, not a guard for this pass.
- **Not promoted: the spending/payments requests (#27, #28, #29).** One organisation's three asks on
  two admin screens in one sitting, with no shared mechanism; a redesign would be inventing a cause.
- **Decision reconciled.** #28 shipped a new design decision with no entry and moved the arithmetic of
  two standing ones (the Overview's "eleven" codes, the sorter's "ten"). Recorded in `decisions.md`
  (2026-10-06, the person-only `micro_stall`); neither rule's substance changed.

**The lane: were #27, #28 and #29 small changes?** `wat_lint` flagged all three. Judged against
Part A step 1 (≤ ~5 files, no new model, no new feature surface, no money/consent/auth/PII):
- **#27 — rightly in the lane; the lint is wrong.** Three files, web only: a count beside a heading,
  equal to the length of the list already drawn, no server change, no new string. The payment run is
  money's screen, but nothing about who is paid, or how much, can change.
- **#29 — rightly in the lane, at its edge.** Five source files (one helper, one component, two tests)
  and the three message files: a computed column on an existing table, read-only, in whole sen. It
  reports money; it moves none and stores nothing. Its one new string moved every budgeted route
  (TD-360's mechanism), which is why the check below now reads every line.
- **#28 — should have been a sprint.** Fourteen files; a migration (choices-only, no DDL, but a
  migration — the 2026-06-29 rule); a new value in a STORED choice list read by the sorter, the
  officer screens, the Overview's money charts and the sponsor card; and a new semantics for a
  person's `unsorted`. Lessons.md's first rule ("a rule that lets the database hold a NEW shape needs
  every reader checked") is exactly the step a sprint would have made deliberate — here it was the
  builder's diligence that found the Overview reader. No harm resulted: the ledger row was applied
  first and the drift test landed with it.
- **Two the lint MISSED, and both were sprints:** TD-306 (17 files, a new module
  `high_utility_variant.py`, student-facing copy about income in three languages, and the route it
  tipped) and TD-210 (16 files, a new backfill command, and a change to how a STORED value — the
  profile's pathway — is derived, with 13 rows repaired). Both were logged as `fix:`.

So the classifier is wrong in both directions, for one reason: it keys on the WORD the author chose
(`" feat:"` or `"migration"` anywhere in the log line, `wat_lint.py` `check_consolidation`). An honest
`feat:` on a three-file label is flagged; a `fix:` on a sixteen-file backfill passes. The window also
breaks the file-count proxy outright — eight of thirteen entries exceeded five files — which the
2026-08-19 review said would, on a third time, need the proxy changed. This is the third time. **The
fix belongs in the workspace repo and is proposed, not landed:** the log line carries the short SHA,
and `wat_lint` reads the commit (`git show --numstat`) and flags more than five non-test, non-locale,
non-asset files, any path under `migrations/`, any `models` path, and any new `management/commands/`
file — whatever the subject says. Step 1 of the lane gains the matching sentence (the exact wording
is in this review's report to the lead).

**Anticipate — one guardrail landed; three classes given workflow lines.**

- **Landed: the near-line check** (`halatuju-web/scripts/bundle-budget.js`, `NEAR_LINE_KB`). Class:
  "a route ends up within a few bytes of its line and the gate refuses it" (`/profile` at 310.007,
  TD-306 at 53 bytes, TD-354 backed out at 28) and its twin "a new string in a shared message file
  moves every route" — the check reads EVERY budgeted line and the median, so the route a change
  never touched is the one it names. A dev-box run now FAILS when any line has less than
  `NEAR_LINE_KB` of room; the deploy gate passes `--gate` and only prints it, because there the line
  is the budget. The lead asked for 0.25 kB; **on this tree 0.25 fails two routes** (apply 0.189,
  application 0.179), and a guard that is red on the day it lands is the always-red gate the
  code-health audit warns about — so it landed at **0.15 kB** (2.4× the 0.062 kB drift seen; a local
  pass is still a gate pass with room), as a ratchet: raise to 0.25 when TD-344 frees those two
  routes, never lower. It agrees with the "recorded 2 kB over" convention: a freshly recorded line
  leaves 1–2 kB, never inside the margin. Five tests (`bundleBudgetReader.test.ts`), bitten by a
  planted 0.05 margin (2 red), and run against today's build in both modes (local exit 0; at 0.25,
  local exit 1 naming both routes, gate exit 0 printing them). It converts a rule that lived only in
  `docs/lessons.md` and in a lead's brief ("the 0.30 kB floor") into a failing command.
- **Workflow lines, proposed for the workspace repo (not this project):** (1) the lane's step 1 —
  count source files, and a migration, a new stored choice value, a new module or command, or a
  changed derivation is a sprint whatever the count; (2) the lane's step 4 — the log line carries the
  short SHA; (3) `sprint-close.md` step 12 — after a rebase or merge onto another session's work, the
  FULL api and web suites run on the result before the push (the class "a feature's tests assume the
  old rule after a parallel session", ×2 in this window).
- **No new guard for "looks armed, does nothing".** Its instances keep changing shape (a button, a
  page, a list that discards); each of this window's three carried its own pin. TD-362 is the
  mechanisable half.

**Close out.** Pending cleared (13 → 0, counter reset). Promoted: TD-360, TD-362 (and TD-344
re-scoped). Guardrail landed: the near-line check, tested and green. `decisions.md` reconciled for
#28. Code-health reading taken (`--full`, 161f11e): no reading worse; the third accept of `big` is
TD-361. The Open Items Index regenerated: **112 open of 359 defined**, the tool's `td_open`, and every
pointer diffed against the register both ways.

### 2026-09-30 — the register itself: every entry read, 36 closed on evidence, 159 open and ordered

**Not a small-change review** (the Pending list above is untouched and its counter stands) — the
owner asked for the whole debt register to be verified and prioritised. Recorded here because the
consolidation workflow owns "regenerate the index by READING".

**Reflect.** Eleven read-only readers, by theme, each entry checked against the code and an evidence
pack; the lead opened every citation behind a closure. Two findings about the register, not the code:
thirty-one entries had been written INSIDE the index (which the tool and the duplicate-id guard skip),
and ninety-four June entries used a bullet shape the tool does not read. The tool said 99 open; the
register held 315 defined and, after this pass, 159 open.

**Cohere.** The clusters, each worth one job: first-draft Malay and Tamil copy (ten entries, one owner
sitting); never walked in a browser (five, behind TD-194); the missing organisation scope (TD-228,
TD-246); the award that cannot be undone (TD-198, TD-252, TD-068, TD-227 — one set of rulings); one
paid re-read of older EPFs (TD-116, TD-117). Three registers-of-habit to stop: closing a TD in a retro
and not in the register (38 entries were resolved in their own text with no marker); writing new
entries into the index; and recording a leftover under a RESOLVED headline (TD-123, TD-135 — now
TD-317, TD-318).

**Anticipate.** The Now tier is eighteen entries and eight are half a day each (TD-203, TD-252, TD-248,
TD-315, TD-292, TD-217, TD-167, TD-153): a two-day money-and-identity sweep would clear them. The
Owner-decision tier is twenty-three questions and blocks more work than any other tier.

**Closed at this pass (overtaken, evidence on each defining line):**
  - TD-003 — 187 web test files and a jest deploy gate
  - TD-018 — ca54b0ef; apps/courses/views.py has one import
  - TD-019 — ca54b0ef; json imported at the top of apps/courses/views.py
  - TD-020 — ca54b0ef; one credit_stv key in apps/courses/serializers.py
  - TD-021 — 20a5d036; eligibility_service.deduplicate_pismp
  - TD-050 — quiz/page.tsx reads the locale from useT; halatuju_lang is gone
  - TD-067 — ec10ee6e; the final profile IS the sponsor version (views_admin/verdict.py)
  - TD-071 — 2d809b2f; Turnstile on sponsor sign-up
  - TD-073 — 93da774b (TD-182); auth-context.tsx isAnonymousAuthSuppressed
  - TD-078 — 11e055f3; tests/test_subject_drift.py pins both maps
  - TD-083 — 7d0fe1fe; AiReliabilityCard shows the override rate
  - TD-086 — a6bed1f5; branding.email_support is help@halatuju.xyz
  - TD-099 — 36912aac; admin/layout.tsx holds a new reviewer on the profile page
  - TD-109 — views.py: students see system document requests; the cockpit shows all
  - TD-113 — b493cfa0; check2 asks each earner for income proof
  - TD-136 — 84338ae2; phone verification via Twilio Verify is live
  - TD-138 — ffbbf5b7; both proposed-slot content SIDs are set on the live api (read 2026-09-30)
  - TD-144 — e2f1cf03; the panel reads the real agreement
  - TD-146 — 636799ce; the sponsored status is retired
  - TD-147 — af9868b0; migration 0079
  - TD-148 — cc0e0ad1; bank-details capture is switched off, students are paid via Vircle
  - TD-149 — cc0e0ad1; bank-details capture is switched off (returns only if the flag is re-enabled)
  - TD-159 — 4135979c; the Blockers card reads consent_blockers
  - TD-161 — 917d43cc + ad2d33ac; services/confirmation.py follows the offer's pathway type
  - TD-175 — 27562de0; the clock is frozen in those tests; no second sighting
  - TD-176 — 3e11699b; sponsorship.sign_admin_credit checks the admin's identity
  - TD-177 — 8636b1b6; bursary_e2e sets the programme
  - TD-188 — 3a6c4586; the owner reviewed the live console on 2026-07-28
  - TD-189 — 5c2fa368; a bare /apply asks which round (views._open_round_choices)
  - TD-193 — the gift crumb filters since 2026-09-03; the organisation half is TD-228
  - TD-199 — 71665063; the wallet-ID band is 7-9 (about 400 students of room)
  - TD-235 — superseded by TD-262, which extends it; c2d0324b serves income_shown
  - TD-237 — f44d9d11; navigation.programmeGroupFolded
  - TD-268 — code_health.py counts import edges since H15
  - TD-272 — 591b6a9b; a declared move keeps its ledger entry
  - TD-274 — workspace 1bcf720; code_health.loosened accepts a declared relabel in list ledgers

**For the owner (23 entries):** TD-043, TD-066, TD-075, TD-096, TD-128, TD-133, TD-140, TD-142, TD-143, TD-152, TD-179, TD-192, TD-198, TD-210, TD-211, TD-225, TD-227, TD-230, TD-260, TD-262, TD-265, TD-311, TD-318.

**Gates.** `test_technical_debt_register.py` 3 passed; `code_health.py` td_open 159 = the index;
`wat_lint.py` 0 fails. Docs only, no deploy.

### 2026-09-18 — eleven changes: five the owner SAW, six nobody could see

**Reflect.** Two clusters, a fortnight apart and completely different in kind.

The 8 Sep seven came from one walk of the console: a layout rule that classified two pages wrongly,
a menu sliced off by the wrapper that rounds the corners, a Save button awake with nothing to save,
a page size of 10 where 25 was wanted, a column that could only ever print a dash, a Resend that
returned in SILENCE, and Enter posting a half-written note to a donor. One engine change rode with
them (an exact NRIC match vouching for a differently-spelt name).

The 18 Sep four came from the machinery, and every one was found by a MACHINE or by an alert, not by
a person using the product: Supabase's own advisor found a table without RLS; the owner asked why a
retired job was still listed; ~860 cron runs were found carrying 8 real changes; 41 phone numbers
predated the formatter. Two more of the same day are recorded in the CHANGELOG rather than here
(#144's dropped activation, #16 closed by hand) because they were data, not code.

**Cohere — the cluster is not a surface, it is a SHAPE.**

Nine of the eleven, plus both same-day data fixes, are the same defect wearing different clothes:
**something that looks armed and does nothing.**

  * Resend drew a link, found no staff account, and returned silently.
  * Save was enabled with no change to save.
  * A paused scheduler job pointed at a job name the server had already forgotten (404).
  * `lapse_expired_offers` is written, tested, and wired to nothing (TD-252).
  * The activation webhook stored a wallet and dropped the activation (TD-251).
  * A new table shipped without RLS; the rule lived in other migrations' docstrings.
  * The 15-minute sync rewrote a whole file 96 times a day to carry nothing.

This is the third consolidation in a row to land near it (2026-08-19's "UI asserts what nothing
checks"; 2026-09-08's "a fix that only exists in a habit"), and it is worth stating plainly: **the
recurring class here is not bugs in what code does — it is code that does nothing while appearing
to.** It survives review because every part is individually correct.

**Anticipate — one guardrail, landed in this pass.** `sprint-close.md` gains a RETIREMENT step: when
code is retired, its scheduler job, its env vars and its settings go in the SAME change, and the
close reconciles Cloud Scheduler against `CronRunView.JOBS` in both directions — a job whose name is
not in JOBS can only 404, and a JOBS entry with no scheduler job is a capability nobody can reach
(which is precisely TD-252). Both halves are one command each and neither existed as a habit.

No sprint was promoted. The console cluster of 8 Sep was five independent misses on five surfaces
with no shared mechanism — a redesign would be inventing a cause. The Vircle pair (TD-251, TD-252)
DO share a mechanism and are now written next to each other, with the owner's ruling recorded: do
not chase Vircle until the next activation.

**Close out.** Pending cleared (counter reset). Guardrail landed in `sprint-close.md`. Open Items
Index in `technical-debt.md` regenerated and dated, WITH its method — and the method now says in so
many words that a resolution marker is a marker, not a word in a sentence, because the first attempt
at the regeneration marked TD-252 resolved on the strength of the phrase "cannot be closed".

### 2026-09-08 — Consolidation review (11 small changes, 19 Aug → 8 Sep)

**Reflect.** Eleven entries over three weeks, and they cluster hard. **Three are BrightPath #21**
(the frozen income gate, the cockpit display, the Approve lock-out — all on 7 Sep); **two are
BrightPath #20** (the repair that could not be run, and the correction its own report caught);
**two are the merit/grades pair** on 2 Sep (an engine backstop and the form fault upstream of it);
the remaining four are one-offs — billing attribution, the eWallet ID band, and two copy fixes.

Most were genuine fixes. Two were symptoms of something the previous review had already named:
the billing-attribution entry is the **fourth** instance of *"complete for the callers that existed
when it was written"*, and #20's repair is a new variant of *"the backward repair is the half that
gets forgotten"* — new because the repair was NOT forgotten. It was written, tested, shipped, and
had nowhere to run.

**Cohere — the clusters.**

- **The income rule has more than one home (3 entries: the #21 gate, the #21 display, the #20
  sweep).** The owner widened "income may be shown any one way" on 25 July. Over six weeks, three
  separate copies of the older narrower rule surfaced, each by a different route and each on a live
  student. Each fix was locally right. The class is the duplication, not the three bugs.
  **Promoted to TD-235** with its trigger written down (a fourth instance, or the next change to
  what counts as income evidence).
- **BrightPath #20 and #21 rode the small lane as five entries.** Both were customer-raised defects
  and each fix was genuinely small, so the lane was the right call per step 1 — but it is worth
  seeing that ONE request produced three same-day entries. Not promoted: they were three distinct
  faults on one report, and the coherence they lack is covered by TD-235 above.
- **The merit pair (2 entries, same day)** is the healthy shape, not drift: an engine backstop AND
  the upstream form fix, shipped together with the reason each alone is insufficient recorded in
  both. Nothing to promote.

**Anticipate — the guardrail landed this round.**

- **Every repair must have a route to the data it repairs.**
  `apps/scholarship/tests/test_repair_commands_have_a_door.py` scans both apps for
  `backfill_*` / `repair_*` and fails unless each is registered in `CronRunView.JOBS` or listed in
  `NO_DOOR` with its reason. **Bite-checked by planting a stranded command.** It self-applies by
  NAME, so the next one is covered with nobody remembering. This converts #20's fortnight — a
  finished, correct, unreachable repair, with nothing broken and no test failing — from a thing we
  noticed by accident into a mechanical catch. The thirteen existing door-less commands are seeded
  into `NO_DOOR` honestly and carried as **TD-234**; the guard's job is that a fourteenth cannot be
  added without a decision.
- **No guard was invented for the income cluster, deliberately.** Its three instances are in two
  languages and answer three different questions, so the cheap cross-check does not exist. The
  previous review's caution applies — a class whose instances no longer share a shape gets a watch,
  not a guard that passes while the next variant walks past. **This is the second class to be given
  a watch rather than a guardrail**; if a third arrives, the pattern itself is worth a look.

**One process finding, cheap and worth keeping.** #20's repair was READ IN REPORT MODE before it
was allowed to write, and that is the only reason a `not_salary` photo did not take a genuine
payslip's slot on a live record. Every prediction on file — the command's docstring, its test, the
24-August changelog — said the opposite would happen. **A prediction written when the code was
written is a claim; the run is the result.** Recorded in `docs/lessons.md`.

**A second guardrail, forced by the review's own push.** Staging this review collided with the
other agent working the same repo: we both raised a ticket within hours, both took the next free
number by reading the register, and both got **TD-233**. Ids are allocated by reading a file, and
the file each of us read was correct when we read it. It surfaced only because the push happened to
be refused as a non-fast-forward — with a different edit order it would have auto-merged silently
and the register would carry two TD-233s for ever. Mine renumbered (**TD-234**, **TD-235**; theirs
was pushed first and stays), and `test_technical_debt_register.py` now fails on a duplicate defining
heading. **It immediately found two collisions from 2026-07-03 that nobody had noticed in two
months** (TD-151 and TD-152 each name two different tickets); they are DECLARED, not renumbered —
two months of citations point at those numbers. ⚠ **My first version of that scan ignored the
register's own counting note and failed on 19 false duplicates, my own two among them.** The note
had said, in as many words, to exclude the index and to distrust the bullet era.

**Close out.** Pending cleared (counter reset). Both guardrails landed in-cycle and bite-checked.
**TD-234** and **TD-235** raised. The Open Items Index in `docs/technical-debt.md` was regenerated
and, in the process, **TD-222 and TD-224 were found closed-but-unmarked** — both closed by Layer 1
sprints that told their retro and the project file and not the register. Marked, and the omission
noted in the index so the next sprint closing a TD says so in the register itself. The index's
own count could not be reproduced from the previous regeneration's figure; the method actually run
is now written down beside it.

### 2026-08-19 — Consolidation review (14 small changes, 25 Jul → 18 Aug)

**Reflect.** Fourteen entries over three and a half weeks, and they are not evenly spread. **Five
are the Requests module** (three on 30 Jul, one on 1 Aug, one on 18 Aug); **three are billing**
(the dark-ship narrowing, the Malaysian-month default, the six senders billing the platform); the
remaining six are one-offs across the officer cockpit, the student Documents tab, payments and the
interview-credit repair. Two entries in the window were correctly refused by the lane and closed as
sprints instead (the sponsor gift-membership, and the exam-type overload — the second caught by
`wat_lint` before the close rather than by a reviewer after it, which is the linter doing its job).

Most were genuine fixes. Three were symptoms: the interview-credit repair (the rule had been fixed
five days earlier and the corrupted rows left behind), the billing attribution (four senders wrapped
in July, the next eight born wrong), and the Requests answer 500 (a rename completed in the service
and the endpoint and not between them).

**Cohere — three clusters, and one of them is now a sprint.**

**1. The Requests module (5 entries) — NOT promoted, and the reason is the interesting finding.**
Five patches to one surface in three weeks reads like a redesign asking to be a sprint. It is not.
The three on 30 Jul were a UI-affordance failure reported three times before it was right, and the
guardrail that answered it — the rendered-test gate plus the four-command frontend gate list, both
landed in `CLAUDE.md` — **held**: no further UI-affordance bug has appeared in this module since.
What appeared instead was a *backend* seam failure (the 18 Aug answer 500). **The guardrail worked
and the failure moved next door.** That is worth recording as a success rather than promoting the
module wholesale, and it points the next guardrail at the seam rather than the surface.

**2. "The fix was complete for the cases that existed when it was written" — now FOUR instances,
and the class regenerates.** The interview credit corrected the rule and left 25 rows carrying the
old one; `award_amount`'s clear fixed the writer and left two stale rows; the billing attribution
wrapped the four senders then firing and left the next eight to be born wrong; and — not previously
counted, because it closed as a sprint — **the SPM exam-year anchor (BrightPath #12) was complete
for the certificates that existed and broke on a differently-cropped scan.** The first two are about
rows already written; the last two are about cases not yet written, which is worse, because nothing
stops them arriving. Guardrail below.

**3. "The UI asserts what nothing checks" — five instances plus a near-miss, and it has stopped
being the same bug.** The hard-coded padlock, `qc_override_reason`, `ai_draft_model` and request
#3's "Answer needed" were all *field stored, never rendered*. The near-miss (a staged draft's
`created_at` rendered date-only on a list where several rows share a day) was *rendered at the wrong
granularity*. The class has drifted from "is it on screen" to "does what is on screen let the reader
decide". That is no longer mechanisable as one check, and a sixth point fix would not converge.
**Deliberately NOT given a guardrail this round** — it is recorded as a live watch, and the next
instance should be read for which of the two it is before anything is built.

**Promoted:**
- **TD-218 — `exam_type` answers two questions and six surfaces read it.** Now the FIFTH instance
  (#11's "No profile found", the dashboard behind it, #14's admin tag, #14's apply step, and the
  `results_exam_type` work itself). The standing note said a fifth is a rename, not a fix. It is a
  sprint and it is now written down as one.
- **TD-219 — nothing tests the seam between a view and the service it calls.** Two instances in one
  day on 18 Aug (the analysis command's dropped triage; every answer 500-ing for 18 days), both with
  a well-tested service, auth-tested endpoint, and nothing exercising the call between them. A gap
  between two well-tested halves is invisible to tests of either half. The mechanisable form —
  diffing view call-sites against endpoint-test URLs — is a sprint, not a checklist line.

**Anticipate — the guardrail landed this round.** Cluster 2 is the one that regenerates, so it is
the one that got prevention rather than another fix. Two rails added to `small-change-lane.md` Part
A, where every future small change has to read them:

- **A fix that changes how a STORED value is derived must state how many existing rows carry the old
  derivation, and whether they are being repaired.** The repo already has the tool shape for it —
  `audit_pathway_ticks` computes the old and the new answer in one pass over real data.
- **A fix whose correctness depends on every FUTURE caller remembering something is a convention,
  not a fix.** Name in the change how the omission is made impossible or loud, or say why it cannot
  be. This is the half that regenerates, and it is the one the 18 Aug billing entry named and
  deliberately did not build.

**Lane honesty carried forward.** One entry in this window was 15 files against the lane's ~5 cap
(the 30 Jul evidence/margin/quote change — three owner directives in one sitting, each individually
tiny). It carried no migration, model or new surface, so it stayed. That is now the second window in
which the file-count proxy has been exceeded by batched directives rather than by scope. **If it
happens again, the proxy needs to become file-count-OR-directive-count** — flagged, not yet changed,
because two instances is thin evidence for a rule change.


### 2026-07-23 — Consolidation review (13 small changes, 1 Jul → 23 Jul)

**Reflect.** The 13 entries fall into four groups: the **STR-proof verdict/copy stream** (4 ×
2026-07-01: means-test refinement to MODEL_VERSION 1.2.1, Lulus chip, prescriptive Check-2 copy,
the raw-ICU rendering fix); the **Administration-panel world split** (2 × 2026-07-15: per-panel
lists, staff-table split); the **tenancy fix-forward annotations** (3 × 2026-07-23, from the
compliance check-up — deliberate rule-1 exemptions recorded in place, not fixes); and four
genuine one-offs (pathway-switch promotion engine fix +9 tests; verdict-item i18n gap + class
guard; witness-card stage-gating +11 tests; cancelled-runs hide-toggle, which records the design
decision that `payments.cancel` deliberately has no delete).

**Cohere.**
- **PROMOTED: the STR-proof cluster** → `docs/retrospective-2026-07-23-str-proof-cluster.md`,
  the consolidated retro the 2026-07-01 entry called for. Honest finding recorded there: the
  1.2.1 means-test refinement rode the small lane but bumped a verification model and touched
  money-adjacent verdicts — by the lane's own boundary that was sprint-grade work. The retro is
  the repayment; the boundary reminder stands: **a MODEL_VERSION bump is never a small change.**
- The Administration-panel pair needed no promotion: coherence was restored by the per-panel
  design + `lib/adminStaff.ts` helpers with regression tests (the guardrail landed with the fix).
  Any further panel polish batches with the next real admin work (deploy cap rule).
- The three tenancy annotations are not drift — they are the 2026-07-22 audit's fix-forwards,
  and their real home (extraction to cohort fields) remains Phase-2 S5–S9.

**Anticipate.**
- **Recurring class (×2): a backend enum value reaches the officer UI without its i18n key**
  (2026-07-01 raw ICU render; 2026-07-23 missing `pathway_type_switch`). The guardrail landed
  with the second fix — `test_verdict_item_i18n.py` covers the WHOLE verdict-item class, so the
  next new verdict item fails CI until its en/ms/ta keys exist. Generalised into
  `docs/lessons.md`: when backend enum values feed frontend i18n keys, ship a class-covering
  parity guard with the first fix, not a per-value patch.
- No other class recurred; 4 of the 13 entries carried their own regression tests — the lane
  working as designed.

**Close-out.** Pending cleared (13 → 0; counter reset). Promoted: 1 consolidated retro.
Guardrails: verdict-item i18n class guard (landed with the 2026-07-23 fix, credited here) +
the lessons.md line. Boundary reminder recorded: MODEL_VERSION bumps and money/consent-adjacent
verdict changes take the sprint lane.

### 2026-06-16 — Live-review round (9 small changes)
**Reflect.** The 9 changes touched three surfaces: the **AI profile generator** (5: distil-all-inputs,
interest-quiz, statement-of-intent, grades-grouping/ethnicity, prompt-versioning), **web i18n hygiene**
(3: TD-118, TD-120, cockpit copy tweaks), and **reviewer access** (2: hide assignee filter, set-password page).
Most were genuine fixes; the profile ones were additive improvements, not symptom-patching.

**Cohere — clusters promoted:**
- **Profile completeness & safety (5).** Not five fixes — one coherent body of work: "make the AI profile use ALL
  the data the student gave us (typed fields, quiz, statement-of-intent), summarised well, and without leaking PII or
  ethnicity." Recognised as a mini-feature; the prompt is now **versioned** so it can evolve safely. Captured in
  `decisions.md` (prompt versioning; grades-by-group; generalise-ethnicity).
- **i18n drift after redesigns (3).** Recurring class: cockpit redesigns leave orphaned `admin.scholarship` keys.
- **Reviewer onboarding (2).** Non-Google invitees couldn't onboard; the set-password page closes the systemic gap.

**Anticipate — guardrails (recurring fix → prevention):**
- i18n orphans → **guardrail test added** (`messages/__tests__/admin-scholarship-i18n.test.ts`, dynamic-aware) — the
  class can no longer silently regrow. ✅
- Stale AI drafts after a prompt change (the #18 trap) → **PROMPT_VERSION + version-aware backfill added** — staleness
  is now detectable by version, and re-running the backfill only refreshes stale drafts. ✅
- **Candidate (not built):** schedule the version-aware backfill (or trigger it on a `PROMPT_VERSION` bump) so drafts
  self-heal without a manual cron call. Logged for a future pass.

**Close out.** Pending cleared (counter reset). Guardrails landed in the same round. Folded into the 2026-06-16
sprint-close (retrospective `docs/retrospective-2026-06-16-livereview-round.md`).

### 2026-06-29 — Consolidation review (15 small changes)
Covers the 14 `## Pending` entries (2026-06-16 → 2026-06-29) plus one reviewer-FAQ-docs entry that had been
misfiled under this section.

**Reflect.** The 15 changes touched five areas:
- **Document extraction & income computation (5)** — SPM 2-column slip under-read; handwritten salary-voucher
  `ringgit|sen` mis-read; salary-route earner Optional/undeclared (#90); `document_unreadable_blockers` list-vs-app
  bug; IC/parent_ic silent-OCR self-heal. All genuine fixes — but all the *same shape*: a document reads wrong and a
  B40 decision turns on the bad read.
- **Reviewer features (4)** — Guide + FAQ pages; language fluency (migration 0059); advance-notice email (migration
  0060); a follow-up FAQ-content update. These were **features with migrations**, not small changes.
- **Check-2 / Action-Centre student visibility (2)** — reviewer-raised requests now notify the student; system
  "couldn't read your doc" requests surfaced to the form-locked student.
- **Interview/status flow (2)** — fold the two interview-question buttons into one; advance `profile_complete →
  interviewing` when slots are proposed.
- **Copy + display casing (2)** — "Sponsor profile (draft)" → "Student profile (draft)"; ALL-CAPS offer programme
  name leaking to the sponsor pool (#107).

**Cohere — clusters promoted:**
- **Document-extraction & income robustness (5) → [TD-151].** The dominant cluster, and the one that keeps
  regenerating: five isolated point-fixes that are really one hardening pass (a scrubbed extraction-regression
  corpus + an income read-sanity gate + a generalised silent-OCR self-heal). Promoted to `technical-debt.md`
  TD-151 as a 1-sprint pass, not an N+1th point fix.
- **Reviewer features rode the small lane (4) → process drift.** Per `small-change-lane.md` step 1, a feature or a
  migration is a **sprint**, not a small change — these four (two with migrations) should have been one
  "reviewer-onboarding & comms" sprint. Shipped fine, but the boundary slipped four times; this is the recurring
  *process* class, addressed by the guardrail below.

**Anticipate — guardrail landed this round:**
- **`wat_lint` now flags a misclassified small-lane entry** — any `## Pending` line containing `feat:` or
  `migration` is reported as "should have been a SPRINT" (`small-change-lane.md` step 1). Converts the recurring
  feature-rode-the-lane drift from a thing-we-notice-in-hindsight into a mechanical catch at the next lint.
- **Display-value leak via a non-canonical write path** (the #107 casing leak) was already converted to prevention
  in the same hotfix (idempotent `title_case_programme` guard + a `docs/lessons.md` rule to grep every writer of a
  normalised field). No further action.

**Close out.** Pending cleared (counter reset). Guardrail (`wat_lint` misclassification check) and the casing guard
landed in-cycle; the extraction cluster is parked as TD-151 for a dedicated sprint.
