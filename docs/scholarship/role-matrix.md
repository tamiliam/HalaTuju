# Organisation Role Matrix — canonical spec (owner-settled 2026-07-15)

The authoritative permission matrix for organisation-level roles. UI and gates must match
this table; change the table first (owner decision), then the code. Platform roles
(`super`, referral `partner`) sit above/outside this matrix. See also
`docs/build-for-tenancy-conventions.md` (referral fields are never access control).

**User-facing rendering:** the role-aware in-app Manual (`/admin/guide`) + FAQ (`/admin/faq`)
are the human-readable rendering of this matrix (content in `halatuju-web/src/content/manual/`).
**Currency rule:** any change to a role's powers here must update that role's Manual chapter AND
its FAQ entries in the same change — the prose must never drift from the gate.

| Role | B40 Applications | Sponsors | Administration | Profile | Guide/FAQ |
|---|---|---|---|---|---|
| **Org Admin** (`org_admin`) | View all · review all · QC all *(no conflict)* · **assign reviewers** | View all · **approve/reject/suspend** | View all · invite all programme roles *(never another org_admin)* · resend/revoke *(never the last org_admin)* | edit | view |
| **Admin — General** (`admin`) | View all *(read-only)* | View all | **View-only** (org section; no invites/actions) | edit | view |
| **Admin — Finance** *(future role — create WITH the payout rails, not before)* | View all *(consider limiting to funding-relevant data — PII minimisation)* | View all | View-only + **Billing & usage** | edit | view |
| **QC** (`qc`) | View all · **review all** · QC unreviewed *(no conflict)* | ✗ *(nav + endpoints)* | ✗ | edit | view |
| **Reviewer** (`reviewer`) | View assigned · review assigned | ✗ *(vetting REMOVED — was reviewer-gated pre-2026-07-15)* | ✗ | edit | view |

## Cross-cutting rules

- **"(no conflict)" — two-person control:** whoever recorded a verdict (`verdict_decided_by`)
  can never QC that case; the assigned reviewer can never QC their own case. Applies to
  `org_admin` and `qc` alike.
- **Withheld from ALL organisation roles (super-only):** decision reopen/cancel-reopen,
  award-amount setting (moves to Finance when that role exists), bursary countersigning,
  tenant-admin (`org_admin`) appointment and the Add Tenant function.
- **Last-org-admin protection:** the sole active `org_admin` of a tenant cannot be revoked.
- **Sponsors under multi-org (D-1 caveat):** sponsor ACCOUNTS are platform-level identities;
  when a second organisation exists, account-level approval may move platform-side while
  pool membership stays org-level. Revisit this cell at tenant #2.
- **Money:** every money power waits for the Finance role + payout rails (payer ≠ decider).

## Payments module (Vircle payment runs) — access

The Payments module (`/admin/payments`, entered via the Administration ORGANISATION-section card;
no top-level nav entry) is **`admin` + `org_admin` only** (super passes as always). `reviewer` /
`qc` / referral `partner` are refused — 403 on every endpoint, cross-org 404. The maker→approver
sign-off is a **two-person** control (D2): the **maker** signs first (role `admin` — Poongulali at
BrightPath), the **approver** countersigns (role `org_admin` — Suresh), and the two must be
different people (`super` may fill either slot, never both on one run). Editing an amount/exclusion
after the first signature reverts the run to draft and clears that signature. This lives *inside*
the Administration surface, so it inherits the org fence; it is **not** a Finance power (the money
here is programme money OUT to students, gated by two named signers, not billing).

## Implementation state (2026-07-15)

- **SHIPPED 2026-07-15** — EVERYTHING in this matrix except the Finance row:
  `docs/plans/2026-07-15-org-admin-powers-v1-brief.md` (single combined brief — org-admin
  + qc org-wide write, QC recorder guard, assignment delegation, sponsor-vetting migration to
  super/org_admin, Admin-General read-only Administration, last-org-admin guard). No migration.
  Tests: `apps/scholarship/tests/test_org_admin_powers.py` +
  `apps/courses/tests/test_org_admin_role.py` (`TestLastOrgAdminGuard`/`TestAdminGeneralReadOnly`).
- **SHIPPED 2026-07-16** — the Payments module (see the Payments section above): `admin`/`org_admin`
  access, org-fenced, two-person maker→approver sign-off. Plan
  `docs/plans/2026-07-16-payments-module-plan.md`; endpoints in `views_admin.py`
  (`_PaymentsBase` + 6 views, classified in `test_org_fence.py`). **▶ Manual/FAQ currency carry:**
  the Payments module is not yet a Manual chapter — fold it into the owner's pending Manual
  screenshot pass.
- Finance role: deferred to payout activation (Vircle/toyyibPay).
