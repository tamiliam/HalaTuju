# Roadmap — Course-Data Freshness Pipeline

**Status:** DRAFT, pending owner approval (2026-06-12). Decomposed via `implementation-planning.md`.
**Owner decision needed before Sprint 3.** Do not begin Sprint 1 until this roadmap is approved.

## Why this exists
Course data is accurate only at a point in time — offerings, entry requirements, merit
scores and links change yearly. Today only **STPM** has a refresh pipeline (MOHE ePanduan
scrape → sync, now with safety guards). The **post-SPM catalogue** (1,300+ courses across
Asasi, Politeknik, UA, Kolej Komuniti, Matrikulasi, PISMP, ILJTM/ILKBS) was built **manually**
during the Streamlit POC and has **no refresh pipeline** — it goes stale silently.

**Urgency is moderate, not critical:** B40 applications snapshot the student's choice (no FK
to the catalogue — see `docs/decisions.md`), so staleness affects only the **accuracy of
advisory recommendations**, not B40 integrity. This lets us build proportionately, not in a rush.

## Source map (from the owner)
| Pathway(s) | Source | Structured? |
|---|---|---|
| Asasi, Politeknik, UA, Kolej Komuniti | **UPU** (one portal; lists requirements) | Yes — **highest leverage** |
| STPM | MOHE ePanduan | ✅ already pipelined |
| Matrikulasi, PISMP | MOE dedicated subsites | Yes-ish |
| ILJTM / ILKBS | UPTVET site | Yes-ish |
| Politeknik / KK rich detail | Their own sites | Partial (enrichment) |
| Institution metadata (address, phone, ranking modifiers) | Web search, case-by-case | **No → stays manual** |

## Non-goals (explicit decisions)
- **Institution metadata is NOT automated.** Address/phone/modifiers are gathered by
  web-search + manual/LLM-assist; a scraper there is a money pit. Keep it manual.
- **No SPM-side change touches B40** — applications stay snapshot-decoupled. Don't normalise.

## Guiding principles
- Reuse the STPM pattern for every source: **scrape → sanity-check (≥95% of reported total)
  → sync (dry-run) → apply with the mass-deactivation guard (>10% abort, `--force`)**.
- Cheapest, do-regardless work first; highest-value automation next; long-tail deferred until
  staleness actually bites.

---

## Sprint roadmap

### Sprint 1 — STPM refresh wrapper + dated archive + annual reminder  ·  *complexity: low*
- **Goal:** Turn the fragile 5-step STPM refresh into one auditable command with rollback history.
- **Scope:** new `refresh_stpm` management command (scrape → sanity-check → validate-urls →
  sync dry-run → audit, single summary); date-stamped CSV archive (`mohe_<date>.csv`, keep last N);
  one-time `/schedule` annual reminder timed to MOHE's intake update.
- **Acceptance:** `refresh_stpm` runs end-to-end and prints a summary; a dated CSV is archived;
  re-running is idempotent; tests for the wrapper's orchestration + archive naming.
- **Files:** ~4–6 (1 new command, small archive helper, test, doc).

### Sprint 2 — Catalogue-wide link-checker + freshness audit  ·  *complexity: low*
- **Goal:** Detect dead links and stale records across the **whole** catalogue (SPM + STPM),
  regardless of source.
- **Scope:** generalise `validate_stpm_urls` to cover `Course`/`CourseInstitution` hyperlinks;
  add a `last_verified` date concept (field or audit-derived) and surface staleness in `audit_data`.
- **Acceptance:** link-checker reports dead links for both catalogues; `audit_data` shows a
  "stale/last-verified" section; tests for the checker + audit additions.
- **Files:** ~4–6.

### Sprint 3 — Post-SPM catalogue via e-Panduan `jenprog=spm`  ·  *complexity: medium*  ·  **(was 2 high sprints — collapsed after the 2026-06-12 spike)**
- **SPIKE RESULT (confirmed live):** e-Panduan exposes exactly two `jenprog` values — `stpm` and
  **`spm`**. The `spm` branch (Asasi/diploma/cert at Poly/KK/UA) is **2 categories** (`A` current-year
  = 363 programmes, `B` past-year) and uses the **identical card structure** the existing scraper
  already parses (`KOD PROGRAM`, `TAHUN`, `PURATA MARKAH MERIT`). So this is an **extension of the
  existing scraper, not a new build**.
- **Goal:** Acquire the SPM-leaver catalogue (Asasi + Politeknik + UA + Kolej Komuniti diploma/cert)
  and sync it into `Course`/`CourseRequirement`/`CourseInstitution` with the safety guards.
- **Scope:** parameterise `scrape_mohe_stpm` for `jenprog` + categories (add `spm` A/B); a sync that
  mirrors `sync_stpm_mohe` (inherits the mass-deactivation guard); map fields → existing models;
  **reuse the existing `Settings/_tools/stpm_requirements/` parser** for the per-programme requirement
  detail pages (same portal HTML — confirm parity, then load with the parse+validate discipline).
- **Acceptance:** dry-run report (new/removed/changed) for the SPM-leaver set; `--apply` guarded;
  scrape fails on shortfall; requirements load with <2% parse warnings; tests; a real scrape validates.
- **Files:** ~8–12. Split scrape/sync vs requirements if it overflows.

### Sprint 4 (optional) — Degree candidate-category completeness  ·  *complexity: medium*
- **From the spike:** the `jenprog=stpm` (degree) branch has ~20 candidate categories but the scraper
  reads only 2 (S, A). The rest — **Matrikulasi** (N/J/P), **Asasi** (K/M/V), **STAM** (T), **Diploma**
  (G1/G2/E1/E2) — are on the same portal, unscraped.
- **Goal:** Scrape the remaining candidate categories to sharpen **degree eligibility/merit for
  non-STPM applicants** (matric/asasi/STAM/diploma holders). Distinct value stream from Sprint 3.
- **Trigger:** do after Sprint 3, only if improving non-STPM degree-eligibility accuracy is a priority.
- **Files:** ~5–8 (mostly the same parameterised scraper + per-category merit handling).

### Sprint 5 (optional, deferred) — Matrikulasi + PISMP + UPTVET scrapers  ·  *complexity: medium each*
- **Goal:** Thin source-specific scrapers on the Sprint 3 base for the remaining structured pathways.
- **Trigger:** build **only when staleness in these pathways actually bites** — not pre-emptively.
- **Files:** ~5–8 per source; can be one sprint each or grouped.

---

## Sequencing rationale
- **1 → 2 first (cheap, do-regardless):** make every future refresh safe + auditable and get
  immediate link-rot detection across the whole catalogue, for very little effort.
- **3 → 4 next (the 80/20):** UPU is one source covering four pathways + their requirements — the
  single highest-value automation. Riskiest (new DOM), so a spike opens Sprint 3.
- **5 deferred:** Matric/PISMP/TVET are smaller; defer until proven necessary.
- **Total core: 4 sprints** (1, 2, 3, 4), with 3 possibly splitting to 3a/3b. Sprint 5 is
  on-demand. Institution metadata stays manual (no sprint).

## Open questions for the owner
1. ~~UPU portal structure~~ — **RESOLVED (spike 2026-06-12):** it's MOHE e-Panduan, one portal,
   `jenprog=spm` (2 categories) for the whole post-SPM catalogue; same parser as STPM. Sprint 3
   shrank from 2 high sprints to 1 medium.
2. Do you want Sprint 1's annual reminder as a real `/schedule`, and to which date (≈ Dec–Jan, before
   the UPU window — see the source inventory)?
3. Any pathway where staleness already worries you (would re-prioritise)?
4. Sprint 4 (degree candidate-category completeness) — worth doing, or is STPM-only degree eligibility
   acceptable for now?
