# Retrospective — Post-Sprint 20: Filter Pill Dropdown Redesign

**Date:** 2026-02-26
**Version:** v1.23.3

## What Was Built

Replaced the 4 native HTML `<select>` filter dropdowns on the `/search` page with custom `FilterPill` components matching the Stitch design screen `ff7ddb0e2bed4181ab1927263a3f1c03`.

- Compact rounded pills with chevron icons (rotate on open)
- Active state: primary blue border + light blue background when a filter is selected
- Dropdown panels: absolute-positioned, scrollable, shadow, rounded-xl
- Outside-click dismiss (same pattern as AppHeader)
- Clear Filters button: added funnel icon, rounded-full to match pills

## What Went Well

- **Reusable component** — `FilterPill` is generic enough to use on any page needing dropdown filters
- **No new dependencies** — built with React state + Tailwind, following the existing AppHeader pattern
- **Clean swap** — replaced 4 `<select>` blocks with 4 `<FilterPill>` instances, no state management changes needed
- **Build passed first try** — no compile errors

## What Went Wrong

- Nothing significant. Small, focused change.

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Custom component vs Headless UI/Radix | No existing dropdown library in the project; adding one for 4 dropdowns is overkill. AppHeader already demonstrates the pattern. |
| `rounded-full` pills | Matches Stitch design — capsule/pill shape, not rectangular |
| `clsx` for conditional classes | Already installed, cleaner than template literals for multi-line conditionals |
| `max-w-[160px] truncate` on pill text | Prevents long field names from blowing out the layout on mobile |
| `max-h-60 overflow-y-auto` on dropdown | Handles the Fields filter which has many options |

## Numbers

| Metric | Value |
|--------|-------|
| Files changed | 2 (1 created, 1 modified) |
| Lines added | ~136 |
| Lines removed | ~43 |
| New component | FilterPill.tsx (~100 lines) |
