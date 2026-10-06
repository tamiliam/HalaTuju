# B40 Redesign — Sprint 9b Retrospective (2026-05-24)

The slice split out of S9: the **My Results → onboarding round-trip**. Frontend only, branch
`feature/b40-redesign`, not deployed.

## What Was Built
- My Results "edit/add results" routes through the **full onboarding** (`/onboarding/exam-type` → grades →
  electives → co-curricular → "a few more details") instead of `/profile`/`/quiz`, so the profile ends up complete
  for course recommendations too.
- The **final onboarding step** (`onboarding/profile`) is context-aware: entered from the apply form, its button
  reads **"Save & return to application"** and routes back to `/scholarship/apply`; otherwise unchanged (→ dashboard).
- **Stash & restore** of in-progress About-Me/My-Family edits across the detour (the form only commits on submit):
  `stashApplyForm` / `popApplyStash` / `hasApplyReturn` / `clearApplyReturn` in `scholarship.ts`, with the
  sessionStorage keys as constants. On return the apply form restores the stash and lands on the Results tab,
  re-reading the (now-updated) academic summary live from the profile.

## What Went Well
- The storage helpers were made **storage-injectable** (`storage?: StorageLike`) and SSR-safe, so node-env jest
  covers the full round-trip with a Map-backed fake — 5 tests, no DOM, no jsdom. Clean separation of logic from
  the browser API.
- Restore-on-mount + a `populatedRef` guard on the profile-prefill effect was a precise, minimal way to stop the
  profile from clobbering the restored edits — and it incidentally fixed a latent issue where a profile refresh
  mid-edit could overwrite the user's input.

## What Went Wrong
- **The return marker can go stale on an abandoned detour.** *Symptom (caught in design, not in prod):* a
  persistent `sessionStorage` boolean set before a multi-step flow lingers if the student abandons onboarding
  mid-way; a later *normal* onboarding in the same tab would then misroute to the apply page. *Root cause:* a
  persistent flag set before a multi-step flow has no clean "cancelled" boundary to clear it. *Fix:* added an
  orphan-clear on any normal apply visit + logged TD-057 (the clean fix is to thread the intent as a query param
  through the onboarding steps rather than a persistent flag). sessionStorage being tab-scoped bounds the blast
  radius (clears on tab close).

## Design Decisions
- sessionStorage stash + boolean return-marker over query-param threading — see `docs/decisions.md` (2026-05-24).

## Numbers
- Frontend jest **44 → 49**; backend unchanged (**1095**); `next build` clean; i18n **1052 keys × 3** (parity).
  5 files (scholarship.ts, its test, apply page, onboarding profile, 3 i18n). No migration, no backend change.
