# Retrospective — School-leaving cert: deterministic read + officer chips + leadership notes (2026-07-15)

Owner follow-up to the genuineness model, off app #66's cockpit: (1) read the *Sijil Berhenti
Sekolah* OCR-first with AI fallback (it showed the "AI" badge — Gemini-only), (2) surface proper
officer chips (School / Name / IC / Behaviour) instead of one "Verified" pill, and (3) show the
co-curricular / leadership notes, on both read paths.

## What Was Built

- **`doc_parse._parse_school_leaving`** — a deterministic label-anchored parser for the standard
  numbered form; reads → "Exact", a free-form testimonial → `None` → Gemini "AI" fallback. Captures
  `activities` (Kurikulum "Jawatan" roles + Catatan). **Strict confidence gates** (see below).
- **`activities`** on the extraction schema + prompt hint.
- **`student_school_leaving_check` + `school_leaving_check` serializer** → `{school, name,
  name_status, nric, nric_status, kelakuan, activities}`; Name + NRIC matched against the student
  (mirrors `semester_check`).
- **Cockpit** — School · Name · IC · Behaviour chips (Name/IC = match, School/Behaviour = read) + a
  value line (school, conduct, leadership notes); i18n en/ms/ta.

## What Went Well

- **The chip + values pattern was a clean mirror** of the existing `semester_check` / utility-values
  rendering — no new UI paradigm, so the FE change stayed small and consistent.
- **Reusing the existing deterministic-first wiring** (`parse_by_labels` → `None` → Gemini, capture
  badge) meant "OCR-first with AI fallback" was just a new parser + the capture-list entry.

## What Went Wrong

- **The first deterministic parser was validated only on a synthetic fixture and shipped dirty reads
  to prod.** The live re-extraction of 18 real certs showed ~1/3 of the Exact reads were wrong: the
  kelakuan grabbed the next field label or a stray colon ("16 Tarikh Berhenti Sekolah", ": TERPUJI",
  "Jawatan Khas"), the school truncated ("SMK BUKIT"), and section boilerplate ("jika ada", "KHAS")
  leaked into the activities. **Root cause:** the parser was written + unit-tested against one clean
  synthetic form; real school-issued certs vary far more (multi-column OCR, labels on their own line,
  template boilerplate) than a single fixture captures — the exact L86/S15 lesson. **Fix:** made the
  parser STRICT — it fires "Exact" only on a validated clean read (kelakuan must be a recognised
  conduct word from the closed vocabulary; the school must be a full ≥3-word name; activities filtered
  of boilerplate), and defers everything else to Gemini (which reads the varied layouts cleanly). A
  second deploy + re-extraction confirmed: **2 Exact (clean), 16 Gemini AI (clean), 0 dirty.** The
  system fix: this retro + the lesson, and the tests now encode the real failure modes (not just the
  happy path), so a future parser tweak can't silently regress them.

## Design Decisions

- **Strict deterministic gate, Gemini for the tail.** For a school-ISSUED doc (unlike a single-issuer
  national form), the deterministic parser should be rare-but-trustworthy: fire only when fully
  confident, defer otherwise. Both paths read cleanly; the Exact badge just marks the free/auditable
  subset. See decisions.md.
- **Notes captured deterministically AND via Gemini (owner's choice).** The Kurikulum/Jawatan +
  Catatan sections are labelled, so the parser reads them too — leadership notes show on both paths.

## Numbers

- +29 BE tests (parser gates + the chip check), +2 jest; 2518 scholarship pytest + 3741 combined;
  jest 503; i18n parity; NO migration.
- 2 api deploys (`50149446` code, `06e38dee` hardening) + 1 web (`50149446`). The hardening was the
  real-doc-validation tuning deploy — the accepted pattern, kept within budget.
