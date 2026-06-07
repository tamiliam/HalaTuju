# Check 2 — Submission review, queries & profile generation (design)

**Status:** Design — not yet built. Author: Claude (pipeline/cockpit workstream).
**Sits between:** student **submit** (`profile_complete`) → reviewer **assignment** (Check 3).
**Anchors already in `b40-phase-ef-prd.md`:** the SLA gate
`is_ready_for_assignment(app) = (open_queries == 0) OR (submitted_at + SLA lapsed)`, the new
`ScholarshipCohort.query_response_sla_days = 5`, and the **B1 allowlist** (withhold name / IC /
phone / email / street / photo for student **and** parents). This doc specifies the AI's role
in that window and the single sponsor-facing profile.

---

## 1. Purpose

When a student submits, turn a raw application into either (a) a clean, sponsor-ready profile,
or (b) a profile **plus** a short list of open queries for the student and suggested questions
for the human reviewer — without ever asserting an unverified claim to a sponsor.

Two jobs, in the user's words:
- **AI** resolves what is *factual and answerable in a sentence*.
- **Human reviewer** resolves what only a conversation can: nuance, motivation, sensitivity,
  and the genuine risk that she can't continue.

## 2. State machine

| Step | Trigger | Actor | Output |
|---|---|---|---|
| **STEP 1 — Review** | on submit (`profile_completed_at` set) | AI | a *facts ledger* (every candidate claim + its verification status) + a gap/inconsistency list |
| **STEP 2 — Resolve** | immediately after STEP 1 | AI | student queries (Action Centre + email) **and/or** items assigned to the human; the **5-day clock starts** |
| **STEP 3 — Generate** | student answers all queries **OR** 5 days lapse (whichever first) | AI | the single sponsor-facing profile from currently-available info; unresolved claims omitted/hedged |
| **STEP 4 — Refine** | after the reviewer files findings / new query answers arrive | AI | regenerated profile incorporating new info; if nothing new, the STEP-3 profile stands |

`is_ready_for_assignment` becomes true at the STEP-3 trigger → the app enters the reviewer
queue. On lapse with queries still open → **proceed-as-is, flagged for the reviewer** (never
block the pipeline).

## 3. STEP 1 — AI submission review

The AI runs three checks; **"verified/accurate" is NOT the LLM's call** — it reads the
deterministic layer:

1. **Completeness** — do we have what a compelling, *fundable* profile needs? (transport
   numbers, device status, sibling level, chosen course, motivation.)
2. **Verified** — every claim the profile will make must map to one of: a **verdict fact**
   (Identity/Academic/Pathway/Income, already computed), a **structured field**, a **read
   document**, or a **resolved query answer**. Anything else is "unverified" and cannot be
   asserted. (The LLM judges consistency, *not* truth.)
3. **Consistency** — narrative vs structured data vs documents: contradictions and
   ambiguities (e.g. *ijazah sarjana* = Bachelor's or Master's? "first-to-university" vs a
   sibling in tertiary? utility spend that looks high for the stated income?).

### Signals STEP 1 MUST ingest (today's gaps — prerequisites)

The current generators ignore real data. STEP 1 has to use **all** of it:

- **P1 — Read the letter of intent (`statement_of_intent`).** Today it is uploaded and never
  OCR'd (no `student_verdict`, no fields). Route it through extraction so its text is available
  — it is the richest source of *motivation* ("why teaching") and may surface strain the form
  doesn't.
- **P2 — Use & display the sibling split.** `siblings_in_school` / `siblings_in_tertiary` exist
  (the form's two counters) alongside the legacy `siblings_studying_count`. **Migrate the legacy
  count into the split and treat the split as authoritative (Q3)** — backfill where possible;
  where it can't be split (e.g. #18's legacy `=1`, both split fields null) it stays a
  clarify-query. Use the split to **auto-resolve the "first-to-university" flag** (tertiary = 0
  ⇒ first-gen holds) instead of raising a query the data already answers; and **surface the
  counts in the cockpit** (currently shown nowhere).
- **P3 — Use utility & EPF values, not just presence.** The income engine reads utility bills
  and EPF for soft signals but the *amounts* never reach STEP 1. Feed: utility per-capita +
  an **"utility spend high vs stated income"** inconsistency signal; EPF balance as a
  corroborating hardship signal (negligible balance supports a genuine-need case). These are
  reviewer flags, not gates.

## 4. STEP 2 — Resolution: AI-query vs assign-to-human

**The triage rule:**

- **AI → student query** (Action Centre ticket + email; answerable in one line; factual;
  non-sensitive):
  - Device: *"Do you have a laptop/tablet to study on, or would you need one?"*
  - Pathway specificity (if blank): *"What course do you plan to take after STPM?"*
  - Degree ambiguity: *"Your 4-year 'ijazah sarjana' — is that a Bachelor's degree?"*
  - Sibling level — **only if** the split is missing: *"Is your sibling in school, or in
    college/university?"*
  - Transport *cost* (the number): *"How do you travel to school, and roughly what does it
    cost a month?"*
- **Assign to human** (surfaced as the reviewer's suggested questions — see §7):
  anything subjective, sensitive, judgement-based, or requiring conversation. Per the advisor:
  household monthly **shortfall / award sizing**; the **texture** that converts a sponsor
  (concrete teaching detail, motivation in her voice, what the support changes, resilience);
  and the **continuation-risk** check.

**One consolidated query stream.** Do not add a fourth system. Check-2 queries reuse the
`ResolutionItem` model + Action Centre, with a `kind` that distinguishes:
`doc` (re-upload, existing) · `clarify` (Check-2 AI student query, new) · `human` (for the
reviewer, not shown to the student). Anomaly flags + interview-gap questions feed the
reviewer's suggested-questions list, not the student's queue.

**Cap the student's queries** to the 2–3 most material. The student is not the reviewer; a
long list suppresses responses and burns the clock. (The current AI produced 5 interview gaps
— that volume is fine for the *reviewer*, not the student.)

**Firewall:** the student-query generator gets only non-sensitive inputs (no scores, no model
objects, no admin data) — same contract as `generate_document_help`.

## 5. The 5-day SLA clock

- Starts at submit. `query_response_sla_days` (cohort field, default 5).
- STEP 3 fires on **all clarify-queries answered** OR **clock lapse**, whichever first.
- On lapse with open queries → profile generated with gaps; app flagged
  `ready-with-open-queries` for the reviewer. Reuse the completion-reminder cron + email
  pattern (already in `services.send_application_reminders`).

## 6. STEP 3 / STEP 4 — The single sponsor profile

**One profile, not two.** The named "draft" is retired — the reviewer reads identity from the
**About** panel; sponsors read the single PII-redacted profile.

**Redaction (per the user, lighter than the PRD's current B1):** withhold only **name, IC,
contact details, street address** — for the student **and** the parent. **Shown:** alias
(`Scholar-XXXX`), state, school/institution, results + merit, pathway, funding need, and the
narrative. ⚠️ This is **re-identifiable to an acquaintance** by design. **Decision (Q4):** the
current consent — *"we will share your details with sponsors"* — covers this for now, so we
build against the lighter redaction today; the precise shown-vs-withheld wording (and the
lawyer bundle / B1 reconciliation) is **narrowed and aligned at the award stage**, not now.

**Claim-gating contract (the core fix).** The generator receives the STEP-1 facts ledger and
**asserts only verified claims**. Unresolved/contested → omit or hedge, never state as fact.
This is the bug behind the live output asserting "first-generation" (a flagged claim) and
silently resolving Bachelor-vs-Master. Concretely: *"first in her family to reach university"*
appears **only if** verified (tertiary-sibling = 0 or the query is answered).

**Tone guardrail (per the advisor).** Honest and dignified; factual warmth, not fundraising
melodrama. Do **not** mine hardship for sympathy ("ripple effect / breaking the cycle" →
out). Grief and poverty are real and may be assets to the case, but are handled with restraint.
Target: the user's "Scholar-0001" example. Accuracy notes: "10 A's" → state the actual band
mix honestly ("ten distinctions, A+/A/A−"); don't invent specifics ("younger" sibling).

**STEP 4** re-runs the generator with query answers + the reviewer's findings; otherwise the
STEP-3 profile stands. (The existing "Refine with interview findings" button becomes the
STEP-4 trigger.)

## 7. The human reviewer's role (from the advisor)

The AI hands the reviewer a **suggested-questions** pack (not student-facing), in two buckets:

**a) Fill genuine gaps** — transport (distance/mode/monthly cost; is the Pulau-Sebang place
now resolving the distance worry?); household monthly **shortfall** (to size the award against
real need); the **device** question; the **sibling's level** (one cost or two).

**b) Strengthen the case** — one concrete, vivid **teaching detail** (how many children, what,
does she enjoy it — a student already teaching while sitting her own exams is a far stronger
"future teacher" story); **why teaching** in her own voice; **what the support changes** in her
words; **resilience, lightly** (let her tell it, don't extract it clinically).

**Handling the sensitive parts:** let her offer detail rather than interrogating; be ready for
something harder than the form shows (18, just started Form 6, sole-earner mother). The goal is
a profile that is *honest and dignified*, not one that mines hardship.

**Continuation check (quiet, not assumed):** verify she can actually take up the place and that
nothing at home is about to pull her out — if there's a real risk, a sponsor should know it's
being managed, not discover it later.

The reviewer **must file a findings report** (the existing interview-capture surface) → feeds
STEP 4.

## 8. Data-model additions

- `ScholarshipCohort.query_response_sla_days` (int, default 5).
- `ResolutionItem.kind` extended: `clarify` (Check-2 student query), `human` (reviewer-only).
- A nullable `query_first_raised_at` (or reuse `submitted_at`) for the SLA clock.
- No new student-pipeline status (the gate is timestamp/criterion-based, per the PRD).

## 9. Prerequisites to fix first (small, independent)

These block STEP 1 from "using all the information" and are worth doing up front:
- **P1** read `statement_of_intent` (extraction pipeline membership).
- **P2** display + use the sibling school/tertiary split; auto-resolve the first-gen flag.
- **P3** surface utility + EPF *values* and the high-utility-vs-income inconsistency.

## 10. Cross-agent boundary

The **profile generator + sponsor pool** is the *sponsor/E-phase agent's* territory
(`pool.py`, `scan_anon_for_identifiers`, the generation prompt). **Check 2 (this doc)** is the
pipeline: STEP 1 analysis, the query model, the SLA clock, the triggers. Interface contract:

- Check 2 **produces** the facts ledger (claims + verification status) and **triggers**
  generation at STEP 3 / STEP 4.
- The generator **consumes** the ledger and **gates claims** on it (the §6 contract).

Neither edits the other's core. Agree this seam before coding so the two workstreams don't
collide.

## 11. Resolved decisions (2026-06-07)

- **Q1 — Transport cost → BOTH.** AI raises a student query for the *number* (mode + rough
  monthly cost); the human reviewer explores the *nuance* (is the distance worry resolved by
  the confirmed Pulau-Sebang place, or still live).
- **Q2 — Advance on last-query-answered.** STEP 3 fires the moment the final clarify-query is
  answered (no dwell), or on clock lapse — whichever first.
- **Q3 — Migrate the legacy sibling count into the split; the split is authoritative.**
  Backfill `siblings_studying_count` into `siblings_in_school` / `siblings_in_tertiary` where
  possible; thereafter read the split. (Where the legacy count can't be split — e.g. #18's
  `=1` with both split fields null — it stays a clarify-query: "is your sibling in school or in
  college/university?")
- **Q4 — Consent alignment deferred to the award stage.** For now the consent says simply *"we
  will share your details with sponsors,"* which covers the lighter redaction. We will
  narrow/align the exact shown-vs-withheld wording (and the lawyer bundle) **at the award
  stage**, not now. So §6's redaction is acceptable to build against today.
