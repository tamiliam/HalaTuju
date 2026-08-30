# Organisation Role Matrix — canonical spec (owner-settled 2026-07-15)

The authoritative permission matrix for organisation-level roles. UI and gates must match
this table; change the table first (owner decision), then the code. Platform roles
(`super`, referral `partner`) sit above/outside this matrix. See also
`docs/build-for-tenancy-conventions.md` (referral fields are never access control).

**User-facing rendering:** the role-aware in-app Manual (`/admin/guide`) + FAQ (`/admin/faq`)
are the human-readable rendering of this matrix (content in `halatuju-web/src/content/manual/`).
**Currency rule:** any change to a role's powers here must update that role's Manual chapter AND
its FAQ entries in the same change — the prose must never drift from the gate.

**Menu rendering (keep-in-sync pair, 2026-07-27):** `halatuju-web/src/lib/navigation.ts` encodes
which roles SEE which route, and its docstring points back here. That file is UX only — it decides
what is worth showing, never what is permitted; the fence stays `_AdminBase._org_scoped` /
`_org_allows` plus the per-endpoint role gates. **Order of change is this table first, then
`navigation.ts`, then the page guard, in one commit.** `navigation.test.ts` holds a per-role
visibility snapshot, so a drift shows up as a failing test rather than a quietly wrong menu.

| Role | B40 Applications | Sponsors | Administration | Profile | Guide/FAQ |
|---|---|---|---|---|---|
| **Org Admin** (`org_admin`) | View all · review all · QC all *(no conflict)* · **assign reviewers** | View all · **approve/reject/suspend** · **countersign + void a wallet credit** *(never records one)* · **edit + switch the sponsor emails** | View all · invite all programme roles *(never another org_admin)* · resend/revoke *(never the last org_admin)* · **Payments: create/edit/cancel + countersignature** | edit | view |
| **Admin — General** (`admin`) | View all *(read-only)* | View all · **record + sign a wallet credit** *(maker; never countersigns)* · void an unconfirmed one · **edit + switch the sponsor emails** | **View-only** org STAFF section (no invites/actions) · **Payments: create/edit/cancel + maker signature** | edit | view |
| **Admin — Finance** (`finance`) | **Payments funding summary ONLY** — award / paid / remaining / eWallet, inside the Payments module. **NO applicant files, documents, income or verdicts** (`_b40_scope='none'`) | View all *(list + detail; no review/approve powers)* · **finance-check signature on a wallet credit** · ✗ sponsor emails | **View-only** org section + **Payments (read + finance-check signature)**. Billing & usage remains future | edit | view |
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

## Wallet credits (sponsor money IN) — access

The mirror image of Payments: money coming IN to a sponsor's wallet, recorded from a bank transfer
that happened off the platform. Reached from **Sponsors → open a sponsor** (no separate route), so
it inherits that surface's role gate; the credit itself is org-fenced on the programme's
organisation (`AdminSponsorDetailView`, `_CreditsBase`).

**Access.** READ the ledger: `admin` + `org_admin` + `finance` (+ super). **RECORD: `admin` only**
(+ super) — `org_admin` is deliberately refused, because the person who opens a chain must not also
close it, and on production the person doing this work is a plain `admin`. VOID an unconfirmed
credit: `admin` + `org_admin`. `reviewer` / `qc` / referral `partner` are refused everywhere.

**The chain is the payments chain**, deliberately — one design, one implementation
(`sponsorship.sign_admin_credit` mirrors `payments.sign`):
`draft → admin_signed → [finance_checked] → confirmed`, with the middle step required iff the
organisation has ≥1 ACTIVE `finance` admin, evaluated live at every attempt.

- **maker** signs the draft (role `admin`) → `admin_signed`.
- **finance check** (role `finance`) → `finance_checked`. An `org_admin` countersigning at
  `admin_signed` while finance is active is refused with `finance_check_required`.
- **approver** countersigns (role `org_admin`) → `confirmed`. **`confirmed` is the step that makes
  the money spendable** on a student (`Donation.is_spendable`).

**Distinctness is keyed on EMAIL, not the typed name** — production carries two active admins both
named "Ve. Elanjelian", so a name key would be wrong in both directions (migration `0125`). Each
signer must type their own name, matched against `PartnerAdmin.name`.

**A confirmed credit is never cancelled** — it is reversed by a compensating entry. Only a
`draft` / `admin_signed` / `finance_checked` credit may be voided, and the row is kept either way.

## Implementation state (2026-07-23)

- **SHIPPED 2026-08-30 (Layer 0 Sprint 5)** — a NEW `org_admin` power: **configure what the
  programme asks for** (`/admin/programme`, "What we ask for"). `org_admin` + super only; `admin`,
  `qc`, `finance`, `reviewer`, `partner` are refused, and `admin`/`qc` lost the empty "Overview"
  nav placeholder that stood in its place. Org-fenced on the programme's organisation (cross-org
  = 404). Six core items (IC, results slip, offer letter, income proof, family roster, consent) are
  floored at Required for every role including super. Endpoint
  `GET/PUT /api/v1/admin/scholarship/programme/configuration/`; tests
  `apps/scholarship/tests/test_layer0_config_screen.py`.
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

## Reviewers surface (Organisation → Reviewers) — access

`/admin/organisation/reviewers` and `/admin/organisation/reviewers/[id]`
(`AdminReviewerListView` / `AdminReviewerDetailView`, request #10, 2026-08-02). Staff invites and
revokes; this is where you look at somebody — what they carry, how long a case sits with them, and
how their cases ended.

**Access: super + `org_admin` + `admin` + `finance`** — the same set as the organisation's other
staff-facing screens, because Staff already shows all four who the reviewers are. `qc` and
`reviewer` are refused: a volunteer has no business reading a colleague's caseload and turnaround.

**Org-fenced** (`list-fenced` in `test_org_fence.py`). A `PartnerAdmin` carries
`owning_organisation`, so a non-super sees only their own tenant's people — and every FIGURE is
fenced too, counted over that tenant's applications alone. A cross-org id answers **404, never
403**: a 403 would confirm that another tenant's staff member exists.

**PII — a deliberate, PARTIAL widening (owner, 2026-08-02).** `ReviewerProfile` is a self-scoped
record; its serializer's docstring says so. This surface widens it, and the ruling is:

| Field | Shown to super / org_admin / admin / finance | Why |
|---|---|---|
| name, email | yes | already on Staff |
| phone | **yes** | the person assigning work needs to reach the reviewer |
| `share_phone_with_students` | yes | it is a consent state, and the assigner must not defeat it |
| qualification, university, graduation year, field of study | yes | it is why they were accepted as a reviewer |
| **home address** | **NEVER** | it exists for nothing on this screen; assigning a case is not a reason to read where somebody lives |

The address is not merely hidden in the template — it is **not serialised**, and a test asserts it
cannot appear in the payload. Widen this cell only by owner decision, recorded here first.

**No corrections figure on the table, by decision (2026-08-02).** 17 of BrightPath's 65 decisions
carry a reopen and several were caused by our own defects, not the reviewer's judgement. A bare
number beside a volunteer's name reads as a competence score to whoever hands out the next case, so
the reopens appear on the DETAIL page only, each with the reason recorded at the time.

**No programmes column, by decision (owner, 2026-08-02).** With one programme every reviewer serves
it, so the column could only ever say one thing; everyone is on the BrightPath Bursary by default.
It returns when a second programme exists — see the revisit clause in `decisions.md` (2026-07-26),
which names the membership table this would need.

## Sponsor emails (what a donor hears) — access

Nine editable emails behind the **Emails** badge on `/admin/sponsors`
(`AdminSponsorEmailsView` / `AdminSponsorEmailDetailView`, S3, 2026-07-28).

**Access: super + `org_admin` + `admin`. `finance` is refused, deliberately** — and that makes
this gate NARROWER than the sponsor list it sits on. Finance reads sponsors because who funds the
programme is finance's business; deciding what every donor is told is editorial, not financial.
`qc` / `reviewer` / referral `partner` are refused everywhere, as on the list.

**Not org-fenced, by construction.** A `Sponsor` is a platform-level account with no organisation
(see the Sponsors caveat above), and enablement is per EMAIL, not per recipient — there is exactly
one welcome email and every sponsor gets that one. Classified `cross-org-by-design` in
`test_org_fence.py`.

**Two independent gates before anything sends:** the platform flag `SPONSOR_COMMS_ENABLED`
(unset today) AND each template's own `enabled` (all off on seeding). Either one shut means
nothing goes out; the panel states the platform gate rather than implying the switches work.

**Two refusals on save**, both enforced in the service and surfaced by the endpoint:
- an **unknown `{placeholder}`** — a rendering guard, and a privacy control: no token in any
  kind's allowlist resolves to a student's identity, so an editable template cannot become a
  route around the pool serializers' anonymity. `{student_cards}` renders the same anonymised
  card a sponsor already sees.
- **banned phrasing** — a **tax-relief claim** (HalaTuju holds no LHDN s44(6) approval, and this
  is the one line that could cost a donor money), student-ownership wording ("your student"), and
  urgency copy that would turn account correspondence into marketing.

**Three of the nine are already live** through their pre-S3 hardcoded senders (`new_students`,
`weekly_digest`, `referral_invite`) and keep sending while their template is dark — otherwise
switching this feature on dark would have silently stopped them.
