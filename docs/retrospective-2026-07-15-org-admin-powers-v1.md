# Retrospective — Org-Admin Powers v1 + Role-Matrix Alignment

**Date:** 2026-07-15
**Brief:** `docs/plans/2026-07-15-org-admin-powers-v1-brief.md`
**Authority:** `docs/scholarship/role-matrix.md` (owner-settled matrix)
**Shape:** One sprint, one deploy, **NO migration** (no schema change anywhere).
**Tests:** 3815 combined pytest (2562 scholarship + 1253 courses/reports) + 530 jest; tsc clean.

## What shipped

The organisation roles gained the write powers the matrix promises — all fenced to the
caller's own organisation, all guarded so the broadened powers can't collapse two-person
control.

- **org_admin + qc are org-wide WRITERS** (`_can_review_app`): both act on ANY application in
  their OWN org (org_admin = the organisation superadmin; qc = the hybrid review-all role).
  A plain `admin`/`reviewer` stays assigned-only. This single change lights up the three
  cockpit action boxes and the verdict recorder for org_admin/qc.
- **QC recorder guard** (`_require_qc`, `self_verdict_qc_forbidden`): with org-wide write,
  assignment no longer proves who recorded a verdict, so the guard now also refuses a
  non-super caller whose email matches `verdict_decided_by` (case-insensitive). The existing
  self-assignment guard stays. Super is exempt (owner override).
- **Assignment delegated to org_admin** (`AdminAssignReviewerView`): a non-super caller may
  (re)assign only an ACTIVE `role='reviewer'` in their OWN org (never a super, cross-org, or
  senior role → `bad_assignee`). The application is already org-fenced. The assignable-admins
  dropdown is org-scoped for a non-super caller (flips it to `list-fenced` in the S3b map).
- **Sponsor vetting migrated** off the reviewer gate onto **super/org_admin**
  (`AdminSponsorReviewView`); the sponsor LIST tightened to **super/org_admin/Admin-General**
  (`AdminSponsorListView`) — qc + reviewer refused.
- **Admin-General (`admin`) read-only Administration** (`AdminListView` + the panel): views the
  own-org staff table; NO invite/resend/revoke (those stay super/org_admin).
- **Last-org-admin guard** (`AdminRevokeView`, `last_org_admin`): the sole active org_admin of a
  tenant cannot be revoked (only a super reaches that branch; the FE also hides the affordance,
  derived from the loaded staff list via the new `owning_org_id` payload field).
- **Frontend keep-in-sync twins**: `canAssign`/`canQc`/`canWrite` extended for org_admin (+qc
  hybrid); nav re-cut per the matrix (QC loses Sponsors; Admin-General + org_admin keep Sponsors
  and gain Administration); QC self-verdict + last-org-admin errors surfaced with i18n (en/ms/ta,
  Tamil first-draft) via a `.code` now attached in `adminMutate`/`revokeAdmin`.

## Deliberately withheld (owner-approved — not built)

Decision reopen/cancel-reopen, award-amount setting, bursary countersign, appointing another
org_admin, the Add-Tenant function — all stay super-only. Finance role stays future (payout rails).

## What went well

- **The org fence + CI guards carried the risk.** The org-wide write is safe because the fence
  already 404s cross-org and the recorder guard closes the two-person-control hole; the S3b
  completeness map + static source guard forced the two reclassifications (AssignableAdmins →
  list-fenced) to be conscious.
- **Sweep-the-old-gate discipline paid off.** The reviewer sponsor-vetting migration would have
  silently broken `TestAdminSponsorVetting` (reviewer approve/list) — swept and rewritten to the
  matrix (reviewer/qc refused, org_admin vets, Admin-General lists) before it hit CI.
- **No production migration** — pure gate/permission change; the deploy is code-only.

## Lessons

- **Assignment is status-gated, not just role-gated.** A case may only change hands while a
  review is live (`profile_complete`/`interviewing`); an `interviewed` (awaiting-QC) fixture
  can't be reassigned — the new-power test had to move the app to an assignable status first.
- **QC fixtures without `verdict_decided_by` are unaffected by the recorder guard** (the guard
  short-circuits on an empty recorder) — every existing QC test stayed green untouched.

## Guide/FAQ currency

The Reviewer Guide + FAQ are reviewer-audience only ("only the applicants assigned to you");
they don't describe reviewer sponsor-vetting, QC scope, or org-admin assignment, so no currency
edit was needed — they remain accurate.

## Rollout — OWNER-GATED (not executed)

1. Smoke as the owner's org_admin test account (`elanjelian@me.com`): assign a reviewer; open an
   unassigned application (the three boxes act, the QC box shows); record-then-QC on the same
   case is refused (`self_verdict_qc_forbidden`); Administration shows no Revoke on a sole tenant
   admin.
2. Owner then reverts `elanjelian@me.com` → `reviewer` (Supabase MCP) and briefs Suresh.

## Carry / follow-ups

- Tamil first-draft review of the new strings (`qcDecision.selfVerdictForbidden`,
  `administration.viewOnlyNote`/`lastOrgAdmin`).
- Finance role + Billing/usage metering remain parked (payout rails).
