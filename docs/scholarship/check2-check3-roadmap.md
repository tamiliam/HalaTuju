# Check-2 / Interview-Stage Cockpit Redesign — Sprint Roadmap

**Status:** Sprint 1 of 4 complete (branch `check2-check3-s1`).
**Approved:** 2026-06-13. **Owner:** tamiliam.

## Problem
The officer cockpit's "Outstanding" box merged two distinct stages — student-facing **Check 2** tasks
(queries + document requests) and **interview** content (pre-interview flags + AI-suggested gaps) — and
interview content was also duplicated in a second section lower down. The student profile sat in the wrong
place, and there was no clean lifecycle for "querying closes when the interview concludes → decision time".

## Confirmed model (the lifecycle)
```
Assigned → reviewer reads profile/docs/responses → raises queries + doc requests
        → student responds over days
        → interview arranged & held (ask any still-unanswered query verbally)
        → interview concluded → DECISION TIME (no more queries / documents)
```
- **One querying activity**, living in **Outstanding**, open until the interview is concluded, then read-only.
- **Interview Stage** does not raise new async queries; it consumes unanswered ones as agenda items, captures
  findings, and **Submit** ends querying → triggers the final profile → decision.
- **Two-stage profile:** *draft* auto-generated at the Check-2→Reviewer handoff (reviewer reads to orient);
  *final polished* regenerated from interview findings on Submit.

## Design decisions (2026-06-13)
1. **Officer decides, AI hints** — officer judges each Check-2 answer; AI shows a soft "may be off-topic" hint, never decides.
2. **Profile draft auto-generates once at handoff**, with a Regenerate button (cost-guarded).
3. Check-3 box is named **"Interview Stage"**.
4. Cockpit column order: **Verification verdict → Student profile (own box, + collapsed own-words) → Check 2 — Outstanding → Interview Stage**.
5. **One** query/doc-request control, in Outstanding only; not duplicated in Interview Stage.

## Cockpit layout mockup
`Downloads/check2-check3-cockpit-mockup.html` (local, signed off 2026-06-13).

## Sprints
| # | Goal | Key scope | Complexity | Status |
|---|------|-----------|------------|--------|
| 1 | **Split the boxes** — Outstanding = student tasks only; interview flags/gaps + Suggest-gaps button move to the renamed "Interview Stage". | `admin/scholarship/[id]/page.tsx`, `messages/{en,ms,ta}` | Medium | ✅ Done |
| 2 | **Outstanding: answers under queries + one querying control + AI hint.** Student answer (or "awaiting") shown beneath each query; doc requests link to Documents and target a specific slot (incl. person — absorbs old item-2 multi-earner tagging); dark answer-relevance check surfaces as a soft hint. | `serializers_admin.py`, `views.py`, `resolution.py`, `page.tsx`, `admin-api.ts`, messages | Medium | ⏳ Next |
| 3 | **Student profile box** — relocate below Verification verdict; collapsed "student's own words" beneath; auto-generate draft once at handoff; Regenerate; info strip. | `page.tsx`, `services.py`/`views.py`, messages | Medium | — |
| 4 | **Interview Stage lifecycle** — agenda carry-over of unanswered Outstanding queries; paired findings; Submit ends querying (Outstanding locks read-only at status ≥ interviewed), triggers final profile, moves to decision. | `page.tsx`, `services.py`, `verdict_engine.py`/`gap_engine.py`, `views.py`, messages | High | — |

## Deploy discipline
Push triggers a Cloud Run deploy on `main` (≤2 deploys/feature). All 4 sprints accumulate on the
`check2-check3-s1` branch (branch pushes do **not** deploy — the trigger is on `main`). Merge to `main`
and deploy once the feature is ready (or at a point the owner chooses).

## Out of scope / deferred
- `CHECK2_STUDENT_QUERIES_ENABLED` stays **OFF** (reviewer-raised queries reach students regardless; flipping the
  flag for *system-generated* Check-2 queries is a separate decision).
- DB `UniqueConstraint(application, doc_type, household_member)` — still deferred (TD-115; app layer prevents dups).
