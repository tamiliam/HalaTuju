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

### Sprint 3 — UPU pipeline (part 1): scrape + course-list sync  ·  *complexity: high*  ·  **riskiest — DOM spike first**
- **Goal:** Acquire the course **listing** for Asasi + Politeknik + UA + Kolej Komuniti from UPU
  and sync it into `Course`/`CourseInstitution` with the safety guards.
- **Scope:** spike the UPU portal DOM first (the main unknown); a `scrape_upu` command (mirrors
  `scrape_mohe_stpm`, inherits `scrape_shortfall`); a `sync_upu` command (mirrors `sync_stpm_mohe`,
  inherits the mass-deactivation guard); map UPU fields → existing models. Extract a shared
  scrape/sync base if a clean one emerges.
- **Acceptance:** dry-run report of new/removed/changed for the 4 pathways; `--apply` guarded;
  scrape fails on shortfall; tests; a real scrape of the live UPU portal validates the parser.
- **Files:** ~8–12. **Split into 3a (spike+scrape) / 3b (sync) if it overflows.**

### Sprint 4 — UPU pipeline (part 2): entry-requirements parse + load  ·  *complexity: high*
- **Goal:** Acquire and load **entry requirements** for the UPU pathways (the high-stakes data the
  eligibility engine depends on), with the parse + validate discipline of the STPM requirements tool.
- **Scope:** parse UPU requirement blocks → structured form; validate (completeness, grade validity)
  before load; load into `CourseRequirement`; spot-check against the engine's golden master.
- **Acceptance:** requirements load with <2% parse warnings; validation passes; golden-master diff
  reviewed; tests on the parser + validator.
- **Files:** ~8–12.

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
1. UPU portal: is it a single listing per pathway (like ePanduan) or per-institution? (affects Sprint 3 size)
2. Do you want Sprint 1's annual reminder as a real `/schedule`, and to which date?
3. Any pathway where staleness already worries you (would re-prioritise Sprint 5)?
