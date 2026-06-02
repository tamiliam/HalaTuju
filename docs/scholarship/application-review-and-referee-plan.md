# Submission Review page + Student Referee — Implementation Plan

**Status:** PLANNED — **not started.** Written 2026-06-02 after a critical evaluation
(workflow `evaluate-submission-summary-page`) + design discussion. Pick this up
**only after the Verification-Verdict branch is deployed/merged to `main`.**

> One reusable "review your complete application, then consent" gate at the
> `/application` submit — plus wiring the student to provide a referee, so the
> application the student attests to (and the officer audits) is **complete**.

---

## 1. Why these two together

A complete B40 application has one missing intake field — a **referee** the
*student* provides (today the referee is admin-only; the student never gives one —
see the verdict plan's "Parked" section). And at the moment the student finalises,
there is **no chance to review everything before an irreversible consent/submit**.

Both are about making the **`/application` submit moment** honest and complete:
the student should add their referee, then see their *whole* application on one
page, fix anything wrong, and only then consent. So we ship them together.

---

## 2. Settled design decisions (from the evaluation + discussion)

1. **Placement = the post-shortlist `/application` flow, at the Consent step** —
   NOT the pre-shortlist `/apply` form. Rationale: at the Consent moment **all the
   data finally exists** (the `/apply` intake *plus* Story, Funding, Documents,
   Consent, and the referee), so a summary can honestly show *everything*. At
   pre-shortlist `/apply` half the application doesn't exist yet. (This supersedes
   the evaluation's earlier `/apply` lean — the user's "consent as submit" placement
   is sharper.)
2. **Consent stays the submit.** The review summary sits **above** the existing
   consent/attest; ticking consent + the existing final action is still the single
   terminal click. We are **not** adding a second submit button — we are giving the
   consent moment a "review everything first" page.
3. **No annual re-review.** (Considered — the IBKR periodic-KYC pattern — and
   explicitly declined for HalaTuju. Build the application-time review only.)
   Design the review as a clean read-only renderer, but do **not** build any
   recurring/attestation-cycle machinery.
4. **Edit = jump back to the relevant tab in place** (reuses the existing in-state
   tab navigation; no backend writes), not inline editing on the summary.
5. **Front-end only. No new model, no migration.** Referee reuses the existing
   student endpoint + dormant component; the review reuses the existing
   data + the existing consent/submit path.
6. **Stitch-first** (mandatory) for the review page (a new screen) and a quick
   Stitch check for where the referee input sits.
7. **British English; i18n parity en/ms/ta** (Tamil first-draft, queued for refine).

---

## 3. What already exists (reuse, don't rebuild)

| Asset | Where | Role |
|---|---|---|
| Student referee endpoint | `views.py RefereeListCreateView` (`GET/POST /api/v1/scholarship/referees/`) | Student adds/lists their own referees — **already live** |
| Referee API fns | `halatuju-web/src/lib/api.ts` `listReferees`/`addReferee` | **already present** |
| Referee form component | `halatuju-web/src/components/ScholarshipReferee.tsx` | A full name/role/relationship/phone/email form — **built but imported nowhere** (the only missing piece is mounting it) |
| Step-4 tabbed shell | `components/ScholarshipNextSteps.tsx` (renders at `/application`) | Quiz / Story / Funding / Documents / Consent + completeness + Action Centre |
| Consent step | the Consent tab (terminal "submit"/complete action) | the attest moment the review sits above |
| Completeness | `ApplicationCompleteness` (server-computed booleans) | drives which tab is incomplete; extend to include referee if we gate on it |
| Documents drawer styling | the S5 admin Documents drawer pattern | a reference for showing uploaded docs read-only on the review |
| Apply-form pure renderers | `halatuju-web/src/lib/scholarship.ts` (`ApplyFormState`, payload/labels) | source of the field labels + conditional Plans logic to render read-only |

---

## 4. Scope

### Part A — Wire student referee collection (small, do first)
- Mount `ScholarshipReferee` into the `/application` flow (recommended: as a small
  card within the **Story** tab, or a light dedicated step — decide in §6). Confirm
  the `listReferees`/`addReferee` round-trip works end-to-end against the live
  endpoint (the backend exists; it has likely never been exercised from the UI).
- Decide whether a referee is **required** for completeness or **optional/encouraged**
  (see §6). If required, add `referee_done` to the completeness rollup; if optional,
  leave completeness untouched and just surface it.
- i18n for the referee labels/help (en/ms/ta). Quick Stitch check on placement.

### Part B — Submission Review page (the main piece)
- A read-only **"Review your complete application"** summary at the **Consent step**,
  showing every section grouped clearly:
  - **About you / family / NRIC** (from `/apply`) — with the NRIC display nuance
    (locked + verified badge when `nric_verified`, else the value; note it was set
    at apply).
  - **Results** (the conditional My-Plans branch rendered read-only: pathway vs
    programme vs matric track/institution vs STPM stream vs ranked top-choices vs the
    optional "uncertain" branch — **required-vs-optional clearly labelled**).
  - **Your Story / Funding** (Step-4 narrative + needs categories + programme length).
  - **Documents** — the uploaded files, reusing the S5 grouped-drawer styling
    (filename + status, View link), read-only.
  - **Referee** (from Part A).
- Each section has an **Edit** link that jumps to its tab in place (no backend write).
- The existing **Consent** acknowledgment + the terminal submit/complete action stay
  exactly where they are, directly below the summary.
- Honest copy: "**Review your application before you submit**" — must NOT imply
  anything beyond this submit (there is no further stage after consent for the student).
- i18n (en/ms/ta) for all new strings. **Stitch prototype first.**

---

## 5. Risks / gotchas (carried from the evaluation)

- **Conditional Plans rendering is the real effort.** Rendering the pathway/programme/
  matric/STPM/uncertain branches read-only, correctly, with required-vs-optional
  labels, is the bulk of the work and the easiest place to omit or mislabel a field.
- **Required-vs-optional honesty.** Don't show optional fields (parent phone, the
  whole "uncertain" branch) as if required, and don't hide a conditionally-required
  one — either traps students or lets incomplete data through.
- **Edit-link stale stash (TD-057).** More edit entry points = more chances to leave
  a stale return-marker if a student abandons mid-edit. Reuse the existing
  stash/return pattern and clear markers on every legitimate entry/exit.
- **Referee endpoint never UI-exercised.** It exists but has likely never been called
  from a real client — smoke it early (auth scope, own-application scoping).
- **Completeness coupling.** If a referee becomes required, the `complete` rollup +
  the Action Centre's "what's left" must include it, or the gate and the queue
  disagree.
- **Copy must not over-promise.** "Review your complete application" is fine *here*
  (everything exists at consent), unlike at `/apply`.

---

## 6. Open decisions (settle before/at Stitch)

1. **Referee placement:** a card inside the **Story** tab, or a small dedicated step
   in the `/application` tab order? (Lean: a card in Story — fewer steps.)
2. **Referee required or optional?** Required → add to completeness + Action Centre;
   optional → surface + encourage only. (Lean: optional-but-encouraged to start,
   since it's a new ask to a B40 audience; can tighten later.)
3. **Review page copy / title** — confirm the exact wording (en first, then ms/ta).
4. **Stitch-first** — confirm you want the review screen visually approved before any
   template coding (standing rule).

---

## 7. Effort & sequence

- **Front-end only, no migration.** Roughly **one focused sprint** (~6–10 files:
  the review renderer + edit-links + referee mount + i18n × 3 + the Stitch screen +
  tests for the new step + the referee round-trip). Part A is small; Part B carries
  the real cost (the read-only Plans rendering).
- **Do Part A (referee) first** — it's small and the review page needs the referee
  to exist to summarise it.
- **Sequence relative to other work:** **after** the Verification-Verdict branch is
  deployed/merged to `main`. This plan does not depend on the verdict work, but we
  finish the in-flight branch before opening a new front-end sprint.
