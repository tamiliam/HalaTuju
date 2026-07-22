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
| **Admin — Finance** (`finance`) | **Payments funding summary ONLY** — award / paid / remaining / eWallet, inside the Payments module. **NO applicant files, documents, income or verdicts** (`_b40_scope='none'`) | View all *(list + detail; no review/approve powers)* | **View-only** org section + **Payments (read + finance-check signature)**. Billing & usage remains future | edit | view |
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
- **Money:** award-amount setting and bursary countersigning still wait on payout rails
  (payer ≠ decider). The `finance` role holds the payment-run CHECK, not the decision — it can
  refuse a run by not signing, but it can never create, edit, cancel or price one.

## Payments module (Vircle payment runs) — access

The Payments module (`/admin/payments`, entered via the Administration ORGANISATION-section card;
no top-level nav entry). It lives *inside* the Administration surface, so it inherits the org
fence.

**Access.** READ (list, run detail, CSV) and the finance-check SIGNATURE: `admin` + `org_admin` +
`finance` (super passes as always). CREATE / EDIT an item / CANCEL: `admin` + `org_admin` **only**
— `finance` is refused. `reviewer` / `qc` / referral `partner` are refused everywhere — 403 on
every endpoint, cross-org 404.

**The chain** is `draft → admin_signed → [finance_checked] → completed`. The middle step is
**required if and only if the organisation has ≥1 ACTIVE `finance` admin**, evaluated LIVE at each
sign attempt and **never stored on the run**. With no finance admin the chain runs exactly as it
did before this role existed — two steps, byte-identical.

- **maker** signs the draft (role `admin`) → `admin_signed`.
- **finance check** (role `finance`) → `finance_checked`. While finance is active, an org_admin
  attempting to countersign at `admin_signed` is refused with `finance_check_required`.
- **approver** countersigns (role `org_admin`) → `completed`.

**Live evaluation, both directions.** A run sitting at `admin_signed` when a finance admin is
first activated DOES need the check before it can be countersigned (deliberate — the FAQ explains
the "awaiting finance check" notice). If the sole finance admin is revoked mid-run, the chain
degrades to two steps by policy; an already-collected finance signature is never a blocker and is
never erased by the degrade.

**Three distinct signers.** Every signature collected on a run must be a different person
(email, case-insensitive). `super` may fill any ONE slot per run and never two — enforced by that
same pairwise-distinctness rule, not a special case.

Editing an amount or exclusion after ANY signature reverts the run to draft and clears ALL
collected signatures ("nobody signs one list and sends another").

This is **not** a Billing power. The money here is programme money OUT to students, gated by named
signers. Platform billing — HalaTuju invoicing the organisation for metered service usage — is a
separate future deliverable and its Administration card stays "Coming soon".

## Implementation state (2026-07-23)

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
  screenshot pass. **(Cleared 2026-07-23 — the Payments module now has org-admin + finance Manual
  sections and FAQ entries.)**
- **SHIPPED 2026-07-23 — the `finance` role** (Sprint 14, brief
  `docs/plans/2026-07-22-sprint14-finance-role-brief.md`): a DORMANT payment-run checker plus a
  funding summary inside the Payments module. Ships **dark** — with no finance admin on prod, the
  production chain is unchanged. Role choice `courses/0066` (choices-only), signature triple
  `scholarship/0109` (3 columns + status choices). Predicate
  `payments.finance_check_required(organisation)`; endpoints in `views_admin.py`
  (`_PaymentsBase` read/write split + `AdminPaymentFundingSummaryView`, classified in
  `test_org_fence.py`). Finance is deliberately absent from `services.REVIEW_ROLES`, the
  assignable-staff list and every QC gate — proven by denial tests.
- Billing & usage: still future. It means HalaTuju invoicing the organisation for metered service
  usage (Gemini / Vision / GCP / Supabase / Twilio / change requests at cost + 15–30%) and needs a
  billing-sources investigation that has not happened. The Administration card stays disabled.
