# Retrospective — Verification-Model Roadmap Sprint V4 (Promote the Nine Human Asks)

**Date:** 2026-07-03
**Branch/worktree:** `feat/verify-v4` in `.worktrees/verify-model` (off main incl. V1–V3)
**Roadmap:** `docs/plans/2026-07-03-verification-model-roadmap.md` (V4 of V1–V6)
**Findings source:** `docs/plans/2026-07-03-check-model-audit.md` §E + owner decision 2
**Migration:** `0091_v4_academic_doc_types` — **choices-only (NO Postgres DDL)**. Recorded on prod
via the claude.ai Supabase MCP at deploy (the owner runs the one-line INSERT; no data change).
**Tests:** 2055 scholarship pytest (+9 net) + 413 jest; tsc clean.
**Owner-visible:** yes — these are new student-facing queries. The owner confirmed the conservative
raise-conditions + "build all 9, tune post-deploy" before implementation.

## What Was Built

The audit found human reviewers still out-ask the model (~60 vs ~47) on nine recurring themes with
no model template. V4 promotes all nine into auto-raised Check-2 items + two new doc types.

- **Two new doc types** (`school_leaving_cert`, `semester_result`) — promoted out of the 'other'
  catch-all (officers hand-requested both). Choices-only migration; Gemini extraction schemas
  (leaving cert: name/school/year; semester result: institution/programme/semester/cgpa); read on
  upload (`SUPPORTING_NAME_CHECK_TYPES`); a `doc_match_verdict` hold on a blank/unread upload;
  cockpit label + a soft "Evidence" officer chip; KNOWN_CODES.
- **Four doc-requests** (uncapped): `school_leaving_cert_missing` (SPM-track applicant with no
  results slip — conservative, not everyone), `semester_result_missing` (continuing STPM student),
  `epf_statement_missing` (an employed parent with a payslip but no EPF — optional corroboration),
  `utility_bill_missing` (neither bill on file).
- **Five clarifies** (capped, income-story priority): `deceased_parent_detail`,
  `informal_work_detail` (own-account vs employer + average wage), `household_roster_undercount`
  (the missing direction of 2C — stated size > described, at a conservative margin of 2),
  `other_scholarships_followup`, `high_utility_expense` (owner decision 2 — promote
  `utility_reasonable`'s 'high' signal to a student clarify).
- Each is gap-detected in `income_engine`, wired through the V3 `_gap_sets` seam, auto-resolves
  when its gap clears, dedupes by satisfied gap (not by code existence), and carries firm-steward
  student + officer copy in en/ms/ta (Tamil first-draft) templated from the officers' own best
  phrasings.

## What Went Well

- **Taking the raise-conditions to the owner first was essential.** "Post-SPM applicant" ≈ everyone;
  firing `school_leaving_cert_missing` naively would have spammed every live B40 student. The owner
  confirmed conservative defaults ("under-ask, tune post-deploy") before a single query hit a real
  student — exactly the right gate for an owner-visible sprint.
- **V3's `_gap_sets` extraction paid off immediately** — all nine detectors slotted into one shared
  seam, and the clarify cap / overflow logic handled the five new clarifies for free.
- **The read-requirement stayed consistent with V1.** The two academic doc gaps require a doc that
  READ (`student_verdict='ok'`), not mere presence — so a blank upload can't tick the box (the same
  integrity principle V1 applied to `income_support_doc`).

## What Went Wrong

1. **The new detectors fired broadly in the shared test fixture, disrupting five existing tests.**
   The base check2 app (no bills, no results slip, employed father without EPF, roster undercount
   5-vs-3) suddenly raised `utility_bill_missing`, `school_leaving_cert_missing`,
   `epf_statement_missing`, and `household_roster_undercount` — crowding out the utility clarifies a
   couple of tests were focused on, and breaking a "no questions" assertion.
   - *Root cause:* a broad new detector reads the DEFAULT fixture as a real gap; the fixture was
     never built to be "V4-neutral".
   - *Fix:* made the base fixture roster-consistent (`siblings_in_school=2` → described = size) and
     satisfied the doc-requests in the "no questions" test (add a results slip / EPF / bill); changed
     the cap assertion to count clarifies only (V4 doc-requests are uncapped). **System note:** when
     you add a detector that reads a common state as a gap, the shared base fixture becomes a
     positive case for it — sweep the fixtures for incidental triggers, don't just add the feature.
   - *This is also the live signal:* the same breadth means these WILL fire for many real
     applicants (utility bills are optional; rosters are often incomplete). That's the
     tune-post-deploy work the owner signed up for — start with the conservative margins here and
     watch the raise rates on the real cohort.

## Design Decisions

Logged in `docs/decisions.md` (V4 block): the conservative raise-conditions (under-ask, owner-
confirmed) for the nine themes; the two doc types promoted from 'other' with a read-requirement +
blank-hold; `household_roster_undercount` at a margin of 2 (an under-count of one is common/benign);
`high_utility_expense` promoted from an officer-only signal to a student clarify (owner decision 2).

## Deploy + carry

- **Migration 0091 is choices-only (no DDL)** — the owner records the `django_migrations` row via
  the claude.ai Supabase MCP at deploy (one-line INSERT; prod works with or without it since the
  `doc_type` column already accepts the new strings). Provided at close.
- **Post-deploy verification (roadmap):** run the sync on one Complete-stage app via a cockpit
  refresh and eyeball that the new items raise only where the human items showed the theme; tune the
  conservative margins (esp. `utility_bill_missing` breadth and the roster-undercount margin) against
  the real cohort.

## Numbers

- 9 items + 2 doc types; 1 choices-only migration; ~14 files (backend 6, FE 4, i18n 3, migration 1).
- +9 net scholarship tests (raise + auto-resolve per item) + fixture reconciliations. 2055 pytest +
  413 jest. New reviewer/student copy en/ms/ta (Tamil first-draft) — for owner review.
