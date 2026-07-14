# Tenancy Audit — HalaTuju Multi-Tenant Platform (Route A)

**Date:** 2026-07-14
**Author:** Research analyst (read-only engagement)
**Status:** Draft for architect + owner review. Nothing here was built, changed, or deployed.
**Companion documents:** `2026-07-14-platform-prd-draft.md` (what to build), `2026-07-14-platform-roadmap-draft.md` (in what order).

---

## How to read this document

This is an **evidence inventory**, not a plan. It answers one question: *given the code as it stands today, what is platform-level (shared, run by tamiliam), what is tenant-level (owned by one organisation's programme), and where is BrightPath welded in so tightly that pulling the two apart will hurt?*

- Every claim about the code carries a `file:line` citation so the architect can check it. Where I reasoned rather than read, I wrote **INFERRED**.
- Where a genuine choice belongs to the owner, I wrote **DECISION NEEDED** with options and a recommendation — I did not decide it.
- A **"Could not verify"** list closes each section. An honest gap is better than a confident guess.
- Citations are relative to `Production/HalaTuju/` (the Django code lives under `halatuju_api/`, the web app under `halatuju-web/`).

**The one finding that shapes everything else:** the Django backend connects to Postgres as the `postgres` **superuser, which bypasses Supabase Row-Level Security entirely** (`halatuju_api/docs/incident-001-rls-disabled.md:41,74`). RLS only guards *direct* access with the public anon key; it does **not** police what the API itself can read. So tenant isolation — the walls between organisations — **must be enforced in Django query code**, not left to the database. Keep this in mind through the whole audit; it is why the #1 risk in the roadmap is "one org sees another's applicants".

---

## Section 1 — Model inventory

Every Django model in the three apps, with a proposed tenancy **scope**:

- **PLATFORM** — shared base, owned by the platform superadmin; every tenant sees/uses the same rows (e.g. the course catalogue).
- **TENANT** — belongs to one organisation's programme; must be fenced so org A never sees org B's rows.
- **SHARED-CONFIG** — a configuration record that *becomes* per-tenant (one row per programme) rather than a global singleton.
- **UNCLEAR** — genuinely ambiguous; flagged as a DECISION NEEDED below.

### 1a. `apps/courses` (the platform base)

| Model | file:line | Proposed scope | Why |
|---|---|---|---|
| `FieldTaxonomy` | `courses/models.py:16` | PLATFORM | Canonical field/discipline classification; shared across all courses and programmes. |
| `Course` | `courses/models.py:53` | PLATFORM | The SPM course catalogue. Base product. |
| `MascoOccupation` | `courses/models.py:99` | PLATFORM | National occupation codes. |
| `CourseRequirement` | `courses/models.py:118` | PLATFORM | Eligibility rules per course; feeds the startup engine. |
| `CourseTag` | `courses/models.py:258` | PLATFORM | Course fit-scoring dimensions. |
| `Institution` | `courses/models.py:315` | PLATFORM | Institution catalogue. |
| `CourseInstitution` | `courses/models.py:359` | PLATFORM | Which course is offered where. |
| `StpmCourse` / `StpmRequirement` | `courses/models.py:807,886` | PLATFORM | STPM degree catalogue + requirements. |
| `CourseDataStatus` | `courses/models.py:952` | PLATFORM | Course-data dashboard freshness. |
| `PartnerOrganisation` | `courses/models.py:397` | **SHARED-CONFIG → the tenant seed** | Today: a referral-source registry (`code`, `name`, `contact_email`). This is the closest existing thing to a "tenant/organisation" record and is the natural spine of the org layer — but today it governs almost nothing (see §3). |
| `PartnerAdmin` | `courses/models.py:415` | **UNCLEAR / SHARED** | One row is simultaneously a *course-data admin* AND a *scholarship reviewer/QC/partner*. Roles: super/admin/partner/reviewer/qc (`courses/models.py:431-451`). This dual identity is coupling hot-spot #3. |
| `StudentProfile` | `courses/models.py:470` | **PLATFORM (but overloaded)** | The shared student account (PK = Supabase UID, `courses/models.py:483`). BUT it also carries scholarship means-test + family + pathway data (`household_income`, `receives_str`, the full family roster, `chosen_pathway`; `courses/models.py:537-582`). Platform-scoped *identity* welded to tenant-scoped *application data* — hot-spot #1. |
| `EmailVerification` | `courses/models.py:671` | PLATFORM | Contact-email verification tokens. |
| `SavedCourse` | `courses/models.py:694` | PLATFORM | Student's bookmarked courses. |
| `AdmissionOutcome` | `courses/models.py:759` | PLATFORM | Longitudinal admission tracking. |

### 1b. `apps/reports`

| Model | file:line | Proposed scope | Why |
|---|---|---|---|
| `GeneratedReport` | `reports/models.py:7` | PLATFORM | AI career-counsellor report for the course selector. FK → `courses.StudentProfile` (`reports/models.py:11`). Grep confirms this app has **no** reference to `scholarship` — cleanly decoupled from the programme (Could-not-verify item retained). |

### 1c. `apps/scholarship` (BrightPath — becomes tenant #1)

Unless noted, scope = **TENANT** (belongs to one programme, must be org-fenced).

| Model | file:line | Scope | Notes / cross-boundary FKs |
|---|---|---|---|
| `ScholarshipCohort` | `scholarship/models.py:14` | **SHARED-CONFIG → per-tenant** | Holds the tunable thresholds + funding params (`min_spm_a_count`, `income_ceiling`, delays; `scholarship/models.py:37-86`). This record IS the programme configuration surface (see §2). Needs an owning-org. |
| `ScholarshipApplication` | `scholarship/models.py:99` | TENANT (root entity) | **FK `profile` → `courses.StudentProfile`** (`scholarship/models.py:142`) — the primary fence line. **FK `assigned_to` → `courses.PartnerAdmin`** (`scholarship/models.py:539`). **Has no org column today.** |
| `FundingNeed` | `scholarship/models.py:778` | TENANT | OneToOne → application. |
| `ApplicantDocument` | `scholarship/models.py:812` | TENANT (most sensitive PII) | ID/income scans. Doc catalogue is a hard-coded enum (`scholarship/models.py:816-854`). |
| `Referee` | `scholarship/models.py:954` | TENANT | |
| `Consent` | `scholarship/models.py:977` | TENANT | PDPA consent artefact; version + text are programme-specific. |
| `OnboardingResponse` | `scholarship/models.py:1026` | TENANT | |
| `SponsorProfile` | `scholarship/models.py:1051` | TENANT | AI-drafted sponsor-facing profile (named + anonymised). |
| `InterviewSession` | `scholarship/models.py:1107` | TENANT | **FK `interviewer` → `courses.PartnerAdmin`** (`:1122`). |
| `InterviewSlot` | `scholarship/models.py:1147` | TENANT | **FK `reviewer` → `courses.PartnerAdmin`** (`:1160`). |
| `InterviewMessage` | `scholarship/models.py:1178` | TENANT | |
| `DecisionReopen` | `scholarship/models.py:1201` | TENANT | **FK `reviewer` → `courses.PartnerAdmin`** (`:1222`). |
| `Sponsor` | `scholarship/models.py:1247` | **UNCLEAR** | A sponsor account. Could sponsor students across *several* programmes → platform-level; or belong to one org's pool → tenant-level. **DECISION NEEDED (D-1).** |
| `Donation` | `scholarship/models.py:1312` | TENANT/UNCLEAR | Follows the Sponsor decision. Money into myNADI. |
| `Sponsorship` | `scholarship/models.py:1334` | TENANT | Sponsor→student allocation. |
| `Disbursement` | `scholarship/models.py:1397` | TENANT | Money-out ledger (mock until toyyibPay, TD-075). |
| `BankAccount` | `scholarship/models.py:1456` | TENANT (financial PII) | Its own table + RLS by design. |
| `ResolutionItem` | `scholarship/models.py:1498` | TENANT | The action queue (Check-2). |
| `ReviewerProfile` | `scholarship/models.py:1586` | **UNCLEAR** | OneToOne → `courses.PartnerAdmin` (`:1597`); reviewer credentials/PII. A reviewer identity may be cross-tenant. Follows the role-split decision (D-2). |
| `AssignmentEvent` | `scholarship/models.py:1630` | TENANT | **FKs `from/to_admin` → `courses.PartnerAdmin`** (`:1642,1646`). |
| `SemesterResult` | `scholarship/models.py:1663` | TENANT | In-programme progress. |
| `GraduationMessage` | `scholarship/models.py:1701` | TENANT | |
| `SponsorReferral` | `scholarship/models.py:1744` | TENANT/UNCLEAR | Follows the Sponsor decision. |
| `TrustContent` | `scholarship/models.py:1781` | **SHARED-CONFIG → per-tenant** | Editable "who we are / governance / funds" content. Today a single active row (`:1808-1809`); becomes one per programme. |
| `StandingGift` | `scholarship/models.py:1820` | TENANT/UNCLEAR | Follows the Sponsor decision. |
| `WhatsAppMessage` | `scholarship/models.py:1855` | TENANT | Outbound comms audit log. |
| `BursaryAgreement` | `scholarship/models.py:1890` | TENANT | **FK `witness_org` → `courses.PartnerOrganisation`** (`:1943`). Foundation signatory from settings. |

### 1d. Foreign keys that cross the proposed platform↔tenant fence

These are the **future fence lines** — the FKs a tenant boundary would have to reason about:

| From (tenant) | → To (platform) | file:line | Fence implication |
|---|---|---|---|
| `ScholarshipApplication.profile` | `courses.StudentProfile` | `scholarship/models.py:142` | **The critical one.** One student, one profile, many programmes. This FK must stay (shared account) — the fence must live *around* it (an org column on the application), not by cutting it. |
| `ScholarshipApplication.assigned_to` | `courses.PartnerAdmin` | `scholarship/models.py:539` | Reviewer identity is a platform admin record. Org-scope must attach to the *assignment*, not the person. |
| `InterviewSession.interviewer` | `courses.PartnerAdmin` | `:1122` | ditto |
| `InterviewSlot.reviewer` | `courses.PartnerAdmin` | `:1160` | ditto |
| `DecisionReopen.reviewer` | `courses.PartnerAdmin` | `:1222` | ditto |
| `AssignmentEvent.from/to_admin` | `courses.PartnerAdmin` | `:1642,1646` | ditto |
| `ReviewerProfile.partner_admin` | `courses.PartnerAdmin` | `:1597` | ditto |
| `BursaryAgreement.witness_org` | `courses.PartnerOrganisation` | `:1943` | Already org-aware; a good precedent. |
| `GeneratedReport.student` | `courses.StudentProfile` | `reports/models.py:11` | Platform-internal (reports is platform); no tenant crossing. |

**Section-1 takeaway (plain language):** The scholarship app is already a mostly-self-contained programme, *except* that (a) it hangs off the shared `StudentProfile`, (b) its reviewers ARE the platform's admins, and (c) **it has no notion of "which organisation owns this application"** — the single biggest missing piece. Adding that owning-org is the spine of the whole refactor.

### Could not verify (Section 1)
- Whether `apps/reports` shares anything with scholarship beyond `StudentProfile` — grep found no `scholarship` references, but I did not read every reports view.
- The live Supabase RLS policy text per table (managed in the dashboard, not in the repo).

---

## Section 2 — Hard-coded BrightPath inventory

Where BrightPath-specific behaviour lives in **code** rather than **data**. For each, a disposition:
**PER-ORG SETTING** (make it tenant config) · **SHARED ENGINE, ORG-SELECTABLE** (the logic stays one shared service; the tenant only *chooses* whether/how it applies) · **STAYS FIXED** (national/statutory — same for everyone).

### 2a. Eligibility rules & thresholds

**Good news first:** the headline B40 numbers are **already data**, on `ScholarshipCohort`:
- Academic floor + income ceilings: `min_spm_a_count`=4, `min_spm_bplus_count`=5, `min_stpm_pngk`=2.9, `income_ceiling`=RM5,860, `per_capita_ceiling`=1584 (`scholarship/models.py:37-57`). The shortlisting engine reads them from the cohort (`scholarship/shortlisting.py:57-104`). → **PER-ORG SETTING** (the cohort record becomes the per-programme config).

**But several rule constants are still baked in code:**

| Item | file:line | What it does | Disposition |
|---|---|---|---|
| SPM grade bands `A_GRADES`, `STRONG_GRADES` | `scholarship/shortlisting.py:25-27` | Maps grades → "A"/"strong" | STAYS FIXED (national grade vocabulary) |
| Hard eligibility gates: consent, `intends_tertiary_2026`, IPTS-excluded | `scholarship/shortlisting.py:111-116` | Programme scope = public study only | SHARED ENGINE, ORG-SELECTABLE (another programme might allow IPTS) |
| `_HEADROOM_THIN_RM = 1584.0` | `scholarship/income_engine.py:1274` | Salary-route yardstick — a **duplicated** copy of the per-capita ceiling, hard-coded | PER-ORG SETTING (bug-risk: should derive from cohort, not a second constant) |
| `SGD_TO_MYR_RATE` (default 3.15) | `settings/base.py:133`, `income_engine.py:1175` | FX for cross-border payslips | STAYS FIXED (shared platform util; env-tunable) |
| STR approval/rejection vocab, EPF rates 11/13%, `_EPF_CONTRIB_RATE=0.24` | `income_engine.py:621-645, 810, 905-934` | Malaysian government-document + statutory semantics | STAYS FIXED (national) |
| Utility per-capita proxy `_UTILITY_B40_CEILING=40`, `_HIGH_FLOOR=60` | `income_engine.py:1443-1444` | Soft officer signals (RM/capita) | PER-ORG SETTING (soft; currently baked) |
| The four-fact verdict (identity/academic/income/pathway) | `verdict_engine.py:1072-1085` (`build_verdict`) | The verification synthesis | **SHARED ENGINE** — the engine stays one platform service; *which facts a programme requires* is the org-selectable part (see PRD §"verification engine") |
| Genuineness ladder bands/steps | `verdict_engine.py:904-1015` | Document-genuineness scoring | SHARED ENGINE (Malaysian doc models; reusable across programmes) |

### 2b. Required-document checklists

| Item | file:line | What it does | Disposition |
|---|---|---|---|
| `income_requirements(application)` | `income_engine.py:1884-1920` | THE checklist generator — per income route (STR/salary), returns compulsory/optional doc lists. **Pure code.** | **SHARED ENGINE, ORG-SELECTABLE** — the *engine* computes requirements; each programme should choose which routes/docs it uses |
| `ApplicantDocument.DOC_TYPES` (21 types) | `scholarship/models.py:816-854` | The fixed enum of every uploadable doc | ORG-SELECTABLE catalogue (baked as model `choices`; a data-driven registry would let a programme enable a subset) |
| `income_doc_blockers`, `application_completeness`, `document_red_blockers` | `services.py:1634-1683, 1391-1450, 1783-1822` | Submission gates driven by the checklist | SHARED ENGINE (fed by the org-selectable checklist) |
| Doc-processing frozensets (`BILL_DOC_TYPES`, `RELATIONSHIP_DOC_TYPES`, `GEMINI_EXTRACT_DOC_TYPES`…) | `views.py:679-744`, `vision.py:1136`, `income_engine.py:2133` | How each doc-type is OCR'd/deduped | SHARED ENGINE (keyed to the doc catalogue) |

### 2c. Application windows / intake gating / reminders

| Item | file:line | What it does | Disposition |
|---|---|---|---|
| `ScholarshipCohort.is_open/is_active/year` | `scholarship/models.py:28-32` | Intake open/close | PER-ORG SETTING (already data) |
| `success_delay_hours`, `decline_delay_hours`, `query_response_sla_days` | `scholarship/models.py:67-86` | Decision-reveal + query SLA timing | PER-ORG SETTING (already data) |
| `REMINDER_THRESHOLDS_DAYS=(2,9,23,53)`, `FINAL_REMINDER_GRACE_DAYS=5` | `services.py:342-343` | Completion-reminder cadence + auto-close — **hard-coded, NOT per cohort** | PER-ORG SETTING (should be cohort config) |
| `CONSENT_VERSION`, `SPONSOR_CONSENT_VERSION` | `services.py:1993`, `views_sponsor.py:39` | Consent artefact version | PER-ORG SETTING (each programme's consent text differs) |

### 2d. Programme name / branding / funding constants (backend)

| Item | file:line | What it does | Disposition |
|---|---|---|---|
| App `verbose_name='B40 Assistance Programme'` | `scholarship/apps.py:8` | Django app label | STAYS FIXED (code identity); the *user-facing* name must be per-org |
| "BrightPath Bursary" + team sign-offs (`_REVIEWER_SIGNOFF`, ~40 hits across en/ms/ta) | `emails.py:429-1035, 1587` | Programme name baked into every email, all 3 languages | **PER-ORG SETTING** |
| Branded HTML shell (`_html_email_shell`: card, blue `#2563eb`, Arial, logo) | `emails.py:2032-2060` | Visual email identity | PER-ORG SETTING |
| "Cikgu Gopal" AI-coach persona | `emails.py:1148-1166`, `help_engine.py`, `verdict_narrative.py` | Student-facing helper persona name | PER-ORG SETTING |
| `SUPPORT_EMAIL='help@halatuju.xyz'` + aliases (`interview@`, `sponsor@`) | `emails.py:16-20, 1150` | Sender/reply-to identities | PER-ORG SETTING |
| Award sizing `_STPM_AMOUNT`=RM3,000, `_CONTINUING`=RM1,000, `_DEFAULT`=RM2,000, `ALLOWED_AMOUNTS` | `award.py:30-78` | Fixed per-pathway bursary amounts — **hard-coded, not cohort config** | PER-ORG SETTING |
| Funding estimate `PATHWAY_ESTIMATES` (RM/month × months per pathway) | `funding_estimate.py:24-156` | Per-programme cost model | PER-ORG SETTING |
| `anomaly_engine` RM3,000 device / JKM>RM3,000 rules | `anomaly_engine.py:159-164, 273` | Hard-coded RM3,000 in flag rules | PER-ORG SETTING |

**Frontend branding (from the web audit):** the programme name "BrightPath Bursary" is baked into i18n string *values* (no `{programmeName}` variable) in `halatuju-web/src/messages/{en,ms,ta}.json` (4024 lines each) — e.g. `en.json:414` (`"b40Heading":"BrightPath Bursary"`), `:720` (nav), `:258` ("Your BrightPath balance"), `:1562-1563` (inside the legal *consent* text), `:1245,1873` (Cikgu Gopal). It is ALSO hard-coded as JSX literals on the legal pages (`terms/page.tsx:52,55`; `privacy/page.tsx:21,29,42`). One global Tailwind theme (`tailwind.config.ts:12-27`, `primary:#137fec`), one logo (`AppHeader.tsx:78`, `/logo-icon.png`), one API host (`lib/api.ts:5`) — no per-tenant parameterisation anywhere.

**Section-2 takeaway (plain language):** roughly half of BrightPath's "policy" is already data on the cohort record (income/academic thresholds, timing). The other half — the document checklist logic, the branding/name/persona, the funding amounts, and a few stray threshold constants — is baked into code and must be lifted into per-org configuration. The **verification maths itself (genuineness, STR, EPF) should stay one shared engine** — it encodes Malaysian document reality, not one org's policy.

### Could not verify (Section 2)
- `family.py` occupation taxonomies (`NON_EARNING`, `INFORMAL_OCC`, `BENEFIT_OCC`, `DECIDED_STATUSES`) — referenced widely; appear to be hard-coded module constants but were not read in full.
- Whether `award.py`/`funding_estimate.py` amounts are ever overridden by cohort config anywhere — high-confidence "no" but not exhaustively searched.
- The full bodies of `application_completeness` / `document_red_blockers` (which parts hard-gate vs soft).

---

## Section 3 — Identity & access map

### How roles work today
- **Auth pipeline:** two custom middlewares — `SupabaseAuthMiddleware` then `NricGateMiddleware` (`settings/base.py:43-44`). The JWT is verified dual-algorithm: HS256 via the shared secret, ES256/RS256 via JWKS from Supabase, with the algorithm pinned to prevent confusion attacks and audience pinned to `'authenticated'` (`halatuju/middleware/supabase_auth.py:56-84`). Identity is set as `request.user_id = payload['sub']` (`:91`). Auth is **non-blocking** — bad tokens fall through anonymous; enforcement is per-view (`:39,102-108`).
- **Where roles live:** admin roles on `courses.PartnerAdmin.role` ∈ {super, admin, partner, reviewer, qc} (`courses/models.py:431-451`), with an `org` FK (null for super, `:442-446`). Sponsor role on `scholarship.Sponsor.status` (`scholarship/models.py:1256`). Student identity = `StudentProfile` keyed by Supabase UID (PK, `courses/models.py:483`). All three account types key off the same Supabase UID space, distinguished by which table the UID appears in.
- **How roles resolve per request:** `PartnerAdminMixin.get_admin` — fast path by UID, fallback by **verified** email (an unverified-email JWT cannot claim an admin row) (`courses/views_admin.py:46-68`). `SponsorMixin.get_sponsor` by UID (`views_sponsor.py:46-50`).
- **NRIC gate:** students must have a `StudentProfile.nric` or get `403 nric_required` (`supabase_auth.py:209-224`); it whitelists `/api/v1/admin/` and `/api/v1/sponsor/` entirely (`:168-177`) — so the whole admin + sponsor surface bypasses it.

### The decisive finding: application visibility is GLOBAL by role, not by organisation
The scholarship admin API authorises through a shared base `_AdminBase(PartnerAdminMixin, APIView)` (`scholarship/views_admin.py:63`). Its scope function `_b40_scope` returns:
- `'all'` for **super + admin + qc** → they see **every application, across every referring organisation**,
- `'assigned'` for **reviewer** → only apps where `assigned_to_id == admin.id`,
- `'none'` for partner (`scholarship/views_admin.py:89-103`).

The list query narrows **only** by `assigned_to` (`views_admin.py:186-189`). The referring-org value is used only as an *optional user filter* (`?source=` → `profile__referral_source`, `:192,207-208`) and a sort key — **never an enforced scope**. The class docstring says it plainly: *"Reuses the existing PartnerAdmin auth (super admin sees all)"* (`views_admin.py:4`).

**So there is no organisation wall on scholarship applications today.** Two organisations' reviewers, if both were `admin`/`qc`, would see each other's applicants. This is the gap the tenancy work closes.

**A template already exists on the courses side:** the Students directory *is* org-scoped for the `partner` role — `get_partner_students` filters `StudentProfile.objects.filter(referred_by_org=admin.org)` (`courses/views_admin.py:80-104`). The scholarship queryset needs the same `admin.org` predicate — but keyed off a durable org column on the application, not the nullable referral marker.

### What org-scoping would have to attach to (INFERRED)
1. **A real owning-org FK on `ScholarshipApplication`** (today it has none; only the severable `StudentProfile.referred_by_org`, `SET_NULL`/nullable, `courses/models.py:644-647` — an attribution marker, too weak to be a security boundary).
2. **The `_AdminBase` gates**, all in `scholarship/views_admin.py`: `_b40_scope` (`:89-103`), `_scoped_application` (`:105-119`), `_can_review_app` (`:121-132`), `_require_app_write` (`:134-148`), `_require_qc` (`:150-175`). Because they are centralised, adding an org predicate here propagates to the ~25 admin endpoints noted in project history.
3. **The list query** at `views_admin.py:186-189` — the single most important line to fence.

### Invites & provisioning
- Admin/reviewer invite: `AdminInviteView` (super-only) issues a Supabase Auth invite via the Admin API with the **service-role key** and creates the `PartnerAdmin` row; `org` is attached **only for the `partner` role** (`courses/views_admin.py:352-461`, esp. `:379-398`).
- Sponsor: self-registers via Supabase Auth then `SponsorRegisterView` creates a `pending` `Sponsor` requiring name+phone+source+PDPA consent (`views_sponsor.py:59-120`); an admin vets it.

### Could not verify (Section 3)
- The full list of endpoints inheriting `_AdminBase` (history says "25 + 2 special") — verified the base gates and the list view, not each endpoint line-by-line.
- Whether the sponsor pool (`pool.py`) applies any org partition — the `Sponsor` docstring implies a single global anonymous pool (`scholarship/models.py:1252-1254`); not read in full.

---

## Section 4 — Storage & documents map

- **One private bucket, one key scheme.** `BUCKET = 'b40-documents'` is a single module-level constant threaded through every storage helper (`scholarship/storage.py:21`). Object keys are `f"{app.id}/{doc_type}/{uuid4().hex}"`, generated once server-side (`scholarship/views.py:666`) and stored on `ApplicantDocument.storage_path` (`scholarship/models.py:887`). **There is no org/tenant element in the path today** — confirmed. Bursary-agreement PDFs share the same bucket (`scholarship/models.py:1958`).
- **Bytes bypass Django for user delivery** (browser PUTs directly to Supabase via a signed upload URL, `storage.py:55-59`; views the object via a 1-hour signed download URL, `storage.py:62-66`, generated lazily in `ApplicantDocumentSerializer.get_download_url`, `serializers.py:692-694`). Bytes *do* pass through Django for two server-side paths only: the GCS backup (`storage.py:139-159`) and OCR/HEIC (`vision.py:729-744`).
- **Access control is Django-only.** Every storage call authenticates with the Supabase **service-role key** (`storage.py:28-29`), which bypasses Storage RLS entirely. The bucket is private and the tables are deny-all to the anon key, so isolation rests entirely on (a) Django scoping the `ApplicantDocument` query before signing a URL, and (b) the key never leaving the backend (`docs/security-posture.md:20-22`).

### What per-org document fencing would require (INFERRED)
1. **Add an org element to the key** — `<org_id>/<app_id>/<doc_type>/<uuid>`. This is a one-line change at the single generation site (`views.py:666`), but `storage_path` is the join key used by backup, delete, OCR and download, so existing objects need migration or a dual-read shim. The column is `CharField(500)` so length is fine (`models.py:887`).
2. **Prefer prefix-per-org over bucket-per-org** — the bucket name is one constant threaded through ~8 functions; a prefix scheme composes with the existing `list_objects(prefix=…)` and the backup walk with minimal change; bucket-per-org would force `BUCKET` to become a per-request parameter everywhere.
3. **Storage RLS can't fence tenants while the service-role key is used** (it bypasses RLS). True storage-layer fencing needs either org-scoped JWTs to Storage with prefix-keyed policies, OR — the lower-risk path — keep the service-role key and make **Django the sole fence** with an org column on the application/document plus a "this `storage_path` starts with the caller's org prefix" assertion before signing.
4. **Signed URLs are implicitly org-scoped if the query is** — they are generated only after Django loads the specific row; the risk surface is any code path that signs a `storage_path` without first re-checking org ownership (`serializers.py:692-694` trusts the row was already authorised).
5. **Backup + OCR byte paths must carry the org prefix too**, or they become a cross-tenant leak in backup/restore.

### Could not verify (Section 4)
- Live `storage.objects` RLS policy text (dashboard-managed; the repo has no `supabase/config.toml` for storage).
- Whether any partner scope already reaches documents today (none found).

---

## Section 5 — External-service map

Every third-party integration is **single-tenant** today: one account/key set from one flat set of env vars, no per-org namespacing. For each: what per-tenant attribution/separation would need.

| Service | What it does / where | Keyed today | Hard-coded identity? | Per-tenant separation (INFERRED) |
|---|---|---|---|---|
| **Brevo email** | All transactional mail via Django SMTP → Brevo (`settings/production.py:102-108`); 2,684-line `emails.py` with `_send_html`/`_send_bilingual`/`_send_plain`. | `EMAIL_HOST_*`, `DEFAULT_FROM_EMAIL`, `FRONTEND_URL`; sender aliases are module constants (`emails.py:16-20`). | YES — programme name, team sign-offs, HTML shell, logo, `help@halatuju.xyz`, `https://halatuju.xyz` all baked (`emails.py:429-1035, 2032-2060`). | Per-org sender domain + SMTP creds (or Brevo sub-account), a per-tenant sender-identity config replacing the 6 alias constants, per-tenant programme name/logo/colour/support-email/`FRONTEND_URL` injected into templates. **Cost metering impossible per-tenant** while one account sends everything → tag every send with a tenant id. |
| **Supabase Auth email** (invite/reset) | Uses Supabase Auth's **own** Brevo SMTP configured in the dashboard, NOT these env vars (project memory `halatuju_supabase_smtp.md`). | Dashboard config | n/a (external) | Per-tenant sender identity would need per-project or per-template Supabase config — outside this codebase. |
| **Gemini + OpenAI** | AI OCR/extraction/genuineness (`vision.py:1469-1512`), sponsor profile prose (`profile_engine.py:243-261`), doc-help (`help_engine.py:544,597`), verdict summary (`verdict_narrative.py:158`), course reports + OpenAI fallback (`report_engine.py:331,367`). | Single shared `GEMINI_API_KEY`/`OPENAI_API_KEY` (`settings/base.py:121-122`); model names literal per module. | No branding; single shared key. | **No cost attribution today.** Per-org metering needs per-tenant keys OR a usage-logging wrapper around the two seams recording `(tenant, model, tokens)`. `GeneratedReport.model_used` records model only, not tenant/tokens (`reports/models.py:31`). |
| **Twilio** (WhatsApp + Verify) | Outbound WhatsApp + OTP via REST (`whatsapp.py`); reminders (`send_interview_reminders.py:79-88`), propose-slot nudge (`scheduling.py:146,162`). | `TWILIO_ACCOUNT_SID/AUTH_TOKEN/WHATSAPP_FROM`, template SIDs, Verify SID (`settings/base.py:153-187`); MY country code `'60'` + sandbox number literal (`whatsapp.py:37,41`). | One account/number/template set for all; MY-CC baked. | Per-org Twilio sub-account or approved sender number + per-brand Meta template SIDs; tag `WhatsAppMessage` rows with tenant for billing; the `'60'` assumption breaks for a non-MY tenant. |
| **Vircle eWallet** (payout) | Manual relay-sheet handoff (no API): email → student confirms → Google Sheet → Vircle acts (`vircle.py:1-14`, `sheets.py`). Dark (`VIRCLE_SETUP_ENABLED`). | `VIRCLE_*` (`settings/base.py:208-218`); rides the Meet Workspace SA. | Programme name in the install email + guide PDF filename. | MY-specific; needs a pluggable payout provider per org, or per-org Vircle merchant + relay sheet in that org's Drive. |
| **Google Workspace** (Meet/Calendar/Drive/Sheets) | Interview Meet/calendar (`meeting.py:102-154`) + Vircle relay sheet (`sheets.py:138`). | ONE service account with domain-wide delegation impersonating `MEET_ORGANISER_EMAIL` (`info@halatuju.xyz`); `GOOGLE_MEET_SA_JSON` env (`settings/base.py:293-303`). | Organiser mailbox + ICS `PRODID`/UID baked. | Per-org Workspace domain + its own delegated SA + organiser mailbox; today all interviews/sheets land in the one HalaTuju Workspace. |
| **Supabase Storage/Postgres/Auth** | Document vault + DB + auth. | `SUPABASE_URL/JWT_SECRET/SERVICE_ROLE_KEY`, one DB project `pbrrlyoyyiftckqvzvvo`. | One bucket, one project. | See Section 4. |
| **Google Cloud Vision** (raw OCR) | `vision.py:643-672`, `document_text_detection`. | `GOOGLE_CLOUD_VISION_API_KEY` if set, else ADC/runtime SA. Billable. | One project. | Per-tenant cost tagging; no per-org isolation needed (read-only OCR). |
| **GCS backup bucket** | Mirrors the doc bucket (`backup_documents.py`). | `DOCUMENT_BACKUP_BUCKET` + ADC. | One destination. | Org prefix must flow into the backup path (see §4). |
| **toyyibPay** | Payment gateway — **not integrated, mocked/deferred (TD-075)** (`disbursement.py:5`, `models.py:1313,1442`). | none (mock) | n/a | Real per-org merchant accounts when built. |
| **Sentry** | Error monitoring (`production.py:81`). | one DSN | one project | Tenant tag on events (optional). |

### Cost-attribution points (for per-tenant metering)
Every billable call site — none tenant-tagged today: Gemini JSON/vision `vision.py:1490,1512`; Gemini prose `profile_engine.py:261,919,967`; doc-help `help_engine.py:544,597`; verdict summary `verdict_narrative.py:158`; report `report_engine.py:331`; OpenAI fallback `report_engine.py:367`; Cloud Vision `vision.py:646,672`; Twilio WhatsApp `whatsapp.py:224`; Twilio Verify `whatsapp.py:112,140`; Brevo — every `_send*` helper (`emails.py:357,1992`). The only per-call audit records are `GeneratedReport.model_used` and `WhatsAppMessage` rows; neither carries a tenant id or token count.

### Could not verify (Section 5)
- Actual live env values / which flags are set in prod (repo doesn't hold them; history says verify with `gcloud run services describe`).
- `GOOGLE_CLOUD_VISION_API_KEY` is read via `getattr` but not defined in settings I read → prod almost certainly runs on ADC.
- Whether the shared Brevo account already tags sends per stream (not determinable from code).

---

## Section 6 — Coupling hot-spots (ranked, 1 = hardest to fence)

| # | What | Evidence | Why it hurts |
|---|---|---|---|
| **1** | **`StudentProfile` is a shared god-model holding BOTH course-selector AND scholarship data** | `courses/models.py:531-624` (household income/size, `receives_str/jkm`, full family roster, pathway block — comments say "mirrors ScholarshipApplication") | The programme's most sensitive means-test + family PII lives on the *platform* model. Shortlisting reads it as "single source of truth" (`shortlisting.py:5`). Fencing means one table two domains write, with two-way sync already in the comments. |
| **2** | **`ScholarshipApplication.profile` → `courses.StudentProfile`** | `scholarship/models.py:142` | The tenant root points into the platform base; every verdict/income/shortlist read chases `application.profile.*`. Must stay (shared account) — fence around it, don't cut it. |
| **3** | **`courses.PartnerAdmin` is the reviewer/QC/assignee — ~7 cross-app FKs** | `scholarship/models.py:539,1122,1160,1222,1642,1646,1597` | One identity carries "course catalogue admin" AND "bursary reviewer/QC". Splitting per-tenant touches every admin endpoint. |
| **4** | **Scholarship admin API authorises through the platform's `PartnerAdminMixin`** | `scholarship/views_admin.py:18-20,63` (`from apps.courses.views_admin import PartnerAdminMixin`, `_fetch_auth_data`, `apply_people_search`) | The whole reviewer permission model is platform code — no clean seam; this is where org-scoping must be inserted. |
| **5** | **Reverse coupling: `courses.views` reaches INTO scholarship at request time** | `courses/views.py:1040-1056,1170-1179,1495,1539` (imports `ScholarshipApplication`, `ApplicantDocument`, `scholarship.vision`, `scholarship.family.DECIDED_STATUSES`, `scholarship.whatsapp`) | The platform base depends on the tenant programme (a cycle). The course profile-sync view reads scholarship state — a naive fence breaks the platform's own endpoints. |
| **6** | **Shared flat URL namespace — all three apps at `api/v1/`** | `halatuju/urls.py:9-11` | No tenant segment anywhere; a multi-tenant routing/namespace split doesn't exist yet. |
| **7** | **`family.py` roster taxonomy + sync is the contract both models copy** | `scholarship/family.py:108-138` (`copy_roster_fields`, pathway sync); occupation codes stored as plain CharFields on courses "to avoid a courses→scholarship import" (`courses/models.py:555-557`) | Two copies kept field-for-field in sync by scholarship code; the codes live un-validated on the platform model — a fragile string-contract fence. |
| **8** | **Scholarship reuses the course catalogue + eligibility engine** | `offer_pathway.py:142,254` (`CourseInstitution`, `Institution`); `serializers_admin.py:172` (`from apps.courses.engine import prepare_merit_inputs, calculate_merit_score`) | Pathway verification + merit scoring reuse platform course code; fencing needs a shared-service seam, not duplication. |
| **9** | **`PartnerOrganisation` referral + org-scoped referee auth span both domains** | `scholarship/models.py:1943`, `services.py:121-126`, `views_admin.py:1636` (referee auth = admin whose org == referring org) | The referring-org concept and the future tenant-org concept overlap ambiguously — the audit must keep them distinct (a *referrer* is not the *owner*). |
| **10** | **Startup DataFrame engine is course-only — scholarship does NOT depend on it (a CLEAN seam)** | `courses/apps.py:30-166` (`CoursesConfig.ready` → `requirements_df`) | The ~1 GB in-memory eligibility engine is purely course-selector; the verification engine never reads it (only `funding_estimate`/`offer_pathway` touch the catalogue via ORM). **This is the one place already well-fenced** — the verification engine can become a shared platform service cleanly. |

**Section-6 takeaway (plain language):** the two hardest knots are (1) the overloaded `StudentProfile` and (3) the dual-hatted `PartnerAdmin`. Everything else is mechanical. The good news is that the *verification engine* — the crown jewels — has no hidden dependency on the course-selector's startup engine (#10), so it can stay a single shared service exactly as the decision requires.

### Could not verify (Section 6)
- Full body of `document_red_blockers` / `application_completeness`.
- `income_engine.py` lines ~1041-1100, 1430-1884, 1997-2744 (utility parsers, salary blocks, occupation constants) — seen by grep, not read in full.
- Frontend `officerCockpit.ts`/`incomeWizard.ts` mirrors of backend policy — additional coupling not inventoried here.

---

## Consolidated DECISION NEEDED register (owner)

*(Full options + recommendations are developed in the PRD; listed here so the audit is self-contained.)*

- **D-1 — Are sponsors platform-level or tenant-level?** A `Sponsor` (`scholarship/models.py:1247`) could fund students across programmes (platform) or belong to one org's pool (tenant). *Recommendation: platform-level sponsor accounts, tenant-scoped visibility of pools — but for v1, BrightPath is the only pool, so defer the cross-programme case.*
- **D-2 — Split the `PartnerAdmin` role, or org-scope it?** *Recommendation: keep one `PartnerAdmin` table, add an org-scope check to the reviewer/QC gates (don't split the table); a super-admin stays global.*
- **D-3 — Document fencing: prefix-per-org vs bucket-per-org?** *Recommendation: prefix-per-org (one bucket), Django as the enforcing fence.*
- **D-4 — Cost attribution: per-tenant API keys vs platform-metered with tagging?** *Recommendation: platform-metered with a tenant tag on each billable call (cheapest to run; keeps the <$10/month baseline).*
- **D-5 — What happens to a tenant's data when a module is switched off (suspend vs delete)?** *Recommendation: suspend (hide, retain), never auto-delete.*

---

## Appendix A — Repo facts (for the roadmap)
- Migration state: `apps/courses` at `0060`, `apps/scholarship` at `0095` (95 migrations), `apps/reports` at `0001`.
- All three apps mount flat at `/api/v1/` (`halatuju/urls.py:9-11`).
- Stack: Django API + Next.js web, both on Cloud Run (asia-southeast1, project `gen-lang-client-0871147736`); Supabase (Singapore, project `pbrrlyoyyiftckqvzvvo`) for Postgres + Auth + Storage; Brevo email; Gemini/OpenAI AI; Twilio comms.
- Deploy does NOT run migrations — they are applied migrate-first to prod manually (project convention).

## Appendix B — Method & limits
Read-only engagement. Evidence gathered from first-hand reading of all three `models.py`, `settings/base.py`, `halatuju/urls.py`, the RLS incident doc, and five parallel read-only sweeps (identity/access, storage, external services, frontend branding/i18n, coupling + hard-coded rules). No code was changed; no database or external service was touched; `git status` at start showed only this brief's own file untracked, branch level with `origin/main`. The consolidated "Could not verify" items above are the honest gaps.
