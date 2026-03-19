# Changelog

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
