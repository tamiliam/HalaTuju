# Implementation Plan — Organisation Payments Module (Vircle payment runs)

**Date:** 2026-07-16 (rev 2, owner corrections applied) · **Status:** Awaiting owner approval
**Implementer:** Opus 4.8
**Feature:** A "Payments" module in the Administration panel where BrightPath's staff create a
monthly payment run, sign it off (Admin → Org Admin), and send it to Vircle.

> **Scope boundary (owner, 2026-07-16):** this module is *programme plumbing* — money OUT to
> students via Vircle. It is NOT billing to BrightPath for platform usage. The existing
> disabled "Billing 💳 — coming soon" card stays untouched; Payments gets its **own new card**.

---

## 1. What the owner asked for

1. Module lives in the **Administration page** (ORGANISATION section, its own card); access
   **Admin + Org Admin only** (super passes any role check as always).
2. Clicking the module asks for a **payment date** (date picker, **past dates not allowed**).
3. A table of **students in good standing** is shown. Columns: **Name** (links to the
   application page, opens in a new tab), **NRIC**, **Vircle ID**, **Amount approved**,
   **Paid to date**, **Amount to be paid**.
4. Filter: **Awarded** + **started their programme** (`reporting_date` < payment date; general
   rule — STPM/Matric/Asasi start June, Poly/UA Diploma July, PISMP August) + **not in semester
   break** + **Vircle status confirmed in the Action Centre** + *(future)* **bursary contract
   signed and completed**.
5. Sign-off flow: **an Admin signs with their full name (as in their profile), then the Org
   Admin countersigns with theirs.** The countersignature triggers: **(1) a CSV file written to
   the Drive Vircle folder; (2) an email to Vircle (future).**
6. **Monthly rule (owner, 2026-07-16):** **RM200/month for every student.** STPM's RM3,000
   award simply runs longer — 15 months. (Standard RM2,000 = 10 months; the continuing-STPM
   RM1,000 = 5 months.) The RM300 figures in the July batch were mistakes, not a rate.
7. **Regularise the July payment run** (the 30/6/2026 batch, i.e. the "1 July" payment) —
   one-time corrections that the system must apply and never repeat:
   - **TAANUSIYA A/P MUGINDRAN** (app 10) and **DIVASHINI A/P MURUGAN** (app 18) were paid
     RM300 instead of RM200 → pay **RM100 on the 1 Aug 2026 run**, then RM200/month from
     1 Sep 2026.
   - **SHAARVESHWAAR A/L SARAWANAN** (app 61, UA diploma/university, reports 19 July) was paid
     RM200 before starting his programme → **skip the 1 Aug 2026 run**, resume RM200/month
     from 1 Sep 2026.
8. **Vircle ID capture:** today's IDs come from the owner's CSV (one-off import). In future the
   **student enters their Vircle ID in the Action Centre** when they confirm their Vircle
   setup — a new field on that task, **with validation** (standardised length; the early
   digits are identical across accounts).

## 2. Investigation findings the plan is built on (verified 2026-07-16)

- **Mount point:** the Administration panel (`/admin/administration`, shipped 2026-07-15)
  ORGANISATION section, gated by `canManage = isSuper || isOrgAdmin`
  (`halatuju-web/src/app/admin/administration/page.tsx:56`). Payments becomes a new icon-card
  beside the (untouched) Billing placeholder (`:307-308`).
- **A money-out ledger already exists and is empty.** `Disbursement`
  (`halatuju_api/apps/scholarship/models.py:1449`, statuses
  scheduled/due/released/withheld/returned, `PAID = ('released',)`) + service
  `apps/scholarship/disbursement.py`. **0 rows in production** — the two real batches
  (30/6/2026 and 16/07/2026) exist only in the owner's spreadsheet
  (`Downloads/brightpath_bursary.csv`). ⇒ a one-off backfill is required so "Paid to date" is
  truthful.
- **Prod data is ready.** All 30 awarded applications have `reporting_date`,
  `chosen_pathway`, and `award_amount` populated, and all 30 match the CSV by NRIC
  (digits-only comparison; 0 mismatches). Pathways: matric(12), stpm(5), poly(5), asasi(2),
  pismp(3), university(3). TAANUSIYA/DIVASHINI verified as STPM RM3,000 (awards stay as-is
  under the 15-month rule); SHAARVESHWAAR verified as `university`, reporting 2026-07-19.
- **Vircle ID is NOT in the database.** It exists only in the CSV (13 digits; all 30 share the
  prefix `8000400175`). New field + import + Action-Centre capture needed.
- **Vircle confirmation** = `ResolutionItem(code='vircle_setup_pending', status='resolved')`
  (`apps/scholarship/resolution.py:517`, `apps/scholarship/vircle.py:83`); the student's
  registered mobile is in `resolution_text`. The Action-Centre form is `VircleTask`
  (`halatuju-web/src/components/ActionCentre.tsx:617`, resolve call `:636`); backend resolve is
  `ResolutionItemResolveView` (`apps/scholarship/views.py`). 20/30 confirmed today. **It is a
  CLAIM, not a verification** (`vircle.py:9-12`) — the UI must never label it "verified".
- **No Vircle API.** Today's channel is a generated Google Sheet in the "03 Vircle" Drive
  folder via the `sheets.py` seam (service account, best-effort, DB is source of truth). The
  payment CSV reuses this seam.
- **Manual exclusions are real.** Of the 4 students excluded from the 16/07 batch, 3 have
  resolved Vircle confirmations — their exclusion was a judgment call. ⇒ the run needs a
  per-student include/exclude toggle with a recorded reason; filters alone don't reproduce
  the owner's decisions.
- **State-machine friction:** `disbursement.release_tranche` requires
  `pool.FUNDED_STATES = ('active','maintenance')`, but the whole cohort sits at `'awarded'`
  (the bursary-agreement chain hasn't completed in-app). See design decision D3.
- **Sign-off names:** `PartnerAdmin.name` exists (`apps/courses/models.py:516`) — typed
  signatures validate against it.
- **Access-control patterns to reuse:** `_AdminBase` + `_org_scoped` + `_org_allows`
  (`apps/scholarship/views_admin.py:63,114,123`; cross-org = 404, never 403), roles per
  `PartnerAdmin.ROLE_CHOICES`, `has_role()` lets super pass any check.

## 3. Design decisions

**D1 — Run model on top of the existing ledger, not beside it.** A `PaymentRun` +
`PaymentRunItem` pair holds the *working* state (draft amounts, exclusions, signatures).
Immutable `Disbursement` rows (`status='released'`) are created **only at countersignature**.
"Paid to date" is always `SUM(disbursements released)` — one source of truth for history,
backfill, and future runs alike.

**D2 — Sign-off = maker → approver, typed full names, two people.**
`draft → admin_signed → completed` (+ `cancelled`). This is a **maker–checker chain** (owner,
2026-07-16): the **maker** (first signature, role `admin` — at BrightPath: Poongulali Veeran)
prepares and signs the run; the **approver** (countersignature, role `org_admin` — Suresh
Thiru) approves it. The two signers must be **different people** (`super` may fill either
slot, still not both on one run). The typed name must match the signer's `PartnerAdmin.name`
exactly (trimmed, case-insensitive) — mirrors the bursary agreement's typed-signature pattern.
Amounts/exclusions lock after the first signature (editing reverts the run to draft and clears
the signature, so nobody signs one list and sends another).

*Future-proofing:* when the parked **finance role** arrives it becomes a **checker** step
BETWEEN maker and approver (`draft → admin_signed → finance_checked → completed`). Keep the
status field + signature columns per-step (not a boolean pair) so inserting that middle state
is additive — a new status value + one more signature triple, no reshaping.

**D3 — Do not fight the application state machine.** Completion writes `released`
Disbursement rows via a new `payments.py` service function that accepts
`status in ('awarded','active','maintenance')` — deliberately wider than
`release_tranche`'s funded-only guard, because the real cohort is paid while at `'awarded'`
(agreement chain not yet live in-app). No status flips from this module; the
`active → maintenance` first-release flip remains `release_tranche`'s business. Document this
in the module docstring.

**D4 — Eligibility ("good standing") for a given payment date:**
1. Org-fenced: `owning_organisation` = the caller's org (super sees the org they operate on).
2. `status in ('awarded','active','maintenance')`.
3. **Started:** `reporting_date <= payment_date` when set (all 30 have it); when NULL, fall
   back to the pathway default start for the cohort year — `stpm/matric/asasi` → 1 June,
   `poly/university` (UA diploma/degree) → 1 July (owner-confirmed, even for a rare June
   starter), `pismp` → 1 August, anything else → 1 July. **Continuing students** (reporting
   date in a previous year) satisfy this automatically and follow the same track — no special
   case.
4. **Vircle ready = a non-blank `vircle_id`**, however it arrived (Action Centre, CSV import,
   or admin edit). Owner 2026-07-16: only 22 students were ever emailed the setup task — 8
   original students were onboarded outside it and will never have a resolved
   `vircle_setup_pending` item, so the resolved item must NOT be a payment gate. The ID itself
   is the payable fact; the Action-Centre confirmation remains visible as an info badge only.
5. **Not on hold:** `maintenance_substate != 'on_hold'` (the only break-like signal that
   exists; see D5).
6. **Remaining balance:** `award_amount − paid_to_date > 0`.
7. *(Future, flag-gated)* when `BURSARY_AGREEMENT_ENABLED`: agreement fully executed
   (Foundation countersigned). Build the check now behind the flag, default off.

Students failing 4–6 are **shown greyed-out with the failing reason** (not hidden) — the admin
must see who is being skipped and why. Students failing 2–3 are simply not listed.

**D5 — Semester break / gap months = manual exclusion (v1), calendar later.** No break
calendar exists in the data. The run detail gives every eligible student an include/exclude
toggle with a required reason (e.g. "semester break"), snapshotted on the item. Owner
2026-07-16: a **per-pathway payment calendar is coming** — e.g. STPM's programme runs ~17–18
months but only 15 are paid, so fixed no-pay "gap months" will be defined once the data is
confirmed, and the same may apply to other pathways. Out of scope for v1, but the eligibility
engine keeps a single choke-point (`eligible_rows`) so the calendar drops in as one more
filter later without touching the run/sign-off machinery.

**D5b — Future good-standing stops feed in automatically.** The owner will later build a
process for pausing/stopping payments on poor standing (low CGPA, dropout, etc.). The
eligibility engine is already shaped for it: a **temporary stop** = the maintenance
`on_hold` substate (already excluded by D4-5, and CGPA already lives in `SemesterResult`);
a **permanent stop** = application status `closed`/`withdrawn` (already outside D4-2's
status set). That future process only needs to set existing states — no payments-module
change required.

**D6 — Amount to be paid: flat rate minus credit, capped by the remaining award.**
`RATE = RM200/month` for **every** student (owner, 2026-07-16 — STPM is not a higher rate,
just a longer tail: RM3,000 = 15 months).

```
amount_due = clamp(RATE − payment_credit, 0, award_amount − paid_to_date)
```

`payment_credit` is a per-application "paid ahead of schedule" balance (new field, default 0).
It is how the **July regularisation** is encoded once and consumed automatically:
- TAANUSIYA (app 10): credit **100** → Aug run defaults to RM100, credit clears, Sep+ RM200. ✓
- DIVASHINI (app 18): credit **100** → same. ✓
- SHAARVESHWAAR (app 61): credit **200** (paid before starting) → Aug run defaults to RM0 —
  shown in the run as included-at-zero with the reason "credit from advance payment" — credit
  clears, Sep+ RM200. ✓

Credit is decremented at **run completion** by the amount it offset (never below 0). Future
overpayments, should they ever happen, are regularised the same way — set the credit, the next
run absorbs it. Per-item amounts remain editable in draft (server-capped at the remaining
award, floor 0), so the admin can override any default.

**D7 — "Send to Vircle" = CSV in the Drive Vircle folder (email = stub).** On
countersignature: build the CSV (schema mirrors the owner's sheet: No, Student NRIC, Vircle
ID, Phone, Student Name, Amount, Payment date, Run reference), write it to the "03 Vircle"
Drive folder through a new `write_payment_csv()` in the existing `sheets.py` seam
(best-effort: a Drive failure logs + leaves the file URL blank, the run still completes, a
"retry upload" action re-writes it — DB remains the record). Also downloadable from the run
page. Phone = the Vircle-registered mobile from the resolution item's `resolution_text`,
falling back to the profile mobile. Email to Vircle: define `send_payment_run_email()` as a
no-op stub with a TODO + setting `VIRCLE_PAYMENTS_EMAIL` (unset = disabled) — wiring it is a
later change once Vircle confirms recipient/format.

**D8 — Backfill as first-class runs.** The import command creates two `PaymentRun` rows
(payment dates 2026-06-30 and 2026-07-16 as recorded in the CSV, `status='completed'`,
`reference='backfill-…'`, no signatures — nullable signature fields cover this) with released
Disbursement rows per the CSV's **actual** amounts (including the two RM300s — history is a
record, not a rule), stamps `vircle_id` on all 30 applications (NRIC digits join), and seeds
the three regularisation credits from D6. Idempotent (re-running changes nothing that exists).
`--dry-run` prints the reconciliation table.

**D9 — Vircle ID captured in the Action Centre, prefix pre-filled.** Owner 2026-07-16: the
standard prefix is `8000400175` (Vircle issues running numbers) and the goal is to minimise
what the student types. So the `VircleTask` form shows **`8000400175` as fixed text and the
student types only the final 3 digits** (digits-only input, exactly 3). The full stored value
is always prefix + suffix = 13 digits. Backend validation enforces the same rule on the full
ID: 13 digits starting `VIRCLE_ID_PREFIX = '8000400175'` (a module constant — if Vircle's
running numbers ever roll past `…175999`, the constant is a one-line change and the admin
PATCH path is the escape hatch meanwhile). On resolve, the backend stores it on
`application.vircle_id` (the mobile stays in `resolution_text` as today). All 30 current
students get their IDs from the CSV import (including the 8 never-emailed originals); future
students supply theirs when they confirm. `vircle_id` is also editable by super/org_admin via
the admin application-detail PATCH path (corrections, without asking the student to redo the
task).

**D10 — Emails must mention the Vircle Wallet ID step.** The award-offer email, the Vircle
installation/setup email, and the Action-Centre confirmation wording must all tell the student
to have their **Vircle Wallet ID** ready and enter it when confirming (templates in
`apps/scholarship/emails.py` + the `send_vircle_install_emails` command; en/ms/ta).

## 4. Data model changes (one migration in `apps/scholarship`)

```python
# ScholarshipApplication — new fields
vircle_id      = models.CharField(max_length=30, blank=True, default='')   # Vircle account ID (13 digits)
payment_credit = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # paid-ahead balance (D6)

class PaymentRun(models.Model):
    STATUS = [('draft','Draft'), ('admin_signed','Admin signed'),
              ('completed','Completed'), ('cancelled','Cancelled')]
    organisation   = FK('courses.PartnerOrganisation', PROTECT, related_name='payment_runs')
    payment_date   = DateField()                     # validated >= today at creation
    status         = CharField(choices=STATUS, default='draft')
    reference      = CharField(max_length=50, unique=True)   # e.g. 'PR-2026-08-001'; 'backfill-…' for imports
    created_by     = CharField(max_length=254)       # admin email (audit, mirrors actioned_by)
    admin_signed_name / admin_signed_email / admin_signed_at        # null until signed
    org_admin_signed_name / org_admin_signed_email / org_admin_signed_at
    drive_file_url = URLField(blank=True, default='')
    note           = CharField(max_length=500, blank=True, default='')
    created_at / updated_at

class PaymentRunItem(models.Model):
    run            = FK(PaymentRun, CASCADE, related_name='items')
    application    = FK(ScholarshipApplication, PROTECT, related_name='payment_run_items')
    included       = BooleanField(default=True)
    exclude_reason = CharField(max_length=200, blank=True, default='')  # required when excluded
    amount         = DecimalField(10,2)              # editable in draft; capped at remaining
    credit_applied = DecimalField(10,2, default=0)   # how much payment_credit this item consumed (audit)
    # snapshots at creation time (so the signed record can't drift):
    award_amount_snapshot / paid_to_date_snapshot = DecimalField(10,2)
    vircle_id_snapshot = CharField(max_length=30, blank=True, default='')
    disbursement   = FK(Disbursement, SET_NULL, null=True, blank=True)  # set at completion
    class Meta: unique_together = ('run', 'application')

# Disbursement — no schema change; completion rows use reference=f'vircle:{run.reference}'
```

## 5. Backend service — new module `apps/scholarship/payments.py`

Follows the `disbursement.py` shape (service functions + `PaymentsError(code)`):
- `MONTHLY_RATE = Decimal('200')` — single flat rate (D6).
- `eligible_rows(organisation, payment_date)` — D4 queryset + per-student reason annotations.
- `default_amount(application)` — D6 formula (rate − credit, capped, floored).
- `create_run(organisation, payment_date, by_email)` — rejects past dates
  (`payment_date < localdate()` → `past_date`); snapshots items incl. `credit_applied`.
- `set_item(run_item, *, included, exclude_reason, amount)` — draft only; enforces caps.
- `sign(run, admin, typed_name)` — role/state machine per D2; name mismatch → `name_mismatch`;
  same-person countersign → `same_signer`.
- `complete(run)` — called inside the countersign transaction: create released Disbursements
  (`released_at=now`, `scheduled_for=payment_date`, `actioned_by=<org-admin email>`),
  decrement each application's `payment_credit` by `credit_applied`, then best-effort
  `sheets.write_payment_csv(run)` + `send_payment_run_email(run)` (stub).
- `paid_to_date(application)` — `SUM(amount) WHERE status='released'`.
- `cancel(run, by)` — draft/admin_signed only.
- `valid_vircle_id(value)` — D9 rule; shared by the resolve endpoint and the admin PATCH.

Management command `import_vircle_csv` (D8) in
`apps/scholarship/management/commands/import_vircle_csv.py`.

## 6. API endpoints (in `apps/scholarship/urls.py` + `views_admin.py`, all `_AdminBase`)

Access rule for every endpoint: `has_role(admin, 'admin', 'org_admin')` **and** org-fenced via
`_org_scoped`/`_org_allows` (cross-org → 404). Reviewer/qc/partner → 403.

| Method + path | Purpose |
|---|---|
| `GET  admin/scholarship/payment-runs/` | List runs (org-fenced), newest first |
| `POST admin/scholarship/payment-runs/` | `{payment_date}` → create draft + items; 400 `past_date` |
| `GET  admin/scholarship/payment-runs/<pk>/` | Run detail: items + greyed ineligible list + totals |
| `PATCH admin/scholarship/payment-runs/<pk>/items/<item>/` | Toggle include/exclude(+reason), edit amount — draft only |
| `POST admin/scholarship/payment-runs/<pk>/sign/` | `{typed_name}` — admin sign or org_admin countersign (completes run) |
| `POST admin/scholarship/payment-runs/<pk>/cancel/` | Cancel a draft/admin_signed run |
| `GET  admin/scholarship/payment-runs/<pk>/csv/` | Download the CSV (any status ≥ admin_signed) |

Student-facing change: `ResolutionItemResolveView` (`apps/scholarship/views.py`) — for
`code='vircle_setup_pending'`, accept + require `vircle_id` in the payload (the frontend sends
the full 13-digit ID it assembled from prefix + 3-digit suffix), validate (D9), store on
`application.vircle_id`. The admin application-detail serializer
(`serializers_admin.py`) gains `vircle_id` (editable, validated) + `paid_to_date` +
`payment_credit` (read-only display).

## 7. Frontend (`halatuju-web`)

- **Stitch first (mandatory):** two screens in HalaTuju Stitch project `10844973747787673276` —
  (a) Payments landing (run list + "New payment run" date dialog), (b) Run detail (eligibility
  table, greyed-out skipped students with reasons, exclude toggles, amount edit, two-stage
  sign-off panel with typed-name inputs, completed state showing Drive link + CSV download).
  Owner approves visuals before any template code.
- **Wiring:** a **new "Payments" icon-card** in the ORGANISATION section of
  `administration/page.tsx` (the Billing placeholder card is **left untouched**) → route
  `/admin/payments` (new `src/app/admin/payments/page.tsx`, detail at
  `payments/[id]/page.tsx`). Guard pages with
  `role === 'admin' || role === 'org_admin' || isSuper`.
  **NO new top-level nav entry** (owner, 2026-07-16, reaffirmed on the Stitch review):
  the nav array in `layout.tsx:81-92` is NOT touched — Payments is a sub-item entered only
  through the Administration panel, and its pages highlight "Administration" as the active
  nav item. Stitch screens must not show "Payments" in the sidebar/menu.
- **Date picker:** native `<input type="date" min={today}>` styled with the shared `input`
  class (no picker library exists in the codebase; keep it that way) + server-side `past_date`
  handling.
- **Table:** hand-rolled Tailwind table per the `staffTable` pattern
  (`administration/page.tsx:157-226`). Name cell:
  `<a href={/admin/scholarship/${appId}} target="_blank" rel="noopener noreferrer">`.
  Columns exactly: Name · NRIC · Vircle ID · Amount approved · Paid to date · Amount to be
  paid (+ include toggle / reason in draft). Footer row: totals. Zero-amount items (credit)
  show their reason inline.
- **Action Centre:** `VircleTask` (`components/ActionCentre.tsx:617`) gains the Vircle ID
  input per D9 — `8000400175` rendered as a fixed, non-editable prefix with a 3-digit
  suffix input beside it; the full 13-digit ID is sent with the resolve call.
- **Email templates (D10):** award-offer + Vircle-setup emails updated to mention the Vircle
  Wallet ID step (en/ms/ta).
- **API client:** new functions in `src/lib/admin-api.ts` (`getPaymentRuns`,
  `createPaymentRun`, `getPaymentRun`, `updatePaymentRunItem`, `signPaymentRun`,
  `cancelPaymentRun`) using `adminFetch`/`adminMutate`.
- **i18n:** `admin.payments.*` + the new Action-Centre strings in `en/ms/ta.json` (British
  English; Tamil per `tamil-style-guide.md`); extend the flat-namespace i18n guard test.
- **Vircle wording:** the eligibility badge says "Confirmed by student", never "verified".

## 8. Sprint roadmap (3 sprints, one deploy at the end)

**Sprint P1 — Ledger foundation + backfill (backend only, ~15 files, medium)**
Migration (vircle_id, payment_credit + PaymentRun/PaymentRunItem), `payments.py` service
(eligibility, flat rate + credit formula, run lifecycle, sign-off state machine, vircle-ID
validator), `import_vircle_csv` command (incl. the three seeded credits),
`sheets.write_payment_csv` + email stub. Tests: `tests/test_payments.py` — eligibility matrix
incl. pathway-fallback dates; the credit formula against the three real regularisation cases
(RM100 / RM100 / RM0-then-RM200); cap/exclusion rules; sign-off state machine incl.
name-mismatch / same-signer / lock-after-sign; completion ledger writes + credit decrement;
backfill idempotency + dry-run against a fixture CSV. Acceptance: full pytest green; dry-run
reconciles all 30 CSV rows; a simulated 1 Aug run produces exactly the owner's expected
amounts for apps 10, 18, 61.

**Sprint P2 — API + UI (~20 files, medium)**
Stitch screens → owner visual approval → endpoints + serializers (`views_admin.py`,
`urls.py`) with org-fence tests mirroring `test_org_admin_powers.py` (reviewer/qc 403,
cross-org 404, partner 403); the Action-Centre Vircle-ID capture (backend resolve + `VircleTask`
frontend prefix+suffix input + validation tests both sides); the D10 email-template updates
(award offer + Vircle setup mention the Wallet-ID step, en/ms/ta); the two admin pages +
admin-api functions + i18n + jest (`src/lib/__tests__/payments.test.ts` + colocated page
tests). Acceptance: full local
walkthrough — create run for a future date, past date rejected, exclude one student with
reason, admin signs, org_admin countersigns, CSV downloads with correct rows/amounts, run
locks; a student resolving the Vircle task with a bad ID is rejected, with a good ID lands in
`vircle_id`.

**Sprint P3 — Production cutover (~8 files, low)**
Deploy api+web (the feature's single deploy). Run `import_vircle_csv` on prod (dry-run first,
owner eyeballs the reconciliation, then live). Verify in prod: paid-to-date figures match the
owner's sheet for all 30; create the real **1 Aug 2026 draft run** and check it shows RM100
for TAANUSIYA and DIVASHINI, RM0/skip for SHAARVESHWAAR, RM200 for everyone else eligible.
Docs: CHANGELOG, `docs/scholarship/role-matrix.md` (payments powers), project CLAUDE.md
Next-Sprint note, retrospective. `wat_lint` + sprint-close per workflow.

**Prod sign-off readiness (verified 2026-07-16):** the full D2 chain exists on BrightPath
today — maker **Poongulali Veeran** (`kulaly29@gmail.com`, active `admin`) and approver
**Suresh Thiru** (`surithiru@gmail.com`, active `org_admin`). No role changes needed.

## 9. Settled with the owner (2026-07-16)

1. **"Should have been RM2000" was a typo for RM200/month** — TAANUSIYA's and DIVASHINI's
   awards stay RM3,000 STPM over 15 months; no award data fix.
2. **Vircle ID prefix is strictly `8000400175`** (running numbers); the student types only the
   final 3 digits (D9).
3. **`university`/UA diploma defaults to July** even for a rare June starter; continuing
   students from previous years follow the same track.
4. **The 8 never-emailed original students** get their IDs from the owner's CSV; the resolved
   Action-Centre item is NOT a payment gate (D4-4).

## 10. Open / future items (none block P1)

1. **Vircle email recipient + required file format** — needed only when the email stub (D7)
   is wired; CSV columns currently mirror the owner's own sheet.
2. **Per-pathway payment calendar** (gap months + semester breaks, D5) — owner will fix the
   rule once programme data is confirmed (e.g. STPM: 15 paid months across a ~17–18-month
   programme); until then, manual exclusion with reason.
3. **Good-standing pause/stop process** (low CGPA, dropout — D5b) — future build; lands on
   existing states (`on_hold`, `closed`/`withdrawn`) that this module already respects.
