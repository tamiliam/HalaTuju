# STPM Entrance — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow STPM (Form 6) graduates to check which degree programmes they qualify for, based on their STPM grades, CGPA, MUET band, and SPM prerequisites.

**Architecture:** New user flow parallel to the existing SPM flow. STPM students enter their STPM grades + MUET band + SPM grades → new STPM eligibility engine checks against ~1,680 degree programmes loaded from CSV into new Django models → results ranked and displayed on the existing dashboard. The current SPM flow is untouched — exam type selection at onboarding routes to the correct engine.

**Tech Stack:** Django REST (models, management command, engine, views), Supabase PostgreSQL, Next.js 14 (onboarding pages, grade entry), existing quiz + ranking infrastructure.

---

## Data Overview

- **Source CSVs:** `stpm_science_requirements_parsed.csv` (1,003 rows), `stpm_arts_requirements_parsed.csv` (677 rows)
- **Total:** ~1,680 degree programmes across ~20 public universities
- **Key columns:** `program_id`, `program_name`, `university`, `stream` (science/arts/both), `min_cgpa`, `stpm_min_subjects`, `stpm_min_grade`, individual STPM subject requirements (`stpm_req_pa`, `stpm_req_math_t`, etc.), `stpm_subject_group` (JSON), SPM prerequisites (`spm_credit_bm`, `spm_pass_sejarah`, etc.), `spm_subject_group` (JSON), `min_muet_band`, `req_interview`, `no_colorblind`, `req_medical_fitness`, `req_malaysian`, `req_bumiputera`
- **STPM subjects:** 20 subjects (PA compulsory + 19 electives), grades A+ to G
- **CGPA:** Calculated from STPM grades (4.0 scale: A=4.0, A-=3.67, B+=3.33, B=3.0, C+=2.67, C=2.33, C-=2.0, D=1.67, E=1.0, F=0)
- **MUET:** Malaysian University English Test, bands 1-6

## Sprint Breakdown

| Sprint | Deliverable | Tasks |
|--------|-------------|-------|
| ~~Sprint 1~~ | ~~Data models + CSV loader + golden master~~ | ~~Tasks 1-5~~ | DONE |
| ~~Sprint 2~~ | ~~STPM eligibility engine + API endpoint~~ | ~~Tasks 6-10~~ | DONE |
| ~~Sprint 3~~ | ~~Frontend onboarding + grade entry~~ | ~~Tasks 11-14~~ | DONE |
| ~~Sprint 4~~ | ~~Dashboard integration + ranking~~ | ~~Tasks 15-18~~ | DONE |
| ~~Sprint 5~~ | ~~Search/filter, course detail, polish~~ | ~~Tasks 19-22~~ | DONE |

---

## Sprints 4-5: COMPLETED

All tasks 15-22 completed across STPM Sprints 3-4 (project-local numbering). See retrospectives:
- `docs/retrospective-stpm-sprint3.md` (ranking engine, Supabase migration, dashboard integration)
- `docs/retrospective-stpm-sprint4.md` (search API, detail API, search page, detail page, i18n)

---

## Risk Register

| Risk | Mitigation |
|------|-----------|
| CSV data quality (parse_confidence < 1.0) | Log low-confidence rows, manual review of edge cases |
| CGPA calculation differs from official MQA | Cross-check with 3 official university websites |
| Subject group JSON parsing errors | Validate all JSON on load, reject malformed rows |
| Performance: 1,680 programmes × N DB queries | Load into DataFrame at startup (same as SPM engine) |
| SPM flow regression | Existing 250 tests + golden master 8283 must pass unchanged |
| STPM subject code mismatch CSV↔frontend | Single source of truth in `stpm_subject_codes.json` |

## Dependencies

- Parsed CSV data files (already available at `Archived/Random/data/`)
- `stpm_subject_codes.json` (already available)
- Supabase project has capacity for 2 new tables (~1,680 rows each)
- No new external APIs or services needed

## Out of Scope

- STPM prediction ("will I pass STPM?") — this is post-STPM eligibility only
- Private university (IPTS) programmes — public universities only for now
- Matric → degree pathway (future feature)
- STPM student financial aid / scholarship matching
