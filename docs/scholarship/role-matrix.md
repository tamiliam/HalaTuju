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

**Organisation access is a set of PERMISSIONS (org request #39, owner 2026-10-19; all four sprints built
by 2026-10-21 — roadmap `docs/plans/2026-10-19-staff-permissions-roadmap.md`).** *"A reviewer is someone
with review permission. A QC likewise is an admin with QC permission."* This file is therefore in three
parts: the **catalogue** (what each permission opens), the **presets** (the set each role starts with),
and the **lead tier** (the organisation admin, fixed). The per-role table further down is what each
role gets **on its preset** — `apps/courses/tests/test_permission_presets.py` (the golden table) proves
the code gives exactly that, gate by gate. Platform roles (`super`, referral `partner`) sit outside: a
super passes every permission (and still fills only ONE signature on a payment run); a partner holds
none.

### 1. The catalogue (`apps/courses/staff_permissions.py` `CATALOGUE`)

| Key | On screen | What it opens (the gates that read it) |
|---|---|---|
| `review` | Review assigned students | May be ASSIGNED cases; opens and works the cases assigned to them, files included; proposes interview times; may be paused. Applications list scope "assigned" |
| `see_all` | See all students | Reads every application in the organisation (no writes unless assigned). Applications scope "all" |
| `qc` | Quality check | The QC gate, and working on any case in the organisation. **Needs `see_all`** (the editor holds it back; the server refuses a set without it and reads a stored one fail-closed) |
| `spending` | Spending | The Spending page: named students' spending, flags, categories |
| `payments_prepare` | Prepare payment runs | Create, edit, cancel runs; sign as MAKER |
| `payments_check` | Check payment runs | The optional middle signature. Dormant until somebody holds it; armed PER RUN when an eligible holder exists |
| `payments_approve` | Approve payment runs | The final signature, which completes the run and releases Vircle → students. Never on a run the person signed OR CREATED (`created_by`; #39 S4 review fix 2) — the organisation admin's fallback excepted |
| `manage_team` | (not switchable) | Invite, resend, revoke, restore, delete, change role, **change permissions**. Lead tier only in #39 (owner question 3) |

Reading Payments (list, run, CSV, funding summary) is open to anybody holding any `payments_*` key, or
the lead tier.

### 2. The presets (`PRESETS`; a NULL `PartnerAdmin.permissions` means "the preset")

| Role (preset label) | Holds | Note |
|---|---|---|
| `reviewer` | `review` | |
| `qc` | `see_all`, `qc` | |
| `admin` | `see_all`, `spending`, `payments_prepare` | |
| `finance` | `payments_approve` | Since #39 S2 (owner option A): Finance APPROVES runs |

**Changing a set (#39 Sprint 4, 2026-10-21):** People → a reviewer's page, or **Permissions** beside an
admin → the card *What <name> can do* (`PATCH admin/admins/<id>/permissions/`). **Only a super or the
organisation admin**, and only on a TEAM member of their own organisation — never their own row, an
organisation admin's, a super's or a partner's (`_staff_target_manageable`, then the service). The
server refuses: an unknown key, `manage_team` (`lead_tier`), `qc` without `see_all`, a revoked person
(`not_active`), a Reviewer / QC left with neither `review` nor `qc` (`would_leave_people` — they would
vanish from People), and taking `review` (or `see_all`, when `review` does not stay) from somebody holding
in-play cases (`has_open_cases`, under the person's row lock; the assign service takes the same lock).
A dry run names the consequences first: the check step switching on/off, the organisation admin's
approval fallback switching off/on, a person who has never signed in (the payment change waits for
their first sign-in), a Finance person's files widening, prepare-and-approve together. A set equal to
the preset is stored as NULL; anything else is "custom" and shows chips on People. **Change role resets
a custom set to the new role's preset** (said before the click); revoke / restore keep it; a TD-335
re-invite resets it. Every change writes a `staff_permission_changes` row (who, whom, before → after,
when) and an `AUDIT staff_permissions_changed` line. The Django admin shows `permissions` read-only.

### 3. The lead tier (`org_admin`, `LEAD_TIER`) — fixed, never edited

`see_all`, `qc`, `spending`, `manage_team`, plus the powers that are not catalogue keys and stay on the
role: configuration, gifts, contracts, sponsors' acceptance, assigning cases, billing, requests, the
parent's contact, creating / editing / cancelling runs (never signing as maker), and approving a run
**only under the per-run fallback** (nobody eligible holds `payments_approve`). Org admins stay OFF the
Reviewers tab although the tier holds `qc` (owner, 2026-10-19).

**Preset-bound surfaces (R2) read the ROLE, not the set:** the Overview sections, the reviewer profile
hold and profile cards, graduation review, sponsors, sources, sponsor emails, wallet credits, team
read-only views. So a Reviewer given Spending (Rohini) gets the Spending page and keeps the reviewer's
Overview; a Finance person given Review reads ONLY the files of students assigned to them (owner,
2026-10-19). A super may still assign an admin / qc / org_admin that holds `see_all`
(`services.R1_SUPER_TARGET_ROLES`).

### 4. What each role gets on its preset

| Role | Programme Overview | B40 Applications | Sponsors | Administration | Profile | Guide/FAQ |
|---|---|---|---|---|---|---|
| **Org Admin** (`org_admin`) | **Everything** — funnel (all 13 statuses), money strip, needs-attention list, **all six charts** (a stage at zero is not drawn) · **sets the widget layout (Customise) — per gift, with the organisation's as the default** *(#42)* · intake-year filter | View all · review all · QC all *(no conflict)* · **assign reviewers** | View all · **approve/reject/suspend** · **accept into / take back a GIFT** · **countersign + void a wallet credit** *(never records one)* · **edit + switch the sponsor emails** | View all · invite all programme roles *(never another org_admin)* · resend/revoke *(never the last org_admin)* · **change role within a pair — Admin ↔ Finance, Reviewer ↔ QC** *(2026-10-09)* · **change a team member's permissions** *(#39 S4, 2026-10-21; never their own, never an org_admin's)* · delete an admin with no recorded work · **set which GIFT a reviewer covers** · **set which GIFT lists a source** · **Payments: create/edit/cancel; approves a run ONLY under the fallback** *(#39 S2: no countersignature while Finance can approve)* | edit | view |
| **Admin — General** (`admin`) | **Everything** — as org_admin (a read; the page has no controls) | View all *(read-only)* | View all · **record + sign a wallet credit** *(maker; never countersigns)* · void an unconfirmed one · **edit + switch the sponsor emails** | **View-only** org STAFF section (no invites/actions) · **Payments: create/edit/cancel + maker signature** | edit | view |
| **Admin — Finance** (`finance`) | **The money, in AGGREGATE** — money strip, released-vs-spent with the running gap, average spend per transaction per week, transactions per active student per week, spending by category. **NO funnel, no case list, no name, no file, no verdict.** ⚠ **A deliberate WIDENING** — see below | **Payments funding summary ONLY** — award / paid / remaining / eWallet, inside the Payments module. **NO applicant files, documents, income or verdicts** (`_b40_scope='none'`) | View all *(list + detail; no review/approve powers)* · **finance-check signature on a wallet credit** · ✗ sponsor emails | **View-only** org section + **Payments (read + APPROVAL — the final signature that releases the money; #39 S2, 2026-10-19)**. Billing & usage remains future | edit | view |
| **QC** (`qc`) | **Own work only** — the cases awaiting QC (oldest wait first) + own pace. **No money, no programme-wide funnel** | View all · **review all** · QC unreviewed *(no conflict)* | ✗ *(nav + endpoints)* | ✗ | edit | view |
| **Reviewer** (`reviewer`) | **Own work only** — own open cases with the verdict-due date per case (open / due soon / overdue) + own pace. **No money, no programme-wide funnel** | View assigned · review assigned | ✗ *(vetting REMOVED — was reviewer-gated pre-2026-07-15)* | ✗ | edit | view |

## Cross-cutting rules

- **"(no conflict)" — two-person control:** whoever recorded a verdict (`verdict_decided_by`)
  can never QC that case; the assigned reviewer can never QC their own case. Applies to
  `org_admin` and `qc` alike.
- **Withheld from ALL organisation roles (super-only):** decision reopen/cancel-reopen,
  award-amount setting (moves to Finance when that role exists), bursary countersigning,
  tenant-admin (`org_admin`) appointment and the Add Tenant function.
- **Correcting a student's parent/guardian contact is super + `org_admin` only (request #26,
  2026-10-05)** — `POST admin/scholarship/applications/<pk>/guardian-contact/`, at ANY time, even
  while the student is frozen out of it during bursary signing — but while frozen, an `org_admin`
  only if their organisation holds the open offer; every change made through the product is recorded
  (`guardian_contact_changes`; Django's staff-only `/admin/` site is the one exception).
- **Recording a call to the parent ("Record call") is super + `org_admin` only (request #26 consent
  framing, 2026-10-05)** — `POST admin/scholarship/applications/<pk>/guardian-call/`, the same
  gate and cross-organisation rule as the correction. A "Corrected" call also stores
  the number. A shared phone with no consenting call holds back the award good-news email, the
  "ready to sign" invitation, the guarantor PIN and the signature itself (owner ruling A).
- **The "Shared phone: call parent" filter on Applications is super + `org_admin` only**
  (`?parent_call=needed`, owner ruling B) — the same roles that see the flag; inside the list's
  organisation fence. `admin`, `qc`, `reviewer`, `finance` and `partner` are refused.
  Manual: `role-org-admin` § *Correcting a parent's phone number*; FAQ: org_admin.
- **Last-org-admin protection:** the sole active `org_admin` of a tenant cannot be revoked.
- **Gift scoping is super + `org_admin` only (S-ASSIGN, 2026-09-04), and it is NARROWER than
  reading the surface it sits on.** `admin` and `finance` may READ the reviewers list and the
  sponsor list; deciding *who may fund your students* and *who is offered which case* is staff
  management, so the three setters (`admin/sponsors/<pk>/membership/`,
  `admin/reviewers/<pk>/programme/`, and `programme_id` on a source PATCH) re-gate rather than
  inheriting. ⚠ Note this points the OPPOSITE way to recording a wallet credit, which is `admin`
  and refuses `org_admin` — bookkeeping is the maker's job; acceptance is the organisation's.
- **A gift scope is a NARROWING, never a fence.** It decides who is OFFERED work; the org boundary
  stays `_org_scoped`/`_org_allows`. NULL means EVERY gift, and no row was backfilled.
- **Sponsors under multi-org (D-1 caveat):** sponsor ACCOUNTS are platform-level identities;
  when a second organisation exists, account-level approval may move platform-side while
  pool membership stays org-level. Revisit this cell at tenant #2.
- **Money:** award-amount setting and bursary countersigning still wait on payout rails
  (payer ≠ decider). ~~The `finance` role holds the payment-run CHECK, not the decision~~ —
  **SUPERSEDED 2026-10-19 (#39 Sprint 2, owner option A):** the `finance` role APPROVES payment runs
  (the final signature, which completes the run and releases Vircle → students); the organisation
  admin funds Vircle outside HalaTuju and approves a run only when nobody else can. Finance still
  can never create, edit, cancel or price a run. On wallet credits Finance still holds the CHECK.

## Programme Overview (`/admin/programme/overview`) — access

The answer to *"how is this gift doing?"*, given once and shaped by role. It is the **first row of
the Programme group** in the menu (labelled **Overview**, shortcut `G` then `I`), it is where a
**gift card on Programmes now lands**, and it is the **default landing page for `reviewer` and
`qc` after sign-in** (they used to land on Applications). Endpoint
`GET /api/v1/admin/scholarship/programme-overview/`; module
`apps/scholarship/programme_overview.py`. **No migration** — every figure is read from data the
system already records.

**Access: every console role** (super + `org_admin` + `admin` + `finance` + `qc` + `reviewer`).
Referral `partner` is refused (403), anonymous 401, another tenant's gift 404.

**⚠ Openness is not sameness. The SERVER decides which sections a role receives**
(`programme_overview.SECTIONS_BY_ROLE`), before anything is serialised — a reviewer's payload has
no `money` key to hide, a finance admin's has no `funnel`. A page that fetched everything and
rendered a subset would be a side door into Applications / Payments / Spending for the roles the
menu already withholds those pages from. A role missing from that map receives nothing at all.

| Role | Sections received |
|---|---|
| `super` / `org_admin` / `admin` | `funnel`, `money`, `attention`, `applications_series`, `money_series` (+ `layout` and `layout_source` for `super` / `org_admin`) |
| `finance` | `money`, `money_series` |
| `qc` | `qc` |
| `reviewer` | `mine` |

(The `intake` block that was on every row from 15 to 18 September is gone — owner: "doesn't add
much value". Every payload now carries `intake` / `intakes` instead: the chosen round and the
picker's options — code, name, year, state — a date, not a person or a sum.)

**⚠ THE ORGANISATION'S LAYOUT NARROWS AND ORDERS THE ROW; IT NEVER WIDENS (phase 2, 2026-09-18).**
`OrganisationOverviewLayout` holds an ordered `[{key, on}]` over the five widgets (`funnel`,
`money`, `attention`, `applications_series`, `money_series`). `programme_overview.build` takes the
role's row above, drops the widgets the organisation switched off, and emits `sections` in the
organisation's order. `mine` and `qc` are **pages, not widgets** — outside the catalogue, never
switchable. A layout that hides every widget a role may see yields `sections: []` with a 200.
**Who edits it: `org_admin` + super** (`AdminOverviewLayoutView`, GET/PUT
`admin/scholarship/organisation/overview-layout/`, organisation derived, `?org=` for a super,
cross-tenant 404). The Overview shows Customise by the PRESENCE of `layout` on the payload.
**Per gift since request #42 (2026-10-22):** `ProgrammeOverviewLayout` is a gift's own layout and
overrides the organisation's for that gift only; the organisation's is the default for gifts without
one. Same endpoint with `?programme=<gift code>` (GET reports `source`, PUT writes the gift's row,
DELETE removes it; another organisation's gift 404). Same writers, same narrowing rule.

**⚠ THE INTAKE FILTER NARROWS EVERYTHING INSIDE THE FENCE.** `?intake=<cohort id>` is resolved by
`_AdminBase._intake_narrowing`: a non-super only within their organisation, and within the named
gift when one was named; unknown / another tenant's / another gift's / non-integer are one answer,
404. With a round chosen every section narrows — the money strip included — so the strip's
byte-equality with the Payments footer is a claim about the UNFILTERED page only.

**⚠ FINANCE IS DELIBERATELY WIDENED HERE, AND THIS POINTS THE OPPOSITE WAY TO THE SPENDING PAGE.**
`/admin/spending` refuses `finance` (since #39 S3: the finance preset does not hold `spending`) and
continues to. On the Overview, finance
sees the money strip (committed / paid / remaining / spent) and every money chart — released
versus spent with the running gap, average spend per transaction per week, transactions per student per
week, and spending by category. Owner ruling, 2026-09-15, recorded in `docs/decisions.md`
("Finance sees aggregate spending on the Overview though not the Spending page"). What finance
gains is **totals**; what it never gains is a name, a file, a document or a verdict, because none
of those is in a section it is given. The Spending page is refused precisely because it is a page
of named students.

**⚠ `reviewer` and `qc` get NO money and NO programme-wide totals.** A reviewer sees only their own
open cases — the verdict-due date per case, banded open / due soon / overdue — and their own pace
(verdicts completed, and how long a student waited, phrased as the student's wait, never as a
score on the volunteer: the `reviewerDetail` ruling of 2026-08-02 applies unchanged). A QC sees
the cases awaiting QC and their own pace. Neither sees a funnel or a ringgit.

**Org-fenced on one queryset** (`programme_overview.application_scope`, classified
`programme-overview-org-fenced+role-shaped` in `test_org_fence.py`). Disbursements and spend rows
are reached only through that scope, never from their own managers. The `?programme=` gift
narrows **inside** the organisation fence and can never widen it.

## Scholars (student maintenance) — access

`/admin/scholars` (list) and `/admin/scholars/<id>` (one scholar's maintenance file), added
2026-10-29 (maintenance S2). **The Applications rule, unchanged — no new reach for anyone:**
`_b40_scope` decides. `see_all` (super, org_admin, admin, qc presets) reads every scholar in the
organisation; `review` without `see_all` (reviewer) reads ONLY the scholars assigned to them;
`finance` and `partner` are refused (403) — finance never sees a name beside case data (the Spending
rule). Another organisation's scholar is 404. Anybody who may read a file may add an activity entry
(note / call / meeting, optionally staff-only) — a record, not a decision. **Placing or lifting a
hold** stays on the cockpit's sub-state endpoint and needs `payments.may_prepare` (super, org_admin,
a `payments_prepare` holder) since maintenance S1. Menu row: same roles and keys as Applications,
inside a gift (`needsProgramme`).

## Payments module (Vircle payment runs) — access

The Payments module (`/admin/payments`, entered via the Administration ORGANISATION-section card;
no top-level nav entry). It lives *inside* the Administration surface, so it inherits the org
fence.

**⚠ REWRITTEN 2026-10-19 — request #39 Sprint 2, owner ruling (option A):** *"Finance role currently
doesn't have clear action items. I would like the role to be able to approve payment — the work that
Suresh does today."* The gates read **permissions** (`apps/scholarship/payments_chain.py`); the
presets give exactly the access below. The earlier wording (Finance CHECKS, the org admin
countersigns) is superseded; see `docs/decisions.md` 2026-10-19.

**Access.** READ (list, run detail, CSV, funding summary) and SIGN (the step is the service's):
any `payments_*` holder or the organisation admin — presets `admin` + `finance` + `org_admin` (super
passes as always). CREATE / EDIT an item / CANCEL: `payments_prepare` or the organisation admin —
presets `admin` + `org_admin` **only**; `finance` is refused. `reviewer` / `qc` / referral `partner`
are refused everywhere — 403 on every endpoint, cross-org 404.

**The chain** is `draft → admin_signed → [finance_checked] → completed` (the stored names are kept;
the screen labels the steps Prepared / Checked / Approved):

- **maker** (`payments_prepare` — preset `admin`) signs the draft → `admin_signed`.
- **check** (`payments_check`) → `finance_checked` — ONLY while somebody ELIGIBLE for this run
  holds that key (active, has signed in, has not signed the run: review fixes 2 and 4), evaluated
  LIVE and never stored. **No preset holds it**, so on every organisation today the chain
  is two steps; granting it to somebody (Sprint 4's editor) arms a third signer, including for a run
  already at `admin_signed`. While armed, an approver at `admin_signed` is refused with
  `finance_check_required`.
- **approver** (`payments_approve` — preset `finance`) → `completed`, which releases the money and
  emails Vircle (the approver AND every active org admin CC'd, deduplicated — owner 2026-10-19,
  option A). Stored in the `org_admin_signed_*` triple (a kept misnomer).
- **the fallback:** when NO active `payments_approve` holder who has SIGNED IN (`first_seen_at`)
  and has not already signed the run exists, the **organisation admin** approves (the pre-change path). Live, per run: an organisation
  with no Finance person works exactly as before; the sole approver who prepared the run, the last
  approver revoked or switched, or a run Finance CHECKED before the change, all fall back. The run
  serves `approver_fallback` so the page says why the org admin sees the button. While a Finance
  person can approve, an org admin trying to is refused with `wrong_role`.

**"Waiting for you".** Each run carries `your_step` (`sign` / `check` / `approve` / null) from
`payments.next_step_for`, the SAME predicate `payments.sign` asks — the landing page lists those runs
and the Payments menu row shows their count. The "ready" email follows the same rule: after the
maker, the checkers when armed, else the approvers, else the org admins under the fallback.

**Distinct signers.** Every signature collected on a run must be a different person (email,
case-insensitive). One person may hold Prepare AND Approve and use them on DIFFERENT runs, never on
one. `super` may fill any ONE slot per run and never two — enforced by that same pairwise rule. The
service also refuses a signer from another organisation, and re-reads the run under a row lock so
two approvers can never both complete it; an edit or cancel is re-checked under the same lock,
so a stale page can never reopen (and re-pay) a completed run.

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

**The chain has the payments chain's SHAPE but, since #39 Sprint 2, NOT its rules** (owner question
6, 2026-10-19: credits keep today's chain; accepting money is the organisation's act):
`draft → admin_signed → [finance_checked] → confirmed`, with the middle step required iff the
organisation has ≥1 ACTIVE `finance` admin (`payments.credit_check_required`, the old predicate,
split out so re-keying the run check could not switch this one off), evaluated live at every
attempt. Roles, not permissions, gate every step here.

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

- **SHIPPED 2026-09-15 — the Programme Overview** (see its own section above): open to every
  console role, shaped server-side by `programme_overview.SECTIONS_BY_ROLE`. Two things changed
  for existing roles and both are deliberate: **`finance` gained aggregate spending** it is
  refused on `/admin/spending`, and **`reviewer` / `qc` now land here after sign-in** instead of
  Applications. No migration; no new field collected. Tests
  `apps/scholarship/tests/test_programme_overview.py` + `tests/test_review_sla.py`.
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

## Referral partners and the witness (sources and referral partners arc, 2026-10-19) — access

**Referral partners — `GET` / `PATCH /api/v1/admin/referral-partners/[<id>/]` — `super` ONLY.**
Every other role (org_admin, admin, qc, reviewer, finance, referral `partner`) gets 403. A super marks
or unmarks a `partner_organisations` row as a platform referral partner: never a tenant, a reserved
code or a switched-off row, and an unmark waits until the row's `partner` logins are revoked
(`referral_links.mark_refusal`; also never a source's old row or a code `?ref=` cannot carry), and a
revoked `partner` login is restored only onto an active referral partner (`AdminRevokeView`, 400
`not_a_referral_partner`). Not org-fenced, by construction: a referral partner belongs to no
organisation. Marking decides whose students a `?ref=` link puts on a partner login's list (NRIC,
phone, address, income), so it is a platform decision. No screen yet (TD-387).

**The bursary witness (`AdminBursaryWitnessView`) — `super` ONLY** since sources Sprint C; the witness
is the override, else the APPLICATION's own source, never the referral partner. Choosing the override
stays super / admin / org_admin. The cockpit serves the application's source as `source` (the old
`referred_by_org` key left in Sprint D).
