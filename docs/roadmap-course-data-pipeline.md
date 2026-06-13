# Roadmap — Course-Data Freshness Pipeline

**Status:** APPROVED + IN PROGRESS. **Sprints 1 & 2 SHIPPED & LIVE 2026-06-13.** **Sprint 3 re-scoped to "3a" + BUILT
2026-06-13** (on branch `spm-catalogue`; migration `0054` NOT yet applied to prod — ships on the owner's next deploy,
migrate-first). `NEXT = deploy 3a` (owner), then Sprint 3b (synthetic-ID crosswalk) or 3c (SPM requirement parser).
Decomposed via `implementation-planning.md`.

> **⚠️ Sprint 3 scope correction (2026-06-13).** The "mirror `sync_stpm_mohe` over the SPM catalogue" plan was based on a
> spike that validated only the **scrape card structure**, not the **sync target**. On building, two gaps surfaced:
> (1) the SPM `Course` model is shaped differently from `StpmCourse` (merit in `CourseRequirement`, URL in
> `CourseInstitution`, no `is_active`); (2) only **89 of 390** SPM courses carry MOHE KOD PROGRAM codes — the other ~300
> use internal `POLY-*`/`KKOM-*`/`TVET-*`/`50PD…` schemes e-Panduan never emits, so a whole-catalogue diff would flag
> them all as "removed". Sprint 3 was therefore **split** (owner-approved): **3a** = the 89 MOHE-coded UA/Asasi courses
> (BUILT — scraper `--jenprog spm`, `Course.is_active` migration `0054`, `sync_spm_mohe` restricted + guarded, +29 tests);
> **3b** = a name+institution crosswalk for the synthetic-ID courses; **3c** = the SPM requirement-page parser (to
> auto-add new courses). See `decisions.md` + `retrospective-course-data-sprint3.md`.

---

## 2026-06-13 — refined model: 3 sources, resilience, a TVET gap, and a dashboard
After investigating the portals + data.gov.my, the picture sharpened from "one scrape" to **three sources**, with one
material coverage gap and a clearer "system" shape (reporting + updating). This section governs; the sprint list below
is extended accordingly.

### The 3-source model (course data depends on THREE external sources, not one)
| Source | Feeds | Fragility | Coverage today |
|---|---|---|---|
| **MOHE e-Panduan** (`online.mohe.gov.my/epanduan`) | SPM + STPM catalogue, entry requirements, merit | High (JS scrape) | STPM ✅ · SPM partial (Sprint 3 fills) |
| **UP_TVET** (`mohon.tvet.gov.my/awam-kursus/katalog` — **public, no login**) | TVET catalogue across **12 ministries / 685 institutions** | High (scrape) | **~2–3 ministries only — big gap** |
| **eMASCO** (`emasco.mohr.gov.my`, MOHR) | course → MASCO occupation code → job | **Low** (published standard, ~rare updates) | loaded; refresh seldom |

**No official feed exists for the catalogue.** data.gov.my / OpenDOSM publish *statistics*, not the programme-level
catalogue (course lists + requirements + merit) — so scraping stays the only route. MASCO is the exception (a published
classification doc, slow-moving).

### Source resilience posture (the "spigot could be cut off" risk)
- **Already decoupled:** the site serves from the **database**; scrapes only *update* it. A source going dark degrades
  **freshness over time**, never **availability**. This is the key fact.
- **Permanent versioned snapshots:** keep the raw scraped data + structured CSV forever (Sprint 1's dated archive starts
  this) → always a last-known-good to recover/diff from.
- **Loud failure + visible staleness:** the scrape sanity-guard fails loudly; the dashboard shows freshness. No silent rot.
- **No feed to migrate to** for the catalogue; **fallback** = the institution umbrella sites if a central portal dies.

### Data organisation — DECIDED (owner, 2026-06-13)
**Backend stays COARSE; frontend DERIVES the finer pathways.** BE `source_type` buckets; FE displays the 9 chips.
- BE `ua` = **Asasi + UA diploma** (FE shows as two chips).
- BE `tvet` = **ILKBS + ILJTM + MARA + Agriculture + other UP_TVET ministries** (FE can split). **No re-architecture** —
  the existing derived-pathway model is correct; missing sources just fold into the right BE bucket.
- Axes: ENTRY qualification (SPM `courses` vs STPM `stpm_courses`) × DESTINATION pathway (`source_type`) × FIELD (`field_key`).

### NEW work items (extend the sprint list below)
- **UP_TVET coverage (the confirmed gap) — split on build (2026-06-13):**
  - **UP_TVET Sprint 1 — scraper + coverage inventory · ✅ SHIPPED 2026-06-13** (merged to `main`; NO DB write,
    NO migration). `scrape_uptvet` (paginated catalogue → CSV: code,
    name, kategori, institution, **sektor Awam/Swasta**, fees, `id_kursus`, detail URLs; `--max-pages`) + `audit_uptvet`
    (total / Awam-Swasta / by-institution / new-vs-held). +9 tests. Live-validated: ~1000 programmes; a 200-sample is
    ~82% Awam and ~39% from providers we lack (agriculture, MARA, craft, regional colleges). **Spike findings:** codes
    (`TVET/QP…`) don't match our synthetic `IJTM-*`/`IKBN-*`; requirements sit behind Semak-Kelayakan detail pages; the
    catalogue mixes Awam/Swasta — so this is a ~1000-programme ACQUISITION, not a refresh.
  - **UP_TVET Sprint 2 — ingest (PENDING, golden-master-adjacent):** add new programmes into the BE `tvet` bucket. Run
    the inventory first to settle **`Sektor = Awam` only vs include Swasta** (owner) + the per-institution priority; pick
    the course_id scheme (likely the portal `id_kursus`); decide a TVET requirements strategy (parse Semak-Kelayakan
    pages vs a conservative default). New `CourseRequirement` rows feed the eligibility DataFrame → careful validation.
    **Carry:** instrument `scrape_uptvet`/`audit_uptvet` to call `record_status('uptvet', …)` so the dashboard's UP_TVET
    card stops reading "never run".
- **"Course Data" admin dashboard — split on build (owner: "build tools, then a dashboard for decisions — no harvesting now"):**
  - **Dashboard Sprint 1 — REPORTING-ONLY · ✅ BUILT 2026-06-13** (branch `course-data-dashboard`; migration
    `0054_coursedatastatus`; deploy = owner). `/admin/course-data` page (super/admin): freshness strip (e-Panduan
    STPM/SPM · UP_TVET · eMASCO, last-run + count + "never run"), coverage table (have/available/gap, live), link-health +
    audit cards. `CourseDataStatus` store + `coverage_snapshot()`; `refresh_stpm`/`validate_course_urls`/`audit_data` record
    status (best-effort). `GET /api/v1/admin/course-data/`. **NO run-triggers** (honours "no harvesting"). +8 tests; next build
    clean; jest 306; parity 2600×3. **Carry:** instrument `sync_spm_mohe` + `scrape_uptvet`/`audit_uptvet` to call
    `record_status` when those branches merge (else their cards stay "never run"); migration parallels `spm-catalogue`'s 0054.
  - **Dashboard Sprint 2 — UPDATE TRIGGERS (hybrid, DEFERRED):** server-runnable buttons — **Run audit**, **Check links**
    (`validate_course_urls`, async), **Apply a refresh** (`sync_stpm_mohe --apply` from an **uploaded CSV**, guarded). The
    **scrape stays local** (run on the laptop → upload CSV). Mirrors `AdminRunVisionView` + `CronRunView`. Build only when the
    owner wants harvesting/updating from the UI. (Option B — a Chromium Cloud Run Job — only if the laptop step is worth removing.)
  - This is the focused "dashboard freshness strip" anticipated in `decisions.md`, not a general notification framework.

---

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

### Sprint 1 — STPM refresh wrapper + dated archive + annual reminder  ·  *complexity: low*  ·  ✅ **SHIPPED & LIVE 2026-06-13** (`main` `b16f7d5`; annual scheduler `halatuju-refresh-reminder` enabled; retro `docs/retrospective-course-data-sprint1.md`)
- **Goal:** Turn the fragile 5-step STPM refresh into one auditable command with rollback history.
- **Scope:** new `refresh_stpm` management command (scrape → sanity-check → validate-urls →
  sync dry-run → audit, single summary); date-stamped CSV archive (`mohe_<date>.csv`, keep last N);
  one-time `/schedule` annual reminder timed to MOHE's intake update.
- **Acceptance:** `refresh_stpm` runs end-to-end and prints a summary; a dated CSV is archived;
  re-running is idempotent; tests for the wrapper's orchestration + archive naming.
- **Files:** ~4–6 (1 new command, small archive helper, test, doc).

### Sprint 2 — Catalogue-wide link-checker + freshness audit  ·  *complexity: low*  ·  ✅ **SHIPPED & LIVE 2026-06-13** (`main` `49d2e12`; retro `docs/retrospective-course-data-sprint2.md`) — `validate_course_urls` (HTTP reachability) + `audit_data` LINK HEALTH section. Chose option (A) — **no `last_verified` field/migration**; freshness is audit-run-derived.
- **Goal:** Detect dead links and stale records across the **whole** catalogue (SPM + STPM),
  regardless of source.
- **Scope:** generalise `validate_stpm_urls` to cover `Course`/`CourseInstitution` hyperlinks;
  add a `last_verified` date concept (field or audit-derived) and surface staleness in `audit_data`.
- **Acceptance:** link-checker reports dead links for both catalogues; `audit_data` shows a
  "stale/last-verified" section; tests for the checker + audit additions.
- **Files:** ~4–6.

### Sprint 3 — Post-SPM catalogue via e-Panduan `jenprog=spm`  ·  **SPLIT 3a/3b/3c on build (see scope-correction box at top)**
- **3a — MOHE-coded (UA/Asasi) subset · ✅ BUILT 2026-06-13** (branch `spm-catalogue`; deploy = owner, migrate-first `0054`).
  `scrape_mohe_stpm --jenprog spm` + `--max-pages`; `Course.is_active` (`0054`, additive, no read filter yet);
  `sync_spm_mohe` restricted to `^[A-Z]{2}[0-9]{7}$`, mass-deactivation guard, merit→`CourseRequirement.merit_cutoff`,
  new reported-not-added. +29 tests. Live-validated the `spm` parser (363 programmes, page 1 clean, MOHE codes + merit + URLs).
- **3b — synthetic-ID crosswalk (PENDING):** map MOHE KOD PROGRAM ↔ our `POLY-*`/`KKOM-*`/`TVET-*`/`50PD…` IDs by
  name+institution so the ~300 non-MOHE-coded courses can sync. Riskier (false-merge into golden-master eligibility).
- **3c — SPM requirement-page parser (PENDING):** parse e-Panduan `spm` requirement detail pages → the 60-boolean
  `CourseRequirement` schema, to auto-add new MOHE-coded courses (currently reported-not-added). Golden-master-adjacent.

_Original Sprint 3 plan (kept for 3b/3c reference):_
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
