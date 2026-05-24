# B40 Decision Engine Redesign — Plan

**Status:** DRAFT for review (2026-05-23) · Planning only — nothing coded yet.
Companion to [b40-phase1-roadmap.md](b40-phase1-roadmap.md) and [b40-assistance-prd.md](b40-assistance-prd.md).

> Supersedes the Sprint 3 model ("synchronous shortlist on submit, pass email immediate")
> and the Phase 1.5b/c behaviour where submit auto-advances the student into the follow-up form.

---

## Why we're changing it

A real test submission landed the student straight on *"You've been shortlisted! Complete these
steps…"* the instant they pressed submit. Three problems:

1. The machine decides **and announces** the verdict in the same breath as submit — feels automated, not considered.
2. It **auto-advances** into the follow-up form. The journey should pause at "received".
3. The old engine treats academics and income as **equal gates**, so a genuinely poor student with
   weak grades is rejected on grades alone — wrong for a need-based assistance programme.

## Locked decisions (this session)

- **Deterministic. No human in the loop.** A formula makes the verdict; **no AI touches the decision**.
- **Decide silently at submit; reveal ≈1 hour later** (email + in-app), so it reads as considered.
- **Need-first.** Results never auto-reject a poor applicant — they're a scored factor (and part of
  the auto-qualify shortcut), not a blanket gate.
- **Per-capita income** (household income ÷ household size) is the need lever in the grey zone.
- **DOSM 2024 bands:** B40 `< RM5,860` · M40 `RM5,860–12,679` · T20 `> RM12,679`.

---

## The decision flow

### Stage 0 — Eligibility pre-filter (hard gates; fail any → decline)
Categorical criteria where need cannot compensate:
- Continuing post-secondary study at a public institution (`intends_tertiary_2026` + pathway).
- Willing to be contacted (consent).
- **[POLICY — open]** Malaysian of Indian descent (pilot scope) — do we collect & verify this, or is
  it self-declared / honour-based at pilot stage? (We may not capture ethnicity today.)

### Stage 1 — Income / merit ladder (eligible applicants only)

| Rung | Condition | Outcome | Bucket |
|------|-----------|---------|--------|
| **1 — Auto-qualify** | Meets income (`< RM5,860`) **AND** academic bar (≥5 A's / PNGK ≥3.0) **AND** receives STR | **Shortlist** | A |
| **2 — Auto-decline** | Household income **> RM12,679** (T20) | **Decline** | — |
| **3 — Formula** | Everyone in between (B40 without STR, near-miss academics, all of M40) | **Score decides** | B if pass |

### Rung 3 — the formula (all weights cohort-configurable, illustrative)

| Factor | Source | Weight |
|--------|--------|--------|
| **Need** — per-capita income (lower = more) | `household_income ÷ household_size` | ~50 |
| **Family** — dependents / household size | `household_size` | ~15 |
| **Hardship** — structured flags (tick-boxes) | new intake fields | ~20 |
| **Results** — merit tiebreak only | `grades` / `stpm_cgpa` | ~15 |
| | **Pass mark** | **50 / 100** |

Per-capita need bands (illustrative — you set; Malaysian per-capita poverty line ≈ RM500–600/head):
`< RM500/head` = full need points · `RM500–1,000` = high · `RM1,000–1,500` = moderate · `> RM1,500` = low.

### Reveal (≈1 hour after submit) — via the existing scheduler
- **Shortlisted** → invitation email ("complete your application here:" + link) · status → `shortlisted`
  · follow-up form unlocks · in-app banner/link on next login.
- **Not shortlisted** → gentle "not this round" email (also at +1h). *Recommended; you may choose silence.*

The student's whole experience: **Submit → "Application received" + ack email → (≈1 h) → invitation _or_
kind decline → only then the deeper form opens.**

---

## Open policy decisions (yours — to set before/while building)

1. **Descent** — collected & verified, or self-declared/honour at pilot?
2. **Academic bar in Rung 3** — hard floor (miss → out) or scored factor only (need-first)?
   *Recommend: scored factor, with an optional minimum-A's floor you can set per cohort.*
3. **Per-capita bands + factor weights + pass mark** (the numbers in the table above).
4. **Hardship flag list** — e.g. single parent, OKU/disability, orphan, sole-breadwinner loss, many dependents.
5. **Decline email** — send a gentle note, or stay silent?
6. **Reveal delay** — confirm 1 hour.

---

## Engineering build

### Sprint 7a — backend
1. **`shortlisting.py`** — rewrite to the 3-rung model. Stays a pure function (no DB writes, no email):
   `eligibility_prefilter()` (Stage 0) → `rung1/rung2` checks → `rung3_score()` (per-capita formula).
   Returns `verdict` (shortlisted/rejected) + `bucket` (A/B) + `reason` + `score_breakdown`.
2. **`models.py` + migration 000X**
   - `ScholarshipCohort`: set `income_ceiling = 5860`; add `t20_decline_ceiling` (12679),
     `pass_mark`, factor weights + per-capita bands (JSON), `decision_delay_minutes` (default 60).
   - `ScholarshipApplication`: add `verdict` (silent computed outcome, pre-release), `decision_due_at`,
     `score` (int), `score_breakdown` (JSON), `decision_released_at`. Status stays `submitted` until release.
3. **`views.py` submit** — stop the instant decision + instant pass email. Score **silently**, store
   `verdict`/`bucket`/`score`/`decision_due_at`, keep status `submitted`, send **only** the ack email.
   The follow-up gate stays `status == 'shortlisted'` (only true after release).
4. **`services.py`** — split into `score_application()` (silent, at submit) and
   `release_decision()` (flip status, send invite/decline, unlock, stamp).
5. **`send_pending_decision_emails`** — generalise from "fail email only" to **release all due decisions**:
   any `submitted` app with `decision_due_at <= now` → flip status to its `verdict`, send invite
   (shortlisted) or decline (rejected), stamp. Driven by `decision_delay_minutes`. Keep `--dry-run`.
6. **`emails.py`** — repurpose the "pass" email as the **invitation** email; keep ack + decline.
7. **Tests** — rung boundaries (the four corners around RM5,860 and RM12,679); per-capita formula;
   STR auto-qualify; **need-first** (poor + weak grades → considered, not auto-rejected); release timing;
   idempotency (don't double-send / double-release).

### Sprint 7b — frontend
8. After submit → **"Application received — we'll be in touch"** screen (no follow-up).
9. **`scholarship/application`** — `submitted` → "received / under review"; `shortlisted` → existing
   follow-up; declined → gentle closed state.
10. **Login banner/link** when the user has a shortlisted application.
11. **Intake form** — add the structured **hardship tick-boxes**; write to profile/application; EN/MS/TA i18n.
12. i18n parity (check-i18n) + jest + `next build`.

### Data + deploy
13. **Cleanup** — reset test application **#1** → `submitted`; clear its test income (RM2,000 write-back).
14. **Cohort `b40-2026`** — `income_ceiling=5860`, `t20_decline_ceiling=12679`, `decision_delay_minutes=60`,
    weights + pass mark.
15. **Wire Cloud Scheduler → `send_pending_decision_emails`** (Cloud Run Job, ~every 15 min).
16. Test locally (`runserver`) → **single deploy** → prod smoke-test (submit → received → +1 h → verdict).
    *Not publicly launched yet (gated on Phase 0), so changing the live flow is safe.*

---

## Notes
- **Audit determinism:** score against `intake_snapshot` (the immutable copy taken at submit), not the
  live profile, so a later profile edit can't change a past verdict. *(Refinement — confirm.)*
- **Buckets retained** for the admin/sponsor view: **A** = auto-qualified (Rung 1), **B** = passed via
  the formula (Rung 3).
- Sizing: ~12–18 files across 7a/7b — one focused sprint, split backend/frontend per the existing pattern.

---

## Identity / NRIC handling — Option A chosen (2026-05-23)

**NRIC is "soft" until verified** — mirror the existing email-verified pattern.
- Add **`nric_verified`** (bool, default false) to `StudentProfile`.
- **Unverified** → the student can see and edit their own NRIC (re-validated each time: format,
  age 15–23, valid state code) — in the **apply form** *and* on the **profile page** (unlock the
  currently-disabled field).
- **Verified + locked** → happens when the **admin reviews and accepts the application** ("moves it
  forward"). At that step the admin works through an **explicit verify checklist** — a few items to
  confirm, **including the NRIC** (plus name, results, uploaded document). Accepting sets
  `nric_verified=true` and **locks** the NRIC (student read-only; admin override only). Until then the
  student can keep editing it.
- **Uniqueness relaxed to verified-only:** drop `unique_nric_when_set` (unique where `nric<>''`);
  add `UNIQUE(nric) WHERE nric_verified`. Duplicate *unverified* NRICs are allowed (a typo of
  someone else's number won't hard-error or block submit); the clash surfaces at verification, where
  only one NRIC can be verified and the admin resolves it. Existing 493 NRICs start **unverified**.
- Close the `PUT /profile/` gap: NRIC only ever changes through the **validated** path, never an
  unchecked write.
- Minor/guardian-consent gate recomputes from the (now editable) NRIC birth-date on each change.
- **Google Vision OCR — automatic, instant feedback (on the application page).** The MyKad is uploaded on
  the **post-shortlist application page** (shortlisted students only). On upload Vision runs
  **synchronously**: checks the image is readable, extracts the printed 12-digit NRIC, compares it to the
  entered NRIC. The student gets an **immediate verdict** ("✓ accepted" / "✗ couldn't read — upload a
  clearer photo") and can re-upload on the spot. **Vision does not verify or lock** — it's an assistant:
  instant feedback for the student, and it surfaces its result to the admin (e.g. "Vision: NRIC matches ✓").
  **Soft, never a hard block** (OCR can fail on a legitimate card → admin fallback). The actual verify+lock
  is the admin's "verify & accept" step above. Image in the private `b40-documents` bucket (PDPA); Vision
  cost negligible at this volume.

## Apply form — inline-editable, commit on submit (2026-05-23)

Replaces the Phase 1.5a "profile read-only in apply; Edit bounces to /profile" pattern.
- **About You** is open and pre-filled from the DB: **name, school, NRIC editable; contact email
  locked** (already verified). Removes the "Edit → /profile" bounce and the read-only
  "From your HalaTuju profile" treatment for these fields.
- **Nothing persists until `Submit Application` succeeds** — edits live in form state, then on a
  successful submit the profile fields (About You + financial) are written back, the
  `intake_snapshot` audit copy is frozen, and the application is created. A failed submit persists nothing.
  *(This unifies the old "financial section writes back while editing" into a single commit-on-submit.)*
- **Section headings go first-person** (the student is describing themselves): **About Me, My Family,
  My Results, My Plans, My Support**. **Tab labels stay short** as now (About / Family / Results / Plans /
  Support). *("My Support" wording may change once that section's content is finalised.)*
- **About Me field set** — all pre-filled from the DB, editable, committed on submit (email locked):

  | Field | Source | Input |
  |---|---|---|
  | Full name | `profile.name` | text |
  | School | `profile.school` | text |
  | NRIC | `profile.nric` | validated text (soft until verified) |
  | Contact email | `profile.contact_email` | **locked** (verified) |
  | Referring organisation | `profile.referred_by_org` | dropdown of active partner orgs (e.g. CUMIG) |
  | Home state | `profile.preferred_state` (the existing onboarding "State" field) | dropdown |
  | Phone | `profile.contact_phone` | text (format `01X-XXX XXXX`) |

- **[To confirm]** Editable scope = About Me + financial section. **Academic/results stays
  read-from-profile** (with the existing quiz prompt), not inline-editable here.
- **Required fields** marked with a red `*` and enforced on submit: name, school, NRIC, referring
  organisation, home state, phone. (Contact email is given/locked; financial income + consent already required.)
- **Info tooltips** — an `i` icon with a hover/tap popover on fields that need explaining, e.g. referring
  org ("the organisation or coordinator who told you about this"), school ("where you sat for SPM"),
  phone ("Format: 01X-XXX XXXX"), NRIC ("used to confirm your identity; editable until it's verified").
- **Referring-organisation options** (from the legacy form): Sri Murugan Centre (SMC), Concerned UM Indian
  Graduates (CUMIG), Ms. Pushparani (Kapar), Sathya Sai Baba Centre, Halatuju.xyz, Tara Foundation,
  Mr. Govind (Melaka), Facebook / WhatsApp, Other. Named orgs → `PartnerOrganisation` rows (seed/confirm);
  the rest are generic sources.
- **Required fields carry both a red `*` *and* an `i` tooltip** (rule: if it's required, it gets an info note).

### My Family (section 2) additions
- **Parent/guardian info:** parent/guardian **name**, **phone**, and **preferred language for calls**
  (English / Bahasa Malaysia / Tamil / Mixed). Stored on the profile (`guardians` JSON / dedicated
  fields — map at build).
- **Household income — open numeric field (exact RM), required.** Kept as an exact figure (not brackets)
  so the engine computes true **per-capita income** (income ÷ household size). No "Prefer not to say".
- **Household definition (confirmed)** — `i` tooltip:
  *"Count everyone who normally lives in your home and shares income or expenses — your parents/guardians,
  you, your brothers and sisters, and grandparents or relatives living with you. Include a working sibling
  if they live at home and contribute; don't count family who live elsewhere."*
- **Income = combined income of _everyone counted_, not just parents (confirmed)** — `i` tooltip:
  *"Add up the monthly income of everyone you counted — salaries, business, pensions, and government aid
  (not just your parents'). An estimate is fine."*
- STR / JKM toggles stay.

### My Results (section 3)
Display the academic record **pre-filled from the profile** (the single structured source that also powers
course matching). **Not inline-editable here** — grades are structured (subject-by-subject) and a free-text
list can't drive eligibility; edits go through the proper grade-entry flow.
- **Four data points shown:** exam type (SPM/STPM); A-count (SPM) / CGPA + MUET (STPM) — **exam-type-aware
  heading**; subjects & grades (formatted from stored grades, e.g. "BM A+, BI A, …"); co-curricular score.
- **Co-curricular score — persist it (decided).** Add a `coq_score` field to `StudentProfile`, save it in
  the onboarding co-curricular step (today it's transient), and pre-fill it in Results — treated like any
  other stored academic value.
- **Edit / add results → full onboarding, then return (decided).** Both cases route to **/onboarding/exam-type**
  with a **return marker** and run the **complete** onboarding (exam type → grades → electives → co-curricular →
  "A few more details": state / nationality / gender / special-needs), so the profile ends up **complete for
  course recommendations too** (user's intent):
  - **No results yet:** Results shows an empty state → "Add your results" → onboarding.
  - **Has results (maybe careless):** "Results wrong? Edit" → same onboarding to review/fix.
  On the **final step's button** the return marker sends them **back to the apply Results tab** (updated)
  instead of the dashboard. *(Resolves deferred "Issue 4": today's link points to /profile, no results editor.)*
- **Final onboarding button — context-aware label (decided):** "See My Recommendations" normally;
  **"Save & return to application"** when a return marker is set — so it always says what it will do.
- **Preserve in-progress apply edits across the detour:** the apply form only writes on Submit, so before
  leaving for onboarding we **stash** the current About Me / My Family edits (sessionStorage) and **restore**
  them on return — otherwise they'd be lost. The academic summary re-reads from the (now-updated) profile.
- Legacy Google Form collected these as plain/free-text fields; ours derives them from the structured profile,
  so they stay a single source of truth (and power eligibility/merit too).

### My Plans (section 4) — proposed (under discussion)
**Leverage HalaTuju's edge:** it already computes each student's **eligible pathways + ranked courses**
(dashboard: "281 courses · Matriculation / Asasi / Poly / University / Kolej Komuniti / ILJTM / ILKBS"). So the
student builds a **concrete top-3 from their *actual* eligible options** rather than free-texting plans — which
doubles as the **seriousness signal** (structured, no AI).
- **Exam-type-aware:**
  - *Post-SPM:* multi-select **pathways considering** (non-exclusive — "keep STPM as a backup") from qualified
    pathways; then **ranked top-3 specific course choices** from eligible courses.
  - *Post-STPM:* **ranked top-3 university programme** choices from eligible courses.
- **IPTS gate — hard disqualifier (decided):** **IPTS-only intent → ineligible** — the scholarship is too small
  to cover private-institution fees. All public pathways are fine; IPTS as a *backup* alongside a public choice is OK.
- **Top-3 from eligible courses (decided)** — concrete, validated, doubles as the clarity signal.
- **Plans data feeds the sponsor profile (decided)** — pathways / choices / field present the student to sponsors.
- **Clarity / focus signal — reframed (decided): NOT a reject lever.** A student who looks lost/unfocused is *not*
  rejected for it; instead it (a) informs **sponsor preference** (sponsors may favour focused students) and
  (b) **flags them for mentoring** — HalaTuju guides them to clarify their path rather than dropping them.
  Deterministic shortlisting stays purely **need + merit**; clarity is a presentation + support layer, captured as
  a coordinator-facing **mentoring-candidate flag** (mentoring delivery itself is ops / Phase 2).
- **Field of study** (dropdown, reuse field taxonomy). **Other scholarships applied/held** (JPA/Petronas/MARA…,
  decided OK) → **funding-overlap** signal (already-funded students are lower-priority for need-based aid).
- **Career-aspiration narrative → post-shortlist STEP 2** (feeds the sponsor profile, which is generated post-shortlist anyway).

### Support I'd Like (section 5)
Bring in the legacy form's support questions — they double as **mentoring / support signals** and feed the sponsor profile.
- **Would you like help with university applications?** (Yes / No / Not sure) — choosing courses, forms, personal statements.
- **Would you like help with scholarship applications & interviews?** (Yes / No / Not sure) — mock interviews, feedback.
- **Anything else you'd like us to know?** (optional free text) — special circumstances, concerns, questions.
- **Consent to be contacted** stays here (required, initial apply). The deeper *"why you need assistance"*
  justification moves to **post-shortlist STEP 2** (feeds the sponsor profile).
- **How used:** the two help questions → **mentoring / support flags** (what help to offer; ties to the Plans
  "mentoring-candidate" idea) + sponsor-profile context. The free text is **narrative context only** — the
  **structured hardship flags that feed the decision are separate** (disability/OKU etc. are tick-boxes, not parsed from prose).
- **Decided:** (a) **merge** the free text into one **optional** "Anything else you'd like us to know?" box at
  initial apply; deeper justification → post-shortlist. (b) the two help radios are **optional**. (c) heading = **"Support I'd Like"**.

---

## Implementation roadmap (Sprints 7–12)
*Per `implementation-planning.md`. Builds on Sprints 1–6 (done). ~≤20 files/sprint. **Work on a feature branch
(e.g. `feature/b40-redesign`); main stays clean; single deploy at S12** (apply flow not publicly launched). Not started — awaiting approval.*

**S7 — Backend foundation: soft-NRIC + coq + new intake fields.** *(no policy calls)* — ✅ **built 2026-05-23, 1091 backend tests green** (commit at sprint close)
- Scope: `nric_verified` + relax unique → verified-only + close `PUT` gap + claim-edit-until-verified + transfer-bug fix;
  `coq_score` field + persist in onboarding/sync; add new intake fields (parent name/phone, call language, field of study,
  pathways-considered, top-3, other-scholarships, support-needs, hardship flags, IPTS/UPU intent, mentoring flag) + one
  migration + serializers. Tests.
- Acceptance: NRIC editable-until-verified + unique-only-when-verified at API; coq persists; new fields round-trip; suite green.
- Complexity: Medium (~16 files).

**S8 — Decision engine + silent-score + delayed reveal (backend).** *(policy calls settled)* — ✅ **built 2026-05-24, 1093 backend tests green** (commit at sprint close)
- Scope: rewrite `shortlisting.py` → 3-rung (eligibility pre-filter incl. IPTS-only/consent/intends-tertiary/descent;
  Rung1 B40+STR auto; Rung2 >T20 auto-decline; Rung3 per-capita formula; need-first) + score breakdown; split
  `score_application` (silent at submit) / `release_decision`; submit → ack-only + "received" + store verdict + `decision_due_at`;
  generalise `send_pending_decision_emails` to release both verdicts at +1h; invitation email; model verdict fields. Tests.
- Acceptance: submit → received+ack; +delay → verdict email + status flip; engine unit tests (rung boundaries, need-first, timing) green.
- Complexity: High (~15 files). **Gated on the 6 policy calls.**

**S9 — Apply form rebuild ①: About Me + My Family (frontend).** — ✅ **built 2026-05-24, backend 1095 / frontend 44 jest green, mobile build approved via local screenshot** (commit at sprint close). *(RE-SCOPED 2026-05-24 — My Results' onboarding-return mechanism split to S9b; desktop responsiveness deferred to S12 per user.)*
- Scope: inline-editable About Me (name/school/NRIC validated, email locked, org/state/phone) + My Family (exact income,
  household/income tooltips, parent info, lang, STR/JKM) + My Results (pre-filled display; edit → /onboarding/exam-type
  return-marker + context-aware final button + stash/restore in-progress edits); required `*`+`i`; commit-on-submit scaffolding; EN/MS/TA i18n.
- Acceptance: sections pre-fill + edit; onboarding round-trip returns to Results; jest + check-i18n + build green.
- Complexity: High (~20 files).

**S9b — My Results edit → onboarding round-trip (frontend).** — ✅ **built 2026-05-24, frontend 44→49 jest, build + i18n green** (commit at sprint close). Split out of S9. My Results edit/add → full onboarding → context-aware "Save & return to application" final button → back to apply; in-progress edits stashed/restored via sessionStorage (storage-injectable helpers); orphan marker cleanup + TD-057 for the abandon edge.

**S10 — Apply form rebuild ②: My Plans + Support + "received" screen (frontend).** — ✅ **built 2026-05-24, frontend 49 jest, build + i18n green, mobile build approved via screenshot** (commit at sprint close). *(no policy calls; top-3 sourced from **saved courses** [decided 2026-05-24], not a fresh eligibility recompute; "received" screen already worked from S8 silent-score; frontend only — backend fields accepted since S7.)*
- Scope: My Plans (pathways multi-select; top-3 from saved courses; UPU/IPTS question; field; other-scholarships);
  Support I'd Like (help radios, optional "anything else", consent); commit-on-submit final wiring; post-submit
  **"Application received"** screen (replaces auto-advance); EN/MS/TA i18n.
- Acceptance: full form submits → received; no auto-advance; persists only on success; green.
- Complexity: High (~16 files).

**S11 — Application page + admin verify-&-accept + NRIC lock + mentoring (full-stack).** *(split 2026-05-24)*
- **S11a — admin verify-&-accept + NRIC lock + mentoring (backend + admin).** — ✅ **built 2026-05-24, backend 1100, build + i18n green, admin card approved via screenshot** (commit at sprint close). `AdminVerifyAcceptView` (checklist → `nric_verified` lock + advance shortlisted→**accepted** [new status]); audit fields + migration `0009`; mentoring PATCH; **TD-054 resolved** (uniqueness enforced at verify, 409 on verified-duplicate); admin `/admin/scholarship/[id]` verify card + mentoring toggle.
- **S11b — applicant application page states + login banner (frontend).** — ⏳ next. Status-driven `/scholarship/application` (submitted=received · shortlisted=follow-up · accepted=confirmed · rejected=neutral) + dashboard login banner when shortlisted/accepted.
- Acceptance: admin verify+accept locks NRIC + advances (S11a ✅); student sees correct state (S11b); green.
- Complexity: High (~18 files; split into ~9 + ~5).

**S12 — Vision OCR + desktop responsiveness + config + deploy.**
- Scope: Google Vision OCR on MyKad upload (instant feedback + re-upload, surfaced to admin); desktop-responsive apply +
  application pages; cohort `b40-2026` config (income_ceiling 5860, t20 12679, delay 60m, weights, pass-mark); wire
  Cloud Scheduler → `send_pending_decision_emails`; reset test data; **single deploy**; prod smoke-test.
- Acceptance: Vision feedback works; responsive verified; scheduler runs; end-to-end prod smoke passes.
- Complexity: Medium-High (~15 files).

**Total: 6 sprints.** Order = dependency + risk: foundation (S7) → engine (S8, riskiest) → frontend (S9–S10) → admin/lock (S11)
→ integration + deploy (S12). **S8 is the only sprint gated on the 6 policy calls** — so we can start **S7 now** and settle the
policy calls before S8 (or reorder S9–S10 ahead of S8 if you'd rather keep deferring them).

---

## Decision engine — FINAL (policy calls settled 2026-05-23)
*Supersedes the earlier exploratory "3-rung + weighted 0–100 score + per-capita bands + hardship flags" sketch.
The settled logic is a simple deterministic rule — no score, no weights, no pass mark, no hardship flags.*

**Inputs** (already on profile/application): `grades` / `stpm_cgpa`, `receives_str`, `household_income`,
`household_size`, `upu_status` (IPTS), `consent_to_contact`, `intends_tertiary_2026`.

**Decision (computed silently at submit):**
1. **Hard gates** — fail any → DECLINE: consent given; intends public post-secondary study; **not IPTS-only**
   (`upu_status='ipts'` with no public pathway). **No descent check — open to all (#1: "we don't want to know").**
2. **Academic floor** — fail → DECLINE: SPM **≥4 grades at A- or better AND ≥1 further grade at B+ or better**
   (≥5 strong subjects; A- counts as an "A" — engine `A_GRADES` = {A+, A, A-}, plus a ≥B+ check) · STPM **PNGK ≥ 2.9**.
3. **Income test:**
   - **STR recipient → PASS** (income-qualified; STR = govt-verified low income).
   - **No STR → per-capita income** = `household_income ÷ household_size`; **< RM1,584 → PASS**, else DECLINE.
     (RM1,584 = B40 ceiling RM5,860 ÷ avg household **3.7** [DOSM 2024]. Per-capita naturally rejects T20 and is
     fairer to large families — **replaces** the household RM5,860 / RM12,679 gates.)
4. **Outcome:** pass all → **SHORTLIST** (Bucket A if STR, Bucket B if via income test); else **DECLINE**.

**Dropped (per #3/#4):** the 0–100 weighted score, per-capita bands, factor weights, pass mark, and hardship
tick-boxes — per-capita income already accounts for household size/dependents, so it captures need; STR is the
verified-need fast path. Clarity/hardship remain **sponsor-profile + mentoring signals only**, never reject.

**Reveal (silent → "received" → delayed email + unlock) — #6:**
- **Shortlisted: +2 hours** → invitation email + follow-up unlocks.
- **Declined: +48 hours** → warm decline email.
- Two cohort-config delays: `success_delay_hours=2`, `decline_delay_hours=48`.

**Emails — #5:**
- Ack (at submit): "received".
- Invitation (+2h, shortlisted): "you've been shortlisted — complete your application".
- Decline (+48h): **warm** — *"not successful for this scholarship this round; all the best in your studies;
  you're welcome at the higher-education seminars we run (online/offline) — we'll send you the invites."*
  (Keeps declined students in the HalaTuju community → implies a seminar-invite list.)

**Confirmations (settled 2026-05-24):**
- **A.** ✅ SPM floor = **≥4 at A-/A/A+ and ≥1 further at B+** (≥5 strong subjects; A- is the minimum "A").
  Engine: `count(grade ≥ A-) ≥ 4` AND `count(grade ≥ B+) ≥ 5`.
- **B.** ✅ Per-capita RM1,584 is the **sole** income gate for non-STR (no separate household RM5,860 / RM12,679).
- **C.** ✅ STR auto-passes **only the income test** — STR students still need the academic floor + hard gates (STR ≠ auto-shortlist).
- **D.** ✅ **Public copy stays as-is** — `/scholarship` keeps advertising "Indian descent (pilot)" + "5 A's / PNGK 3.0".
  The engine is **intentionally more lenient** (no descent; 4A+1B+ / 2.9) to **accommodate students who barely
  miss** the advertised bar — under-promise on the page, be generous in practice. **No frontend copy change.**

**→ All 6 policy calls settled. S8 (decision engine) is unblocked.**
