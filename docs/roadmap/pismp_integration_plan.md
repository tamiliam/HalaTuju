# PISMP Integration Plan

> **Status:** ACTIVE (v1.x)
> **Last Updated:** 2026-02-04
> **Priority:** HIGH - Must complete this release

---

## 1. Current State

### Data Available
| Item | Location | Count | Status |
|------|----------|-------|--------|
| Requirements Draft | `data/archive/pismp_requirements_draft.csv` | 74 programs | ✅ Parsed |
| Source PDF | `SchoolScraper/input_docs/01_PISMP 2025...pdf` | - | ✅ Available |
| Parser Script | `Random/scripts/etl/parse_pismp.py` | - | ✅ Exists |

### Data Structure (Already Defined)
```csv
type,course_id,course_name,min_credits,age_limit,req_malaysian,pass_bm,...,subject_group_req,notes
PISMP,50PD010M00P,Bahasa Melayu Pendidikan Rendah,5,20,1,...,"[{...}]",General: 5 Cemerlang
```

### Key Requirement Pattern
- All PISMP programs require **5 Cemerlang (A-/A/A+)** minimum
- Age limit: 20 years
- Malaysian citizens only
- Subject-specific requirements via `subject_group_req` JSON

---

## 2. Integration Tasks

### Phase 1: Data Finalization
- [ ] Move `data/archive/pismp_requirements_draft.csv` → `data/pismp_requirements.csv`
- [ ] Verify subject key mappings match engine (BM, BI, HISTORY, MATH, etc.)
- [ ] Add missing institution data (IPG locations)

### Phase 2: Engine Extension
- [ ] Add PISMP to `data_manager.py` loading logic
- [ ] Ensure `subject_group_req` JSON parsing works for PISMP
- [ ] Add age eligibility check (if not already present)

### Phase 3: Dashboard Integration
- [ ] Add "PISMP" / "Teacher Training" category to dashboard
- [ ] Add institution type filter for IPG
- [ ] Add translations (EN/BM/TA) for PISMP labels

### Phase 4: Testing
- [ ] Verify eligibility logic with sample profiles
- [ ] Check that high-achieving students (5A+) see PISMP courses
- [ ] Verify average students (3A, 2C) are correctly excluded

---

## 3. Missing Data (To Be Filled)

| Field | Current State | Action Needed |
|-------|---------------|---------------|
| **Institution ID** | Not assigned | Create IPG institution entries |
| **Institution Name** | Not in CSV | Map to IPG campuses |
| **Duration** | Not in CSV | Default to "4 Tahun" (standard PISMP) |
| **Fees** | Not in CSV | "Fully Sponsored" (MOE scholarship) |
| **Course Details** | Empty | Add synopsis from PDF |
| **Jobs** | Empty | "Guru Sekolah Rendah" default |

---

## 4. IPG Institutions to Add

PISMP is offered at Institut Pendidikan Guru (IPG) campuses nationwide:

| ID | Name | State |
|----|------|-------|
| IPG001 | IPG Kampus Bahasa Melayu | Kuala Lumpur |
| IPG002 | IPG Kampus Bahasa Antarabangsa | Kuala Lumpur |
| IPG003 | IPG Kampus Ilmu Khas | Kuala Lumpur |
| IPG004 | IPG Kampus Pendidikan Islam | Selangor |
| ... | (27 campuses total) | Various |

---

## 5. Worst Case Scope

If full integration is not feasible, minimum viable:
1. Load PISMP requirements CSV
2. Show in results with basic card (no location details)
3. Link to official PISMP application portal

---

## 6. Dependencies

- `subject_group_req` JSON parsing (already implemented for UA)
- Dashboard category system (already supports multiple types)
- Institution type mapping (need to add IPG type)

---

## 7. Estimated Effort

| Task | Effort |
|------|--------|
| Data finalization | 1-2 hours |
| Engine extension | 2-3 hours |
| Dashboard integration | 2-3 hours |
| Testing | 1-2 hours |
| **Total** | **6-10 hours** |
