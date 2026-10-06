# Sprint 13 Retrospective — Localisation (EN/BM/TA)

**Date**: 2026-02-18
**Duration**: ~1 session
**Scope**: Full i18n support for 6 core pages in 3 languages

## What Was Built

1. **i18n infrastructure** (`lib/i18n.tsx`): React context + `useT()` hook with localStorage persistence
2. **Translation files**: 142 keys per locale across en.json, ms.json, ta.json — covering common, landing, onboarding, dashboard, login, and subjects sections
3. **Page localisation**: All 6 core pages (landing, stream, grades, profile, dashboard, login) fully localised with `t()` calls
4. **Language selector**: Dropdown component on landing page nav and dashboard header
5. **Validation script**: `scripts/check-i18n.js` checks JSON parsing, key completeness, and empty values

## What Went Well

- **Simple architecture paid off**: Chose React context over next-intl middleware since all pages are `'use client'` components. Zero routing changes, no directory restructuring, just wrap in provider and call `t()`.
- **Tamil quality**: Applied style guide rules — kept brand name in Latin script, joined compound words (e.g. "வண்ணக்குருடு" not "வண்ணக் குருடு"), applied sandhi consistently. Having the style guide in memory files was invaluable.
- **Existing translation files**: The 3 JSON files already existed with ~85 keys each from a previous attempt. Expanded to 142 keys rather than starting from scratch.
- **Build-driven validation**: Running `npm run build` after each batch caught issues immediately.

## What Went Wrong

- **Landing page SSR tradeoff**: Converting the landing page from server component to client component (`'use client'`) was necessary for the `useT()` hook but loses server-side rendering benefits. For a production app, a shared layout component or server-side locale detection would be better.
- **Subject names not fully translated**: Stream and elective subject names in the grades page remain in Malay (official SPM names). Only core subjects use `t('subjects.XX')`. This is intentional (they're official names) but could confuse Tamil-speaking users.

## Design Decisions

1. **Client-side i18n over next-intl**: next-intl requires middleware routing (`/en/`, `/ms/`, `/ta/`) and major restructuring. React context is simpler, works with existing `'use client'` pages, and persists via localStorage.
2. **Static JSON imports**: All 3 locale files are bundled into the client JS. With 142 keys per locale, the size impact is negligible (~10KB total) vs the complexity of dynamic loading.
3. **Selector placement**: Language selector only on landing page and dashboard — not on onboarding steps or login, keeping those flows focused.
4. **Official subject names**: SPM subject names (Fizik, Kimia, etc.) kept in Malay for stream/elective dropdowns since they're official Malaysian education system names.

## Numbers

- **Translation keys**: 142 per locale (up from ~85)
- **Locales**: 3 (English, Bahasa Melayu, Tamil)
- **Pages localised**: 6 (landing, stream, grades, profile, dashboard, login)
- **Sub-components with useT()**: 5 (InsightsPanel, FilterDropdown, RankedResults, LoadingScreen, SubjectPicker)
- **New files**: 3 (i18n.tsx, LanguageSelector.tsx, check-i18n.js)
- **Modified files**: 10 (3 JSON + 6 pages + providers.tsx)
- **Backend tests**: 148 (unchanged)
- **Frontend build**: Passes (all 17 routes)
