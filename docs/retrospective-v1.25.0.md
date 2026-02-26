# Retrospective — v1.25.0 (26 Feb 2026)

## What Was Built

Two frontend features on the `/search` page:

1. **Eligible Toggle Auth Gate** — The "Eligible Only" toggle was permanently disabled because `halatuju_eligible_courses` was never written to localStorage. Rewired the toggle to call the eligibility API directly. If the user is not logged in, clicking it opens the auth gate modal (encouraging sign-up). After login, the toggle auto-activates via `halatuju_resume_action` in localStorage.

2. **Merit Progress Bar (Variation C)** — Replaced the simple traffic-light dot (coloured circle + "High/Fair/Low Chance" text) with a visual progress bar. Shows the student's merit score inside the bar, a dashed cutoff line at the course threshold, and a label row with chance + numeric scores ("You: 72 | Need: 65").

## What Went Well

- **User-guided design process** — The user drove the design direction: from 5 broad indicator options → progress bar selected → 4 sub-variations → Variation C chosen. Iterative HTML mockups were effective for getting visual feedback.
- **Auth gate pattern reuse** — The existing `AuthGateReason` + `showAuthGate()` + resume action pattern made it straightforward to add `'eligible'` as a new gated feature. The architecture scaled cleanly.
- **Both features deployed and verified in one session** — rev 40 (toggle) and rev 41 (progress bar), both working in production.

## What Went Wrong

- **Stitch MCP produced generic pages** — Two attempts to generate merit indicator comparison screens in Stitch both produced full app pages (course explorers, search results) instead of focused component designs. Had to fall back to manual HTML mockups.
- **Playwright browser launch failed** — Chrome was already running, blocking the persistent context launch. Used `start ""` command instead.

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Toggle prompts login instead of fixing localStorage write | User wanted to encourage account creation. Auth gate is a better UX for conversion than a silently-enabled toggle. |
| `eligibleMap` (Map) alongside `eligibleIds` (Set) | Search page needs both: Set for O(1) filtering, Map for looking up merit scores to pass into CourseCard. |
| Variation C (score-in-bar + dashed cutoff + chance label) | User evaluated 4 options side-by-side in realistic card mockups and chose C for its information density without visual clutter. |
| Fallback to dot+label when no numeric scores | Not all courses have numeric merit data. Graceful degradation preserves the original UX where data is missing. |

## Numbers

| Metric | Value |
|--------|-------|
| Files changed | 6 (3 components, 3 i18n) |
| Commits | 2 (`04ed94f`, `2953cf1`) |
| Backend changes | None |
| Frontend revisions | rev 40, rev 41 |
| Tests | 173 collected, 164 passing (unchanged — no backend changes) |
| Golden master | 8280 (unchanged) |
