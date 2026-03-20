# Architecture Decisions

## W11 RIASEC injection at view layer — Ranking Improvements Sprint, 2026-03-19
**Decision:** Derive RIASEC seed from STPM subjects in `StpmRankingView.post()` (view layer), not inside the ranking engine.
**Alternatives considered:** (A) Inject in `get_stpm_ranked_results()` inside stpm_ranking.py, (B) Add a middleware/preprocessor.
**Rationale:** Keeps the ranking engine pure — it just consumes whatever signals dict it receives. The view is already responsible for assembling the request. Easier to test via API calls.
**Trade-offs:** View has slightly more logic, but it's 10 lines and clearly marked with a W11 comment.
**Revisit if:** Multiple callers of the ranking engine need the same pre-processing (would warrant extracting to a shared preprocessor).

## W14 UNIVERSITY_TIER three-tier grouping — W14+W21 Sprint, 2026-03-20
**Decision:** Group Malaysian universities into 3 tiers for STPM sort tiebreaking: Research (UM, USM, UKM, UPM, UTM = tier 3), Comprehensive (UIAM, UMS, UNIMAS, UPSI = tier 2), Focused (all others = tier 1).
**Alternatives considered:** (A) Use official MQA star ratings (not publicly machine-readable), (B) Binary research/non-research split, (C) Per-university scoring from external rankings.
**Rationale:** Three tiers are simple, defensible, and aligned with how Malaysian students/parents informally rank universities. Default tier 1 for unlisted universities avoids maintenance overhead.
**Trade-offs:** Coarse grouping — doesn't distinguish within tiers. Some universities (e.g. UiTM, UMT) may deserve tier 2 but are defaulted to 1.
**Revisit if:** Student feedback indicates the ranking feels unfair for specific universities, or official machine-readable rankings become available.

## W8 State-based institution modifiers — W8 Part 1 Sprint, 2026-03-20
**Decision:** Derive `cultural_safety_net` from state alone (9 high-Indian-population states = "high", rest = "low"). Derive `urban` from state (KL/Putrajaya/Penang = always urban) + city keyword matching in address/name.
**Alternatives considered:** (A) Per-institution Indian population data from census (not readily available as structured data), (B) Postcode-based urbanisation classification (institutions don't have postcodes in DB), (C) Google Places API for urbanisation level (cost, external dependency).
**Rationale:** State-level granularity matches how Tamil community networks actually operate. City keyword matching catches urban institutions in mixed states. Zero external dependencies, zero cost.
**Trade-offs:** Misses intra-state variation (e.g., rural Johor campus classified "high" safety net because Johor overall has significant Indian population). Penang classified as fully urban — accurate for the island, slightly generous for rural mainland.
**Revisit if:** Students report rankings feel wrong for specific institutions, or census data becomes available at postcode level.
