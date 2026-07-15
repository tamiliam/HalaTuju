# Organisation Role Matrix — canonical spec (owner-settled 2026-07-15)

The authoritative permission matrix for organisation-level roles. UI and gates must match
this table; change the table first (owner decision), then the code. Platform roles
(`super`, referral `partner`) sit above/outside this matrix. See also
`docs/build-for-tenancy-conventions.md` (referral fields are never access control).

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

## Implementation state (2026-07-15)

- EVERYTHING in this matrix except the Finance row:
  `docs/plans/2026-07-15-org-admin-powers-v1-brief.md` (single combined brief — org-admin
  powers + QC hybrid + sponsor migration + Admin-General view-only + guards). Awaiting execution.
- Finance role: deferred to payout activation (Vircle/toyyibPay).
