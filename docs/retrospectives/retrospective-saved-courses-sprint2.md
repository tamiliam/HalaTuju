# Retrospective — Saved Courses Sprint 2 (Frontend)

**Date:** 2026-03-15
**Sprint scope:** Shared `useSavedCourses()` hook, Toast component, wire into all surfaces, tabbed saved page

---

## What Was Built

- `useSavedCourses()` shared hook — auth gating, optimistic toggle, toast feedback, resume-after-login
- `ToastProvider` + `useToast()` — success/error toasts with auto-dismiss and slide-in animation
- Dashboard: replaced ~50 lines of inline save logic with one hook call
- Search page: save now works (was hardcoded `isSaved={false}`)
- SPM detail page: fixed broken save (was missing auth token), added green/red/blue visual states
- STPM detail page: same fix as SPM
- Saved page: SPM/STPM tabs with counts, correct detail links (`/course/` vs `/stpm/`)
- Translation keys added in EN/MS/TA for new UI strings

## What Went Well

- **Clean build first time.** Zero compilation errors after wiring the hook into all 5 pages. The hook's API (`savedIds`, `toggleSave`) was simple enough that each page integration was mechanical.
- **Design doc paid off again.** Sprint 2 scope was fully defined in the roadmap. No ambiguity, no scope creep.
- **No backend changes needed.** Sprint 1's API design (course_type in response, qualification filter, auto-detect STPM) was exactly what Sprint 2 needed. Zero API modifications.

## What Went Wrong

1. **No issues.** This was a clean sprint — straightforward extraction of existing logic into a shared hook, then mechanical wiring into each page. The prior sprint's retrospective lesson (grep call sites before changing signatures) was not needed because the hook was additive, not a signature change.

## Design Decisions

- **ToastProvider wraps inside AuthProvider**: Toast must be inside Auth so that `useSavedCourses` (which uses `useAuth`) can also use `useToast`. Provider nesting order: QueryClient > I18n > Auth > Toast > children.
- **Resume-after-login split**: Save resume moved to hook (it's save-specific). Report resume stays in dashboard (it's dashboard-specific). The hook checks for `action === 'save'` and returns early, letting dashboard handle the rest.
- **Hover-to-reveal "Remove"**: Detail page save button shows green "Saved" normally, switches to red "Remove from Saved" on hover. This avoids accidental unsaves while keeping the remove action discoverable.

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Files with save logic | 4 (dashboard, course, stpm, saved) | 1 (hook) |
| Pages with working save | 2 (dashboard, saved) | 5 (+ search, course detail, stpm detail) |
| New files | — | 2 (hook, toast) |
| Files modified | — | 8 |
| Translation keys added | — | 6 (2 per language) |
| Build status | Pass | Pass |
