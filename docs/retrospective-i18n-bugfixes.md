# Retrospective — i18n & Bug Fixes Sprint (2026-03-19)

## What Was Built

Three workstreams in one sprint:

1. **i18n error mapping**: `ERROR_MAP` lookup + `apiErrors` translation keys. Replaced hardcoded strings in auth callback, quiz, report, and IC onboarding pages with `t()` calls.

2. **Dashboard bug fix (BooleanField conversion)**: Converted `StudentProfile.colorblind` and `disability` from `CharField("Ya"/"Tidak")` to `BooleanField`. Updated engine.py, stpm_engine.py, serializers.py, views.py, and all test files (~50 student profiles). Migration 0046 applied to Supabase.

3. **UI fixes**: Landing page stats (1,300+ / 800+), login button compact styling (prevents text wrap on mobile), profile incomplete count badge (was hardcoded to "1").

## What Went Well

- **Root cause investigation paid off**: User's report of intermittent "Failed to load recommendations" led to a thorough investigation that found the real bug — a CharField/BooleanField mismatch introduced when the profile sync was built. The symptom (intermittent failures) was misleading; it only happened for logged-in users whose profile had been synced from the backend.
- **End-to-end conversion was clean**: Despite touching 8+ files and ~50 test data entries, the golden masters (SPM=5319, STPM=2026) remained unchanged — confirming the conversion was semantically identical.
- **`replace_all` saved time**: Bulk-replacing `colorblind='Tidak'` → `colorblind=False` across 50 lines in the golden master test was instant.

## What Went Wrong

1. **Initial misdiagnosis as Cloud Run cold start.**
   - *Symptom*: Dashboard showed "Failed to load recommendations" intermittently.
   - *Root cause*: Hypothesised cold start latency. The user corrected this — "I don't have the same problem when I click explore though" — which proved the backend was fine, and the issue was specific to the eligibility endpoint receiving "Ya"/"Tidak" strings.
   - *Fix*: User feedback forced proper investigation. Lesson: when a user reports "intermittent", always check what differentiates the failing path from the working path before guessing infrastructure.

2. **Proposed a stopgap fix before the canonical fix.**
   - *Symptom*: Proposed a two-part workaround (serializer accepts "Ya"/"Tidak" + frontend normalises) instead of fixing the data model.
   - *Root cause*: Defaulted to minimal-change thinking. The user explicitly asked "Is this a canonical fix?" — it wasn't.
   - *Fix*: User preference documented — no stopgaps or workarounds. Fix the actual data model. This is already in the feedback memory.

## Design Decisions

1. **CharField → BooleanField (not serializer workaround)**: The canonical fix is at the data model layer. The serializer previously converted `True/False` → `"Ya"/"Tidak"` for the engine; now booleans flow through unchanged. This eliminates the entire class of "string boolean" bugs.

## Numbers

- Files changed: 22 (9 backend, 1 migration, 8 frontend, 3 i18n message files, 1 error-i18n lib)
- Tests: 892 pass, 0 fail
- Golden masters: SPM 5319, STPM 2026 (unchanged)
- Supabase migration: 0046 applied (data converted in-place)
