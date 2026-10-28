<!-- Decomposed via Settings/_workflows/implementation-planning.md; owner-approved 2026-10-28. -->

# Roadmap — Bumiputera courses + Islamic subjects

## Context
At launch we left out three things on purpose:
- Bumi-only courses (UiTM, other "Melayu / Anak Negeri / Orang Asli sahaja" programmes, MARA TVET).
- Islamic SPM subjects in grade entry (ruling `docs/decisions.md:6502`).
- Kolej Mara / Kolej Profesional MARA at catalogue build.

Now we want every public UPU course (post-SPM + post-STPM) and UP_TVET, plus a Bumiputera Yes/No on "A Few More Details". Only Bumi students see Bumi-only courses.

Owner rulings (2026-10-28):
- Bumi answer is **course-guide only**. Never sent to scholarship, sponsors, reports, CSV exports (keeps the s44(6) no-ethnicity stance).
- **No religion question, no "Muslim only" label.** Islamic courses are open to anyone; the academic (subject) requirement is the only gate.

## What exists today (from investigation)
- **STPM**: 162 UiTM courses already in DB with `StpmRequirement.req_bumiputera=True` (`models_stpm.py:142`). Hidden by `stpm_engine.py:405-407` and `views.py:248-249`. `StpmSearchView` (`views.py:1736`) does NOT hide them (bug). Islamic STPM subjects (Syariah, Usuluddin, Tahfiz, B. Arab) already supported.
- **SPM catalogue**: no bumi field on `CourseRequirement`. Bumi/UiTM/Islamic courses were dropped at build by archived scripts (`Archived/Random/archive/spm/scripts/parse_syarat_khas.py`, `create_requirements.py`). Funnel: 363 MOHE → −87 UiTM −47 Bumi −24 Islamic → 208. Original `HalaTuju/data` folder is gone; `scrape_mohe_stpm.py` captures no bumi / syarat-khas data.
- **SPM subjects**: backend already knows all 16 Islamic keys (`stpm_engine.py:SPM_CODE_MAP`, `academic_engine._SUBJECT_BM`). Web grade form omits most (`halatuju-web/src/lib/subjects.ts:177-252`). Tests pin the exclusion (`subjects.test.ts:45-52,116-121`, `test_merit_pools.py:45-48`). `map_subject_code` maps `BA → b_arab`, a dead key (`engine.py:140`).
- **UP_TVET**: `halatuju_api/data/tvet/uptvet_latest.csv` (2026-06-14): MARA 536 programmes / 232 institutions never ingested; 62 other open programmes not ingested; ingest sprint already pending (`docs/roadmap-course-data-pipeline.md:52-64`).
- **Profile screen**: `halatuju-web/src/app/onboarding/profile/page.tsx` (inline toggles, Nationality block 263-299). Profile model `models.py:778-782`; serializer `serializers.py:294/516`; sync `views.py:1223`.

## Status
- **Sprint A DONE 2026-10-28** — `docs/bumi-inventory-2026-10-28.md`. STPM data already exact → **Sprint E dropped**. Sprint D = 150 SPM courses (136 Bumi + 14 Islamic-subject). Sprint F parses `info_url` (kelayakan pages now need a login).
- **NEXT = Sprint B.**

## Roadmap — 6 sprints (now 5: E dropped)

### Sprint A — Data spike (no shipping) · medium
- Fresh MOHE scrape (SPM + STPM, current UPU cycle) that **also captures `bumiputera` + `syarat_khas`** text. Extend `scrape_mohe_stpm.py` (needs owner OK — tool change).
- Cross-check bumi flag against a 2nd signal (UiTM / institution type + syarat text) — `docs/lessons.md:539`.
- Output: a count report (new SPM courses by bucket: UiTM, other bumi, Islamic-subject, Kolej Mara/KPM; STPM bumi flags changed). Owner approves counts before Sprint D.
- Sample 20 MARA kelayakan pages from UP_TVET to size Sprint F.

### Sprint B — Bumi toggle + STPM unlock · medium (eligibility → adversarial review)
- Stitch mock of the screen first (Yes/No beside Nationality; shown only when Malaysian).
- `StudentProfile.bumiputera` nullable bool, migration `courses/0086` (applied by hand before push).
- Serializer, `ProfileView`, `ProfileSyncView`, web `profile.ts`, `auth-context.tsx`, `AuthGateModal.tsx`, onboarding page, profile page, i18n (en; ms/ta go to Sol).
- STPM engine: `bumiputera=False` param; `if req.req_bumiputera and not bumiputera: continue`. Pass it from `StpmEligibilityCheckView`, dashboard, search, `degreeChoices.ts`.
- Search: make both `CourseSearchView` and `StpmSearchView` hide bumi courses only for non-bumi.
- Guard tests: scholarship, sponsor, report, partner export serializers must NOT contain `bumiputera`.
- Gate: STPM golden master stays 2,026 (default False). New tests for bumi=True path.

### Sprint C — Islamic SPM subjects in grade entry · medium
- Add the 13 missing Islamic keys + `islam` as selectable electives (no new stream → no merit-pool mirroring).
- Also in the SPM block for STPM students (`SPM_PREREQ_OPTIONAL`).
- Check printed slip names on a real result slip; fix `_SUBJECT_BM` + `SUBJECT_NAMES` together (drift test).
- Fill `report_engine.SUBJECT_LABELS`; add to `pathways.py` social-science group where right.
- Fix `BA → b_arab` only if a fixture uses `BA` (else leave; golden-master file).
- Rewrite the 4 exclusion tests; record a new ruling superseding `decisions.md:6502`.

### Sprint D — SPM catalogue: add UiTM + other bumi + Islamic + Kolej MARA courses · high (adversarial review)
- `CourseRequirement.req_bumiputera` + engine check in `engine.py` (copy `req_disability` pattern, lines 593-615); flag flows via `apps.py:117`.
- Ingest the approved Sprint A rows. Requirement parsing: rebuild from archived scripts as a proper tool in `Settings/_tools/` (needs owner OK).
- Institutions + `CourseInstitution` links for new rows.
- SPM golden master **will move** (new courses). Re-baseline on purpose, with a diff report showing old 5,319 rows unchanged.
- May split into D1 (UiTM) / D2 (others) if > ~40 files or the review is heavy.

### Sprint E — STPM refresh check · low
- Apply any Sprint A changes to STPM bumi flags / new bumi STPM courses. Golden master re-baseline only if rows change.

### Sprint F — UP_TVET ingest incl. MARA · high
- This is the already-pending "UP_TVET Sprint 2". Add `id_kursus` reconciliation, the 62 open programmes, then MARA 536 with `req_bumiputera=True`.
- Likely split F1 (open providers + reconciliation) / F2 (MARA).

## Not changing
- Matrikulasi: bumi quota is a quota, not a hard rule → no filter.
- Scholarship engine, sponsor views, reports: never see the bumi answer.

## Verification (each sprint)
- `pytest` full suite + `jest`; both golden masters (expected numbers stated per sprint).
- Local run: onboard as non-bumi → no UiTM; as bumi → UiTM shows; STPM search + course search agree.
- `next build` passes; adversarial review before push for B and D (eligibility rule).
- CHANGELOG, decisions.md, halatuju.md updated; push = deploy, so only push a finished sprint.

## Lessons that bind Sprint A (from docs/lessons.md)
- L539: never trust one bumiputera column — cross-check against syarat-khas text AND institution.
- L708: validate the scraper's per-page count on the real portal (`--max-pages 2`) before trusting it.
- L709: inventory only — NO DB writes in Sprint A; new-vs-held is an upper bound for human judgement.
- L710: SPM IDs are mixed (89 MOHE-coded vs ~300 synthetic); diff only the MOHE-coded set.
- L560: scrape in a worktree; check `git log` before and after any long subagent run.
