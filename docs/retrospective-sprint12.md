# Sprint 12 Retrospective — Report Frontend + PDF

**Date**: 2026-02-18
**Duration**: ~30 minutes
**Tests**: 144 → 148 (+4)
**Golden Master**: 8280 (unchanged)

## What Was Built

1. **Report display page** (`/report/[id]`) — renders AI counsellor markdown report using `react-markdown` with Tailwind Typography prose styling
2. **PDF download** — `window.print()` with `@media print` stylesheet (A4, clean layout, hidden navigation, print-only footer)
3. **Generate Report CTA** on dashboard — auth-protected button, calls report API, redirects to report page
4. **Report API client** — `generateReport()`, `getReport()`, `getReports()` with full TypeScript types
5. **4 view tests** — list (own reports only), detail, cross-user 404 regression, validation

## What Went Well

- **Bug caught during sprint planning**: FK filtering bug in `ReportDetailView` and `ReportListView` (from Sprint 11) would have caused silent 404s/empty results in production. Caught by reading the code before building the frontend.
- **Clean PDF approach**: `window.print()` + Tailwind print utilities = zero dependencies, works on all browsers. Students just "Save as PDF" from the print dialog.
- **Fast build**: All frontend changes built cleanly on first try. `react-markdown` + `@tailwindcss/typography` integrated smoothly.

## What Went Wrong

- **FK bug shipped in Sprint 11**: The `student_id=request.user_id` filter compared an integer FK with a UUID string — would never match. This passed Sprint 11 because the engine tests mocked at the function level, not the view level. **Lesson**: Always write view-level integration tests for auth-filtered endpoints, not just unit tests for the underlying functions.

## Design Decisions

| Decision | Why |
|----------|-----|
| `window.print()` for PDF | Zero cost, no server-side PDF library needed, works everywhere |
| `react-markdown` for rendering | Standard, lightweight (~37KB in bundle), proper markdown rendering |
| `@tailwindcss/typography` | Consistent prose styling without manual CSS for every markdown element |
| Report CTA requires auth | Report generation calls Gemini (costs money), must be gated behind login |

## Numbers

| Metric | Value |
|--------|-------|
| Tests added | 4 |
| Tests total | 148 |
| Files created | 2 (report page, view tests) |
| Files modified | 5 (views.py, api.ts, dashboard/page.tsx, globals.css, tailwind.config.ts) |
| Dependencies added | 2 (react-markdown, @tailwindcss/typography) |
| Report page bundle | 36.7 kB first load |
