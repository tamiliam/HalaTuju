# Retrospective — UP_TVET Coverage Sprint 1 (2026-06-13)

Roadmap: `docs/roadmap-course-data-pipeline.md` (the "UP_TVET coverage" track). Scope chosen with the
owner: **scraper + coverage inventory first, NO DB writes** — produce the numbers needed to decide the
ingest scope before touching the golden-master eligibility engine.

## What Was Built
- **`scrape_uptvet`** — Playwright scraper for the public UP_TVET Perdana catalogue
  (`mohon.tvet.gov.my/awam-kursus/katalog?page=N`, ~50 pages × 20). Captures per card: Kod Tauliah, name,
  Kategori, Institusi, **Sektor (Awam/Swasta)**, reg/tuition fees, the stable `id_kursus`, and the Info /
  Semak-Kelayakan detail URLs. `--max-pages` for spikes; a soft sanity note (no hard guard — it writes a
  CSV, not the DB). Robust card parse: anchor on the one numbered `<h6>` per card and walk up to the
  enclosing row (fields span sibling columns), not a single all-fields container.
- **`audit_uptvet`** — coverage inventory over a scrape CSV (no DB writes): total, Awam/Swasta split,
  by-institution ranking, and new-vs-already-held institutions (by normalised name). Pure helpers
  (`summarise`, `coverage_gap`, `_norm_inst`) unit-tested.
- Live-validated across 10 pages (200/200 parsed; Awam 165 · Swasta 35). The 200-sample **confirms the
  gap**: ~39% from providers we don't hold — Agriculture (Kolej Universiti Agrosains, Kolej Pertanian
  Malaysia), MARA, Institut Kraf Negara, Kolej Ketengah — the rest ILKBS/ILJTM we already have.

## What Went Well
- **Scope-before-code, again.** A read-only prod query (we hold 83 TVET courses: ADTEC/JTM + IKBN/IKTBN) +
  a live portal spike (≈1000 programmes, paginated HTML, mixed Awam/Swasta, requirements behind detail
  pages, codes that don't match our synthetic IDs) reframed this from "scrape it" to "a ~1000-programme
  acquisition whose valuable part is golden-master-adjacent" — so the safe, decision-enabling first cut
  (scrape + inventory, no writes) was the right call, agreed with the owner before building.
- **The parser self-corrected fast** — the first card heuristic under-counted (1/page); re-anchoring on the
  per-card `<h6>` fixed it to 20/page, caught immediately by the `--max-pages 2` validation run.
- No migration, no model change, no DB write → golden master untouched; 1056 courses pytest, +9, 0 failures.

## What Went Wrong
- **First card-detection heuristic under-counted (1 card/page instead of 20).** Symptom: the 2-page spike
  wrote 9 rows, not ~40. Root cause: I required one `div` to contain h6 + all labels + the anchor, but
  UP_TVET splits a card's fields across sibling Bootstrap columns, so only oddly-nested cards matched.
  Fix: key on the stable per-item heading (`<h6>` with a leading number) and walk UP to the card row.
  Caught by validating on the real page immediately (L86 paid off). Lesson added.

## Design Decisions
- **Scrape + inventory FIRST, ingest later.** Logged in `decisions.md`. The ingest (adding ~1000 programmes
  to the `tvet` bucket) needs new `CourseRequirement` rows that feed the golden-master DataFrame, plus a
  requirements strategy (TVET requirements sit behind Semak-Kelayakan detail pages). Doing that blind is
  reckless; the inventory produces the Awam/Swasta + per-institution numbers to scope it deliberately.
- **Coverage is reported by institution NAME, and it's an upper bound.** Portal full names
  ("INSTITUT KEMAHIRAN BELIA NEGARA …") differ from our DB abbreviations ("IKBN …"), so new-vs-existing
  matching is itself a fuzzy crosswalk. The inventory surfaces the institution list for human judgement
  rather than pretending a clean code/name diff (same lesson family as the SPM ID mismatch).

## Numbers
| Metric | Value |
|--------|-------|
| New tests | 9 (scraper constants ×2, _norm_inst ×2, summarise ×2, coverage_gap ×3) |
| Suite | 1056 courses pytest (was 1047 off main), 0 failures; no migration/model change |
| Deploys | 0 (branch `uptvet-coverage`; no migration — merges as harmless new admin tooling on owner's deploy) |
| Files | 2 new commands + 1 test file + docs |
| Live validation | 200 programmes scraped clean; gap confirmed (~39% new providers in sample) |
