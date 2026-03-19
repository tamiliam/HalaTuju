# Architecture Decisions

## W11 RIASEC injection at view layer — Ranking Improvements Sprint, 2026-03-19
**Decision:** Derive RIASEC seed from STPM subjects in `StpmRankingView.post()` (view layer), not inside the ranking engine.
**Alternatives considered:** (A) Inject in `get_stpm_ranked_results()` inside stpm_ranking.py, (B) Add a middleware/preprocessor.
**Rationale:** Keeps the ranking engine pure — it just consumes whatever signals dict it receives. The view is already responsible for assembling the request. Easier to test via API calls.
**Trade-offs:** View has slightly more logic, but it's 10 lines and clearly marked with a W11 comment.
**Revisit if:** Multiple callers of the ranking engine need the same pre-processing (would warrant extracting to a shared preprocessor).
