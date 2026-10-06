# Retrospective — `/scholarship/application` redesign, Sprint 1 (5-tab shell) — v2.4.0, 2026-05-27

First sprint of the Step-4 (post-shortlist "complete your profile") redesign. Plan:
`docs/scholarship/application-redesign-plan.md`. Commit `359f62e`.

## What Was Built
The shortlisted view of `/scholarship/application` went from one long scroll to a **5-tab sectioned shell**
mirroring `/apply` — desktop left step-rail + active section card, mobile bottom tab bar, progress bar + "Step N of
5" indicator. Tabs: Quiz · Your story · Funding · Documents · Consent. Referee dropped from the student flow. Section
*content* ported in unchanged (the single details form split across the Story + Funding tabs, shared state, one
PATCH). New pure helpers `NEXT_STEP_ORDER` + `defaultNextTab` (+9 jest). Frontend only, no backend/model change.

## What Went Well
- **Delegated the contained refactor to a subagent under context pressure.** The main thread was deep into a very
  long session; a tightly-specced subagent built S1 in a fresh context and returned green (build, jest 86, i18n
  1177) + mobile/desktop screenshots. The orchestrator then reviewed the diff + screenshots and re-ran the build
  before deploying. Clean division of labour that respected the sprint context budget.
- **One approved Stitch screen was enough to start.** The signed-off "Your story" prototype validated the shell +
  section pattern, which covers S1 *and* S2 — so the build wasn't blocked on prototyping every screen up front.
- **Shell-first sequencing de-risked the layout** before any model changes (S2–S4).

## What Went Wrong
1. **Stitch generation repeatedly timed out on the denser screens, costing ~4 polling cycles.**
   - *Symptom:* `generate_screen_from_text` for the Funding screen timed out client-side twice (GEMINI_3_1_PRO, then
     GEMINI_3_FLASH); neither persisted after repeated `list_screens` polling.
   - *Root cause:* the Stitch MCP's client-side timeout is shorter than the server-side generation time for
     content-dense screens, and a timed-out generation does **not** reliably persist. I initially kept waiting/polling
     instead of pivoting, burning turns.
   - *System change:* lesson added — treat Stitch dense-screen generation as best-effort; generate ONE representative
     screen to get the *pattern* signed off, then prototype the remaining sections **just-in-time before their own
     sprints** rather than all up front; don't block a sprint on a stuck Stitch render.
2. **Ported sections carry a cosmetic double-number heading** ("3. Funding" tab title above the old "3. Your funding
   need" inner heading).
   - *Symptom:* redundant numbering visible on the Funding/Story tabs.
   - *Root cause:* S1 deliberately ports old section content verbatim under the new tab titles.
   - *System change:* already planned away — S2/S3 rework each section's content and drop the old inner headers; noted
     as a known carry-over in the plan doc so it isn't mistaken for a regression.

## Design Decisions
Captured in `docs/scholarship/application-redesign-plan.md` (shell mirrors `/apply`; details form split across two
tabs with shared state + one PATCH; referee removed from the student flow → coordinator verify-&-accept). No new
architectural decision beyond the plan doc.

## Numbers
- 7 files changed; +9 jest (full suite **109** frontend); i18n parity **1177**; backend unchanged (**1110**, zero
  backend files touched).
- 1 web deploy (rev `halatuju-web-00213-mvf`); v2.4.0; build clean; verified live + screenshot-verified both
  breakpoints.
