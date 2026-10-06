# Retrospective — Post-S20 Polish (v1.22.3–v1.23.4)

**Date**: 2026-02-23 to 2026-02-26
**Versions**: v1.22.3 → v1.23.4
**Nature**: Patch releases between Sprint 20 and Sprint 21

---

## What Was Built

A series of polish patches improving UX, fixing bugs, and adding the course search/explorer page. Not a formal sprint — these were iterative improvements driven by Stitch design alignment.

### v1.22.3 — Merit Formula Fix + Supabase Security
- Corrected UPU merit formula in `lib/merit.ts`
- Fixed stale grades bug (localStorage lingering)
- Rewrote 14 Supabase RLS policies for performance

### v1.22.4 — Profile Page Polish
- Replaced emoji icons with inline SVGs for nationality, gender, health

### v1.23.0 — Course Search / Explorer
- New `/search` page with text search + 4 filters
- Search API backend with server-side filtering and pagination
- Eligible-only toggle, "Explore" nav link
- 10 new backend tests

### v1.23.1 — Deploy Fix: Suspense Boundary
- Fixed Next.js prerender crash (`useSearchParams()` needs `<Suspense>`)
- Cleaned up stale Container Registry image

### v1.23.2 — Search Page Stitch Alignment
- Institution info on course cards (name, state, "+N more")
- Clear Filters button, eligibility toggle redesign
- 3 new backend tests, 3 new i18n keys

### v1.23.3 — Filter Pill Dropdown Redesign
- New `FilterPill` component replacing native `<select>` elements
- Active state styling, outside-click dismiss

### v1.23.4 — Stitch Design Polish
- Shorter pill labels, gray fill, descriptive placeholder
- Clear Filters always visible (greyed out when inactive)

---

## What Went Well

1. **Stitch-first design worked**: Each iteration was designed in Stitch, then coded to match. Result: consistent, polished UI.
2. **Small patches, frequent deploys**: 7 patch releases over 3 days, each self-contained and testable.
3. **Backend stayed stable**: Golden master (8280) unchanged throughout. Only 13 new backend tests needed.
4. **No regressions**: 164/173 tests passing throughout (9 pre-existing JWT failures).

## What Went Wrong

1. **Suspense boundary oversight** (v1.23.1): `useSearchParams()` on `/search` page crashed during Cloud Run build. Should have caught this in local build step before deploying.
2. **Stale Container Registry image**: A failed deploy left a stale image in the old gcr.io registry. Had to redeploy from source to Artifact Registry.

## Design Decisions

1. **FilterPill as reusable component**: Custom dropdown pill (`FilterPill.tsx`) instead of native `<select>` — matches Stitch design, portable to other pages.
2. **Institution info via Subquery**: Backend returns alphabetically-first institution per course using Django Subquery, avoiding N+1 queries.

---

## Numbers

| Metric | Value |
|--------|-------|
| Patches released | 7 (v1.22.3–v1.23.4) |
| New backend tests | 13 |
| Total tests | 173 collected, 164 passing |
| Golden master | 8280 (unchanged) |
| Backend deploys | 1 (rev 32) |
| Frontend deploys | 6 (rev 33→38) |
