# Retrospective — Verification-model V6 (FINAL): Gopal in the Action Centre + persona polish (2026-07-04)

Roadmap `docs/plans/2026-07-03-verification-model-roadmap.md` §V6; audit findings F1, #15, #17.
The last sprint of the six-sprint verification-model hardening roadmap.

## What Was Built

1. **Cluster coach in the Action Centre (#15b).** The dead end: a held income cluster doc
   (wrong-person salary slip/EPF, a mismatching BC) mounted the per-document coach, which
   `verdict_for_document` deliberately leaves silent for cluster docs (they're voiced by the
   cluster coach) — so the student saw a red task with no explanation. Fix: an open income
   doc-task now mounts the existing per-earner `IncomeClusterCoach`, keyed on the task's member
   (the salary-route request tag, or the STR-route declared earner). Deduped to one coach per
   earner across that member's tasks.
2. **Reload-persistent coach (#15a).** The Action Centre now fetches the student's documents
   alongside the tickets, so a non-cluster held task re-surfaces Gopal's doc-anchored advice
   after a page reload — previously it lived only in in-session upload state and vanished on
   refresh. The coach self-hides if the latest doc actually reads clean.
3. **Telemetry (F1).** One `AUDIT coach_serve` line per serve (kind + app + source + verdict)
   in both help views, so Gopal's ai/fallback/none rate is finally measurable in Cloud Run
   logs (previously his usage was real but uninstrumented). Query in the CHANGELOG + the view
   docstring.
4. **Persona polish (#17).** Lean-register rewrite of the greeting; "the earner" officer jargon
   → "this family member" in the student fallback strings + `str_recipient_mismatch.desc`; the
   officer `grades_unverified` line tightened; and the persona-critical Tamil fix —
   "சிக்கு கோபால்" ("Trouble Gopal") → "Cikgu Gopal" in Latin script.
5. **Docs (#5).** The Action Centre's neutral third register is documented in `str-proof-spec.md`
   §4 alongside Cikgu Gopal (Check 1) and the Check-2 fiscal steward.

## What Went Well

- The heavy lifting was already in place: `IncomeClusterCoach` is a standalone component and
  `getIncomeHelp(member)` already existed, so #15b was a wiring job, not a rebuild. The backend
  `income_cluster_advice` computes the verdict from the app's real route + docs, so the FE only
  had to supply the member.
- Extracting `clusterMemberOf` / `latestDocFor` to `lib/actionCentre.ts` kept the new logic
  unit-testable in the node env (the jest-can't-render-components constraint), +10 tests.

## What Went Wrong

- **Nearly shipped duplicate cluster coaches.** The first cut mounted `IncomeClusterCoach` on
  every open income doc-task — a member with two open tasks (IC + salary slip) would render two
  identical coaches. Caught in review before testing. Root cause: I reasoned per-card and forgot
  the cluster coach is per-*earner*, not per-*document* (the same mismatch the audit's #15 is
  about). Fix: compute a per-member anchor (the first open task of each member) in the list and
  pass `showClusterCoach` so only the anchor renders it. System note: when reusing a
  "once per cluster" component in a per-item list, dedup at the list level, not the item level.
- **The audit's named Tamil grammar slip ("எனத் உறுதிசெய்யவும்") wasn't in the current string.**
  The top-traffic STR coach string (`str_not_current` fallback) now reads grammatically
  ("என உறுதிப்படுத்த முடியவில்லை") — likely fixed in an earlier sprint. Left untouched and flagged
  for the owner's expert eye at the checkpoint rather than inventing a change.

## Design Decisions

- **Member-neutral "this family member" over param-threaded member names in the fallback
  strings.** The audit suggested threading the member into the fallback via params. But the
  fallbacks only show when the AI is down (rare — the AI message already names the member from
  the backend context), and "this family member" removes the officer-jargon defect cleanly
  without threading a param through the fallback render path. Lower risk, same register outcome.
  Flagged the alternative for the owner.

## Numbers

- 2066 scholarship pytest (+2 telemetry) + 426 jest (+10 coach-wiring logic); tsc clean for
  touched files. No migration, no backend engine change (views telemetry + FE wiring + i18n only).
- Persona strings: 19 changed across en/ms/ta (Tamil first-draft for owner review).

## Roadmap complete

All six sprints of the verification-model hardening roadmap (V1 slot integrity → V2 resolution
correctness → V3 query lifecycle → V4 promote the nine human asks → V5 verdict evenness + QC floor
→ V6 Gopal in the Action Centre) are shipped. **Owner final checkpoint due** — the copy review
(especially the Tamil first-drafts across V4/V5/V6) is the last gate.
