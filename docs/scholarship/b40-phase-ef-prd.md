# PRD — B40 Assistance Programme: Sponsor, Reviewer & Student Features (Phase E/F)

> **Status:** Approved 2026-06-07 — requirements baseline. **No feature code until the open decisions (§ end) are resolved.**
> **Author:** Claude (picked up from the sponsor/E-phase workstream).
> **Investigated:** `serializers.py`, `pool.py`, `sponsorship.py`, `views_sponsor.py`, `models.py`, `emails.py`,
> `application-processing-pipeline-plan.md`, `reviewer-role-scoped-access-plan.md`, `lawyer-review-bundle.md`, the
> `/scholarship`, `/sponsor`, `/admin/invite` routes.

---

## Context — why this PRD

The B40 Assistance Programme is a sponsor→student giving platform run by Yayasan myNADI. The **money-flow backend**
(donate → fund → offer → accept → lapse) and the **anonymised sponsor pool** are already built but **dark behind the
`SPONSOR_POOL_ENABLED` flag**, gated on lawyer sign-off (`lawyer-review-bundle.md`). The **application pipeline** (Check
1/2/3) and **reviewer scoped-access** are partly built, partly planned. A ~20-student pilot is live to gauge student
response; there are no sponsors yet.

This PRD specifies the **next nine features** needed to bring the programme to a usable, demoable end-state across the
three personas — **sponsor**, **reviewer**, **student** — and reconciles every one against the two hard boundaries in
this codebase:

1. **The anonymity allowlist (enforced in code, not prose).**
2. **The existing pipeline / state machine** (do not invent states).

Where a feature collides with either, this PRD **flags it and offers options** rather than silently resolving it. New
fields that would cross the sponsor-facing boundary are flagged as **decisions for the user**, never made here.

**Priorities (user-set):** Features **1, 3, 8** are must-have-for-closure and are specified in most depth. Features 2,
4, 5, 6, 7, 9 are specified completely but more concisely.

---

## The binding constraints (the non-negotiables every feature is checked against)

| # | Constraint | Where it lives (binding) |
|---|---|---|
| B1 | **Sponsor allowlist** — a sponsor may see ONLY: `ref` (alias S-XXXX), `state` (region, not city/street), `field`, `academic` (band), `funding_categories`, `programme_months`, `award_amount`, and (detail) the generated `anon_profile` blurb. Every field is explicitly derived; **no model field auto-crosses.** | `serializers.py:38` `SponsorPoolCardSerializer` (+ `:80` detail, `:90` sponsorship card) |
| B2 | **Pre-publish identifier scan** — an anon profile cannot be published if it contains the student's name/school/city/NRIC/phone/email. | `pool.py:87` `scan_anon_for_identifiers` |
| B3 | **Pool eligibility** — a student is in the pool iff `SponsorProfile.anon_published` is true **AND** an active `share_with_sponsors` consent exists **AND** status ≠ `sponsored`; whole pool behind `SPONSOR_POOL_ENABLED`. | `pool.py:43,50`; `models.py` `SponsorProfile.anon_published` |
| B4 | **Two-way anonymity** — the student NEVER sees the sponsor. The student's award view has no sponsor field. | `serializers.py:105` `StudentAwardSerializer` |
| B5 | **One consent system** — reuse `CONSENT_VERSION` + `record_consent` + the `Consent` model; no parallel consent. | `services.py:790,844`; `models.py` `Consent` |
| B6 | **Pipeline state machine** — `ScholarshipApplication.status`: `submitted → shortlisted → profile_complete → interviewing → interviewed → accepted → sponsored` (+ `rejected/withdrawn/expired`). `Sponsorship.status`: `offered → active / lapsed / cancelled`. | `models.py` `STATUS_CHOICES`, `Sponsorship.STATUS` |

**Legend used below:** **EXISTS** (built, reuse) · **PARTIAL** (backend or shell exists, needs the rest) · **NET-NEW** (build from scratch).

---

# SPONSOR-SIDE FEATURES

## ⭐ Feature 1 — Sponsor landing page *(PRIORITY — must-have)*  ·  PARTIAL

**Purpose.** A public, persuasive entry page for prospective sponsors — the mirror of the student `/scholarship` landing
page, but selling the *act of giving*. It is the destination for the referral/invite links (Feature 4) and the top of
the sponsor funnel.

**Existing building blocks.** `/sponsor` exists as a **portal shell** (`halatuju-web/src/app/sponsor/page.tsx`) that
renders pending/approved/rejected states off `getSponsorMe()`. `/sponsor/register` and `/sponsor/login` exist. The
student landing `app/scholarship/page.tsx` (212 lines, `'use client'`) is the **look/feel/structure to mirror**.

**User-facing behaviour.**
- A marketing page at **`/sponsor`** (unauthenticated view) mirroring the `/scholarship` structure: hero, "how it works"
  (donate → we match → you fund a need, anonymously), the **three core promises** (it's a donation; you can't withdraw to
  bank; permanent anonymity), an FAQ, and a primary CTA **"Become a sponsor" → `/sponsor/register`**.
- Must reuse the same components/Tailwind system as `/scholarship` for visual consistency.
- Authenticated sponsors hitting `/sponsor` are routed to their portal/profile (Feature 2), not the marketing page.
- Content must align **verbatim in spirit** with the lawyer bundle's §1 and the seven disclosures (Appendix A) — but the
  *binding* disclosures/quiz/agreement happen in onboarding (already specced), not on the landing page. The landing page
  **must not** make tax-deductibility claims (bundle A6 / §7.3 is still open with the lawyer).

**Pipeline states/triggers touched.** None on the student pipeline. Sponsor-account states only (`Sponsor.status`
`pending/approved/...`), and only as the "what happens next" copy.

**Data fields.** None new. Read-only marketing content + a link. (Optionally a live, non-identifying stat like "N students
seeking support" — see Open Question Q-1; this would read pool size and is a **mild** disclosure, flag.)

**Privacy/PDPA.** No personal data. If a live "students waiting" counter is added, it must be a **count only** (never
cards) and respect `SPONSOR_POOL_ENABLED`.

**Dependencies.** Feeds Feature 4 (referral links land here). Independent of the money flow — can ship while the pool is
still dark.

**Open questions.** Q-1 (live student-count stat yes/no); Q-2 (does the landing page require login to see *any* pool
preview, or is it fully public marketing only — recommend public marketing only, no cards pre-approval).

---

## Feature 2 — Sponsor profile page + sponsored-students list  ·  PARTIAL

**Purpose.** A signed-in sponsor's home: their own details, their **giving balance**, and the (anonymised) students they
are supporting, each with a progress indicator.

**Existing building blocks.** `SponsorWalletView` (`views_sponsor.py:168`) returns balance + donations + holding
sponsorships. `SponsorSponsorshipsView` (`:224`) returns the sponsor's allocations. `SponsorSponsorshipSerializer`
(`serializers.py:90`) already wraps each sponsorship as **the anon card + money/status only**. No "my students" frontend
yet (deferred E3b).

**User-facing behaviour.**
- Sponsor account block: name, email, phone, organisation, status (from `SponsorSerializer`, `serializers.py:11`).
- Giving balance: donated − committed (`sponsorship.sponsor_balance`).
- **My students:** a list of the sponsor's sponsorships, each shown as the **anonymised card** (`ref`, field, academic
  band, award amount, status `offered/active`) + a **progress indicator**.

**Pipeline states/triggers touched.** Reads `Sponsorship.status` (`offered/active/lapsed/cancelled`) and the linked
application's pool card. No writes.

**Data fields.** Reuses the allowlist card. **Progress indicator = the conflict** — see **FLAG-1**.

**Privacy/PDPA.** Must render strictly through `SponsorSponsorshipSerializer` (anon card). No raw application/profile
passthrough.

**Dependencies.** Feature 9's student progress data feeds the indicator (and shares FLAG-1).

> **🚩 FLAG-1 — "each student's progress" is NOT in the allowlist.** Showing progress to a sponsor needs a *new*
> sponsor-facing field, which by B1 is a decision, not something to add silently. **Options:**
> (a) **Coarse status only** (recommended) — reuse what already crosses: the sponsorship `status` + a derived,
> non-identifying enum like `on_track / semester_completed / needs_attention / graduated`, computed by myNADI from the
> results upload (Feature 9) — **never** the results slip itself. Add ONE allowlist field `progress_state`.
> (b) **Milestone counter** — "Semester 2 of 6 funded/released" tied to tranche releases (§3.6 of the bundle, *not built*).
> (c) **No per-student progress at launch** — show only `offered/active` status; defer progress to the tranche build.
> *Open decision: which option, and exactly which enum values may cross the allowlist?*

---

## ⭐ Feature 3 — Sponsor email notifications *(PRIORITY — must-have)*  ·  NET-NEW

**Purpose.** Tell sponsors when there is **a new student to support**, so they return and fund. The user described the
journey as "applied → verified → final anonymised profile generated," and asked to **tie the trigger to the actual
pipeline stage where the anonymised profile is published.**

**Existing building blocks.** None for sponsors. `emails.py` has a full student-email stack (ack/shortlist/decline/
reminders) and `send_sponsor_interest_admin_email` (admin alert only). There is **no** sponsor-facing notification and
**no** digest/preference machinery.

**Reconciliation of the trigger (important).** A sponsor must never learn of a student *before* anonymisation, and
"applied"/"verified" are **not** sponsor-visible events (they involve identity). The single safe, correct trigger is the
**publish point**: when `SponsorProfile.anon_published` flips **true** and `pool.is_pool_eligible(app)` becomes true (B3).
That is the first moment a student legitimately exists *to a sponsor*. → **We collapse "applied/verified/generated" into
one event: "a new anonymised student is available."** (See FLAG-2 if the user wants earlier signals — they can't cross
the boundary.)

**User-facing behaviour.**
- In onboarding/profile, a **notification preference**: `Real-time` · `Weekly digest` · `Off`.
- **Real-time:** on each `anon_published` event, send an email — *"A new student is now seeking support"* — with the
  **anon card only** (ref, field, academic band, funding need, award amount) and a link to the pool. **No identity.**
- **Weekly digest:** a scheduled job batches all students published since the sponsor's `last_digest_sent_at` into one
  email (counts + a few anon cards).

**Pipeline states/triggers touched.** Hooks the **publish transition** (`SponsorProfile.anon_published False→True`).
Does **not** touch the student state machine. The digest is a new scheduled job (alongside the existing reminder/lapse
crons).

**Data fields (new, sponsor-side — these do NOT cross the student allowlist, so B1 is not breached):**
- `Sponsor.notify_frequency` — enum `realtime | weekly | off` (default `weekly`).
- `Sponsor.last_digest_sent_at` — datetime.
- (Email content is rendered through the existing `SponsorPoolCardSerializer`, guaranteeing allowlist compliance.)

**Privacy/PDPA.** Sponsor email is the sponsor's own PII (already held, PDPA-noticed). The student content is the anon
card — already allowlist-safe. Unsubscribe/Off honoured. Digest must respect the **Brevo daily-quota** discipline if it
fans out widely (see HalaTuju email infra).

**Dependencies.** Requires the publish transition to emit a signal/hook (small backend addition). Independent of Feature 1.

**Open questions.** Q-3 default frequency (recommend `weekly` to protect deliverability); Q-4 whether real-time should be
**debounced/batched hourly** to avoid a burst when an admin publishes many at once; Q-5 send channel (Brevo, same as
student emails — recommend yes, from `noreply@halatuju.xyz`).

> **🚩 FLAG-2 — "applied/verified" cannot be sponsor-trigger events.** They precede anonymisation and involve identity.
> The PRD ties the trigger to `anon_published` only. *If the user wanted sponsors notified earlier, that is impossible
> under B3/B4 without weakening anonymity — flagged, not resolved.*

---

## Feature 4 — Sponsor referral / invitation  ·  NET-NEW

**Purpose.** Let an existing sponsor invite prospective sponsors (email now, WhatsApp later) with a personal endorsement;
invitees land on the **Feature 1** landing page.

**Existing building blocks.** None. Sponsors self-register (email/password + Google). No referral/invite primitive. The
`/admin/invite` flow is for *admins*, not sponsors — different model (PartnerAdmin), do not reuse directly.

**User-facing behaviour.**
- From the sponsor profile: **"Invite a friend to sponsor"** → enter name(s)+email(s) + an optional personal note.
- Sends an invite email (the sponsor's note + programme pitch) with a link to `/sponsor` (Feature 1), carrying a
  **referral code** (e.g. `/sponsor?ref=<code>`).
- (Later) a WhatsApp share button with a prefilled message + link.
- Optional attribution: when an invitee registers via the code, record who referred them (no reward mechanic at launch).

**Pipeline states/triggers touched.** None on the student pipeline. Sponsor-side only.

**Data fields (new, sponsor-side):**
- `SponsorReferral` (new model): `inviter` (FK Sponsor), `invitee_email`, `invitee_name`, `note`, `code`, `status`
  (`sent/registered`), `created_at`, `registered_sponsor` (FK, null). *(Or a lighter `referred_by` FK on `Sponsor` +
  a sent-log — see Open Q-6.)*

**Privacy/PDPA.** The invitee's email is third-party PII supplied by the inviter — needs a lawful basis. Include a
**one-time** invite with a clear "you were invited by a friend; we will not retain your email if you don't sign up"
notice, and purge unconverted invitee emails after a short window (ties to the open PDPA retention item, bundle §7.6).

**Dependencies.** Requires Feature 1 (landing) to exist as the destination.

**Open questions.** Q-6 model shape (full `SponsorReferral` vs lightweight); Q-7 retention window for unconverted invitee
emails; Q-8 any reward/recognition for successful referral (recommend none at launch).

---

# REVIEWER-SIDE FEATURES

## Feature 5 — Reviewer invitation at `/admin/invite`  ·  EXISTS (extend)

**Purpose.** Invite a reviewer (partner interviewer) into the admin, scoped to the reviewer role.

**Existing building blocks.** `/admin/invite` (`halatuju-web/src/app/admin/invite/page.tsx`, super-admin only) +
`POST /api/v1/admin/invite/` (`views_admin.py`) already create a `PartnerAdmin` with name/email/org and an **optional
role**. The `reviewer-role-scoped-access-plan.md` lists **"Invite page role selector"** as *not started*.

**User-facing behaviour (extension).**
- Add a **role selector** to the invite form: `super | reviewer | viewer` (reviewer is the new first-class option).
- On invite, the new reviewer can be sent an invite link/email and prompted to complete their **reviewer profile**
  (Feature 6) on first sign-in.

**Pipeline states/triggers touched.** None on the student pipeline. Creates a `PartnerAdmin` row with `role='reviewer'`.

**Data fields.** Reuses `PartnerAdmin` (`email`, `name`, `role`, `is_active`, `is_super_admin`). No new fields here
(profile fields are Feature 6).

**Privacy/PDPA.** Reviewer email/name handled as staff PII.

**Dependencies.** Pairs with Feature 6 (profile) and Feature 7 (scoped access). **Do not** flip reviewer-role semantics
without first auditing existing `PartnerAdmin.role` values (see FLAG-3).

**Open questions.** Q-9 does inviting a reviewer auto-send an email now, or is the invite link surfaced for manual send
(current invite emails are noted as "deferred to a separate email service")?

---

## Feature 6 — Reviewer profile page  ·  PARTIAL (model extend + new UI)

**Purpose.** A reviewer's own profile: professional credentials + contact details, so coordinators know who is
interviewing and reviewers can maintain their info.

**Existing building blocks.** `PartnerAdmin` (in the `courses` app) has `email`, `name`, `is_super_admin`, `is_active`,
`role`. No professional/credential fields, no self-service profile UI.

**User-facing behaviour.**
- A reviewer-facing **profile page** (within `/admin`, scoped to self) showing/editing: **name, highest qualification,
  university, year of graduation, field of study, contact phone, address**, email (read-only, identity key).
- **Credentials are explicitly out of scope as data:** passwords are hashed by auth and are **never** modelled, stored,
  or displayed as a profile field. Do not add a "password" field to this view.

**Pipeline states/triggers touched.** None.

**Data fields (new, on `PartnerAdmin` or a `ReviewerProfile` 1:1):**
- `highest_qualification`, `university`, `graduation_year`, `field_of_study`, `phone`, `address`.
- Treat `phone` + `address` as **sensitive PII** under the same PDPA retention/handling as student personal data.

**Privacy/PDPA.** Reviewer phone/address are sensitive — access limited to the reviewer + super-admins; included in the
PDPA notice/retention policy. Never exposed to students or sponsors.

**Dependencies.** Feature 5 creates the reviewer; Feature 7 governs what the reviewer can *see/do*.

**Open questions.** Q-10 store new fields on `PartnerAdmin` (simpler) vs a separate `ReviewerProfile` 1:1 (cleaner
separation of staff-PII) — recommend a `ReviewerProfile` 1:1 for retention/segregation; Q-11 is `address` structured or
free-text.

---

## Feature 7 — Reviewer assignment & reassignment workflow  ·  PARTIAL (build on the plan, don't reinvent)

**Purpose.** Assign applications to reviewers and reassign as needed, with the reviewer seeing **only** their assigned
students — exactly as specified in `reviewer-role-scoped-access-plan.md` and threaded into the umbrella pipeline plan.
**This feature builds on that plan; it does not redefine the assignment gate.**

**Existing building blocks.** Assignment EXISTS: `AdminApplicationDetailView.PATCH` sets `assigned_to`;
`AdminAssignableAdminsView` lists eligible admins; the frontend has a reassignment dropdown. `PartnerAdmin.role` choices
exist. What's *planned, not built* (per the reviewer plan §6): server-side list scoping, detail/interview 403/404 scoping,
**assign = super-only**, per-action split, menu denial, and the assignment **gate**.

**User-facing behaviour / rules (from the plans — quote, don't invent):**
- **Assignment gate** (`application-processing-pipeline-plan.md` §2): a case becomes assignable when
  **`is_ready_for_assignment(app)` = (open_queries == 0) OR (submitted_at + SLA lapsed)** — i.e. Check-2 queries resolved
  or the **5-day** window elapsed. On lapse with gaps still open → proceed-as-is (flagged for the reviewer), not
  auto-declined.
- **Scoped access** (`reviewer-role-scoped-access-plan.md` §3): a reviewer sees only `assigned_to == self`; direct-URL
  access to others returns 403/404; **assign is super-only**; reviewer keeps interview + record-verdict + raise-query;
  **verify-&-accept / reject / assign are super-only**; Students/Sponsors/Invite/Dashboard menus deny reviewers.
- **Reassignment:** manual, super-only (the existing PATCH, but tightened to super-only). **Stale-case auto-reassign**
  (~2 weeks + demerit points) and the **assignment audit trail** (`assigned_changed_by/at`) are **DEFERRED** per the plan.

**Pipeline states/triggers touched.** Reads `ResolutionItem.status` (open count), `submitted_at`, the new cohort SLA
field; writes `assigned_to`. Depends on **Check-2 existing** (queries created at submit) — see Dependencies.

**Data fields.** `assigned_to` (exists). New per the plans: `ScholarshipCohort.query_response_sla_days` (default 5),
`ResolutionItem.response_deadline`; helper `is_ready_for_assignment(app)`. (Audit-trail fields deferred.)

**Privacy/PDPA.** Scoping is itself a privacy control — a reviewer must not see students they aren't assigned. Server-side
enforcement is mandatory (not just UI hiding).

**Dependencies.** **Ordering constraint (from the plan): Check-2-at-submit must land before the assignment gate is
finalised**, because the gate depends on queries being created at submit + the cohort SLA field. Pairs with Features 5/6.

> **🚩 FLAG-3 — reviewer-role semantic flip is breaking.** Today `reviewer` is *powerful* (every write endpoint gates on
> `has_role('reviewer')`), so existing reviewers can assign/accept/reject on **every** application. The plan **restricts**
> reviewer to assigned-only and moves powerful actions to `super`. **Audit existing `PartnerAdmin.role` values first**
> (esp. CUMIG admins) before flipping — otherwise live admins silently lose access. *Decision: confirm the audit + the
> super/reviewer split before implementation.*

---

# STUDENT-SIDE FEATURES

## ⭐ Feature 8 — Student post-match notifications & onboarding *(PRIORITY — must-have)*  ·  PARTIAL

**Purpose.** When a student is successfully matched (an award is accepted → `Sponsorship.active`, app → `sponsored`),
welcome them: an **award announcement**, then an **onboarding flow** mirroring the sponsor onboarding pattern, then a
**questionnaire** so the student understands what is expected of them (attendance, progress, results uploads, conduct).

**Existing building blocks.** `StudentAwardView` + `respond_to_award()` (`sponsorship.py:84`) handle accept/decline with
the **guardian gate** for minors, and on accept record a `consent_to_sponsorship` consent, flip app → `sponsored`, and
remove the student from the pool. There is **no** post-accept email, **no** onboarding flow, **no** questionnaire. The
consent machinery (`CONSENT_VERSION`, `record_consent`, `Consent`) is the system to reuse (B5).

**User-facing behaviour.**
1. **Award announcement** — on `Sponsorship offered→active` (accept), send a congratulations email + in-app banner: "Your
   support is confirmed." (The sponsor identity is **never** included — B4.)
2. **Onboarding flow** (mirrors the sponsor's seven-card pattern, student-appropriate): a short set of **acknowledgement
   cards** — what the support is, that it's tied to progress (and may be staged/withheld — *see FLAG-4 / bundle §6 open
   item*), conduct, how results uploads work, the two-way anonymity (they won't know the sponsor), and data handling.
   Each card acknowledged; recorded via `record_consent` with a **new `consent_type` and version** (B5 — reuse the
   machinery, add a type, do not fork it).
3. **Questionnaire** — a short comprehension/expectations questionnaire (mirroring the sponsor quiz intent) confirming the
   student understands obligations. Stored as structured responses tied to the application.

**Pipeline states/triggers touched.** Trigger = `Sponsorship` `offered→active` (accept) and/or app `accepted→sponsored`.
Onboarding completion can be a new sub-state/flag on the application (e.g. `onboarded_at`) — **does not** add a new top
status value (B6); it's a timestamp gate like `profile_completed_at`.

**Data fields (new):**
- New `Consent.consent_type` (e.g. `student_onboarding_ack`) + a version bump (reuse the model; **B5 respected**).
- `ScholarshipApplication.onboarded_at` (datetime, nullable) — gate for "onboarding complete."
- Questionnaire responses: a JSON field on the application or a small `OnboardingResponse` model (Open Q-13).
- New email(s): `send_award_confirmed_email` (+ digest-safe). All student-side; no allowlist impact.

**Privacy/PDPA.** All student-side; no sponsor exposure. Award emails must not name the sponsor (B4). Questionnaire data
is student PII under existing handling.

**Dependencies.** Sits directly on the existing `respond_to_award` accept path. Independent of Features 1–4. Reuses
consent machinery — **must not** create a parallel consent table.

**Open questions.** Q-12 confirm a **new `consent_type` + version** vs reusing `consent_to_sponsorship` (recommend a new
`student_onboarding_ack` so the sponsorship-acceptance consent stays clean); Q-13 questionnaire storage (JSON on app vs
`OnboardingResponse` model); Q-14 is the questionnaire **blocking** (must pass before funds release) or informational;
Q-15 staged-release disclosure wording for the student (ties to bundle §6 open item — lawyer-dependent).

---

## Feature 9 — Student profile page + graduation thank-you relay  ·  PARTIAL (profile) / NET-NEW (relay)

**Purpose.** (a) A student profile: basic details, institution & field, grades (CGPA), **latest-semester results
upload**, and (if 18+) **consent to be featured in promotional materials**. (b) A **graduation closeout**: a thank-you
note from the student to their sponsor that **preserves two-way anonymity** — relayed through myNADI, stripped of
identifying detail, validated against `scan_anon_for_identifiers`, and surfaced in the sponsor's profile as a message
from *"a student you supported."*

**Existing building blocks.** The Step-4 `/scholarship/application` page holds story/funding/documents/consent tabs;
`ApplicantDocument` handles `results_slip` uploads with OCR. `share_with_sponsors` consent exists; a **promotional/
featuring** consent does **not**. `scan_anon_for_identifiers` (`pool.py:87`) is the relay's validator.

**User-facing behaviour.**
- **Profile:** basic details, institution + field, CGPA, **upload latest-semester results**, and (18+) a
  **promotional-use consent** toggle.
- **Progress signal:** myNADI derives a non-identifying `progress_state` from the results upload — this is what may reach
  the sponsor (Feature 2 / FLAG-1). The **results slip itself never reaches the sponsor** (it carries name/IC).
- **Graduation thank-you relay:** on closeout, the student writes a thank-you note → it is **relayed through HalaTuju/
  myNADI**, run through `scan_anon_for_identifiers` (blocking on any leak), and surfaced in the sponsor's profile as a
  message from *"a student you supported."* **Never a direct student→sponsor channel.**

**Relay mechanism (specified, per the task's request).**
1. Student submits note → stored as `GraduationMessage(application, raw_text, status='pending_review')`.
2. **Automated scan:** `scan_anon_for_identifiers(raw_text, profile)` must return empty; if not, it's **blocked** and the
   student is asked to revise (same UX as the anon-profile publish gate).
3. **myNADI review (recommended):** a human approves the scanned-clean note (defence-in-depth, mirrors the anon-profile
   admin-approve step) → `status='approved'`.
4. **Surface:** the approved, stripped note appears in the sponsor's profile attributed to *"a student you supported"* —
   no ref, no field that could correlate to a single student if the sponsor funded several (Open Q-17).

**Pipeline states/triggers touched.** Profile reads existing application/profile + documents. Relay triggers at
graduation/closeout (a new terminal step after `sponsored`; model as a timestamp/flag, not a new top status — B6).

**Data fields (new):**
- Promotional consent: new `Consent.consent_type` `promotional_use` (18+ only; reuse machinery, B5).
- `progress_state` — the **one** new allowlist field, if FLAG-1 option (a) is chosen.
- `GraduationMessage` model: `application`, `raw_text`, `scrubbed_text`, `scan_result`, `status`
  (`pending_review/approved/blocked`), `approved_by`, timestamps.

**Privacy/PDPA.** Results slips and CGPA are student PII — myNADI-only, never sponsor-facing. Promotional consent is
**explicit, 18+, withdrawable**. The relay is the privacy-critical path: **scan is mandatory and blocking**; human review
recommended.

**Dependencies.** Feature 2 consumes `progress_state` (shared FLAG-1). Reuses `scan_anon_for_identifiers` and the consent
machinery.

> **🚩 FLAG-4 — promotional-use consent is a NEW consent type + version bump.** Reuse the `Consent` model/`record_consent`
> (B5) but add `promotional_use` and bump `CONSENT_VERSION`; 18+ gate enforced server-side. *Decision: confirm the new
> type + version, and the 18+ enforcement point.*
> **🚩 FLAG-5 — thank-you relay correlation risk.** If a sponsor funded several students, even a stripped note plus timing
> could correlate. *Decision Q-17: attribute as a generic "a student you supported" with no per-student linkage, or allow
> linkage to the specific (still-anonymous) `ref`? Recommend generic, no linkage, to protect anonymity.*

---

## Cross-cutting reconciliation summary (all flags in one place)

| Flag | Feature(s) | The conflict | Recommended option |
|---|---|---|---|
| FLAG-1 | 2, 9 | Sponsor "student progress" is not in the allowlist | Add ONE derived enum `progress_state` to the allowlist; never the results slip |
| FLAG-2 | 3 | "applied/verified" can't be sponsor triggers (pre-anonymisation) | Single trigger at `anon_published` only |
| FLAG-3 | 7 | Reviewer-role flip is breaking for existing admins | Audit `PartnerAdmin.role` values before flipping; confirm super/reviewer split |
| FLAG-4 | 8, 9 | New consent types needed | Reuse `Consent`/`record_consent`; add `student_onboarding_ack` + `promotional_use`, bump version |
| FLAG-5 | 9 | Thank-you relay could correlate to a student | Generic "a student you supported", no per-student linkage |
| FLAG-6 | 8, 9 | Staged-release/withholding not yet disclosed to students (bundle §6 open item) | Lawyer-dependent; align onboarding copy to the bundle's §7.2 answer |

**Boundary verdict:** only **two** new fields would ever cross the sponsor-facing allowlist — `progress_state` (FLAG-1)
and nothing else. The thank-you note crosses only **after** the `scan_anon_for_identifiers` gate. Everything else is
sponsor-side or student-side and does not touch B1.

---

## Priorities & suggested sequencing

- **Must-have (user-set): 1, 3, 8.** I agree these are the closure-critical demoable trio (a front door, a reason to
  return, and a real student welcome). 
- **Sequencing note:** Feature **3** needs the `anon_published` hook + the new `Sponsor.notify_frequency` field; Feature
  **7** is **blocked on Check-2-at-submit** (per the pipeline plan ordering constraint) — so 7 should follow the Check-2
  submission work, not lead it. Features **1** and **8** are standalone and can start immediately.
- Suggested order: **1 → 8 → 3** (must-haves) → **6 → 5 → 7** (reviewer track, after Check-2) → **2 → 9** (need
  `progress_state` + relay decisions) → **4** (after 1 ships).

---

## Open decisions I need from you

1. **Q-1 / Q-2 (F1):** Live "students waiting" counter on the public landing page — yes/no? Landing page fully public
   marketing (no pool preview pre-approval) — confirm?
2. **FLAG-1 (F2/F9):** Which progress model crosses to sponsors — (a) one derived `progress_state` enum *(recommended)*,
   (b) tranche milestone counter, or (c) no per-student progress at launch? And the exact allowed enum values.
3. **Q-3/Q-4 (F3):** Default notification frequency (recommend `weekly`); should real-time be hourly-batched to avoid
   publish bursts?
4. **FLAG-3 (F7):** Confirm we audit existing `PartnerAdmin.role` values and adopt the plan's super/reviewer split before
   flipping semantics.
5. **Q-12/Q-14 (F8):** New `student_onboarding_ack` consent type + version *(recommended)* vs reuse `consent_to_sponsorship`?
   Is the onboarding questionnaire **blocking** (gate funds release) or informational?
6. **FLAG-4/FLAG-5 (F9):** Confirm new `promotional_use` consent (18+, version bump); and thank-you attribution —
   generic "a student you supported" with **no** per-student linkage *(recommended)*?
7. **FLAG-6 (F8/F9):** Staged-release/withholding disclosure to students is **lawyer-dependent** (bundle §6/§7.2) — hold
   that copy until the lawyer answers, or draft provisional wording now?
8. **Q-6/Q-7 (F4):** Referral model shape (full `SponsorReferral` vs lightweight `referred_by`) and the retention window
   for unconverted invitee emails.
9. **Logistics:** Save the approved PRD to `Production/HalaTuju/docs/scholarship/b40-phase-ef-prd.md`? (And note: another
   session has been active in this repo — I'll path-scope any future commit.)

---

## Verification (how we'll validate once features are built — not now)

- **Allowlist:** the existing serializer tests assert no name/NRIC/address/phone/email/school in sponsor output; extend
  them for any new field (`progress_state`) and for the digest email body.
- **Relay:** unit-test `scan_anon_for_identifiers` against the thank-you path with planted identifiers (must block).
- **Consent:** assert `record_consent` writes the new types with the bumped version and the 18+ gate.
- **Assignment gate:** test `is_ready_for_assignment` for (queries-open) vs (5-day lapsed); test reviewer 403/404 on
  unassigned students (server-side, not UI).
- **Pipeline:** assert no new top-level `status` values were introduced (only timestamps/flags), preserving B6.
