# Retrospective — Sponsor-profile income honesty + cockpit final-label fix (2026-06-18)

A short live-review round driven by reading two real generated profiles (#21, #10) plus a
cockpit labelling bug spotted on #4. Worktree `.worktrees/sched` (branch
`feat/interview-scheduling`); shipped on `main` `73b9586` (backend) + `289853a` (frontend).

## What Was Built

1. **Income honesty in the sponsor profile — one principle, both directions: documented = certain,
   self-reported = a claim.** (`PROMPT_VERSION` 2026-06-16.2 → 2026-06-18.1)
   - **Don't over-claim (#21).** `profile_engine._gated_str` / `_gated_jkm` now mirror the existing
     `_gated_first_in_family` claim-gating: STR is asserted as fact only when a *current* STR document
     is on file (reusing `income_engine.student_str_check` → `current_status == 'current'`); a
     self-declared tick with no doc, or a stale/rejected one, returns the `_DO_NOT_CLAIM` sentinel.
     JKM has no document in the flow, so a declared JKM is never assertable. The INCOME & WELFARE
     prompt rule was rewritten to enforce this.
   - **Don't under-state (#10).** The documented-salary rule changed from permissive ("you MAY state")
     to mandatory ("you MUST state ... as the documented income, naming the document"), with the
     reported figure allowed only as context (e.g. base pay vs an overtime month). The data already
     reached the prompt via `_income_evidence`; only the instruction was too weak.
   - Same clause added to `REFINE_PROMPT` so the final pass can't re-introduce a welfare claim the
     draft dropped. +9 tests in `test_profile_engine.py` (1343 scholarship pytest green).

2. **Cockpit profile panel: label "final" once a final exists.** The panel header and info-box hint
   were static; an already-generated final (v2 with interview) was shown under "Student profile
   (draft)" + "this draft will be replaced". Both now key off `profile.final_markdown`
   (`profileFinalTitle` / `profileFinalHint`, en/ms/ta; i18n guardrail green).

## What Went Well

- The claim-gating pattern already existed (`_DO_NOT_CLAIM` + the facts ledger, built for the
  "first-generation" bug). The STR fix was the same shape applied to a new field — no new machinery.
- Investigated from the data every time (reversed the `pool_ref` alias to the application id, read the
  actual documents and `vision_fields`) rather than guessing which line was wrong — which is what
  caught that #4's STR/income claims were actually *backed* (so the bug there was the label, not the
  prose).

## What Went Wrong

- **Twice diagnosed the wrong thing on #4 before the user redirected.** Symptom: I first proposed the
  income line as the bug, then the narrative specifics, when the real bug was the panel label.
  Root cause: I pattern-matched to the income work we'd just been doing instead of reading the
  *whole* panel — the footer ("Final profile (v2 — with interview)") already disproved the "draft"
  header, and I'd skipped past it. Fix (lessons.md): when a screenshot shows a status/label, read the
  whole component's state (header + body + footer) before assuming the defect is in the content.

## Design Decisions

- **STR/JKM gated on a document, not the self-declared flag** (decisions.md). A welfare *self-tick* is
  a claim; only an on-file, current welfare document makes it certain. Consistent with the standing
  need-signal principle (auditable evidence only).
- **Documented income is mandatory to state, reported income is context.** A documented payslip/EPF
  figure must appear and be attributed to its document; the softer reported household figure may only
  contextualise it (overtime vs base), never replace it.

## Numbers

- Backend: 1343 scholarship pytest (+9). Frontend: i18n parity/orphan guardrail green; no type errors
  in the cockpit page.
- 2 commits, 2 Cloud Builds (api + web). No migration.
- **Pending (billable, owner's call):** run `backfill-assigned-profiles` to regenerate existing
  drafts onto `2026-06-18.1`. New generations after this deploy already use the new prompt.
