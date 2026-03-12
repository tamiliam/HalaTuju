# Sprint 20 — Onboarding Redesign: Design Decisions

**Date**: 2026-02-23
**Status**: Design confirmed, implementation pending

## Context

Sprint 19 shipped 37-category course image classification (100% course coverage). During sprint close, we compared the current onboarding implementation against two Stitch designs and identified improvements. The user confirmed all design decisions below.

## Current State (Sprint 19)

Three onboarding pages:
1. **Stream Selection** (`/onboarding/stream`) — 3 stream cards (Sains, Sastera, Teknikal & Vokasional)
2. **Grade Input** (`/onboarding/grades`) — Button grid (A+ through G) for each subject
3. **Profile** (`/onboarding/profile`) — Gender, nationality, health conditions

Key files:
- `src/app/onboarding/stream/page.tsx`
- `src/app/onboarding/grades/page.tsx`
- `src/app/onboarding/profile/page.tsx`

## Design Decisions (Confirmed)

### 1. SPM/STPM Exam Type Selection (NEW Screen 1)

**Decision**: Introduce a new first screen for exam type selection.

- Two large cards: SPM and STPM
- This is the entry point — determines the entire downstream flow
- STPM course data and eligibility engine rules are a future task; the screen will be ready

### 2. Merge Stream + Subject/Grade Entry (Screen 2)

**Decision**: Combine stream selection and grade input into one screen.

**Rationale**: Stream choice directly determines which subjects appear. Keeping them on the same page avoids a redundant navigation step and reduces drop-off.

**Layout — three sections on one page:**

#### Section A: Core Subjects (4 compulsory)
- Stitch-style button grid: A+, A, A-, B+, B, C+, C, D, E, G
- Green checkmark icon when grade selected, delete/clear icon
- **Desktop**: All 10 grade buttons in one row
- **Mobile**: 5 buttons per row (A+ through C+ on row 1, C through G on row 2)

#### Section B: Stream Subjects
- Compact dropdown row per subject:
  - Subject name dropdown (e.g. "Kimia")
  - Grade badge dropdown (e.g. "GRADE B+")
  - Delete icon to remove
- Subjects pre-populated based on stream selection
- User can change the subject via dropdown if needed

#### Section C: Elective Subjects
- Same compact dropdown + grade badge style as stream subjects
- "Tambah Subjek Elektif" (Add Elective Subject) button with dashed border
- Maximum 2 elective subjects

### 3. Personal Details (Screen 3)

**Decision**: Adopt Stitch compact layout.

**Layout — single card:**
- **Negeri** (State): Dropdown selector
- **Jantina** (Gender): Toggle buttons — Lelaki / Perempuan (with icons)
- **Keperluan Khas** (Special Needs): Checkboxes — Warna Buta (Colour Blind), OKU (Disability) with accessibility icons
- All in one compact card, no full-page spread

### 4. Progress Stepper

**Decision**: YES — add progress indicator.

- Format: "Step 1 of 3", "Step 2 of 3", "Step 3 of 3"
- Visible on all three onboarding screens
- Shows completed/current/upcoming state

### 5. Improved Helper Text

**Decision**: YES — contextual and motivating.

- Each screen gets a clear header explaining why this step matters
- Helper text should guide the student, not just label the form
- Examples:
  - Screen 1: "Choose your exam type to get started"
  - Screen 2: "Enter your grades so we can find courses that match your results"
  - Screen 3: "A few more details to personalise your recommendations"

### 6. Final Screen Flow

| Screen | Content | URL |
|--------|---------|-----|
| 1 | Exam Type (SPM/STPM) | `/onboarding/exam-type` |
| 2 | Stream + Grades (merged) | `/onboarding/grades` |
| 3 | Personal Details | `/onboarding/profile` |

The old `/onboarding/stream` page will be removed — stream selection moves into the grades page.

## What Was NOT Changed

- **Button grid for core subjects** — kept from current implementation (better than Stitch's sliders for grade precision)
- **3 screens total** — not 4 (merging stream+grades prevents extra screen from STPM addition)

## Stitch Reference Screens

- Screen `21f05682fdd948368d271d2428294c22` — "HalaTuju Academic Profile Input" (Step 1 of 3, Lexend font, progress stepper)
- Screen `249e438bdb0f463392ba3bb5fe9df81b` — "Academic Profile Input" (Step 2 of 5, core subjects with checkmarks)
- Stitch Project: `projects/7363298109642864230`

## Implementation Notes

- This is part of Sprint 20 scope alongside remaining i18n and report loading screen
- STPM exam type screen will be UI-ready but backend STPM logic is a future sprint
- Current 176 tests must remain passing throughout
- Prototype in Stitch before coding (per engineering discipline)

## Session Summary (2026-02-23)

### What Was Accomplished

1. **Sprint 19 completed and closed**:
   - Fixed Supabase Storage RLS policy (added temporary INSERT, uploaded 37 images, dropped policy)
   - Verified all 383 courses resolve to correct images via keyword matcher
   - Fixed 2 misroutes: Senibina Kapal (naval arch → marin-perkapalan) and Teknologi Kimia Lemak dan Minyak (food oil → kimia-alam-sekitar)
   - Deployed to Cloud Run (frontend rev 22)
   - Full sprint close: CHANGELOG, retrospective, CLAUDE.md, memory updates
   - Committed and pushed to `feature/v1.1-stream-logic`

2. **Design comparison with Stitch**:
   - Examined 2 Stitch screens via MCP (preview URLs don't render in WebFetch)
   - Identified what Stitch does better: progress stepper, Lexend font, language toggle, helper text, completion feedback
   - Identified what our implementation does better: button grid precision, stream cards showing subjects, fewer pages, better CTA copy

3. **STPM integration approach decided**:
   - 3 screens (not 4) — merge stream+grades to absorb the new exam type screen
   - All UI component specifications confirmed with screenshots

### Files Modified This Session

| File | Change |
|------|--------|
| `halatuju-web/src/components/CourseCard.tsx` | Fixed 2 image matcher misroutes |
| `CHANGELOG.md` | v1.21.0 entry (Sprint 19) |
| `halatuju_api/CLAUDE.md` | Next Sprint → Sprint 20 |
| `docs/retrospective-sprint19.md` | Created (Sprint 19 retro) |
| `docs/sprint20-design-decisions.md` | Created (this file) |
| Memory: `halatuju.md`, `MEMORY.md` | Updated status and sprint info |

### Errors Encountered and Resolved

1. **Supabase Storage 403** — No INSERT RLS policy on `field-images` bucket. Fixed with temporary policy.
2. **Cannot delete storage objects via SQL** — `storage.protect_delete()` prevents it. Left old 9 images (harmless).
3. **Senibina Kapal misroute** — Matched 'senibina' before checking for 'senibina kapal'. Fixed with specific check first.
4. **Teknologi Kimia misroute** — Matched 'minyak' before 'teknologi kimia'. Fixed by reordering checks.
5. **Windows bash paths** — `c:\Users\...` fails in Git Bash. Use `/c/Users/...` format.

### Current Repository State

- Branch: `feature/v1.1-stream-logic`
- Git: Clean (all committed and pushed)
- Backend: rev 26 (unchanged this sprint)
- Frontend: rev 22 (deployed this sprint)
- Tests: 176 passing, golden master 8280
- Supabase Security: 0 errors
