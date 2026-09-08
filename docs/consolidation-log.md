# Small-Change Consolidation Log

Tracks one-off small-lane changes between full sprints. Every ~10 pending entries triggers a
Consolidation Review (see `Settings/_workflows/small-change-lane.md` Part B).

## Pending

_(cleared at the 2026-09-08 review — counter reset; the 11 reviewed entries are listed in that review)_

- 2026-09-08 fix: three detail pages get the wide layout — the owner walked the console after the layout standard shipped and found the payment run and the B40 application cramped. Both had been forced to `reading` because they show ONE of something, which is not what the rule asks. The rule's WORDING was the fault and is corrected: "leads with a table?" → "lays its content out in MULTIPLE COLUMNS?". ⚠ The cockpit is the sharp case — it had been **1152px** for months, so standardising it to 900 made it NARROWER than it had ever been, a regression dressed as a standard. `/admin/sponsors/<id>` was widened unprompted for the same reason (two tables) before it became the next report. 2 files, web only, bite-checked. **Check a classification rule against the pages it will get WRONG.**

- 2026-09-08 fix: Resend on a donor invitation now actually sends (BrightPath #16) — the link was drawn on donor rows, checked for a staff account, found none and returned in SILENCE: no request, no record, no message, which is why the owner could not tell whether it had worked. Wired to `create_or_refresh`, which is what a resend already was (idempotent on an open invitation: finds the row, moves its expiry, sends, records) — no new endpoint. Reports both ways, and the reloaded row carries the failure reason. No note (not stored; storing it would need a new column) and no `programme_id` (naming one would re-home the benefactor). 4 files, no schema change, +2 i18n keys, both directions bite-checked. ⚠ **This corrects our own posted analysis**, which told BrightPath the capability "does not exist today — not behind the broken link, not anywhere else" and priced 2.0h to build it. It existed. The analysis was written from the button inwards and never read the engine's docstring, which says idempotent-and-refreshes in its second line. **Read the engine before pricing the absence of one.** First change built in my own worktree, which is also why `next build` did not collide this time.

- 2026-09-08 fix: the sponsors table drops the Role column instead of dashing it — owner, on the live page while testing #17: *"what is the purpose of the role column?"* None, there: a sponsor invitation creates no account and carries no role, so the column could only ever print "—" for every row for ever (confirmed on production — every sponsor invitation has an empty role). `InvitationsTable` takes `showRole`, passed by KIND, never derived from the rows: reading it off whichever rows are loaded would hide the column on a staff table the day one arrives blank, turning a missing value into no question at all. 3 files, web only, both directions bite-checked. **A dash is not neutral — it reads as a value we failed to fetch, which is exactly the question it prompted.**

- 2026-09-08 fix: Enter in the invitation note no longer sends it (BrightPath #17) — the note was a single-line `<input>` inside the form whose main action is Send invite, so the browser's own "Enter means I have finished" posted a half-written note to a DONOR, unrecoverable. Now a `<textarea>`; nothing else on the form moved. The email already carried line breaks and that is pinned rather than assumed (plain text + `email_templates.render` fills blocks without collapsing) — two tests, one on the built-in body and one on a stored `PartnerEmailTemplate`, because production has a seeded row and the stored path is the one that sends. 3 files, no schema change, no new i18n keys. ⚠ **The first rendered test was VACUOUS and is deleted**: "press Enter, assert nothing was sent" passes against the broken input too, because jsdom does not implement implicit form submission. Caught by injecting the old `<input>` and watching the file stay green. **Second silent bite in one day** — the other was #20's fixture with no `parent_ic`. What is asserted now is the pair that decides the behaviour: a textarea, inside the form.

- 2026-09-08 fix: a matching IC number vouches for a differently-spelt name (BrightPath #19) — a birth certificate and the mother's MyKad carrying **the same twelve digits** and two Latin spellings of one Tamil name read as a red name mismatch; we asked the student for "a corrected birth certificate" she cannot obtain, and the JPN letter she sent instead attesting that both spellings are the same woman could not be machine-read either. `_combine_relationship` gains `check_name` — name differs + NRIC matches EXACTLY → amber, never green, never on `nric_close`. It is the **mirror of the rule already in that function**, which forgives a misread NUMBER when the name agrees; the number is the stronger evidence of the two. Blast radius MEASURED over all 62 live mother rows before shipping: exactly 2 move (144, and 84 where the misreading was OUR OWN OCR), and both genuinely-different-person reds stay red because neither number matches. 7 files, no schema change, +1 i18n key, bite-checked. ⚠ **The second fault on that record is deliberately unfixed**: her certificate never reached the name check, because `_pdf_first_page_png` reads page 1 only of a scanned PDF and hers is a merged scan. Reading every page is its own decision (cost, and which page wins) and was the alternative the owner declined.

- 2026-09-08 fix: the round menu escapes the table, and the edit dialog's Save sleeps until there is a change — owner, on the deployed screen: *"Clicking the close opens something, but it is hidden"* and *"the save is enabled even though no change has been made"*. The menu was `absolute` inside a table wrapper carrying `overflow-hidden` (there to round the corners), so it was sliced off at the table's edge. Fixed in the PRIMITIVE — `Menu`'s panel is a portal on `document.body`, measured and placed, flipping above the trigger when the space below is short — because the local fix would have left the trap armed for the next card, modal or rounded panel. ⚠ The portal takes two obligations with it: the click-outside guard must test the panel as well as the wrapper (or the mousedown on an item closes the menu before its click fires, and every menu item in the console becomes a no-op), and a `fixed` box anchors to `documentElement.clientWidth`, not `window.innerWidth`. The Save now compares as it will be SENT (name trimmed, blank box as null). 4 files, web only, no schema change, no new i18n keys, three bite-checks. ⚠ **The placement arithmetic has no test that can fail** — jsdom returns 0x0 at 0,0 from every `getBoundingClientRect`; only the panel's place in the DOM is pinned.

## Reviews

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
