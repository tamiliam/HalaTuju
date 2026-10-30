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
- **Sprint B BUILT 2026-10-28** (branch `sprint-b-bumi-toggle`; migration 0087 migrate-first). Owner Option A: scholarship pickers show every course and never read the answer.
- **Sprint C BUILT 2026-10-29** (branch `bumi-sprint-c`, on TD-416): 13 Islamic subjects selectable as electives under their slip names; doc recognition 1.18.0; `BAHASA_ARAB_MUASIRAH_SPM` also met by `lughah_arabiah`. Golden masters unchanged. `SPM_PREREQ_OPTIONAL` turned out to be dead (the STPM SPM block reads `SPM_ALL_ELECTIVE_SUBJECTS`); `BA` left alone (no fixture uses it); `pathways.py` left alone (no source).
- **B, TD-416 and C LIVE 2026-10-29 (1a4aedc8). D1 LIVE 2026-10-29 (f5282643; 84 UiTM rows ingested). D2 LIVE 2026-10-29 (914d4a5b; 66 rows + MARA-BPT). NEXT = Sprint F (UP_TVET / MARA).**
- **F1 LIVE 2026-10-30 (a60662cc; 35 courses + 33 links + 4 institutions ingested; retro `docs/retrospectives/retrospective-2026-10-30-bumi-sprint-f1.md`). F1b LIVE 2026-10-30 (579e27ca; 63 held courses' flags from their pages). NEXT = F2 (MARA).**
- **Sprint F2 BUILT 2026-10-30** (branch `bumi-sprint-f2`, no migration): public MARA UP_TVET. The parser now reads
  606 of 665 MARA pages (21 before; MARA's bare Warganegara / Bumiputera headings, blanket OKU wording, summary
  lines, two gates on one line, "Tidak Tamat Sekolah", vocational-group SPM headings). 181 courses (606 campus
  offerings), 177 Bumi-only + 4 open (GIATMARA pages silent on Bumi), 233 `MARA-NNN` institutions, 59 flagged
  (`data/tvet/tvet_new_courses_F2.json`); no D2 duplicate. Golden: original 5,293 identical; non-Bumi gains
  exactly the 4 open F2 rows (199) beside F1's 1,494 (6,986); bumi=True 12,621 (F2 +5,069, digest-pinned; after review round 1);
  STPM 2,025. Runbook: halatuju_api/CLAUDE.md ("Bumi F2 order"). NEXT = review, read-only SQL (`--sql`), deploy, `--apply`.
- **Sprint F1 BUILT 2026-10-29** (branch `bumi-sprint-f`, no migration): public UP_TVET, non-MARA. 35 new courses (39 campus offerings), 33 new campus links to 20 held courses, 90 flagged, 4 proposed institutions (`data/tvet/tvet_new_courses_F1.json`); pathways `mara` + `tvet_other`; golden: original 5,319 identical, non-Bumi gains exactly the F1 set (1,494), bumi=True 7,578, STPM 2,025. Runbook: halatuju_api/CLAUDE.md ("Bumi F1 order"). NEXT = review, then F2 (MARA: data + condition wording; 665 pages already saved).
- **Sprint D1 BUILT 2026-10-29** (branch `bumi-sprint-d`; migration courses/0088 migrate-first): 84 of the 87 UiTM rows parse (3 flagged: UE0520001, UE0545001 two grades over one list; UE4811004 ATAU), `count_once` construct, `ingest_spm_courses` (dry run first), all 7 doors. Golden masters 5,319 (original + full at bumi=False) / 5,865 (bumi=True, after review round 1) / STPM 2,025. NEXT = adversarial review, then the read-only SQL checks, migrate, deploy, `--apply`.

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

#### Sprint D — detailed plan (2026-10-29, owner answers)
Owner answers: (1) re-scrape Syarat Am with a new `--with-syarat-am` flag on `scrape_mohe_stpm` (approved tool change);
(2) parser lives in the repo (`apps/courses/spm_syarat.py` + `ingest_spm_courses` command), not `Settings/_tools`;
(3) link each UiTM / MARA course to ONE parent institution now, campuses later; (4) **the 2 Bumi Matrikulasi
programmes become 2 new Bumi-only matric tracks** (KA0000002 Sains 4-semester, KA0000006 Perakaunan Profesional).

**Split.** D1 = foundations + the 87 UiTM rows. D2 = the other 63 (UIAM, MARA, the 14 open Islamic, UMS / UNIMAS /
UM / UniSZA / USIM) + the 2 Bumi matric tracks + `any_of` / hand entry for the ATAU rows.

**D1 builds:** migration `courses/0088` `CourseRequirement.req_bumiputera` (default False + DB default; migrate-first);
engine gate after the `req_disability` block (`engine.py` ~615), `StudentProfile(bumiputera=False)`; Syarat Am
scrape; parser with a new "N remaining subjects, minus an exclude list" construct; dry-run-first ingest command;
reviewed data file `data/spm/spm_new_courses_D1.json`, appended to both fixtures; every door below.

**Doors (adversarial review brief):**
1. `EligibilityRequestSerializer` + `EligibilityCheckView` read `bumiputera` via `resolve_bumiputera` (foreigner never Bumi).
2. **Scholarship pickers** (`scholarship/apply/page.tsx` ~213, `PathwayPicker.tsx` ~104) send the whole profile: they must
   force `bumiputera: true` (Option A, every course), like `degreeChoices.ts`. Jest guard.
3. Dashboard + search send the profile (correct for the course guide); cached profile carries the flag.
4. `CourseSearchView` SPM branch excludes `req_bumiputera` unless Bumi; its pick-lists use the same visible set.
5. `CourseDetailView` shows a "Bumiputera only" badge (no 404); `req_bumiputera` in `GENERAL_FIELDS`.
6. Client-filtered readers (ranking, insights, report_engine, saved, CourseListView) — confirm no leak, no filter needed.
7. Scholarship `card_display` / `offer_pathway` read by id, unfiltered (Option A) — the Bumi-blind guards stay green.

**Golden masters:** freeze the original fixture IDs; their total stays **5,319** and every student's set is identical.
Full set at bumi=False = 5,319 + (only open Islamic rows; a Bumi row adding anything is a bug); record a bumi=True
baseline too. STPM stays **2,025**.

**Baseline measured 2026-10-29 (`origin/main` 7a19c93d, `pytest -n auto`):** 9,834 passed / 3 skipped.

**Lessons applied:** L539 two Bumi signals (both already agree, 0 disagree); L708 check the scraper's page count on
`--max-pages 2` first; L710 the fixtures are 2 rows behind prod (89 vs 87 MOHE-coded) — reconcile by read-only SQL
before `--apply`; the slip-name alias lesson (old stored names stay); a count-once rule is a matching.

#### Sprint D2 — built 2026-10-29 (branch `bumi-sprint-d2`, no migration)
66 rows in `halatuju_api/data/spm/spm_new_courses_D2.json` (ids + buckets: `spm_new_courses_D2.ids`), 0 flagged:
47 Bumi-only non-UiTM (UIAM 20, MARA 15, UMS 4, UNIMAS 3, UM 3, UniSZA 2), 14 open Islamic (UniSZA 9, USIM 4
Tamhidi, UM 1), the 3 UiTM rows D1 flagged, and the 2 Bumi matric tracks (`matric-sains-4-semester`,
`matric-perakaunan-profesional`). New: `any_of` count-once groups for ATAU, read through reviewed scopes
(`spm_atau_scopes.py`); "X in ONE AND Y in THREE" as two groups in one block; MARA's Syarat Am; per-row parent
institutions and an explicit `--create-institutions` for the proposed `MARA-BPT`; the search pick-list refresh.
Golden masters: original 389 = 5,319 identical; full bumi=False 5,319 (+0: no golden student holds an Islamic
subject); bumi=True 5,986 (after review round 1); STPM 2,025. Not done: UL0481001 / FB0500001 (prod-only, not Bumi — lead ruling: not
in this sprint). Runbook + rollback: `halatuju_api/CLAUDE.md` ("Bumi D2 order"). Rollback ids (D2):
    'UY0000010', 'UH0010003', 'UY0000015', 'UY0000001', 'UY0000016', 'UY0000014', 'UY0000012',
    'UY0000011', 'UY0000005', 'UY0000006', 'UY0000004', 'UE0520001', 'UY0520001', 'OM0520001',
    'OM0520002', 'UM0221002', 'UW0010003', 'UY0000019', 'UY0000018', 'UD0010001', 'UE0545001',
    'UH0010001', 'UM0440001', 'UW0010002', 'UY0000002', 'UM0421001', 'UW0010001', 'UY0000013',
    'UY0000017', 'UY0000003', 'UY0481001', 'UD0010004', 'UH0010004', 'UM0010001', 'UY0000009',
    'UH0010002', 'UY0000007', 'UD4221001', 'UD4224001', 'UD4221005', 'OP4344001', 'OP4344003',
    'OP4340002', 'OP4340003', 'OP4481001', 'OP4481002', 'OP4213001', 'OP4224001', 'OP4345002',
    'OP4840001', 'OP4340001', 'OP4343001', 'OP4342001', 'UD4221008', 'UE4811004', 'UD4221002',
    'UD4221003', 'UD4221007', 'UD4380001', 'UD4221006', 'matric-perakaunan-profesional',
    'matric-sains-4-semester', 'UQ0340001', 'UQ0421001', 'UQ0010002', 'UQ0381001'

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
