# HalaTuju Documentation

**Last Updated:** 2026-02-04

---

## Live Documentation (Source of Truth)

| Document | Description |
|----------|-------------|
| [ranking_logic.md](ranking_logic.md) | v1.5 - Ranking algorithm, scoring rules, tie-breaking hierarchy |
| [DATA_FOLDER_POLICY.md](DATA_FOLDER_POLICY.md) | Data management rules, file consolidation guidelines |

---

## Roadmap (Future Plans)

All implementation plans live in `roadmap/`. Each file must have a status header.

### v1.x Release (Current)

| Plan | Status | Priority | Description |
|------|--------|----------|-------------|
| [v1.x_remaining_work.md](roadmap/v1.x_remaining_work.md) | **MASTER** | - | Consolidated view of all v1.x work |
| UI/UX Flow Rework | ACTIVE | **CRITICAL** | Users confused, leaving app |
| Counselor Report Update | ACTIVE | **HIGH** | Add merit/UA to PDF report |
| [pismp_integration_plan.md](roadmap/pismp_integration_plan.md) | ACTIVE | HIGH | 74 teacher training programs |
| [ui_ux_improvement_plan.md](roadmap/ui_ux_improvement_plan.md) | DEFERRED | LOW | Phase 2: Elective multiselect |
| [university_requirements_rebuild_plan.md](roadmap/university_requirements_rebuild_plan.md) | DEFERRED | LOW | Enhanced syarat_khas parsing |

### v2.x Release (Future)

| Plan | Status | Description |
|------|--------|-------------|
| [stpm_implementation_plan.md](roadmap/stpm_implementation_plan.md) | DEFERRED | STPM eligibility engine (needs UI/UX rethink) |

**Status Values:**
- `ACTIVE` - Currently being worked on
- `PLANNED` - Approved, ready to start
- `DEFERRED` - On hold / paused
- `CLOSED` - Policy decision made, no action needed

---

## Archive (Historical Reference)

### Completed Work (2026-02)

Implementation summaries for finished features. Useful for understanding how things were built.

| Document | What Was Done |
|----------|---------------|
| [CONSOLIDATION_SUMMARY](archive/2026-02-completed/CONSOLIDATION_SUMMARY_2026-02-04.md) | Master summary of Feb 2026 data consolidation |
| [ua_ranking_complete](archive/2026-02-completed/ua_ranking_complete.md) | 87 UA courses tagged, 20 institutions ranked |
| [university_integration_complete](archive/2026-02-completed/university_integration_complete.md) | UA courses merged into main system |
| [data_consolidation_complete](archive/2026-02-completed/data_consolidation_complete.md) | Poly/KK/UA data unified |
| [institution_sync_complete](archive/2026-02-completed/institution_sync_complete.md) | institutions.csv/json synchronized |
| [requirements_cleanup_complete](archive/2026-02-completed/requirements_cleanup_complete.md) | Requirements CSV standardized |
| [merit_integration_plan](archive/2026-02-completed/merit_integration_plan.md) | Merit badges on course cards |
| [project_cleanup_plan](archive/2026-02-completed/project_cleanup_plan.md) | Scripts moved to scripts/analysis/ |
| [spm_subject_expansion_plan](archive/2026-02-completed/spm_subject_expansion_plan.md) | CLOSED: Policy decision made on subject coverage |

### Audits & Analysis

One-time analysis reports and superseded planning docs.

| Document | Purpose |
|----------|---------|
| [spm_subject_analysis_report](archive/audits/spm_subject_analysis_report.md) | SPM subject coverage gap analysis |
| [data_files_audit](archive/audits/data_files_audit.md) | Initial data file inventory |
| [data_files_comprehensive_audit](archive/audits/data_files_comprehensive_audit.md) | Detailed column-level audit |
| [implementation_plan](archive/audits/implementation_plan.md) | Original UA integration plan (superseded) |
| [university_integration_plan](archive/audits/university_integration_plan.md) | UA plan before completion |
| [public_university_integration_plan](archive/audits/public_university_integration_plan.md) | Early draft (superseded) |
| [data_consolidation_plan](archive/audits/data_consolidation_plan.md) | Plan before consolidation |

---

## Management Rules

### Naming Conventions
- `*_plan.md` - Future work (lives in `roadmap/`)
- `*_complete.md` - Done (archive immediately)
- No suffix - Live documentation (stays in root)

### Required Status Header
Every plan file must start with:
```markdown
> **Status**: ACTIVE | PLANNED | DEFERRED | COMPLETED
> **Last Updated**: YYYY-MM-DD
```

### Monthly Cleanup
At month-end, move all `*_complete.md` files to `archive/YYYY-MM-completed/`
