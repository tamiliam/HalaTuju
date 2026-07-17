# Contract Module — design brief (for the detailed implementation plan)

**Status:** brief / foundation. Another agent turns this into the detailed implementation plan.
**Author context:** written off the post-award signing flow (built + deployed DARK behind
`BURSARY_AGREEMENT_ENABLED`) and the owner's review of the lawyer's amended contract ("2026 June —
Donor Student Conditional Agreement v2" + 7 accepted amendments + an 8th, below).
**Date:** 2026-07 (owner is still awaiting the lawyer's *final* text; see "Sequencing").

---

## 1. Why this module

Today the bursary agreement is **hard-coded** in `apps/scholarship/bursary.py`
(`AGREEMENT_TITLE`/`AGREEMENT_PREAMBLE`/`AGREEMENT_CLAUSES` EN+BM, `DEFAULT_PAYMENT_SCHEDULE`,
`particulars_for`), and the comprehension quiz is a static typed file
(`halatuju-web/src/lib/awardComprehension.ts`). HalaTuju is now **multi-tenant** (BrightPath = org #1;
`PartnerOrganisation` already carries branding/sign-off/persona tenant columns; conventions in
`docs/build-for-tenancy-conventions.md`). A hard-coded, single-org contract can't scale to tenants and
forces a code change for every wording tweak.

**Goal:** move the agreement to an **org-owned, versioned, configurable artifact**. Each org owns its
contract text, signatory, payment schedule, party rules, and quiz — no code change per org. The signing
*flow* (below) is unchanged; only its *source of truth* moves from code constants to org config.

Owner's shape for it: an org admin **uploads / authors the final text**, **ticks the key clauses** a
student must understand (→ quiz candidates), and the module holds the **configuration** the signing
engine reads.

---

## 2. What is already built (do NOT rebuild — the module feeds it)

The post-award signing **flow** is complete and deployed DARK (`BURSARY_AGREEMENT_ENABLED=false`),
migrations `0083`/`0084`/`0085` live; see `docs/retrospective-2026-07-01-post-award-signing.md` +
`docs/scholarship/bursary-go-live-playbook.md`:

- Follow-up email → Action Centre → **comprehension quiz** ("Understand", 8 checkpoints,
  `comprehension_passed_at`) → **signing**.
- **Parent/guardian co-signs, gated by an SMS PIN** to their pre-declared LOCKED phone
  (`guarantor_phone`/`guarantor_phone_verified_at`, Twilio Verify; `bursary.sign_agreement` raises
  `guarantor_phone_missing`/`_unverified`).
- **Notify-and-sign chain** (`notify_after_guarantor_signed` → witness → counter-sign → executed →
  student "in effect" email); daily SLA cron; owner "ready to sign" send.
- **Signed instance** = `BursaryAgreement` — freezes the rendered HTML + SHA256 + a PDF snapshot at
  signing (the immutability guarantee already exists at the instance level).
- Local end-to-end driver `python manage.py bursary_e2e` (mocks all seams); cockpit ticks (TD-144).

**The flow is mechanically test-ready as-is.** The module changes *what text/config it signs against*,
not the plumbing. The engine touch-points the module must feed: `bursary.render_agreement_html`,
`particulars_for`, `sign_agreement`, `sponsorship.respond_to_award`, the notify chain, the quiz, and
the disbursement schedule.

---

## 3. BrightPath v1 content spec (seed the module with this — nothing lost)

The module's **org #1, version 1** = the lawyer's amended v2 with the accepted changes. The **actual
legal text is owner-held** (contains Suresh's NRIC + address — PII, never commit it); the org admin
uploads it. Recorded here PII-free so the plan is accurate:

### 3.1 Parties & roles (these drive the FLOW, not just words)
- **Donor = Suresh, personally** (interim; TD-152). He signs in his personal capacity as co-founder
  until the org is incorporated, then **novates to the Foundation** (the v2 "Successor Company" clause).
  So the counterparty must render from **config** (a name/title/NRIC), not the hard-coded "Foundation".
- **Student** — types their signature (name + NRIC).
- **Parent/guardian = a consenting CO-SIGNER for EVERY student** (owner decision), **not a liable
  "surety/guarantor".** This keeps the SMS-PIN gate we built (identity/consent verification) but
  reframes the word — the code + template currently say "guarantor/surety" and must become
  "co-signing parent/guardian". *This is the 8th tweak to hand the lawyer:* the lawyer's v2 only
  involves the parent for minors; we need the parent as a co-signer for all, framed as consent
  (a gift bursary — nothing to "guarantee" after amendment 1 removes clawback except for fraud).
- **Witness** — a single, OPTIONAL witness (amendment 6). Non-blocking (the Foundation/Donor can
  execute without it). Drop the v2 "Sponsor Organisation" line on the witness block (anonymity leak).

### 3.2 The 7 accepted amendments (+ the 8th) — clause numbers per the lawyer's v2
Summaries only (full redline is the owner's "Interviewer/… Suggested Edits" doc + the earlier
clause-by-clause markup):
1. **10.4.II** clawback → repayment ONLY for fraud/misrepresentation/misuse, 90 days; every other
   termination stops future payments, no clawback. (Optional 10.4.III "save as provided in II".)
2. **4.1.VII** "no other aid" → **disclose**, not exclude; may adjust if over-funded.
3. **4.1.VIII** (2nd sentence) "any criminal offence" → serious/dishonesty/violence only.
4. **4.2** unilateral amendment → obligations fixed at signing; changes by written agreement only.
5. **13.1/13.2** publicity → **opt-in, revocable**, not a condition of the bursary (delete 13.2 into 13.1).
6. **Execution block** → **electronic signature valid (ECA 2006)**; single OPTIONAL witness; no wet ink.
7. **8.1.I** suspension → material breach + 14-day cure (optional 8.1.III "deferred not cancelled").
8. **(NEW) Parent = co-signer for all**, framed as consent — see 3.1.

CGPA 3.0 is ACCEPTED as-is (bright, min-5A students). Internal: align the engine's 2.0 flag + the quiz
to 3.0. "Donor's Personal Data Notice" (referenced in v2 cl. 12) must actually exist before signing.

### 3.3 Payment schedule (STRUCTURED — feeds the contract Schedule AND Vircle)
Every student gets **RM200/month**; the **number of months (and which months) varies by pathway**, so
the total varies **RM1,000–3,000**. Anchored to the **Reporting Date** (course start, read from the
offer letter); a payment releases on the 1st only once the Reporting Date has passed. Exam months are
skipped (the "0" cells). Per the owner's schedule table:

| Pathway | Months paid | Total | Notes |
|---|---|---|---|
| STPM | 15 | RM3,000 | Jul–Nov, (Dec 0), Jan–May, (Jun 0), Jul–Nov |
| Matriculation | 10 | RM2,000 | Jul–Apr |
| Asasi | 10 | RM2,000 | Jul–Apr |
| Poly Diploma | 10 | RM2,000 | Aug–May |
| UA Diploma | 10 | RM2,000 | Aug–May |
| PISMP | 10 | RM2,000 | Sep–Jun |
| STPM (second year) | 5 | RM1,000 | Jul–Nov |

Current code holds only the **total** (`award.py` `proposed_award_amount`: STPM 3000 / continuing-STPM
1000 / else 2000) and a **wrong placeholder string** (`bursary.DEFAULT_PAYMENT_SCHEDULE = "RM500
one-time then RM250/month for 10 months"`). The module must hold this as a **structured per-pathway
month-pattern** (one source of truth) that renders into the contract's Schedule 1 AND drives the Vircle
disbursement cron — otherwise the student signs one schedule and is paid another.

### 3.4 Quiz clauses
The 8 current checkpoints (true/complete info · study the stated programme · notify of changes · maintain
CGPA 3.0 · upload results · participate · gift-not-loan · etc.) are the quiz-candidate set. In the
module these become **clauses the org admin ticks** as "must understand", each with an
owner-authored/approved question (NOT LLM-generated — see challenge #4).

---

## 4. Current-state code the module replaces (map for the plan)
- `apps/scholarship/bursary.py` — `AGREEMENT_TITLE`/`AGREEMENT_PREAMBLE`/`AGREEMENT_CLAUSES` (EN+BM,
  no TA), `DEFAULT_PAYMENT_SCHEDULE` (wrong), `particulars_for`, `render_agreement_html` (reads
  constants; hard-codes "the Foundation" as counterparty).
- `halatuju-web/src/lib/awardComprehension.ts` — the static 8-checkpoint quiz (en/ms/ta) + the
  `AwardComprehensionQuiz` component; the phantom-term guardrail test that pins the quiz to
  `AGREEMENT_CLAUSES` (Code-health S3, 2026-07-03).
- `sponsorship.respond_to_award` / `bursary.sign_agreement` — the party model (minor→guardian-guarantor,
  adult→student+guarantor) hard-codes the "guarantor/surety" framing → becomes "co-signer" + config.
- Signatory config already exists as env: `FOUNDATION_SIGNATORY_NAME/_TITLE/_NRIC`,
  `FOUNDATION_NOTIFY_EMAIL` — these move to org config.

---

## 5. Module outline

### 5.1 Data model (all org-fenced + versioned; respect `docs/build-for-tenancy-conventions.md`)
- **`ContractTemplate`** (per org, versioned): `org`, `version`, `status` {draft/active/archived},
  `effective_from`; config — counterparty {name/title/NRIC}, parent_role {co_signer_all/minor_only},
  parent_pin_required, witness {none/optional/required}, languages_present.
- **`ContractClause`** (ordered; per template + language): `number`, `heading`, `body`,
  `is_quiz_candidate`, and if flagged: `quiz_question`, `quiz_options` (+correct), `quiz_plain` ("what
  this means").
- **`PaymentScheduleRow`** (per template): `pathway` → month-pattern + RM/month. One source of truth.
- **`BursaryAgreement`** (existing) → add a reference to the exact `ContractTemplate` **version** signed
  (keeps the frozen HTML/SHA/PDF snapshot it already has).

### 5.2 Org-admin surfaces
- Author clauses per language (structured, clause-by-clause — challenge #1), or import.
- Tick clauses "must understand" → quiz candidates; author/approve each question.
- Configure signatory, schedule table, parent role, witness, flags.
- Preview the rendered agreement + the generated quiz.
- **Publish** a version through a **review/approval gate** (challenge #3) → active; signed agreements
  keep their own version.

### 5.3 How the flow consumes it
- `render_agreement_html` + `particulars_for` read the org's **active template** + schedule.
- The quiz is **served from the API per template version** (replaces the static file); the pass endpoint
  keys to the version.
- Signatory / parent-role / schedule config drive `sign_agreement`, `respond_to_award`, the notify chain,
  and Vircle disbursement.

---

## 6. Challenges to design around (biggest first)

1. **Free-text upload vs structured clauses.** A Word/PDF blob has no clause boundaries the module can
   offer for quiz selection (numbering varies — recall the lawyer's `10.4.II`). **Decide the source of
   truth:** the structured clause list should be what is rendered + quizzed; an uploaded PDF may be
   attached as the canonical legal reference, but the two MUST NOT diverge — the student must sign
   exactly what the quiz covers.
2. **Immutability / legal artifact.** Editing a template must never mutate a signed agreement. Hard
   versioning: a signature references its template version; a signed student can always reproduce
   exactly what they agreed to.
3. **Legal-review gate.** Phase-0's whole point is a *lawyer* vetting the text. If any org admin can
   upload and go live, that gate is gone → a **publish gate** (a "legally reviewed" attestation +
   attribution, or a super/legal approval step). Also decides who may author (challenge 11).
4. **Quiz ↔ contract lockstep at runtime.** The static phantom-term guardrail becomes runtime
   validation: every quiz question maps to a live clause in the active version. **Do NOT LLM-generate
   quiz questions** from the clause — that reintroduces the drift we avoided. Org admin flags the clause
   AND authors/approves the deterministic question.
5. **Config and text must agree.** Parent role, counterparty, witness are flow settings, not just words.
   If the text says "parent for minors" but config says "co-signer for all", the artifact and the flow
   contradict → cross-validate config vs clauses at publish.
6. **The payment schedule is a data structure, not a field.** The per-pathway RM200×N month-pattern
   (anchored to the Reporting Date, exam-month gaps) must feed BOTH the contract Schedule AND the Vircle
   disbursement cron from ONE source, or they drift.
7. **Multi-language legal parity.** The signed contract + quiz must exist in the language the student
   signs (en/ms/ta). Auto-translating legal text is unsafe → block signing in a language the template
   lacks, or require all three. (BrightPath already carries a Tamil-first-draft debt.)
8. **Counterparty change over time (novation).** Suresh → Foundation must be forward-only: new signings
   get the Foundation; already-signed keep Suresh. Versioning covers it; consider a recorded novation.
9. **Migration / seeding.** BrightPath has a live-dark template + reconciled quiz. Seed org #1 v1 from
   the amended v2 so nothing regresses when the constants are removed. Never leave an org with the flow
   on and no active template.
10. **PDF rendering of arbitrary text.** `xhtml2pdf` renders controlled HTML today. Arbitrary org rich
    text (tables, long clauses, Tamil) can break/ugly the PDF → constrain to a safe rich-text subset +
    preview, not raw HTML/Word paste.
11. **Authoring authority + the org fence.** Authoring the legal instrument is significant power —
    super-only vs org_admin-with-approval. Templates + signed PDFs respect the org fence (org-prefixed
    storage keys, cross-org read = 404, `_AdminBase` gates, `test_org_fence.py`).
12. **Front-end quiz becomes dynamic.** Quiz moves from the static typed file to API-served per template
    version; the pass endpoint keys to the version. A modest FE refactor (dynamic render + API i18n).
13. **Testing + go-live gate.** `bursary_e2e` must seed a template; the playbook's "lawyer-vet the
    template" gate becomes the module's publish gate; keep the phantom-term guardrail as a runtime
    invariant.

---

## 7. Sequencing & open decisions

- **The flow is already testable** mechanically (dark, `bursary_e2e`) — no dependency on this module for
  a plumbing test.
- **Do NOT hard-code the amended v2 into `bursary.py` now** — the module owns it; interim edits are
  throwaway and collide with the module work on the same file. The amended v2 lands as org #1 v1 *in the
  module*.
- **Owner is still awaiting the lawyer's FINAL text.** Design the module now; the final text is uploaded
  when it lands (the module makes that a data operation, not a code change — a key benefit).
- **Open decisions for the detailed plan:** (a) upload-PDF-as-reference vs structured-clauses-as-truth
  (challenge 1); (b) who authors + the review/approval gate (3, 11); (c) whether the schedule config
  lives on `ContractTemplate` vs `ScholarshipCohort`/`PartnerOrganisation` per tenancy conventions;
  (d) how the quiz question is authored/stored (4); (e) the language-parity policy (7).

Related: `docs/scholarship/bursary-go-live-playbook.md`, `docs/scholarship/bursary-signer-provisioning.md`,
`docs/build-for-tenancy-conventions.md`, TD-152 (Donor-personal-capacity interim), TD-144 (cockpit ticks).
