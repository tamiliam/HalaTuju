# Retrospective — Verification Verdict roadmap, Sprint 4 (2026-06-02)

Branch `feature/verification-verdict` (committed + pushed, **not deployed**). Plan:
`docs/scholarship/verification-verdict-plan.md`. First UI sprint of the roadmap.

## What Was Built

The **Student Action Centre** — the student-facing half of the IBKR loop. A warm,
self-service "things to finish" surface at the top of `/application` that consumes
the S3 resolution endpoints and lets a shortlisted student clear each gap in place:

- `doc` → inline upload (reuses the signed-URL upload flow);
- `explanation` → a short typed reply (`POST …/resolve/`);
- `confirm` → a "Review" button that switches to the relevant `/application` tab
  (the ticket auto-clears server-side once the gap closes).

Header "Almost there, {name}" + a progress bar, amber "To do" pills, a **Cikgu
Gopal** graduation-cap coach bubble, and a green **all-done** banner when the queue
empties. Additive + non-blocking (renders nothing if there are no tickets or the
fetch fails). New `ActionCentre.tsx` + pure `lib/actionCentre.ts` (16 jest tests),
`getResolutionItems`/`resolveResolutionItem` in `api.ts`, student i18n
`scholarship.actionCentre.*` × en/ms/ta. **No migration, no backend change.**

## What Went Well

- **The backend did its job.** Because S3 already produced clean, discrete tickets
  with a `kind`, the UI was a thin renderer + three resolve flows — no new logic on
  the frontend beyond presentation.
- **Reconcile-before-build paid off.** Doing the main↔branch merge first meant S4
  built on the hardened OCR foundation with zero surprises.
- **Delegation worked cleanly.** A well-specced subagent built the whole sprint
  under heavy main-thread context; the orchestrator independently re-ran `next
  build` (EXIT=0), jest (199), and `check-i18n` (1750), and read the component +
  API + wiring before committing — trust-but-verify, not trust.

## What Went Wrong

1. **Stitch timed out twice and the screens didn't appear in `list_screens`.**
   *Symptom:* two `generate_screen_from_text` calls returned a client timeout; the
   new screens weren't in the (10-item) `list_screens` result, so I couldn't
   confirm they'd persisted. *Root cause:* content-dense prompts time out
   client-side and persist *late* (the known #72/#76 behaviour), and `list_screens`
   appears to page/cap so a just-created screen isn't necessarily near the top.
   *Resolution:* the user pasted the Stitch **preview URL**; the `node-id` in it is
   the **screen id**, which `get_screen` resolves directly. *Fix (system):* lesson
   added — recover a timed-out Stitch screen via the preview URL's `node-id` →
   `get_screen`, rather than relying on `list_screens`.
2. **`confirm` routing for academic is imperfect.** A `confirm` ticket with
   `fact==='academic'` (e.g. "add 2 missing subjects") routes to the **Documents**
   tab, but subjects are added in the onboarding/grades flow, not Documents — the
   page has no dedicated grades tab. Logged as **TD-082**; acceptable for now (the
   ticket copy tells the student what to do; the gap clears once they add the
   subjects), to be tidied with the grades-edit surface.

## Design Decisions

None met the "non-obvious architectural choice" bar — the placement (top of
`/application`), the kind→action mapping, and the additive/non-blocking posture
follow directly from S3's contract and the approved Stitch design.

## Numbers

- Frontend jest: **199** (was 183; +16 pure `actionCentre.ts` tests). Backend
  unchanged on the branch (**1512**, from the main↔branch merge).
- i18n parity **1750** × en/ms/ta (Tamil first-draft). `next build` clean. No migration.
- New: `ActionCentre.tsx`, `lib/actionCentre.ts` (+ tests). Changed: `api.ts`,
  `ScholarshipNextSteps.tsx`, `application/page.tsx`, 3 i18n files.
- New TD: **TD-082** (academic `confirm` routes to Documents, not a grades surface).
