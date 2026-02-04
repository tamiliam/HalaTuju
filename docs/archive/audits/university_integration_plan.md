# University Integration Plan

> **Status**: PENDING - Data Files Required
>
> **Last Updated**: 2026-02-03
>
> **Blocked By**: Missing data files (see Data Requirements below)

## Overview

This plan outlines the integration of **Asasi (Foundation)** and **Universiti Awam (Public University)** programs into HalaTuju. This will add 2 new categories to the existing 4 (Poly, KK, ILJTM, ILKBS), bringing the total to 6 institution types.

## Current State

### Existing Data (Ready)
- `university_requirements.csv` - 221 courses with eligibility requirements and merit cutoffs
- `university_courses_update.csv` - Minimal course info (course_id, course name, wbl flag)

### What's Missing

The university data does **NOT** follow the same structure as Poly/KK and TVET data. Key files are missing or incomplete.

---

## Data Requirements Checklist

Before implementation can proceed, the following data files must be created/populated:

### 1. `university_institutions.csv` (NEW FILE REQUIRED)

Must follow the same structure as `institutions.csv` and `tvet_institutions.csv`.

**Required Columns:**
| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `institution_id` | string | Unique ID | `UA-UKM`, `UA-UM`, `UA-USM` |
| `institution_name` | string | Full name | `Universiti Kebangsaan Malaysia` |
| `acronym` | string | Short form | `UKM` |
| `type` | string | Institution type | `UA` |
| `category` | string | Category | `Universiti Awam` or `Asasi` |
| `subcategory` | string | Optional grouping | `Research University`, `Comprehensive`, etc. |
| `State` | string | Location state | `Selangor` |
| `address` | string | Full address | `43600 UKM Bangi, Selangor` |
| `phone` | string | Contact number | `03-89215555` |
| `url` | string | Official website | `https://www.ukm.my` |
| `latitude` | float | GPS coordinate | `2.9214` |
| `longitude` | float | GPS coordinate | `101.7764` |

**Malaysian Public Universities to Include:**
1. Universiti Malaya (UM)
2. Universiti Kebangsaan Malaysia (UKM)
3. Universiti Sains Malaysia (USM)
4. Universiti Putra Malaysia (UPM)
5. Universiti Teknologi Malaysia (UTM)
6. Universiti Utara Malaysia (UUM)
7. Universiti Islam Antarabangsa Malaysia (UIAM)
8. Universiti Malaysia Sabah (UMS)
9. Universiti Malaysia Sarawak (UNIMAS)
10. Universiti Pendidikan Sultan Idris (UPSI)
11. Universiti Teknologi MARA (UiTM) - **Note: Exclude if Bumiputra-only**
12. Universiti Malaysia Terengganu (UMT)
13. Universiti Sultan Zainal Abidin (UniSZA)
14. Universiti Tun Hussein Onn Malaysia (UTHM)
15. Universiti Teknikal Malaysia Melaka (UTeM)
16. Universiti Malaysia Pahang Al-Sultan Abdullah (UMPSA)
17. Universiti Malaysia Perlis (UniMAP)
18. Universiti Malaysia Kelantan (UMK)
19. Universiti Pertahanan Nasional Malaysia (UPNM)
20. Universiti Sains Islam Malaysia (USIM)

### 2. `university_courses.csv` (EXPAND EXISTING)

Rename/expand `university_courses_update.csv` to include full course details.

**Required Columns:**
| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `course_id` | string | Unique ID | `UH0010003` |
| `course` | string | Course name | `ASASI AGRISAINS` |
| `wbl` | int | Work-based learning flag | `0` or `1` |
| `level` | string | Education level | `Foundation`, `Degree` |
| `department` | string | Faculty/Department | `Fakulti Pertanian` |
| `field` | string | Field of study | `Agriculture` |
| `frontend_label` | string | Display category | `Sains & Teknologi` |
| `semesters` | int | Duration | `2` (Asasi), `8` (Degree) |
| `description` | text | Course description | Full description |
| `career` | text | Career prospects | Career info |

### 3. `university_links.csv` (NEW FILE REQUIRED)

Maps courses to institutions (one course may be offered at multiple universities).

**Required Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `institution_id` | string | Links to university_institutions.csv |
| `course_id` | string | Links to university_courses.csv |

### 4. Update `university_requirements.csv`

Current file has requirements but needs cleanup:
- [ ] Extract course names from `notes` column into proper `course` column
- [ ] Extract institution names from `notes` into separate linking
- [ ] Remove any Bumiputra-only courses
- [ ] Verify all requirement columns align with engine expectations

---

## Code Changes (Ready to Implement)

Once data files are ready, the following code changes can be applied:

### 1. `src/data_manager.py`
- Uncomment/enable UA data loading section (lines 205-247)
- Load `university_institutions.csv`, `university_courses.csv`, `university_links.csv`
- Merge similar to Poly/KK pattern

### 2. `src/dashboard.py`
- Uncomment Asasi/UA detection in `get_institution_type()` (lines 87-92)
- Add `inst_asasi`, `inst_ua` to `stats_keys` array
- Update `total_matches` calculation

### 3. `main.py`
- Change from 4 columns to 6 columns for stats display
- Order alphabetically: Asasi, ILJTM, ILKBS, Kolej Komuniti, Politeknik, Universiti Awam

### 4. `src/translations.py`
Add translations for new categories:

```python
# English
"inst_asasi": "Asasi (Foundation)",
"inst_ua": "Public University",

# Bahasa Malaysia
"inst_asasi": "Asasi",
"inst_ua": "Universiti Awam",

# Tamil
"inst_asasi": "அசாசி (அடித்தளம்)",
"inst_ua": "அரசு பல்கலைக்கழகம்",
```

---

## Implementation Checklist

### Phase 1: Data Preparation
- [ ] Create `university_institutions.csv` with all 20 public universities
- [ ] Expand `university_courses.csv` with full course details
- [ ] Create `university_links.csv` mapping courses to institutions
- [ ] Clean `university_requirements.csv` (extract from notes column)
- [ ] Verify no Bumiputra-only restrictions in data
- [ ] Add course tags to `course_tags.json` for UA courses (for ranking)
- [ ] Add institution modifiers to `institutions.json` for UA (for ranking)

### Phase 2: Code Implementation
- [ ] Enable UA loading in `data_manager.py`
- [ ] Update `dashboard.py` with Asasi/UA categories
- [ ] Update `main.py` for 6-column display
- [ ] Add translations for new categories
- [ ] Run golden master tests
- [ ] Test locally with sample student profiles

### Phase 3: Testing & Validation
- [ ] Verify all UA courses display correctly
- [ ] Check merit badges show for UA courses
- [ ] Confirm Asasi vs Degree classification works
- [ ] Test alphabetical ordering of categories
- [ ] Validate no broken cards or missing data

---

## Notes

### Why This Was Deferred (2026-02-03)
Initial implementation attempt revealed that university data files don't follow the established pattern. Course cards would display with significant gaps (missing institution names, states, URLs, etc.) leading to poor UX.

### Bumiputra-Only Policy
Some programs (especially at UiTM) may be restricted to Bumiputra students. These should be:
1. Identified during data preparation
2. Either excluded entirely OR clearly marked with eligibility warnings
3. User confirmed: "There shouldn't be any courses restricted only to Bumiputra"

### Merit Cutoffs
University requirements file already contains `merit_cutoff` data. This will integrate with the existing merit badge system once enabled.

---

## Related Files

- `data/university_requirements.csv` - Current requirements (221 courses)
- `data/university_courses_update.csv` - Minimal course data
- `src/data_manager.py` - Data loading (UA section disabled at line 205)
- `src/dashboard.py` - Category detection (UA commented out at line 87)
- `main.py` - Stats display (line 1263)
