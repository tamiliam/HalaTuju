# B40 Redesign — Sprint 12a Retrospective (2026-05-24)

Desktop responsiveness for the apply form — the item deferred from S9. Frontend only, branch
`feature/b40-redesign`, not deployed. (S12 was split: Vision OCR → post-launch S13; the deploy → gated S12b.)

## What Was Built
- `/scholarship/apply` desktop layout: on `lg` it becomes a two-column grid — a left vertical **step-nav rail**
  (the five sections, active highlighted, completed ticked, clickable) beside the active section card +
  Back/Continue. Container widens `max-w-2xl` → `lg:max-w-4xl`; the mobile bottom tab bar is now `lg:hidden` (the
  rail replaces it on desktop). Mobile is unchanged.

## What Went Well
- The change was **contained to the layout shell** — the section content (`sections[tab]`) and all the field logic
  from S9/S10 were untouched, so there was zero risk to the working mobile flow. Wrapping the existing progress +
  card + nav in a `lg:grid` and adding a desktop-only `<aside>` rail was the whole change.
- Reused the same throwaway-preview-route + Playwright pattern (now well-worn) to screenshot desktop *and* mobile
  without signing in; verified the mobile layout was untouched, not just the new desktop one.

## What Went Wrong
- Nothing notable. Small, contained, frontend-only layout sprint.

## Design Decisions
- Left step-nav rail on desktop (vs forcing 2-column fields, which reads worse for a form) — a routine UI choice,
  not logged in decisions.md. Kept fields single-column; the rail uses the otherwise-empty horizontal space.

## Numbers
- `next build` clean; frontend jest unchanged (**49** — layout only, no new pure logic); backend unchanged
  (**1100**); no migration, no i18n change. 1 source file (`apply/page.tsx`). Approved via desktop + mobile screenshots.
