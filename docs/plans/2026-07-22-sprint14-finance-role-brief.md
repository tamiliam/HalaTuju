# Sprint 14 — Finance role (dormant checker) + payments funding summary (implementation brief)

**Date:** 2026-07-23 (v2 — supersedes the 2026-07-22 draft) · **Author:** architect session (owner-approved) · **Executor:** Opus 4.8 agent
**Roadmap:** `docs/plans/2026-07-14-platform-roadmap-draft.md` Phase 5, Sprint 14 (trigger FIRED 2026-07-22)
**Authority for role powers:** `docs/scholarship/role-matrix.md` — change the matrix FIRST (Phase 1), then code.

> **v2 scope correction (owner, 2026-07-23):** the finance checker is built INSIDE the existing
> payments module — a third signature card in the shipped run-detail design — never a parallel
> surface. **Billing & usage is OUT of this sprint entirely**: it means HalaTuju invoicing the
> organisation for metered service usage (Gemini/Vision/GCP/Supabase/Twilio/change requests at
> cost + 15–30%), it requires a billing-sources investigation that has not happened, and its
> Administration card **stays "Coming soon" untouched**. Do not build any billing page, endpoint,
> or model.

---

## 0. Read before you start

1. Follow `Settings/_workflows/sprint-start.md` (workspace level): pre-flight `git status` + `git log origin/main..HEAD` — **start on a clean, fully pushed tree or STOP and report.**
2. Read `halatuju_api/CLAUDE.md` and `docs/build-for-tenancy-conventions.md`. Every rule binds this sprint.
3. **Migrate-first discipline:** deploys do NOT run migrations. DDL is applied by hand via Supabase MCP (project `pbrrlyoyyiftckqvzvvo`) BEFORE the deploy; migration files are recorded as `django_migrations` rows. NEVER run `sqlmigrate` (renders SQLite). See §8 runbook.
4. **Push = deploy** (Cloud Build). This sprint has ONE deploy at the end (§8). Do not push before Phase 5 verification passes.
5. **UI rule:** no new pages in this sprint. The checker card copies the shipped run-detail signature-card design (two green "Authorised by (Maker)" / "Approved by (Approver)" cards → three cards); the funding summary is a new section on the shipped Payments landing page, in its existing style. Match the existing components exactly — no redesigns.
6. All line numbers below were verified 2026-07-22. If drifted, find the construct by name — do not guess.

### Owner-settled decisions (binding — do not relitigate)

| # | Decision |
|---|---|
| D1 | **Finance = a CHECKER between maker and approver.** Chain becomes `draft → admin_signed → finance_checked → completed`. |
| D2 | **The finance step is DORMANT until activated.** Activation is data-driven: the org has ≥1 ACTIVE `finance` PartnerAdmin. With none, the chain runs exactly as today (2-step) — **existing payment tests must pass UNMODIFIED**. |
| D3 | **No Billing & usage work.** The Administration card stays disabled "Coming soon". (Platform-billing design is a separate future deliverable.) |
| D4 | **Finance gets NO B40 access** (`_b40_scope` = `'none'`): no list, no cockpit, no documents/income/verdicts. Its student view is the funding summary INSIDE the Payments module (§2.6). |
| D5 | Finance is org_admin-manageable: Suresh can invite Sam himself. |
| D6 | Phase 0 fix-forwards ride this run as separate small-change-lane commits. |

---

## Phase 0 — Check-up fix-forwards (3 separate commits, small-change lane)

Log each in `docs/consolidation-log.md` under Pending.

**0a. `halatuju_api/apps/scholarship/payments.py:49-54`** — `PATHWAY_PAYMENT_START_MONTH` + `_DEFAULT_PAYMENT_START_MONTH` stay in place as **documented template-superseded defaults**. Add a comment block stating: the org-owned tunable already lives on `ContractScheduleRow.start_month` (read via `_schedule_row`); these constants govern only pre-template applications and mirror the seeded rows. Mark with `# tenancy: rule-1 exemption — template-superseded fallback`. No behaviour change.

**0b. `halatuju_api/apps/scholarship/income_engine.py:2112-2113`** — `_INCOME_MATCH_TOL_FRAC` / `_INCOME_MATCH_TOL_MIN`: same treatment. Comment: advisory-only cockpit reconciliation tolerance (never a gate, non-mutating); promote to `ScholarshipCohort` fields when a second programme asks to tune it. Same tenancy marker. No behaviour change.

**0c. `docs/build-for-tenancy-conventions.md` rule 6** — add `contracts.py` `_gemini_generate` (contract-quiz generation, `contracts.py:394-407`) to the sanctioned Gemini seams list, alongside `vision.py` / `profile_engine.py`. Doc-only commit.

---

## Phase 1 — Role-matrix doc FIRST (own commit)

Edit `docs/scholarship/role-matrix.md`:

1. **Rewrite the Finance row** (drop the "*future role*" marker):
   - B40 Applications: **Payments funding summary only** (allowlist: award/paid/remaining/Vircle; NO applicant files, documents, income, verdicts) — `_b40_scope='none'`.
   - Sponsors: View all (list + detail; NO review/approve powers).
   - Administration: View-only org section + **Payments (read + finance check sign)**. Billing & usage stays future (note: platform-billing statement, separate deliverable).
   - Profile: edit. Guide/FAQ: view.
2. **Rewrite "Payments module — access"** for the conditional 3-step chain:
   - Access: read = `admin` + `org_admin` + `finance` (+ super); create/edit/cancel = `admin` + `org_admin` only. `reviewer`/`qc`/`partner` refused.
   - Chain: `draft → admin_signed → [finance_checked] → completed`. The finance step is **required iff the org has ≥1 active finance admin, evaluated live at each sign attempt** (never stored). A run at `admin_signed` when finance activates needs the finance check before countersign (`finance_check_required`); if the sole finance admin is revoked mid-run, the chain degrades to 2-step by policy (an already-collected finance signature is never a blocker).
   - **Three-distinct-signers:** all collected signatures on a run must be pairwise distinct people (email, case-insensitive). `super` may fill any ONE slot per run, never two (enforced by the same distinctness rule).
   - Editing an amount/exclusion after any signature reverts the run to draft and clears ALL collected signatures.
3. Update **Implementation state** with this sprint.

**Currency rule applies:** the Manual/FAQ changes in Phase 4 are mandatory, same sprint.

---

## Phase 2 — Backend (one commit + 2 migration files)

### 2.1 Models (`halatuju_api/apps/scholarship/models.py:1597-1651`)

- `PaymentRun.STATUS_CHOICES`: insert `('finance_checked', 'Finance checked')` between `admin_signed` and `completed` (varchar(20) — fits; choices-only for the status).
- New signature triple after `admin_signed_*`, mirroring the existing pattern:
  - `finance_signed_name = CharField(max_length=200, blank=True, default='')`
  - `finance_signed_email = CharField(max_length=254, blank=True, default='')`
  - `finance_signed_at = DateTimeField(null=True, blank=True)`
- Update the model docstring (the parked middle state is now real, conditional on activation).
- Migration `scholarship/0109` (or next number): 3 AddField + AlterField choices. **Real DDL — see §8.**

### 2.2 Role choice (`halatuju_api/apps/courses/models.py`)

- `ROLE_CHOICES` (:489-496): add `('finance', 'Finance admin')`.
- Extend the role-semantics comment block (:466-488): *finance — org finance admin: payment-run CHECKER (middle signature), payments read + funding summary (allowlist; no applicant files), Sponsors view, Administration view-only. No B40 scope, no review/QC/assignment. The chain's finance step is DORMANT until the org has ≥1 active finance admin.*
- Migration `courses/0066` (or next): **choices-only, NO DDL** — `django_migrations` row only.

### 2.3 Payments service (`halatuju_api/apps/scholarship/payments.py`)

- New predicate (never persisted, evaluated live at every sign attempt):
  ```python
  def finance_check_required(organisation):
      from apps.courses.models import PartnerAdmin
      return PartnerAdmin.objects.filter(
          owning_organisation=organisation, role='finance', is_active=True).exists()
  ```
  (Match the actual active-flag field name on PartnerAdmin — verify in the model.)
- **`sign()` rewrite (:425-467):**
  - `draft` → maker signs (role `admin` or super) → `admin_signed`. If finance is active for the org, notify finance (§2.4) instead of the org-admin countersign email.
  - `admin_signed` + finance ACTIVE → only role `finance` (or super) may sign → `finance_checked`, then notify org admins to countersign. An org_admin attempt → `PaymentsError('finance_check_required')`. A finance attempt when DORMANT → `wrong_role`.
  - `admin_signed` + finance DORMANT → approver countersigns (role `org_admin` or super) → `complete(run)` → `completed` (today's path, byte-identical).
  - `finance_checked` → approver countersigns (`org_admin` or super) → `complete(run)` → `completed`.
  - Guards kept/generalised: `bad_state`, `name_mismatch` (`_name_matches` :420), and **`same_signer` generalised to pairwise distinctness**: finance email ≠ maker email; approver email ≠ maker email AND ≠ finance email (when set). Casefolded comparison, same as today.
- `_revert_to_draft` (:378-386): editing an `admin_signed` OR `finance_checked` run reverts to `draft` and clears the maker AND finance triples.
- `set_item` (:389): editable statuses = `('draft', 'admin_signed', 'finance_checked')`.
- `cancel` (:530): allowed from `draft`/`admin_signed`/`finance_checked`. Cancel stays an admin/org_admin power.
- `complete()` unchanged except docstring.
- Module docstring: update the D2 two-person paragraph to describe the conditional third step.

### 2.4 Email (`halatuju_api/apps/scholarship/emails.py`)

- New `send_payment_finance_check_email(run)` — best-effort, mirrors `send_payment_countersign_email` (:3198): recipients = active finance admins of the run's org; reuse `_run_month_label`/`_rm_amount` and existing helpers. **No new programme-name literals (conventions rule 2)** — same wording pattern as the countersign email.
- Call-site switch in `sign()` per §2.3.

### 2.5 Admin views (`halatuju_api/apps/scholarship/views_admin.py`)

- **`_PaymentsBase._payments_admin` (:2192-2200) — read/write split:** signature becomes `def _payments_admin(self, request, roles=('admin', 'org_admin', 'finance'))`. Read+sign endpoints (List GET, Detail GET, Csv GET, Sign POST) use the default; **write endpoints (List POST create, Item PATCH, Cancel POST) pass `roles=('admin', 'org_admin')`**. The service's `wrong_role` still backstops the sign step. Regression risk: this touches all six payment views — the dormant-chain tests are the guard.
- `_payment_run_detail` (:2160-2189): add `'finance_signed': _sig(run.finance_signed_name, run.finance_signed_email, run.finance_signed_at)` and `'finance_check_required': payments.finance_check_required(run.organisation)`. **The frontend reads these fields — it must never mirror the predicate.**
- `AdminPaymentRunCsvView` (:2342-2358): allowed statuses = `('admin_signed', 'finance_checked', 'completed')` (finance must read the CSV to check it).
- `_b40_scope` (:91-106): explicit `finance → 'none'` branch + docstring line. `_can_review_app` / `_require_qc` need no code change (scope 'none' / role lists already deny) — update their docstrings to name finance.
- Sponsors: add `'finance'` to the VIEW gates at :910-912 and :937; the review gate at :952 stays super/org_admin.
- **NOT added anywhere:** `services.py:491 REVIEW_ROLES` (extend its comment instead), the assignable-staff `role__in` at :1325, QC gates. Tests must prove denial (§7).

### 2.6 Funding summary endpoint (INSIDE the payments module)

- **`AdminPaymentFundingSummaryView`** — `GET /api/v1/admin/payments/funding-summary/`. Rides `_PaymentsBase` with the default read gate (super/admin/org_admin/finance), org-fenced, **classified in `test_org_fence.py` `FENCED_OR_EXEMPT`**. Super with no org context → `no_org` 400 (same as run creation).
- Rows = own-org applications in `payments.PAYABLE_STATUSES`, serialized by a new **`FundingSummaryRowSerializer`** (`serializers_admin.py`) — **explicit allowlist by construction** (follow the `SponsorPoolCardSerializer` pattern, `serializers.py:41-141`; every field explicit, nothing passed through). Fields, exactly:
  `application_id`, `name`, `ref` (pool ref where present, else ''), `status` (coarse: awarded/active/maintenance), `pathway`, `award_amount`, `paid_to_date`, `remaining`, `vircle_id`, `last_run` (`{reference, payment_date}` of the newest completed run item, or null).
  **Excluded by decision:** NRIC, and anything document/income/verdict/contact-shaped. A snapshot test asserts the exact key set (§7).
- Payload also carries org totals for the footer: `{students, award_total, paid_total, remaining_total}`.

---

## Phase 3 — Frontend (one commit) — extend the EXISTING payments UI only

**No new pages. No Billing page. The Administration "Billing & usage" card stays disabled "Coming soon" — untouched.**

1. `src/lib/adminStaff.ts:7`: add `'finance'` to `PROGRAMME_STAFF_ROLES` + extend `src/lib/__tests__/adminStaff.test.ts`.
2. `src/app/admin/layout.tsx` (:99-111): **new `finance` nav branch → Administration / Profile / Guide / FAQ only** (no Scholarship link; finance reaches Payments via the Administration card, same as admin/org_admin today).
3. `src/app/admin/administration/page.tsx`:
   - `StaffRole`/`STAFF_ROLES` (:21-22): add `'finance'` (invite buttons grid 3 → 4; check layout).
   - Role flags (:71-75): add `isFinance`; access check (:107) admits finance.
   - Finance renders the non-manager branch: read-only staff table, cards **Sponsors / Payments** (+ the disabled Billing card, same as other org roles see it). No Sources/Contracts/Invite.
4. Payments pages:
   - `payments/page.tsx` (:24) + `payments/[id]/page.tsx` (:56): add finance to `allowed`. Hide create-run, item editing, and Cancel for finance.
   - **Run detail `[id]/page.tsx` — the third signature card:** extend the shipped maker/approver card row to three cards — "Authorised by (Maker)" → **"Checked by (Finance)"** → "Approved by (Approver)" — identical design language (green cards, serif signature name, timestamp). Rendering is driven ONLY by payload fields (`status`, `finance_signed`, `finance_check_required`) — never a local predicate:
     - finance viewer at `admin_signed` + required → the typed-name sign box in the finance card;
     - org_admin viewer at `admin_signed` + required → "Awaiting finance check" notice, countersign disabled;
     - dormant org → today's 2-card layout exactly (NO empty third card);
     - **historical completed runs with a null finance triple → 2-card layout** (no "skipped" step).
   - Known-error list (:45): add `'finance_check_required'`.
5. **Funding summary section on the Payments landing page** (`payments/page.tsx`): a table section below the runs list, existing page style — columns per §2.6 + totals footer. Student names are plain text — NO links into applicant pages. Visible to super/admin/org_admin/finance (same page gate).
6. `src/app/admin/scholarship/[id]/page.tsx` `canQc`/`canWrite` (:227/:232): **no change** (finance never reaches the page).
7. **i18n ×3 in the same commit** (`src/messages/en.json`, `ms.json`, `ta.json` — the parity guard suites in `src/messages/__tests__/` enforce): `admin.role.finance` (~en:4005-4013), `admin.administration.staffRole.finance` (~en:4282-4286), payments additions (`financeCheck` card labels, `awaitingFinanceCheck`, error copy for `finance_check_required`, funding-summary headers/totals). ms/ta = your best working translation, flagged in the retro for owner's Tamil review (per `tamil-style-guide.md`; never leave keys missing).

---

## Phase 4 — Manual/FAQ currency (one commit, EN only — NEVER machine-translate Tamil)

1. New chapter `src/content/manual/role-finance.tsx`, shaped like `role-admin-general.tsx`: what finance sees (Administration → Payments), the checker step (dormant vs active, three-distinct-signers), the funding summary, what finance can NOT do (no applicant files, no verdicts, no run creation/edit/cancel, no billing yet).
2. Extend `src/content/manual/types.ts` `ManualRole` + `Audience` unions with `'finance'`; register the chapter in `index.ts` `CHAPTERS`; `manualRole()` resolves `'finance'`. (Union extension ripples through manual tests — run them.)
3. FAQ entries in `faq.tsx` (audience `finance` + org-admin-relevant): "What can a finance admin do?"; "Why can't I countersign yet?" (the awaiting-finance-check explanation, for org admins); "Why can't finance open applicant files?".
4. **Fold in the pending carry from role-matrix.md:** the Payments module gets its Manual sections (org-admin + finance chapters) — it shipped 2026-07-16 without one.
5. Screenshots: ship labelled placeholders per the established pattern (`docs/plans/2026-07-16-manual-screenshot-manifest.md`) — add the new finance/payments screens to that manifest for the owner's pass.

---

## Phase 5 — Verify, migrate-first, single deploy

### 7. Test plan (all mandatory)

**Backend (pytest — suite currently ~3815; every gate change gets a test):**
- `test_payments.py`: dormant chain byte-identical (**existing tests pass UNMODIFIED**); inactive finance admin still dormant; activated 3-step happy path (maker → finance → approver → completed, disbursements written); org_admin blocked at `admin_signed` with `finance_check_required`; finance signing draft → `wrong_role`; finance signing when dormant → `wrong_role`; finance at `finance_checked` → refused; **in-flight activation** (run at `admin_signed`, THEN create finance admin → countersign blocked until finance checks) and **deactivation** (revoke finance at `admin_signed` → 2-step completes; at `finance_checked` → approver completes); three-distinct pairwise (maker=finance, finance=approver, maker=approver both paths → `same_signer`; super fills exactly one slot, second → `same_signer`); edit at `finance_checked` reverts to draft + clears BOTH triples; cancel at `finance_checked` ok, at completed → `bad_state`; `name_mismatch` on the finance slot.
- `test_payment_endpoints.py`: finance GET list/detail/CSV (CSV at `finance_checked`) + POST sign OK; finance POST create / PATCH item / POST cancel → 403; detail payload carries `finance_signed` + `finance_check_required`; the error code surfaces on the sign endpoint.
- `test_org_fence.py`: finance fixtures per tenant; classify `AdminPaymentFundingSummaryView` in `FENCED_OR_EXEMPT`; cross-org funding-summary/run for finance → 404/empty; the `__subclasses__` completeness test passes.
- `test_org_gates.py` / `test_org_admin_powers.py` / `test_qc_gate.py`: finance denied B40 list + app detail + verdict/QC/interview writes + sponsor review; finance NOT in assignable-admins; finance allowed sponsor list/detail.
- Funding-summary tests: **allowlist key-set snapshot** (exact keys; no nric/document/income keys); totals correctness; role gate (reviewer/qc/partner → 403); org fence.
- `apps/courses/tests/test_admin_auth.py` + `test_org_admin_role.py`: org_admin invites finance → own-org binding; org_admin resend/revoke finance; super invites finance → org #1 binding; reviewer/partner cannot invite finance.
- `test_interview_scheduling.py:279` drift tuple: add `'finance'`.

**Frontend (jest — suite currently ~552):** i18n parity ×3; `adminStaff` finance classification; manual registry + `manualRole('finance')` + FAQ audience filter; nav branch if covered.

### 8. Migrate-first runbook (STRICT ORDER)

1. **DDL via Supabase MCP** (`apply_migration`, project `pbrrlyoyyiftckqvzvvo`) — safe while old code runs:
   ```sql
   ALTER TABLE payment_runs
     ADD COLUMN finance_signed_name  varchar(200) NOT NULL DEFAULT '',
     ADD COLUMN finance_signed_email varchar(254) NOT NULL DEFAULT '',
     ADD COLUMN finance_signed_at    timestamptz NULL;
   ```
   Pre-check first: if the columns already exist (double-run), abort DDL and verify state instead.
2. **Record BOTH migrations** as applied (`django_migrations` rows): `courses/00XX` (choices-only — row only, no DDL) + `scholarship/01XX` (the DDL above).
3. **ONE push = ONE deploy.** Verify the build by SHORT_SHA (`gcloud builds list --project gen-lang-client-0871147736 --account tamiliam@gmail.com`). Keep the second deploy slot for a hotfix only.

### Close-out

- `CHANGELOG.md` under a "Sprint 14 — Finance role (dormant checker) + payments funding summary" heading (incl. the three Phase-0 entries).
- Retrospective `docs/retrospective-2026-07-23-sprint14-finance-role.md` (flag ms/ta strings for owner's Tamil review; add new screens to the screenshot manifest).
- Run `python Settings/_tools/wat_lint.py` at close; follow `Settings/_workflows/sprint-close.md`; update the project CLAUDE.md Next Sprint section.
- Delete any scratch files.

### Rollout (OWNER steps — record in the retro, do not perform)

Deploy ships the role **dark** (no finance admin exists → production chain unchanged). Then Suresh (org_admin) or the owner invites Sam via Administration → Invite staff → Finance. The moment Sam's account is active, the checker step arms for BrightPath — **including any run then sitting at `admin_signed`** (deliberate; the FAQ explains the "awaiting finance check" notice).

---

## Risks / edge cases (build with these in mind)

1. In-flight run at activation — org_admin blocked mid-run: deliberate; error code + UI notice + FAQ.
2. Sole-finance revocation mid-run silently degrades to 2-step — policy, stated in the matrix.
3. Historical completed runs have empty finance triples → serializer emits `finance_signed: null` → FE renders the 2-card historical layout.
4. `_payments_admin` signature change touches six views — dormant-chain regression tests are the guard.
5. The frontend must NEVER mirror the activation predicate — read `finance_check_required` from the payload (same principle as `earliest_payment_date`).
6. New email must not introduce programme-name literals (conventions rule 2).
7. The funding summary must never link into applicant pages — names are plain text (finance has no B40 routes anyway; don't create dead links for admin/org_admin either, keep it consistent).
