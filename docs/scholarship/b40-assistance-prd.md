# PRD — B40 Assistance Programme (HalaTuju Extension)

**Version:** 0.1 (draft for review)
**Date:** 21 May 2026
**Author:** tamiliam
**Status:** Awaiting approval before sprint decomposition

---

## 1. Mission & summary

HalaTuju helps Malaysian students *find* the right post-secondary pathway. This extension
helps **B40 students *fund* that pathway** once they reach IPTA/ILKA, by connecting them with
individual sponsors who each "adopt" one student. The course-discovery mission is unchanged;
financing is an additive layer that reuses the same students, profiles, and quiz.

The platform **matches and tracks**; it never holds money. Sponsors pay into **MyNadi
Foundation** (entity tentative) via a payment gateway, and MyNadi staff execute periodic
disbursements with a human approval gate.

**Mission bonus:** even applicants who fail shortlisting retain a working HalaTuju account for
free course guidance — honouring the core mission and making the "we'll keep your details"
consolation real.

---

## 2. Goals & non-goals

### Goals
- Let a B40 student apply through a native form, get an instant acknowledgement, and be
  mechanically shortlisted.
- Auto-sort shortlisted students into **Bucket A** (meets all criteria) and **Bucket B**
  (meets all but marginally fails one).
- Turn messy intake + interview notes into a polished, sponsor-ready profile **automatically**
  (AI-drafted, human-approved).
- Give sponsors a vetted, identity-protected way to browse and adopt one student, after
  demonstrating financial commitment.
- Track pledges, disbursements, and student "good standing" with **near-zero routine admin**,
  keeping a human gate only on money leaving the account.
- Be fully PDPA-compliant, including guardian consent for minors.

### Non-goals (explicitly out of scope)
- ❌ **No financial return to sponsors, ever.** Keeps us a charity, not a P2P-financing
  operator regulated by the Securities Commission. Hard rule.
- ❌ Platform does not custody or auto-transfer funds. MyNadi's account and staff do.
- ❌ Not a loan, not crowdfunding-with-rewards.
- ❌ No replacement of the existing course-recommendation product.

---

## 3. Design principles

1. **Philanthropic-only** — sponsors receive gratitude, a story, and progress reports. Never
   money or equity.
2. **Platform is a matchmaker + ledger** — money flows sponsor → gateway → MyNadi → (staff) →
   student. We record, instruct, and prove; we don't hold.
3. **Human gate on irreversible actions** — money out and profile-go-live both require a click.
4. **Consent before exposure** — no PII reaches a sponsor without written, versioned,
   age-appropriate consent.
5. **Reuse before rebuild** — lean on Supabase Auth, RLS, the quiz, and the Gemini report
   engine that already exist.

---

## 4. Personas

| Persona | Who | Key needs |
|---|---|---|
| **Applicant / Student** | B40 school-leaver (often a HalaTuju user already) | Apply easily, know status, upload docs once, control what sponsors see |
| **Guardian** | Parent of a minor applicant | Consent on the child's behalf |
| **Sponsor** | Individual donor (P2P-investor *feel*, philanthropic *substance*) | Trust the vetting, browse safely, adopt one student, see impact |
| **MyNadi Admin** | Foundation staff | Review borderline cases, approve profiles, approve & execute payouts, handle exceptions |
| **Referrer** | CUMIG, schools, community contacts (already modelled as `PartnerOrganisation`) | Refer students, vouch as referee |

---

## 5. End-to-end workflow

```
"APPLY FOR B40 ASSISTANCE"  (one front door)
        │
   ┌────┴─────────────────────┐
Returning user             Fresh student
(log in → form pre-fills    (fills form; submit
 grades/NRIC/school)         auto-creates HalaTuju
        │                    account via NRIC gate)
        └────────────┬───────────────┘
                     ▼
              SUBMIT APPLICATION  ── ack email
                     ▼
              MECHANICAL SHORTLIST   ◀── needs only grades+income+intent+consent
                     │                    (NOT the quiz)
            ┌────────┴────────┐
          FAIL              PASS
   "we'll keep you;     "Congratulations!"
    good luck"               │
   (keeps free HalaTuju      ▼
    course access)    STEP 1A: complete course profile + quiz
                      to be put forward to sponsors  ◀── quiz gate lives HERE
                             ▼
            STEP 2: deeper info + documents + e-consent
                             ▼
            STEP 3: phone interview (optional, human)
                             ▼
            STEP 4: AI-drafted profile → MyNadi approves
                             ▼
            STEP 5: profile published to sponsor marketplace
                             ▼
            ADOPT → PLEDGE (pay MyNadi via gateway)
                             ▼
            PERIODIC DISBURSEMENT (good-standing → human-approved payout)
```

### Application flow decision (confirmed)
**Apply first, quiz deferred.** A single "Apply" front door for everyone. Account-type sorting
happens silently via login state — returning users pre-fill from their profile; fresh students
get a HalaTuju account auto-created on submit (reusing the existing NRIC hard gate). The course
quiz is required only **after** a student passes shortlisting (STEP 1A, to be put forward to
sponsors), surfaced via the existing incompleteness-badge pattern — never as a barrier to
applying. Grades live once in `StudentProfile.grades`; the application pre-fills the quiz and
vice versa, never asked twice.

---

## 6. Functional requirements (by module)

### M1 — Application intake (native form, single front door)
- Trilingual (EN/MS/TA) form capturing: identity, school, SPM/STPM results, household income &
  sources, STR/BR1M/JKM status, family composition, intended pathway
  (UPU/Asasi/Matrik/STPM/PISMP), and consent-to-be-contacted.
- Returning user → log in → form pre-fills from `StudentProfile`.
- Fresh student → submit triggers anonymous-sign-in → link-by-NRIC, creating the account
  transparently. NRIC entered once serves both application and account.
- **Primary contact = the account's verified Google email + in-app dashboard.** Students
  authenticate with Google Sign-In, so HalaTuju already holds a real, verified Gmail for every
  account (~600 created this way). Phone/WhatsApp login is planned but not yet implemented, so
  WhatsApp notifications are a Phase 2 enhancement bundled with that work.
- On submit: create `ScholarshipApplication`, fire acknowledgement notification (email + in-app),
  run shortlisting.
- Open applicants welcome (not only existing HalaTuju users).

### M2 — Mechanical shortlisting + buckets + notifications
- Rules engine evaluates configurable criteria (see §9). Outputs: `FAIL`, `BUCKET_A`, `BUCKET_B`.
- **Acknowledgement email** immediately on apply.
- **Fail email** after a configurable delay (e.g. 3 days): courteous, "didn't meet this round's
  criteria, but we'll keep your details and contact you if something opens up — good luck."
- **Pass email**: congratulations + next-step invitation (M3).
- Fully automatic.

### M3 — Deeper profile + documents + consent (STEP 1A, 2)
- **STEP 1A:** if no completed quiz, route to the existing course-ID quiz. Required-to-proceed
  gate to reach the sponsor stage (not required-to-submit on the application). Returning students
  who already did the quiz skip to STEP 2.
- Structured deeper-info capture: aspirations, plans, fears, **quantified funding need**
  (tuition gap, laptop, hostel, transport, books, monthly allowance × months → an envelope
  total). Fixes the "funding ask not quantified" gap from the B40 analysis.
- **Document vault** (Supabase Storage, private bucket, signed URLs): IC, results slip, photo,
  EPF, STR, statement of intent, reference letter. AI-assisted OCR can pre-read income docs for
  the human reviewer.
- **One referee** captured (name, role, contact) — the B40 analysis flagged its absence.
- **E-consent** replacing verbal consent: versioned text in the student's language, checkbox +
  timestamp + IP, stored in a `Consent` record. **Minor (<18) → guardian consent step required.**

### M4 — Sponsor onboarding + commitment + approval
- Sponsor self-registers (separate auth, mirroring the `PartnerAdmin` pattern).
- Light **KYC** (name, IC/passport, contact) — proportionate; heavier AML only for large amounts.
- **Demonstrates commitment by paying a minimum amount first** (gateway → MyNadi) before
  browsing. Top-ups allowed later.
- Account → `APPROVED` (auto on payment clear + KYC pass, or admin review) before marketplace
  access unlocks.

### M5 — Profile marketplace + PII protection
- Approved sponsors browse published profiles.
- **Default = redacted view:** first name + initial, state, partial school, grades, story,
  funding breakdown, photo *only if consented*. Hidden: NRIC, full name, contact, address, docs.
- **Reveal rules:** fuller identity shown only when the student gave explicit written consent
  **and is ≥18** (guardian path for minors), and only to an approved sponsor — enforced in code
  via RLS + visibility tier, not policy.
- Filters: state, field/pathway, funding size, bucket.

### M6 — Adoption + pledge (1:1)
- Sponsor selects **one** student, commits to the funding envelope.
- Pledge routed to MyNadi via gateway; platform records a `Contribution` with gateway reference
  and status.
- Student marked `ADOPTED`; profile removed from open marketplace.

### M7 — Disbursement ledger + good-standing + human-gated payout
- **Good-standing:** student periodically uploads proof of enrolment + results + a short update;
  auto-reminders; auto-flag if missing or below the academic minimum.
- Platform **prepares** a periodic payout instruction (amount, bank details, period) **only if
  good-standing passes**.
- **MyNadi staff approve & execute** through their separate setup (e.g. DuitNow/bank transfer),
  then mark paid with a reference. Nothing leaves automatically.
- Sponsor sees a running impact ledger + progress reports.

### M8 — Admin console (MyNadi)
- Queues: borderline shortlist (Bucket B), profiles awaiting approval, payouts awaiting approval,
  flagged good-standing.
- One-click approve/reject with audit trail.
- Cohort configuration (criteria thresholds, funding envelope, disbursement frequency).

---

## 7. Data model additions

Building on existing `StudentProfile`, `PartnerOrganisation`, `PartnerAdmin`
(`apps/courses/models.py`) — new tables (all with RLS):

| Table | Purpose |
|---|---|
| `ScholarshipCohort` | Round config: criteria thresholds, envelope, disbursement schedule |
| `ScholarshipApplication` | One per applicant per cohort; raw intake, status, bucket, score; FK to `StudentProfile` (nullable until created) |
| `ApplicantDocument` | Typed uploads (IC/results/EPF/STR/photo/SOI/reference), verification status, storage path |
| `FundingNeed` | Structured envelope breakdown |
| `Referee` | Name, role, relationship, contact |
| `Consent` | Versioned consent; `is_guardian`, locale, timestamp, IP |
| `SponsorAccount` | Sponsor auth + KYC + approval + committed total (mirrors `PartnerAdmin`) |
| `Sponsorship` | 1:1 adoption link (sponsor ↔ student), envelope, status |
| `Contribution` | Sponsor → MyNadi payment via gateway (ref, amount, status) |
| `GoodStandingReport` | Periodic student submission |
| `DisbursementInstruction` | Prepared payout, good-standing check, approval, paid reference |

---

## 8. Technical architecture

No new stack. Reuse Django REST (`halatuju_api`) + Next.js (`halatuju-web`) + Supabase
(Postgres, Auth, Storage, RLS) on Cloud Run, per `halatuju_api/CLAUDE.md`. Additions:
- New Django app, e.g. `apps/scholarship/`.
- Supabase **private Storage bucket** for documents (signed URLs only).
- Payment gateway integration (webhook → `Contribution` status). Cost-conscious Malaysian NGO
  candidates: **ToyyibPay** or **Billplz** (cheap FPX), or iPay88/Curlec. Final choice TBD.
- Gemini (`apps/reports/report_engine.py`) extended to draft sponsor profiles from intake +
  interview notes.
- Email via existing verified-email infrastructure.

---

## 9. Eligibility & shortlisting rules (configurable)

From the B40 PDF's stated criteria:
- **Income:** combined household monthly income within B40 band (anchored to STR status +
  uploaded proof).
- **Academic:** ≥ 5 A's in SPM **or** ≥ 3.0 PNGK in STPM.
- **Intent:** active intent to continue to tertiary education this cohort year.
- **Consent:** recorded.

**Bucket logic:** Bucket A = all four strictly met. Bucket B = exactly one criterion *marginally*
missed (e.g. 4 A's, or income just over band) — routed to admin review. All thresholds live in
`ScholarshipCohort` so they can be tuned without code changes.

---

## 10. Consent, PDPA & minors
- Written, versioned, purpose-specific e-consent in the student's language; immutable audit record.
- **Under-18 → guardian consent mandatory** before any sponsor exposure.
- Sensitive data (financial, identity, documents) encrypted at rest in a private bucket; access
  via short-lived signed URLs; RLS restricts every row to its owner / adopting sponsor /
  MyNadi admin.
- Right to withdraw consent → profile auto-unpublishes.

---

## 11. What stays human (intentionally)
Borderline income adjudication (Bucket B), optional phone interview, profile go-live approval,
and **every payout release**. Everything else in the funnel is automatic. This is the correct
boundary for handling real money and real identities.

---

## 12. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Mistaken for regulated P2P financing | Strict no-return rule; donation framing in all copy and terms |
| Fund-handling / charity-solicitation compliance | MyNadi is custodian; confirm fundraising permit + LHDN status; **lawyer review required** |
| PDPA breach via sponsor exposure | Consent-gated redaction enforced in code; minor guardian gate |
| Income fraud / overstatement of need | Document upload + OCR + human review of Bucket B; STR as anchor |
| Wrong-account / wrong-amount payout | Human approval gate; good-standing precondition; reconciliation |
| Selection bias (B40 doc noted all-female, two-state first batch) | Cohort dashboards surface demographic spread to admins |
| Entity not finalised (MyNadi vs other) | Phase 0 gate before any money module is built |

---

## 13. Phased delivery

- **Phase 0 — Legal/entity groundwork (not code):** confirm MyNadi, fundraising/LHDN status,
  gateway account, consent templates, criteria sign-off. *Gate for Phases 2–3.*
- **Phase 1 — Intake & profile engine (MVP, serves the 51 existing applicants):** native form +
  acknowledgement + shortlisting + buckets + document vault + e-consent + AI profile draft +
  admin review. No sponsor money involved. Kills the manual ~20-min-per-profile bottleneck.
- **Phase 2 — Sponsor portal:** onboarding + KYC + commitment payment to MyNadi + approval +
  marketplace + redaction + 1:1 adoption.
- **Phase 3 — Money & good standing:** contribution ledger + good-standing tracking +
  human-gated payout instructions + sponsor progress reports.
- **Phase 4 — Polish:** dashboards, analytics, automation tuning.

---

## 14. Success metrics
Time-to-acknowledgement (instant), admin minutes per profile (target ↓ from ~20 to <5), %
shortlist auto-decided, applicant→published conversion, sponsor approval→adoption rate, on-time
disbursement %, good-standing submission rate, zero PDPA incidents.

---

## 15. Cost
Incremental and small: same Cloud Run + Supabase footprint; modest extra Storage for documents;
payment-gateway fees (FPX ≈ flat ~RM1/transaction on ToyyibPay/Billplz, pass-through). Gemini
already integrated. Comfortably within the <$10/month app-infra target.

---

## 16. Open decisions still needed
1. **Confirm the entity** (MyNadi Foundation?) and its fundraising-permit / LHDN tax-deductible
   status.
2. **Lawyer review** of PDPA consent text + the MyNadi custody arrangement + minors handling.
3. **Payment gateway** choice (ToyyibPay / Billplz / other) + MyNadi's receiving account.
4. **Numbers:** minimum sponsor commitment, funding envelope size (PDFs used RM5,000),
   disbursement frequency, exact Bucket A/B thresholds.
5. **Naming/branding** of the programme within HalaTuju.
