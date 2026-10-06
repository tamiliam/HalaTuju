# Retrospective — Field Taxonomy Sprint 3: Ranking Engine field_key Integration

**Date:** 2026-03-16
**Sprint:** Field Taxonomy Sprint 3

---

## What Was Built

1. **SPM ranking engine** — `FIELD_LABEL_MAP` (frontend_label strings) replaced with `FIELD_KEY_MAP` (taxonomy keys). `calculate_fit_score` now accepts `field_key` parameter. Field interest matching uses taxonomy keys instead of BM label strings.

2. **STPM ranking engine** — Removed 48-line `COURSE_FIELD_MAP` keyword→signal map and keyword-scanning `_match_field_interest`. Replaced with simple `field_key` lookup against shared `FIELD_KEY_MAP` imported from ranking_engine (DRY).

3. **Eligibility results** — Added `field_key` to both SPM and STPM eligibility result dicts so ranking engines receive it.

4. **Bug fix** — `field_health` signal now correctly maps to health fields (`perubatan`, `farmasi`, `sains-hayat`) instead of agriculture (`Pertanian & Bio-Industri`). This was a mapping error in the original `FIELD_LABEL_MAP`.

---

## What Went Well

- **Clean, focused sprint** — only 6 files modified, no surprises or blockers.
- **DRY improvement** — both SPM and STPM ranking engines now share a single `FIELD_KEY_MAP`. Previously they had completely separate mapping structures (one using label strings, the other using keyword scanning).
- **No golden master breakage** — both SPM (5319) and STPM (1811) baselines unaffected. Ranking changes don't affect eligibility.
- **STPM simplification** — `_match_field_interest` went from 10-line keyword scanner to 6-line field_key lookup.

---

## What Went Wrong

Nothing significant. This was a straightforward refactoring sprint with well-understood inputs and outputs.

---

## Design Decisions

- **Shared `FIELD_KEY_MAP`** — STPM ranking imports from SPM ranking engine rather than maintaining its own copy. This follows the existing architectural decision to keep ranking modules separate while sharing constants where appropriate.
- **`field_key` as parameter, not in course_tags** — added `field_key` as an explicit parameter to `calculate_fit_score` rather than stuffing it into the course_tags_map. Clearer intent and avoids coupling ranking to the tags data structure.

---

## Numbers

| Metric | Value |
|--------|-------|
| Files modified | 6 |
| Lines removed | ~60 (COURSE_FIELD_MAP, FIELD_LABEL_MAP) |
| Lines added | ~30 (FIELD_KEY_MAP, field_key plumbing) |
| New tests | 2 |
| Total tests | 544 |
| Golden master | Unchanged (SPM=5319, STPM=1811) |
