# Retrospective — SPM Prereq UI & Content Sprint

**Date:** 2026-03-18
**Duration:** ~1 session
**Commits:** 3

---

## What Was Built

1. **STPM SPM prerequisite stream-based UI** — Section 4 of the STPM grades page (`stpm-grades/page.tsx`) was redesigned from a flat compulsory+optional layout to a stream-based selection pattern:
   - 3 stream pills (Science, Arts, Technical) — vocational excluded per user instruction
   - 4 stream subject dropdown slots that populate based on selected stream
   - 0-2 elective slots with add/remove capability
   - New data structures: `SPM_PREREQ_STREAM_POOLS`, `SPM_ALL_ELECTIVE_SUBJECTS`
   - `SPM_PREREQ_OPTIONAL` expanded from 2 to 9 entries

2. **Admin layout fixes** — NRIC/phone display formatting standardised, mobile responsive layout improved

3. **Site content update** — Marketing/content text updated to reference both SPM and STPM students (was SPM-only)

---

## What Went Well

- **Stitch-first design**: Used Stitch to prototype 3 design variations before coding. User selected the cleanest option, and the final code matched the design closely.
- **Reuse of SPM pattern**: The SPM subject selection UI pattern (stream pills → core → stream → elective) was successfully replicated for STPM SPM prerequisites, maintaining UX consistency.
- **User-driven simplification**: User correctly pushed back on an over-engineered accordion design with 9 collapsible categories for 100+ subjects. The stream-based approach with 3 buttons is much simpler and more effective.

---

## What Went Wrong

1. **Over-engineered initial design**
   - *What happened:* First proposal was an accordion-based UI with 9 collapsible categories covering all 100+ SPM subjects
   - *Why:* Tried to expose every possible subject in the UI instead of thinking about the student's workflow (pick a stream first, then subjects narrow down)
   - *Fix:* When designing subject selection UIs, always start with "how do we narrow the choice?" not "how do we show everything?"

2. **Multiple Stitch attempts needed**
   - *What happened:* First two Stitch screen generation attempts returned empty results
   - *Why:* Insufficient detail in prompts and wrong model selection
   - *Fix:* Use GEMINI_3_PRO model for Stitch and provide detailed component-level descriptions in the prompt

---

## Design Decisions

- **3 stream buttons, not 4**: Vocational stream excluded from UI per user instruction. Vocational subjects remain mapped in the backend (SPM_CODE_MAP has all `voc_*` keys) but are not selectable in the STPM prereq UI.
- **Islamic subjects excluded**: Agama stream and all Islamic studies subjects excluded from frontend scope. Backend handles them correctly.

---

## Numbers

| Metric | Value |
|--------|-------|
| Commits | 3 |
| Backend tests | 654 (unchanged) |
| Frontend tests | 17 (unchanged) |
| New i18n keys | 7 × 3 languages |
| New subject names | 8 |
| SPM golden master | 5319 (unchanged) |
| STPM golden master | 2026 (unchanged) |
