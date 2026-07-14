# Draft PRD — HalaTuju Multi-Tenant Platform (Route A)

**Date:** 2026-07-14
**Author:** Research analyst (drafting engineer) — for architect + owner review
**Status:** **DECIDED 2026-07-15** — the owner accepted the recommendations on ALL open decisions (D-1…D-10; see §8), and the architect's amendments (`2026-07-15-platform-architect-review.md`) are folded in below. This is the plan of record. Nothing has been built.
**Reads with:** the audit (evidence) and `2026-07-14-platform-roadmap-draft.md` (sequence).

---

## Five-minute summary (read this first)

**What we're doing, in one sentence:** turn HalaTuju from *"a course selector with one bursary programme bolted on"* into *"a course-selector platform that can host many organisations' bursary programmes, each in its own locked room."*

**The shape:**
- The **course selector + student accounts stay the shared base**, run by you (the platform superadmin).
- **Each scholarship/bursary becomes a "programme" owned by one organisation.** BrightPath becomes the first one. A hypothetical second — call it "Inspire" — is the test case we design against.
- Three levels of people: **you** (create organisations, decide which features each gets) → **an organisation admin** (runs their programme, sees nothing outside it) → **their staff** (reviewers, officers, sponsors — always locked to that one programme).
- **A student registers once** and can apply to several programmes. Their uploaded documents are reused across programmes **only if the student explicitly agrees**.
- The **document-checking engine stays one shared service** (the genuineness models, the STR/income logic). Organisations *choose which checks and documents apply* to their programme; they never get their own bespoke logic.

**Why it's safe to attempt:** the audit found the scholarship app is already ~90% self-contained. The two hard knots are (1) the student profile carries both course data and scholarship data on one table, and (2) reviewers are the same account type as course-data admins. Everything else is mechanical. The verification engine — the valuable part — has no hidden tie to the course-selector's startup engine, so it can become a shared service cleanly (audit §6, hot-spot #10).

**The single most important technical fact:** the API connects to the database as a superuser that *ignores* Supabase's row-level security (audit intro; `halatuju_api/docs/incident-001-rls-disabled.md:41`). So the walls between organisations must be built in the application's query code — a missing "which organisation owns this application?" column and an org check on every admin query. That is the spine of the whole project, and it's why "one org sees another's applicants" is the #1 risk in the roadmap.

**Decisions:** all ten owner decisions were made on 2026-07-15 — the owner accepted every recommendation (see §8 for the decided register). Nothing blocks Phase 1.

**What v1 is NOT:** no per-organisation custom code, no separate deployments, no tenant self-signup (you create each org by hand), no automated billing. Deliberately.

---

## 1. Vision & roles

### The three levels
1. **Platform superadmin (you, tamiliam).** Owns the shared course selector and the student base. Creates organisations, toggles which modules each organisation gets, and is the only role that can see across organisations. Maps to today's `super` role (`courses/models.py:431-463`), which already "sees all".
2. **Organisation admin.** Runs one organisation's programme end-to-end: configures eligibility and branding, invites their own staff, sees their own applicants — **and nothing outside their organisation**. This is a *new* effective scope; today the nearest role (`admin`) sees *everything* (audit §3), so this is the central behaviour change.
3. **Programme staff** — the existing scholarship roles, always organisation-scoped:
   - **Reviewer** — interviews + records the verdict on applicants **assigned to them** (already assignment-scoped, `scholarship/views_admin.py:89-103`); now also organisation-scoped.
   - **Officer / QC** — quality-control gate before a recommendation (`qc` role, `scholarship/views_admin.py:150-175`); organisation-scoped.
   - **Sponsor** — funds anonymised students (see D-1 for whether they are platform- or org-owned).

### A day in the life (plain-language walkthroughs)

**Platform superadmin (you).** You get an email from a new organisation, "Inspire", who want to run a bursary for rural STEM students. You open the superadmin portal, create the organisation record (name, contact, branding, sender email), switch on the "Scholarship" module for them, and set the programme's **initial** configuration — which eligibility checks and documents apply (e.g. they don't means-test on STR, they require a school-leaving letter). You invite their admin by email; from then on the org admin may adjust that configuration themselves, within the whitelisted catalogue (§3). You never touch their applicants again — that's their job. You still run the course selector for every student.

**Organisation admin (Inspire).** You accept the invite, land on *your* dashboard — only Inspire's applicants, branded as Inspire. You set your income ceiling, your funding amounts, your programme's consent text, and invite two reviewers. When applications arrive you assign them. You cannot see BrightPath's applicants, and BrightPath's admin cannot see yours.

**Reviewer (BrightPath).** Nothing changes from today except the wall: you log in, see only the BrightPath applicants assigned to you, do the interview, record the four-fact verdict. You never encounter an Inspire applicant.

**Student applying to two programmes.** You registered once on HalaTuju to check your SPM course options. BrightPath opens — you apply, upload your IC, results slip, and STR. Later Inspire opens too. When you apply to Inspire, the platform asks: *"You already uploaded these documents for BrightPath — reuse them for Inspire?"* You tick yes for your IC and results slip, no for your STR. Inspire's reviewers see only what you consented to share, and only your Inspire application — never your BrightPath verdict, notes, or reviewer comments.

---

## 2. Organisation & module model

### What an "Organisation" record contains
The audit found `courses.PartnerOrganisation` (`courses/models.py:397-412`) is the natural spine — today it's a thin referral registry (`code`, `name`, `contact_email`, `is_active`). The platform version grows it (or a new `Organisation` model supersedes it — see roadmap D-6) to carry:
- **Identity:** display name (per-language), slug, logo, brand colour, status (active/suspended).
- **Sender identity:** From/reply-to email, support email, programme name (per-language), team sign-off, AI-coach persona name — the things currently hard-coded in `emails.py:16-20, 429-1035` and the frontend i18n.
- **Module flags:** which modules are switched on (below).
- **Contact + governance:** admin contact, and the per-org trust content that today lives in the single-row `TrustContent` (`scholarship/models.py:1781`).

### Which modules exist, and what toggling one grants
For v1, keep the module list small and honest:
| Module | Toggling it ON grants… | Default |
|---|---|---|
| **Course selector** | (Platform base — always on for every student; not a per-org toggle.) | Always on |
| **Scholarship programme** | The organisation gets a programme: a cohort/config record, an applications inbox, reviewer/QC assignment, the verification engine, the sponsor pool. | Off until the superadmin enables it |
| **Sponsor marketplace** | The anonymised discovery pool + sponsor accounts + funding + agreements for that programme (already flag-gated today by `SPONSOR_POOL_ENABLED`, `settings/base.py:148`). | Off |
| **Comms channels** (WhatsApp / email cadence) | Per-org reminder cadence + WhatsApp (today `WHATSAPP_ENABLED`, `settings/base.py:153`). | Email on, WhatsApp off |
| **Payout** (Vircle/bank) | The post-award disbursement + eWallet setup (today `VIRCLE_SETUP_ENABLED`, `BANK_DETAILS_CAPTURE_ENABLED`). | Off |

**Note:** the platform already has a rich feature-flag system (`settings/base.py`) — but those flags are **global** env vars. The tenancy work re-homes the *programme-scoped* ones onto the organisation record, so BrightPath can have WhatsApp on while Inspire has it off.

### What happens to a tenant's data when a module is switched off
**DECISION NEEDED (D-5): suspend vs delete.**
- **Option A — Suspend (recommended).** Switching a module off *hides* its surfaces (endpoints 404/403, the org's staff lose access) but **retains all data**. Reversible. Matches today's flag behaviour, where flipping a flag off "sweeps" open tasks but never deletes rows (e.g. `BANK_DETAILS_CAPTURE_ENABLED` note, `settings/base.py:196-201`).
- **Option B — Delete.** Switching off purges the data. Irreversible; dangerous for PII + audit trails; needed only if an organisation demands erasure.
- **Recommendation:** Suspend by default; deletion is a separate, deliberate, superadmin-only "off-board this organisation" action with an explicit confirmation and a PDPA-compliant erasure routine — never a side effect of a toggle.

---

## 3. Configuration surface (the definitive per-organisation settings)

Derived from audit §2. Each setting: type, default, who may edit. **Anything not listed here is NOT configurable** — it stays a shared platform behaviour.

### 3a. Branding & identity
| Setting | Type | Default | Editable by |
|---|---|---|---|
| Programme display name (en/ms/ta) | text ×3 | — | Superadmin (org admin may request) |
| Logo | image | platform default | Superadmin |
| Brand colour | hex | platform `#137fec` (`tailwind.config.ts:13`) | Superadmin |
| AI-coach persona name (en/ms/ta) | text ×3 | "Cikgu Gopal" | Superadmin |
| From / reply-to / support email | email ×3 | platform aliases (`emails.py:16-20`) | Superadmin |
| Team sign-off (en/ms/ta) | text ×3 | "The BrightPath Bursary Team" | Superadmin |
| Frontend URL / domain | url | `halatuju.xyz` | Superadmin |

### 3b. Eligibility (means-test + academic)
| Setting | Type | Default | Editable by |
|---|---|---|---|
| Academic floor: `min_spm_a_count`, `min_spm_bplus_count`, `min_stpm_pngk` | int/float | 4 / 5 / 2.9 (`scholarship/models.py:37-46`) | Org admin |
| Income ceiling (gross) | int RM | 5,860 (`:47`) | Org admin |
| Per-capita ceiling | int RM | 1,584 (`:52`) | Org admin |
| Whether STR is a fast-path anchor | bool | true | Org admin |
| Whether IPTS-only is a disqualifier | bool | true (`shortlisting.py:111-116`) | Org admin |
| Whether income is means-tested at all | bool | true | Org admin |

### 3c. Documents (the checklist — "shared engine, org-selectable")
| Setting | Type | Default | Editable by |
|---|---|---|---|
| Which document types the programme uses (subset of the 21-type catalogue, `scholarship/models.py:816-854`) | multi-select | BrightPath's current set | Org admin |
| Which are compulsory vs optional per income route | config | current `income_requirements` logic (`income_engine.py:1884`) | Org admin |
| Which verification facts apply (identity / academic / income / pathway) | multi-select | all four (`verdict_engine.py:1072`) | Org admin |

### 3d. Funding & amounts
| Setting | Type | Default | Editable by |
|---|---|---|---|
| Per-pathway award amounts | RM table | current `award.py:30-78` constants | Org admin |
| Funding cap ("up to RM3,000") | int RM | 3,000 | Org admin |
| Funding-estimate model (RM/month × months per pathway) | table | `funding_estimate.py:24-156` | Org admin |

### 3e. Timing & intake
| Setting | Type | Default | Editable by |
|---|---|---|---|
| Intake open/close (`is_open`) | bool/date | true | Org admin |
| Decision reveal delays (`success_delay_hours`, `decline_delay_hours`) | float | 48 / 48 (`:71-79`) | Org admin |
| Query SLA (`query_response_sla_days`) | int | 5 (`:82`) | Org admin |
| Completion-reminder cadence (currently hard-coded `(2,9,23,53)`, `services.py:342`) | day list | current | Org admin |
| Consent version + text | text | per-programme | Org admin (legally reviewed) |

### What is explicitly NOT configurable (stays shared platform behaviour)
- **The verification maths** — genuineness scoring, STR-currency logic, EPF reverse-rates, the four-fact synthesis. Organisations *select which checks apply*; they never edit the algorithm (audit §2a, `verdict_engine.py`, `income_engine.py`). This is the safety promise: no org gets bespoke logic.
- **National/statutory constants** — SPM grade bands, EPF 11/13% rates, STR portal vocabulary (`shortlisting.py:25`, `income_engine.py:621-645, 905-934`).
- **The course selector** — one shared catalogue + engine for all students.
- **Security primitives** — auth, RLS-bypass fencing rules, the org-scoping gates themselves.

---

## 4. Student account & consent

- **One platform account per student**, keyed by Supabase UID (`courses/models.py:483`). A student registers once (for the course selector) and may apply to several programmes. This is already true structurally — `ScholarshipApplication` links to the shared profile (`scholarship/models.py:142`).
- **Per-application data sharing.** An application belongs to one programme (one organisation). Today applications have **no owning-org** (audit §3) — the refactor adds it, and every org-admin query is fenced to it. An organisation sees only *its own* applications for a student, never another programme's application, verdict, reviewer notes, or interview findings.
- **Document reuse across programmes requires explicit consent.** Documents are keyed today as `<app_id>/<doc_type>/<uuid>` (`scholarship/views.py:666`) — i.e. per-application, not per-student. So reuse is a deliberate feature: when a student applies to a second programme, the platform offers *"reuse the IC / results slip you already uploaded?"* Each reused document is copied (or referenced) into the new application **only on an explicit per-document consent tick**, recorded as a versioned `Consent` row (the model already supports versioned, withdrawable consents, `scholarship/models.py:977-1023`). **DECISION NEEDED (D-7):** copy the file into the new org's document space, or reference-share one file? *Recommendation: copy, so each organisation's document fence (audit §4) stays clean and one org's deletion can't affect another.*
- **The student's own profile data follows the student (D-10, decided).** The means-test and family-roster data lives on the shared `StudentProfile` (audit hot-spot #1), so a second application starts from the data the student already entered — it is NOT re-collected from scratch, and it is NOT consent-gated the way documents are. This is deliberate: it is the *student's own declared data*, and re-entering everything would punish the students the platform exists to help. The honesty requirement: the second programme's apply flow must clearly disclose it — *"we've pre-filled this from your profile — please review and update"*. The god-model is NOT split in v1.
- **What an organisation can and cannot see about a student:**
  - **Can see:** the data the student submitted *to that programme* (grades, and the student's own declared family/income as pre-filled + confirmed at apply time per D-10, the documents they consented to share), plus the shared verification engine's output *for that application*.
  - **Cannot see:** the student's other applications, other programmes' verdicts/reviewer notes/interview findings, the student's course-selector activity, or any document the student did not consent to share.

---

## 5. Cost attribution

Every external cost is single-account today, untagged by organisation (audit §5): one Brevo account, one Gemini/OpenAI key, one Twilio account. The billable AI/SMS/email call sites are enumerated in audit §5 ("Cost-attribution points").

**DECISION NEEDED (D-4): how to meter per-tenant costs.**
- **Option A — Platform-metered with a tenant tag (recommended).** Keep one set of platform accounts/keys; add a lightweight usage log that records `(organisation, service, model, units)` at each billable call site (wrap the two AI seams `vision._call_gemini_json` / `profile_engine._call_gemini_text`, the report path, and the email/WhatsApp senders). Cheapest to run, keeps the <$10/month platform baseline, no per-org account setup. Downside: the platform fronts the cost and bills back (or absorbs it) — fine at current volume.
- **Option B — Tenant brings own keys.** Each organisation supplies its own Brevo/Gemini/Twilio credentials, stored per-org. True billing isolation; per-org sender identity comes free. Downside: heavy onboarding friction, secret storage per org, and small orgs may not have accounts.
- **Recommendation:** **Option A for v1** (tag + meter, platform-fronted), with the per-org config *designed to also hold optional own-keys* so Option B can be added later without a schema change. This keeps the baseline cheap now and leaves the door open.
- **Reality check on the baseline:** the heavy costs are AI OCR/extraction (per document) and email. At today's applicant volume these are pennies; the <$10/month platform baseline holds as long as a second tenant doesn't run a large cohort. Meter first, decide billing policy when a real second tenant's volume is known.

---

## 6. Data protection (one page, plain language)

**What PII is processed, per programme:** each programme handles a student's identity (NRIC, name, MyKad scan), academic records, **household means-test data** (income, family roster, STR/JKM status), uploaded financial documents (payslips, EPF, bank statements), and — post-award — bank details and a signed agreement. This is sensitive PII under Malaysia's PDPA 2010.

**Why each organisation needs its own data-processing agreement (DPA):** when Inspire runs a programme on the platform, *Inspire* is the data controller for its applicants; *the platform* is the data processor. Each organisation must have a written DPA saying: what data it collects, why, how long it's kept, and that it authorises the platform to process on its behalf. BrightPath's DPA is effectively with yourself; a real second organisation needs a proper one before it goes live. (This is a legal artefact, not code — flagged for the owner + lawyer.)

**What the platform promises each organisation:**
1. **Isolation.** One organisation's staff can never see another's applicants or documents. Enforced in application query code (because the DB superuser bypasses RLS — audit intro), with a test that *proves* the fence (roadmap risk #1).
2. **Deletion.** On request, an organisation's data can be fully erased — applications, documents (from the bucket), and derived records — without touching any other organisation or the student's shared account.
3. **Breach notification.** If applicant data is exposed, affected organisations are told promptly so they can meet their own PDPA obligations.
4. **Document privacy.** Documents live in a private bucket, reachable only through the backend, with a per-organisation path fence (audit §4); signed view-URLs are short-lived (1 hour, `storage.py:62`).

**The known historical lesson:** RLS was once disabled on all tables for ~4 days (`incident-001-rls-disabled.md`). The takeaway baked into this design: **isolation is enforced in Django, tested explicitly, and never assumed from the database.**

---

## 7. Non-goals for v1 (deliberately out of scope)

- **No per-tenant custom code.** Organisations configure; they never get bespoke logic. The verification engine stays one shared service (§3, "not configurable").
- **No per-tenant deployment.** One codebase, one deployment, one database (Route A). No white-label hosting (Route B rejected).
- **No tenant self-signup.** The superadmin creates each organisation by hand and toggles its modules. No public "create your organisation" flow.
- **No billing automation.** Costs are metered (§5 Option A) but not auto-invoiced. Billing policy is a later, human decision.
- **No cross-programme sponsor marketplace in v1** (pending D-1). BrightPath is the only pool at launch; the second-tenant sponsor case is designed for but not built.
- **No second real tenant onboarded in v1.** "Inspire" is a *design test case* and a rehearsal (roadmap Phase 4), not a live launch.

---

## 8. Decisions register — ALL DECIDED 2026-07-15 (owner accepted every recommendation)

| # | Decision | DECIDED |
|---|---|---|
| **D-1** | Sponsors platform-level or tenant-level? | Platform-level sponsor accounts, tenant-scoped pool visibility; the cross-programme case is deferred — BrightPath is the only pool in v1 |
| **D-2** | Split the `PartnerAdmin` role table, or org-scope it? | Org-scope the existing gates; one table; super stays global |
| **D-3** | Document fencing: prefix-per-org or bucket-per-org? | Prefix-per-org, one bucket, Django enforces. **Amended (review §2.3): new uploads only — NO bulk re-key of existing objects; keys without an org prefix are org #1 legacy** |
| **D-4** | Cost attribution model | Platform-metered + tenant tag on every billable call; config designed to hold optional per-org keys later |
| **D-5** | Module switched off: suspend or delete data? | Suspend (hide, retain). Deletion is a separate, deliberate, superadmin-only off-boarding action — **and the erasure routine must be BUILT before any real second tenant signs a DPA** (review §2.2) |
| **D-6** | Tenant record: extend `PartnerOrganisation` or new model? | Extend `PartnerOrganisation` — it's already the org spine |
| **D-7** | Cross-programme document reuse: copy or reference-share? | Copy into the new org's space — each org's fence stays clean, deletion-safe |
| **D-8** | Owning-org on the application: direct FK or via cohort? | `Cohort.organisation` + a denormalised org on the application, with a drift guard asserting `application.organisation == application.cohort.organisation`. **Naming rule: the new FK is `owning_organisation` (or equally unambiguous) — never another `org`, which already means *referring* organisation on `PartnerAdmin`** |
| **D-9** | Reviewer identities cross-tenant or per-org? | Cross-tenant identity allowed in principle; access scoped per assignment/org; v1 assumes per-org and revisits |
| **D-10** | A student's own income/family profile data: re-entered per programme, or carried with them? | Carried with the student, clearly disclosed at apply time ("we've pre-filled this from your profile — review and update"); the shared profile is NOT split in v1 (see §4) |

---

## Appendix — traceability to the audit
- Roles/scoping → audit §3 (global-by-role today; `_AdminBase` gates).
- Configuration surface → audit §2 (what's data vs code today).
- Document reuse/fence → audit §4 (key scheme, service-role key, prefix-per-org).
- Cost attribution → audit §5 (billable call sites, single accounts).
- Data-protection/#1 risk → audit intro (RLS bypass) + `incident-001-rls-disabled.md`.
- The "shared engine, org-selectable" principle → audit §2a/§2b + hot-spot #10 (engine has no startup-engine dependency).

**Could not verify / needs owner or legal input:** the DPA content per organisation (legal, not code); the real second-tenant cost volume (unknown until one exists); whether sponsors will ever span programmes (D-1, a business call).
