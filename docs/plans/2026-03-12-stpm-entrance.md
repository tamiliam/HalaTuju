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
| Sprint 4 | Dashboard integration + ranking | Tasks 15-18 | **NEXT** |
| Sprint 5 | Search/filter, course detail, polish | Tasks 19-22 | |

---

## Sprint 4: Dashboard Integration + Ranking

### Task 15: STPM results on dashboard

**Files:**
- Modify: `halatuju-web/src/app/dashboard/page.tsx`
- Modify: `halatuju-web/src/components/CourseCard.tsx`

**Step 1: Route dashboard by exam type**

If `profile.exam_type === 'stpm'`:
- Call STPM eligibility endpoint instead of SPM
- Display degree programmes instead of diploma/sijil courses
- Show university name, CGPA requirement, MUET requirement

**Step 2: Adapt CourseCard for STPM programmes**

- Programme name (not course name)
- University (not institution)
- Min CGPA badge
- MUET band badge
- Interview required badge

**Step 3: Test manually, commit**

---

### Task 16: STPM ranking engine

**Files:**
- Create or modify: `halatuju_api/apps/courses/stpm_ranking.py`
- Test: `halatuju_api/apps/courses/tests/test_stpm_ranking.py`

**Step 1: Write ranking tests**

Ranking for STPM should consider:
- CGPA margin (how far above min_cgpa)
- University prestige (UA type)
- Stream match
- Quiz signals (reuse existing quiz infrastructure)

**Step 2: Implement ranking**

Simple ranking based on:
1. CGPA margin (student CGPA - min CGPA) → higher margin = safer bet
2. University prestige bonus
3. Quiz field interest match (reuse FIELD_LABEL_MAP concept)

**Step 3: Run tests, commit**

---

### Task 17: STPM ranking API endpoint

**Files:**
- Modify: `halatuju_api/apps/courses/views.py`
- Modify: `halatuju_api/apps/courses/urls.py`

Add `POST /api/v1/stpm/ranking/` endpoint that takes STPM eligibility results + student signals → returns ranked programmes.

**Step 1: Write tests**
**Step 2: Implement view**
**Step 3: Run tests, commit**

---

### Task 18: Sprint 4 close

Run full test suite, update CHANGELOG, commit and push.

---

## Sprint 5: Search, Course Detail, Polish

### Task 19: STPM programme detail page

**Files:**
- Create: `halatuju-web/src/app/stpm/[id]/page.tsx`

Show:
- Programme name
- University
- All STPM requirements (subjects, grades, CGPA)
- SPM prerequisites
- MUET band
- Interview/colorblind/medical flags
- Link to university website (if available)

---

### Task 20: STPM search with filters

**Files:**
- Modify: `halatuju-web/src/app/search/page.tsx`

Add STPM tab or route to search page:
- Text search
- Filter by university
- Filter by stream (science/arts)
- Filter by min CGPA range
- Pagination

---

### Task 21: i18n completion for STPM

**Files:**
- Modify: `halatuju-web/src/messages/en.json`, `ms.json`, `ta.json`

Add all STPM-specific strings in all 3 languages. Run `scripts/check-i18n.js` to verify parity.

---

### Task 22: Sprint 5 close — full integration test + release

**Step 1: Full test suite**

```bash
# Backend
cd halatuju_api && python -m pytest apps/courses/tests/ -v

# Golden masters
python -m pytest apps/courses/tests/test_golden_master.py -v  # SPM: 8283
python -m pytest apps/courses/tests/test_stpm_golden_master.py -v  # STPM: TBD
```

**Step 2: Manual E2E test**

1. Fresh user → select STPM → enter grades → see dashboard
2. Verify programme count is reasonable
3. Verify search works
4. Verify programme detail shows correct requirements

**Step 3: Deploy to Cloud Run**

**Step 4: Update CHANGELOG, tag release, push**

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
