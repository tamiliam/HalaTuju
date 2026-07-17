# Implementation Brief — Sponsor Card Data Fix (derivation, write guard, repair)

**For:** the implementing agent (Opus 4.8), in `c:\Users\tamil\Python\Production\HalaTuju`
**Shape:** ONE sprint, one deploy, NO migrations. Owner-diagnosed 2026-07-16 from live cards; every bug below is confirmed at the cited code.

## Context — three confirmed bugs on the live sponsor cards

1. **Polluted `chosen_programme` at write time.** The offer-confirm path (`apps/scholarship/services.py:~1088-1096`) stores the offer parse verbatim: for at least one live student the parser put the INSTITUTION into `programme` and the "Tarikh dan Masa Daftar: …" date line into `institution` — the card renders an institution as its title and a timetable string as its institution, and `reporting_date` stays null (no countdown) because the date is trapped in the junk string.
2. **Pre-U fallback surfaces secondary schools.** `SponsorPoolCardSerializer.get_institution` (`serializers.py`) falls back to `pre_u_institution` — per its model help-text a "Chosen **STPM school** or Matriculation college name" (`models.py:260`) — so SMK names reach sponsor cards, contradicting the serializer's own allowlist promise ("the SECONDARY SCHOOL is NEVER surfaced"). Privacy drift, fix as such.
3. **"—" titles.** When `course_name` and `field_of_study` are both blank the card title renders an em-dash — while the student's `pre_u_choice`/`pre_u_track` (e.g. `perakaunan`) sit unused.

## Fix 1 — read-side derivation (serializers.py; the allowlist stays an allowlist)

- **`get_course` resolution order:** (a) catalogue course name via `chosen_programme['course_id']`; (b) `chosen_programme['course_name']` ONLY if it passes sanity (not equal/near-equal to the resolved institution string; no date/`Tarikh`/time patterns); (c) canonical pre-U label from `pre_u_choice` + `pre_u_track` with proper display names — "STPM · Sains", "Matrikulasi · Perakaunan", "Asasi …" (build the small display map; British-cased; reuse existing track vocabularies — grep for the pre_u_track choices); (d) the field taxonomy display name for `field_of_study`; NEVER `''` when any of these exist.
- **`get_institution` resolution order:** (a) catalogue institution via `course_id`; (b) `chosen_programme['institution']` ONLY if sane (no date/`Tarikh` patterns) AND not school-like; (c) `pre_u_institution` ONLY if not school-like; else `''`.
  **School-block rule (enforces the existing promise):** reject values matching secondary-school patterns — `\bSMK\b`, `\bSJK\b`, `\bSMJK\b`, `Sekolah Menengah`, `Sekolah Jenis` (case-insensitive). Politeknik / Universiti / Kolej Matrikulasi / Kolej Tingkatan Enam / `\bKTE\b` / IPG etc. pass. Put the pattern list in ONE named constant with a docstring citing the allowlist promise; unit-test both directions.
- Keep every derivation inside the serializer's explicit-allowlist style with docstrings updated.

## Fix 2 — write-side guard (services.py offer-confirm path ~:1088-1096)

Before storing: (a) if the parsed `institution` contains a date/`Tarikh` pattern, run it through the existing `pathway_engine.parse_reporting_date` — a parsed date fills `application.reporting_date` (only when currently null) and the junk is NOT stored as institution; (b) if `programme` ≈ `institution` (or matches a known-institution shape while `institution` is junk), store what is trustworthy and leave the rest '' rather than writing garbage. Never let a value the read-side would reject be written. Log a warning naming the doc id when the guard fires (ops visibility, no PII beyond the app id).

## Fix 3 — report-first data repair (management command, run on the LIVE service only)

`repair_chosen_programme` with `--report` (default) and `--apply`:
- **Report:** every application whose `chosen_programme` values fail the Fix-1 sanity/school rules, or whose card would title-dash — with current values, the proposed repaired values (derived from the offer's already-stored extraction fields / the Fix-1 chain), and `reporting_date` fills. NO writes.
- **Apply:** performs exactly the reported repairs. NEVER re-runs Vision/Gemini extraction (standing rule: local re-extraction destroys `vision_fields`; this command only re-reads stored fields). Owner runs report → reviews → apply, via the internal cron/management path on the live service.
- Register it in `CronRunView.JOBS` only if the existing convention requires; otherwise document the run command in the retro.

## Fix 4 — frontend no-dash rule

The pool card and detail must NEVER render a `'—'` placeholder: a missing course line falls back per Fix 1 server-side; if `institution` is empty the line shows state only; empty state shows nothing. Mirror of the Part-2 email rule. Jest cases for each omission.

## Tests & verification

- Anonymity suite: extend with the school-block cases (an SMK in `pre_u_institution` never reaches the card) — this is now a PRIVACY test, mark it as such.
- Unit tests: full derivation matrices for course/institution (catalogue, sane free-text, junk free-text, pre-U label, taxonomy fallback); write-guard cases (Tarikh string → reporting_date filled, junk not stored); repair command report/apply on fixtures reproducing the three live bugs.
- Full pytest + jest + `next build`; after push verify build by SHORT_SHA (`gcloud builds list --project gen-lang-client-0871147736 --account tamiliam@gmail.com`).
- Live smoke: the three owner-reported cards (title = real programme or pre-U label; no SMK anywhere; no dashes; countdown appears once repair fills `reporting_date`) — run the repair report, owner approves, apply, re-check the cards.

## Out of scope

Offer-parser (vision/doc_parse) accuracy improvements (the guard + repair contain the damage; parser work is its own future fix); My Students page; email Part-2 content (already specified in the pool brief).

## Sizing & risks

~10–14 files. Risks: (1) over-aggressive school-block hiding a legitimate institution — the pattern list is conservative + unit-tested both ways, and the audit report surfaces every blocked value for owner review; (2) repair touching the wrong rows — report-first, owner-gated apply; (3) breaking pool tests that pinned old fallbacks — update deliberately, never weaken the anonymity suite.
