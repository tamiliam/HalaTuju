# Changelog

## Sprint 5 — Per-org branding & email (backend) — 2026-07-24

Backend-only. Extracts every rendered brand literal in the email + coach layer behind one read
seam so a second tenant renders its own identity, while BrightPath output stays byte-identical.
No migration, no model change, `halatuju-web/` untouched.

### Added
- **`apps/scholarship/branding.py`** — the single read seam for org branding columns (D1). A
  `PLATFORM` block holds today's brand constants verbatim (the one sanctioned home); a tenant
  resolves per the D3 fallback chain `org.col(lang) → PLATFORM.default(lang) → PLATFORM.default('en')`.
  Topical aliases (`interview@`/`sponsor@`) are platform-domain-only (D4). Sender identity + frontend
  URL read live from settings so output is identical in every environment. *(seam landed in the
  prior executor's commit `f41951e1`; completed this sprint.)*
- **Golden snapshot suite** `tests/test_email_branding.py` + `fixtures/email_branding_golden.json`
  — 113 frozen snapshots (subject + text + from + reply_to + HTML + attachment names, en/ms/ta): the
  byte-identity contract, kept green UNMODIFIED through the extraction.
- **Org-2 leak test** — a fixture tenant ("inspire") proves every branding-accepting `send_*`
  renders the tenant's programme/sign-off/persona/sender and leaks NO platform token.
- **AST brand-guard** `tests/test_branding_guard.py` — scans string constants (not comments/
  docstrings) of `emails.py` + `help_engine.py` for the platform brand literals + MS/TA canonicals,
  allowing only `branding.py`. Self-checking: `send_*` set derived via `inspect`, minimum scanned
  send/constant counts asserted so a broken scan fails loudly (D6).

### Changed
- **Phase 0 (copy normalisation)** — drifted BrightPath sign-offs unified to one canonical form per
  language (owner rulings): EN `The BrightPath Bursary Team`; MS `Pasukan Program Bursari BrightPath`
  + programme `Bursari BrightPath`; TA `BrightPath Bursary குழு`. *(prior executor commits
  `8f65fe56` + `6511b0df`.)*
- **`emails.py`** — all ~126 `BrightPath`, 5 `Cikgu Gopal`, 4 `halatuju.xyz` string-constant
  literals routed through the seam. The 5 core `.format` families (award / award-sign / vircle /
  sign / agreement) take an optional `branding=None` (default platform) and fill
  `{programme}`/`{signoff}`/`{domain}` at send time (the per-language brand form comes from the seam,
  not the caller's cohort name); `_send`, `_award_offer_html`, `_vircle_install_html` thread branding.
  Reminder/closure persona reads `branding.persona_name(lang)`. Tail (interview ×5, reviewer,
  executed/witness/countersign, sponsor, payment + vircle-activation) route through the platform seam.
- **`help_engine.py`** — coach prompt persona + programme name read from the seam
  (`persona_name('en')` for the prompt; platform default `Cikgu Gopal`), resolved from the
  application both help views hold. Only docstrings/comments now name the brand.
- **`tests/test_help_engine.py`** — firewall guardrail updated: `branding` is an allowed
  non-student-data param. **`tests/test_vircle.py`** — one manual-render test supplied the two new
  `{programme}`/`{signoff}` placeholders from the seam (behaviour unchanged).
- Test count: 4346 → **4350** (0 failures, 0 skips). SPM/STPM golden masters intact.

## W8 Part 1: Institution Modifiers Sprint — 2026-03-20

### Added
- **W8 Part 1: Institution modifiers populated** — `derive_institution_modifiers` management command. Derives `urban` (boolean) and `cultural_safety_net` ("high"/"low") from state and address data. Applied to all 838 production institutions: 171 urban, 438 high safety net. Activates previously inert `income_risk_tolerant` (+2 urban) and `proximity_priority` (+4/-2 safety net) quiz signals. 31 tests.

### Changed
- Test count: 966 → 997

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
