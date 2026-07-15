# Retrospective — Administration panel + surface partition + `org_admin` role

**Date:** 2026-07-15
**Scope:** Two sprints, one deploy. (A) backend: the `org_admin` role, a platform-surface
security partition, and org-scoped staff endpoints; (B) frontend: the Administration panel
(Stitch v2). Ends with BrightPath's lead (Suresh) ready to become the first organisation
admin in the wild.
**Commits:** `1b14566e` (Sprint A) · `e903f11b` (Sprint B).
**Migration:** `courses/0064` (choices-only, no DDL) recorded on prod via Supabase MCP before push.
**Tests:** 3770 pytest + 506 jest passing.

## What shipped

- **`org_admin` role** — an ORGANISATION superadmin: org-wide B40 read + the QC gate + staff
  management (invite/list/resend/revoke reviewers/admins/qc), own organisation only; never
  cross-org, never the platform surfaces, never platform-super. QC powers included (owner
  decision — small-team compromise; segregate when the org grows). Wired through every role
  branch (the A2 sweep): `_b40_scope`, `_require_qc`, `REVIEW_ROLES`, `AdminAssignableAdminsView`,
  the scheduling drift guard, and the invite owning-org binding.
- **Surface partition (the security fix)** — `get_partner_students`' ALL-students branch is now
  SUPER-ONLY. Before this, a B40 `admin` (and any org role) could fetch the platform-wide student
  directory by direct API call — every course-selector student's PII, well beyond their programme.
  The frontend already hid the nav, but the **backend didn't gate it**. One choke-point fixed
  Dashboard / Students / export / detail; Course-Data views likewise super-only. The referral
  `partner` role is unchanged (that IS its purpose).
- **Staff endpoints gain org_admin delegation** — invite (own-org reviewer/admin/qc; never
  partner/super/org_admin → 403), list (own-org non-super staff), resend/revoke (own-org non-super
  targets; cross-org/super → 404, no existence leak), via one `_staff_target_manageable` helper.
- **Add-tenant (super-only)** — a super inviting `role='org_admin'` resolves/creates a TENANT org
  (owning_organisation, not the referral org) and switches `module_scholarship` on. The thin
  add-tenant slice of the future superadmin portal, pulled forward per the gate-split.
- **Administration panel** (`/admin/administration`, Stitch v2 icon grid): a PLATFORM section
  (super — invite referral partner, add tenant) and an ORGANISATION section (super + org_admin —
  invite reviewers/admins with the org-scoped staff table, and a disabled "Billing & usage —
  coming soon"). `/admin/invite` redirects here. Role plumbing + nav + i18n (en/ms/ta) + a new
  `admin.administration` i18n guard test (the flat `admin.*` namespace was previously untested).

## Live verification

- Migration `0064` recorded on prod (choices-only; no DDL — the role value fits the existing
  varchar with no CHECK). Build: api + web both SUCCESS on SHA `e903f11`.
- Smoke: a super sees the Administration panel (both sections) with Dashboard/Students/Course-Data
  intact; a non-super gets 403 on `/api/v1/admin/students/`.

## What went well

- **The A2 sweep checklist made the role wiring exhaustive.** Adding a role touches many branches;
  following the enumerated list (not improvising) meant no missed site, and the existing fence CI
  guard + drift test caught the rest.
- **The partition landed with almost no test churn** — the existing student/dashboard/course-data
  tests authenticate as super, so making the branch super-only left them green; only the new
  `test_org_admin_role.py` proves the non-super 403s.
- **Design-memory alignment beat the literal spec on one point:** the brief split the staff table
  across both panel sections, but the design memory says ALL programme-staff management lives in
  the org section (never beside the referral "Partner" concept). Putting the staff table only in
  the org section is cleaner and avoids a duplicate table for a super — a deliberate, documented
  deviation.

## Lessons

- **A role's QC/graduation endpoints check the role gate before the org gate**, so a cross-org
  test must use a caller with the right role (a qc/org_admin of org A), not any admin — else it
  403s on role before the org 404. (Same lesson as Phase 1; re-encountered.)
- **The seeded BrightPath org is in the test DB** (migration 0098) — fixtures must not reuse
  `code='brightpath'` or `email` values that collide with the base fixture accounts.
- **`referral org` ≠ `owning org` remains the sharpest edge:** the invite path now resolves BOTH
  (`org` for a partner, `owning_organisation` for a tenant/staff). Keeping them distinct in one
  view took care; the tests pin caller-org forcing so a delegated invite can't drift.

## Rollout — OWNER-GATED (not yet executed)

Promote BrightPath's lead to organisation admin (his account is verified: `id=4`,
`surithiru@gmail.com`, currently `role='qc'`, active, already bound to BrightPath):
```sql
UPDATE partner_admins SET role='org_admin' WHERE email='surithiru@gmail.com';
```
Then the live walkthrough with him (owner-led): he sees only the org section, invites one reviewer
end-to-end, still QCs, and CANNOT reach Students / Dashboard / Course Data. Left for the owner
because it changes a real person's live permissions and the walkthrough needs him present.

## Carry / follow-ups
- **Finance role** — parked (payer ≠ decider); design with real payout rails (Vircle/toyyibPay).
- **Billing & usage** — the panel card is a disabled placeholder until per-tenant metering
  (roadmap Sprint 13a); while BrightPath is the sole tenant, attribution = 100%.
- **Tamil first-draft** on the new `admin.administration.*` strings — owner's eye at leisure.
- Platform Console (Sprints 10–11) stays gated on a second-tenant prospect.
