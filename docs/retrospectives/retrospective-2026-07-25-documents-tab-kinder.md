# Retrospective — Documents tab: calmer, kinder progressive disclosure — 2026-07-25

A live-review UX arc on the student **Documents** tab (`ScholarshipDocuments.tsx`), driven by the
owner reading real screens. The through-line: **a wall of upload boxes intimidates B40 applicants —
show only what must be acted on, fold away what's finished, and never demand proof a genuine family
can't produce.** Plus one QC copy fix at the start of the session.

## What Was Built (in ship order)

1. **QC decline-route copy fix** (`311bc956`, deployed). On an `interviewed` (awaiting-QC) case with
   an officer **decline** verdict, the cockpit card said "Accept to move it to Recommended" while the
   button read "Confirm decline" — a direct contradiction. Made the hint + secondary action
   **verdict-aware**: a decline case gets its own hint (`hintDecline`), the secondary button is
   **Reopen** (not "Reopen/Reject" — reject is already the primary), and the reopen panel copy fits
   "send back to the reviewer". Redundant reject toggle hidden. i18n en/ms/ta.

2. **Calmer Documents tab — done + optional stages fold** (`fc3529df`, deployed). One reusable
   `CollapsibleSection`, three uses: a verified doc (IC / results slip via `docDone`) folds to a green
   "all done" summary; the **income** block folds once a route is *satisfied* (`strComplete` / new
   `salaryComplete`) with an inviting "add more to strengthen your case" line, not "nothing to do";
   **Utilities** and **Additional documents** collapse by default (optional stages). Guard: nothing
   required-but-unmet ever collapses.

3. **Tidier file rows + STR-route optional fold** (`35034192`, deployed). New `FileChip` — one bordered
   row with the filename left, **Replace + Remove grouped right**, instead of the two actions stacking.
   Applies to every single-file card. STR-route salary/EPF optional cards folded under a "More income
   documents" collapsible like Utilities.

4. **Income shown "any one way" — the Janani redesign** (`f37db48d`, committed by the deploy agent from
   this session's handoff). Reframes the salary-route income requirement: IC + relationship doc stay
   required; income is satisfied **any one way** — a payslip, a readable EPF, **or a declared amount +
   a supporting letter** (or a non-breached STR). New single source `income_engine.member_income_evidenced`
   drives both `member_cluster_complete` and the submission gate; the salary slip is no longer
   compulsory and the gate emits a friendlier `income_evidence_missing`. A declared amount ALONE stays
   blocked until the letter lands. **Submission-gate only — no verdict/band moves.** FE: an "Income —
   show it any one way" group (green once shown), warm cash path (the orange "we'll ask for a document"
   tone removed), letter sourced "from your school, your ketua kampung or penghulu, or employer".

Data op: **test app #16 reset awarded → shortlisted** for re-testing (cleanly: holding sponsorship #36
cancelled to restore sponsor balance, award_amount/awarded_at/recommended_at/award_due_at cleared).

## What Went Well

- **Artifact-demo-before-build.** Each non-trivial change was demoed as an interactive Artifact
  (theme-aware, product-faithful) and iterated in the demo *before* touching code — the collapse
  behaviour, the income redesign, the wording. The owner shaped copy and behaviour cheaply; the built
  result matched the approved demo first try.
- **Reusable primitive over per-case hacks.** One `CollapsibleSection` served three surfaces; one
  `member_income_evidenced` became the single source shared by the gate and the wizard, so they can't
  drift (the exact class of bug that made #45/#116 traps).
- **Backend gate change was test-anchored.** The old-policy tests were updated *to* the new policy and
  new cases added (Janani's declared+letter, EPF-with-value, declared-alone-blocks) — 3270 scholarship
  pytest green before handoff.

## What Went Wrong

1. **The `salary_slip_missing` gate was more permissive on paper than in practice — the declared path
   didn't actually unblock anyone.** Symptom: the "Can't get a payslip?" flow existed but a cash/informal
   earner with no STR still hit a red-`*` salary slip they couldn't satisfy. **Root cause:** the declared
   + support-doc path fed the *assessment* (`earner_monthly_income` → `declared_evidenced`) but was never
   added to the *submission gate* (`income_doc_blockers` only relaxed the slip for an STR) — two code
   paths encoding "what counts as income" independently, so they drifted. **Fix:** a single
   `member_income_evidenced` now owns the rule, read by both the gate and `member_cluster_complete`; a
   guard test asserts the wizard and gate agree. Lesson for lessons.md.

2. **Concurrent agent on a non-isolated repo.** Symptom: repeated "file modified on disk since last read"
   warnings mid-edit; my uncommitted work was later committed by a second agent (`f37db48d`) alongside
   its own Billing sprint. **Root cause:** two agents sharing `Production/HalaTuju` without worktree
   isolation. **Fix:** it resolved cleanly here (edits were on disjoint files; the deploy handoff used
   my suggested message), but the standing rule holds — stage explicit paths, never `git add -A`, and
   prefer `parallel-work-isolation.md` worktrees when two agents share a repo. Already in CLAUDE.md; no
   new system change needed.

## Design Decisions

See `docs/decisions.md` (2026-07-25): income shown "any one way"; EPF-with-a-value counts; declared
amount alone (no letter) stays blocked; collapse only a required-but-**met** or genuinely-optional stage.

## Numbers

- **4523 pytest + 738 jest** (1 pre-existing env-only jest failure: `scholarship.test.ts` localStorage
  under Node 26 — fails identically on untouched origin, green on CI). No migration.
- Commits: `311bc956`, `fc3529df`, `35034192`, `f37db48d`. Four web deploys (SUCCESS); the income
  redesign committed via the deploy handoff.
- Frontend-only except the income gate (backend logic, no schema change).
