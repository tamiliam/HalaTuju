# Retrospective — i18n Sprint 2: Admin Pages

**Date:** 2026-03-19
**Scope:** Internationalise all admin panel pages (7 pages, 118 keys)

## What Was Built

- Full i18n coverage for all 7 admin pages: layout, login, dashboard, students list, student detail, invite, profile
- 118 new keys under `admin` namespace in `en.json`, `ms.json`, `ta.json`
- Interpolation support for dynamic strings (`studentsCount`, `showingRange`, `orgInfo`)
- All 3 message files verified in parity (identical key sets)

## What Went Well

- **Mechanical approach worked**: Systematic page-by-page replacement with existing `useT()` hook was fast and reliable
- **Key reuse**: Reused existing keys where possible (`common.loading`, `common.save`, `header.logout`, `login.or`, `profile.angkaGiliran`, `apiErrors.*`) — avoided duplication
- **Single namespace**: All admin keys under one `admin` namespace kept things organised and easy to verify
- **Build verification**: `next build` confirmed zero compile errors after all changes

## What Went Wrong

1. **Edit tool string matching failed on the referral source card**
   - Symptom: `old_string` not found when replacing "Sumber"/"Organisasi" labels in Card 9 of `students/[id]/page.tsx`
   - Root cause: Prior edits in the same file shifted line numbers and surrounding context, making the match string ambiguous or stale
   - Fix: Re-read the file to get current state, then applied the edit with correct context. Going forward: re-read file state after multiple sequential edits to the same file before attempting further edits.

## Design Decisions

- **Acronyms stay hardcoded**: "SPM", "STPM", "CGPA", "MUET", "WhatsApp" are universal across all 3 languages — no need to translate
- **Brand names stay hardcoded**: "WhatsApp", "Google" in login/share buttons
- **Admin namespace flat**: All 118 keys in a flat `admin.*` namespace rather than nested per-page, since many keys are shared across pages

## Numbers

- Pages modified: 7 (+ 3 message files)
- Admin i18n keys: 118
- Hardcoded admin strings remaining: 0
- Build: passes
- Backend tests: 892 (unchanged — frontend-only sprint)
- Frontend tests: 17 (unchanged)
