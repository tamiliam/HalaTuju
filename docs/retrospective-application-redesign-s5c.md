# Retrospective — Step-4 Redesign S5c: AI sponsor-profile generator rebuilt + Tamil/BM-aware (v2.4.6)

**Date:** 2026-05-28
**Shipped:** web `halatuju-web-00219-8ck`, api `halatuju-api-00177-vm2` (both builds SUCCESS, 100% traffic, smoke 200). **No migration. Resolves TD-060.**

## What Was Built

The AI sponsor-profile generator (`profile_engine.py`), which TD-060 flagged as broken against the post-refactor schema:

- **`_build_prompt` rewritten** to the current data model: profile-canonical academic/financial (`profile.exam_type`, `count_spm_a_grades(profile.grades)`, `profile.stpm_cgpa`, `household_income/size`, `receives_str/jkm`), the "Your story" narrative (`aspirations`, `plans`, `first_in_family`, `parents_occupation`, `siblings_studying`, `family_context`, `daily_life`), the pathway (`field_of_study` + `pathways_considered`), the simplified funding (`categories` + `funding_note` + `programme_months` — **not** the dead `total`), and referees.
- **Language-aware.** The prompt tells the model the student's own words may be in **Malay, English, or Tamil** (understand all three) and to write the profile in a **target language**. `generate_sponsor_profile(application, language=None)` defaults output to the applicant's locale (en→English, ms→Malay); the admin overrides via an **EN / BM** selector on `/admin/scholarship/[id]`.
- **Tests:** new `test_profile_engine.py` (8) exercises the *pure* prompt builder — current fields present, multilingual + target-language instructions present, no dead `total`, language resolution, and the **TD-060 regression** (no `AttributeError` on a current-model application). Gemini is never called.

**This completes the Step-4 redesign (S1–S5c).**

## What Went Well

- **Pure-function design made it testable without paid calls.** `_build_prompt` and `_resolve_language` are pure, so 8 unit tests cover the rebuild end-to-end with Gemini untouched — no API key, no cost, no flakiness.
- **Discovery → fix in one cycle.** S5b's scoping found the broken generator; S5c fixed it the same session, with the regression test locking it.
- **Serial gates stayed clean.** `next build` then full `pytest` run serially → 1143 passed, no contention noise.

## What Went Wrong

1. **The generator silently rotted for several sprints — and the tests didn't catch it.**
   - *Symptom:* `_build_prompt` referenced four fields the profile-canonical refactor had removed; a real "Generate" call would have 500'd. It went unnoticed across the refactor + S1–S5b.
   - *Root cause:* the only coverage was `test_admin_scholarship.py` mocking **the entire `generate_sponsor_profile`** function. Mocking the whole unit meant the prompt **builder inside it was never executed** in any test, so schema drift (removed fields) failed nowhere. The dormant programme + no API key in CI hid it further.
   - *System change:* added a lesson — when a unit wraps an external call (AI/HTTP/etc.), **extract the payload/prompt builder as a pure function and unit-test it directly**, so input-schema drift fails loudly even while the external call stays mocked. S5c did exactly this (`test_profile_engine.py`).

## Design Decisions

- **Output language defaults to the applicant's locale, with an admin EN/BM override; Tamil *input* understood, Tamil *output* deferred to Phase 2.** The profile is sponsor-facing and sponsors read EN/BM, so Tamil output isn't needed yet — but the student may well write their story in Tamil, so understanding Tamil *input* is the real requirement and is handled now. Output language is a **prompt parameter**, not a stored column, so enabling Tamil output later (or per-sponsor language) is a one-line change with no migration.
- **`language` accepts a locale code or a full name** (`_resolve_language`), so the admin endpoint can pass `'en'`/`'ms'` while the prompt gets "English"/"Malay (Bahasa Melayu)".

(Logged in `docs/decisions.md`.)

## Numbers

- Files changed: 9 (`profile_engine.py`, `views_admin.py`, `test_profile_engine.py` [new], `admin-api.ts`, `admin/scholarship/[id]/page.tsx`, en/ms/ta.json) + CHANGELOG. **No migration.**
- Backend: 1143 pytest (+8). Frontend: jest 125 (unchanged; admin page build-verified). `next build` clean.
- i18n parity: 1246 keys × {en, ms, ta} (+1).
- Deploys: 1 (web + api). **No paid Gemini calls** — a live end-to-end generation check remains an admin-triggered, billable call (programme dormant).
