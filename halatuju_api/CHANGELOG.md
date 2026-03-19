# Changelog

## W14+W21 Ranking Tiebreak & Science Tracks Sprint — 2026-03-20

### Added
- **W14: STPM 5-level sort tiebreaking** — replaced 2-level sort (score, name) with 5-level: score → university tier (research=3, comprehensive=2, focused=1) → min_cgpa competitiveness → difficulty_level → name. UNIVERSITY_TIER map covers 5 research and 4 comprehensive universities. 5 tests.
- **W21: TRACK_FIELD_MAP science tracks** — added `matric:sains` and `stpm:sains` mapping to `field_health` + `field_agriculture`. Science-track pre-U students with health/agriculture interest now get +3 field preference bonus. 3 tests.

### Changed
- Test count: 958 → 966

## W7 FIELD_KEY_MAP Expansion Sprint — 2026-03-20

### Added
- **W7: Expanded FIELD_KEY_MAP** — 7 new field_key mappings to existing quiz signals: kejururawatan+pergigian→field_health, sains-data→field_digital, kejuruteraan-am→field_mechanical+field_heavy_industry, komunikasi→field_creative, sains-fizikal→field_agriculture. Coverage: 22/37 → 30/37 leaf keys. 8 tests.

### Changed
- Test count: 932 → 940
- Search filter pills now sorted alphabetically (source type + field)

## Ranking Improvements Sprint — 2026-03-19

### Added
- **W4: PISMP course tag backfill** — `backfill_pismp_tags` management command maps 12 specialisations (Sains, Matematik, Jasmani, Seni Visual, Muzik, Reka Bentuk, Kaunseling, Khas Masalah/Pendengaran/Penglihatan, Kanak-Kanak, Sejarah, Islam, Languages) to CourseTag dimensions. 73 PISMP courses backfilled in production Supabase. 33 tests.
- **W11: STPM pre-quiz RIASEC signal** — `StpmRankingView` derives RIASEC seed from `stpm_subjects` when no quiz signals present, using existing `calculate_riasec_seed()`. Science students see I-type programmes ranked higher; arts students see A-type higher. Post-quiz signals take precedence. Frontend sends subject keys from grade input. 7 tests.
- **Ranking audit document** — Comprehensive audit of all 4 ranking modes (SPM pre/post quiz, STPM pre/post quiz) with scoring rules, point adjustments, sort hierarchies, and priority matrix. See `docs/2026-03-18-ranking-audit.md`.

### Changed
- Test count: 892 → 932
- CLAUDE.md: Updated pending ranking work items (W4 done, W11 done, W16 resolved, W21 documented)

### Fixed
- STPM pre-quiz ranking no longer CGPA-only — science and arts students now see field-aligned programmes ranked appropriately without needing to complete the quiz first
