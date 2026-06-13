# Retrospective — Document slot model, Sprint 1: tolerant readers + per-person tagging (TD-115, 2026-06-13)

Sprint 1 of the document slot model (spec: `docs/scholarship/document-slot-model-plan.md`). Lays the
foundation for 27 fixed `(doc_type × person)` slots. **Code + data migration; no schema change.** Shipped to
`main` (`7b460d4`) + backfill applied via Supabase MCP. The Check-2/Check-3 process flow & display are a
separate, deferred pass (owner's call).

## What Was Built
- **Tolerant readers** — `income_engine._cluster_docs` + cockpit `officerCockpit.incomeDocLayout` read income
  docs **by person** with a blank-as-earner fallback on the STR route. They read correctly whether a doc carries
  the legacy blank tag or the new person tag — so deploying them changed nothing, and they kept working after the
  backfill.
- **Authoritative upload tagging** (`views.DocumentListCreateView`) — STR-route `str/parent_ic/salary_slip/epf`
  are tagged with `income_earner` regardless of what the client sends (also slots Action-Centre/Check-2 uploads,
  which carry no member), and the single-instance sweep also replaces the **legacy untagged** copy so a re-upload
  overwrites instead of duplicating. Wizard STR cards tag + display per-earner (legacy blank tolerated).
- **Backfill** (MCP) — 53 STR-route blank income docs tagged to their earner; **0 blanks left, 0 duplicate slots.**
- **Route correction** — #12 (the one mis-routed app) flipped `salary → STR/mother` via the audited
  `switch_income_route` service.

## What Went Well
- **Tolerant-then-tighten gave a zero-downtime rollout.** The hard rule (readers tolerant *before* the backfill)
  meant there was never a window where prod code couldn't find a doc — deploy, then backfill, both safe in isolation.
- **Verdict invariance fell out for free.** Reading the verdict engine first showed its STR branch already reads by
  doc-type (not member), and salary by member tag — so the migration provably couldn't change any verdict. Proven
  by 1197 pytest staying green with no expected-value edits.
- **Investigate-the-prod-data-first paid off.** Mapping every `(doc_type, member)` pair + the route-mismatch scan
  *before* writing code meant the migration was deterministic for ~all docs, with only one real route correction (#12)
  and a 3-app exception set we'd already hand-reconciled — no surprises during the live backfill.

## What Went Wrong
- **The DB uniqueness constraint turned out bigger than "add a constraint" and was deferred.** Symptom: planned as
  part of the tighten, but adding `UniqueConstraint(application, doc_type, household_member)` breaks existing tests
  that deliberately pre-create two same-slot docs to verify the sweep (e.g. `test_single_instance` makes two blank
  ICs directly), and it needs a careful migrate-first reconciliation. Root cause: the constraint changes a long-standing
  invariant (multiple same-slot rows were possible and tests leaned on it). Decision: defer — the **app layer already
  prevents duplicates** (authoritative tagging + tolerant sweep on STR; single-instance per slot on salary), so the
  constraint is belt-and-suspenders, not load-bearing. Lesson: a "just add a unique constraint" step is rarely just
  that — check what currently relies on the absence of the constraint (fixtures, flows) before scoping it into a sprint.
- **Two agents shared `main` without worktree isolation, and the search fix got pushed earlier than intended.** The
  course-data-pipeline agent's sprint-close push swept up my locally-committed "don't push" search fix, deploying it
  ahead of plan. No harm (it was tested + good), but it violated the explicit hold. Root cause: this slot-model work
  branched normally off a shared `main` instead of using a git worktree (`parallel-work-isolation.md`), so local
  commits intended to stay local rode along on someone else's push. Lesson: when another agent is active in the repo,
  use worktree isolation — a local commit on shared `main` is not a private commit.

## Design Decisions
See `docs/decisions.md` — "Slot model: tolerant-then-tighten rollout; route controls display not storage; backend
authoritative for income-doc tagging."

## Numbers
- 1197 scholarship pytest + new tolerant-reader (3) & STR-tagging (1) tests; FE build clean.
- Backfill: 53 docs tagged, 0 blanks, 0 duplicate slots. No schema change.

## Deferred / Next
- **DB `UniqueConstraint(application, doc_type, household_member)`** — add via migrate-first with the test-fixture
  rework (the permanent guarantee; app layer covers it meanwhile).
- **Salary-route Action-Centre member-tagging** — a salary-route query upload must carry the member from the
  resolution item's `:member` code (the STR path is already fixed by the authoritative backend tagging).
- **Check-2 / Check-3 process flow & display** — the separate pass the owner asked to tackle next.
