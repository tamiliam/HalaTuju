# Retrospective — B40 Phase E/F Sprint 3: Student award + onboarding frontend (F8b)

**Date:** 2026-06-09
**Branch:** `main` (held local, not pushed — ships dark; deploy owner-gated)
**Migration:** none (FE only)

## What Was Built

The student-facing half of post-match onboarding, wired to the F8a backend.

- **`/scholarship/award`** — the award-acceptance screen: trophy badge, "your studies are funded", the two-way
  anonymity line, amount + accept-by date, Accept / Not-now. An adult accepts in one tap → onboarding; a minor accepts
  via a guardian modal (name + relationship dropdown reusing `scholarship.consent.relationship.*` + NRIC via
  `formatNric`) → `respondToAward({granted_by:'guardian',…})`. Backend error codes mapped to friendly i18n.
- **`/scholarship/onboarding`** — a 3-step wizard (Welcome acknowledgement cards → Questions → Finish) with a 4-label
  progress nav. The Finish step auto-calls `submitOnboarding` once; `code:'not_awarded'` routes back to the award page;
  the success screen shows "what happens next" + a coming-soon anonymous-thank-you line (the F9 relay is a later sprint).
- **API clients** — `getStudentAward` / `respondToAward` / `submitOnboarding` + `onboarded_at` on the application type.
- **Application panel** — an "accept your award / complete onboarding" card on `/scholarship/application`, shown only
  when an offer exists, routing to award (un-accepted) or onboarding (accepted, not onboarded), hidden once onboarded.
- **i18n** — `scholarship.award.*` + `scholarship.onboarding.*` + `scholarship.application.awardPanel.*` in en/ms/ta
  (parity verified). Tamil is a first-draft for the owner.

## What Went Well

- **Delegation worked.** With the main context deep after Sprints 1–2, the contained, well-specced FE sprint went to a
  fresh-context subagent (lesson #73). It built the pages + clients + i18n, ran its own `next build`, and left
  everything uncommitted; the orchestrator reviewed the diff, re-ran `next build` + jest, and committed. Quality was
  high — anonymity preserved, existing patterns reused (`AppHeader`/`AppFooter`, `formatNric`, the consent relationship
  labels), no new primitives invented.
- **Stitch recovered with owner help.** After a flaky generate (auth blip, then a timeout that polled too early), the
  owner pasted the four preview `node-id`s; fetching each via `get_screen` was cheap and gave clean approval artifacts.
- **Naturally dark.** No explicit flag gating was needed on these pages — a student only ever has an award offer once a
  sponsor funds them, which requires `SPONSOR_POOL_ENABLED`. So the pages are inert in production until go-live.

## What Went Wrong

- **Polled Stitch too early after the timeout, so the screen looked like it hadn't persisted.** *What happened:* I
  waited ~45–70s then `list_screens`, twice, and the new screen wasn't there; I concluded the generation failed.
  *Why:* generation on this project takes longer than that, and `list_screens` returns a large dump so each poll is
  expensive. *Fix (captured):* wait ~90–150s before the first poll; the owner can also paste the preview `node-id`s,
  which `get_screen` resolves cheaply. (Saved to the Stitch workflow memory.)

## Design Decisions

- **Delegate the FE build to a subagent; orchestrator reviews + re-builds before committing.** (Logged in
  `decisions.md`.) The right call when the main context is deep and the sprint is well-specced (approved screens +
  fixed backend contracts + an established i18n pattern).
- **"Accepted" = award status ≠ `offered`.** The panel + onboarding treat any non-`offered` status (active/sponsored)
  as accepted, matching the backend accept flow. Simple and correct for the current state machine.

## Numbers

- **Frontend:** `next build` clean (`/scholarship/award` 3.56 kB, `/scholarship/onboarding` 2.8 kB); 276 jest green
  (pages are render-only — covered by build typing, per the node-env jest constraint).
- **Backend:** untouched this sprint (873 scholarship pytest unchanged).
- **Files touched:** 7 (api.ts, application page, 3 message files) + 2 new pages.
- **Migrations:** none. **Deploys:** 0 (held; ships dark).
- **Carried:** TD-094 (Tamil refine of the award/onboarding copy — joins the Tamil-refine queue).
