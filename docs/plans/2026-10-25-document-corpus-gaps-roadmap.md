# Document corpus gaps — roadmap (2026-10-25)

**Status:** APPROVED by the owner 2026-10-26 — decisions A, B, C (paid OCR capture), D all "yes". Built from `docs/plans/2026-10-25-document-corpus-gaps-brief.md`
(read it first — the counts, line refs and harm ranking live there). Origin: org request #47.

**Related, separate:** `docs/plans/2026-10-25-third-results-route-roadmap.md` (another session). It
keeps plain TYPE detection (`results_kind.py`, routing only, S3b); the genuineness FAMILIES are here.
Its S3 shows higher results as "not checked" until this roadmap's STPM family lands.

## 0. Rules every sprint here follows

- Any doc-recognition change bumps the genuineness `MODEL_VERSION` with a History line, in the same
  change (`feedback_doc_recognition_versioning`).
- Never re-extract or call Gemini/Vision from a local checkout; a rescore is a re-run ON THE LIVE
  SERVICE (cockpit Re-run or a job), paid, owner-approved (`halatuju_never_reextract_locally`).
- STPM `ua_offer` + `suspect` is often correct — Form 6 announcements are not a gap.
- Each sprint changes what blocks or flags a student's offer/results → adversarial review before push.
- Opus-family builder to a written brief in a worktree; the lead verifies the diff, re-runs both
  suites (gate command lines), owns the push and the close.
- Wording for a family comes from REAL letters, never invented (see decision C).

## 1. Sprints

### C0 — Gather the wording (owner + lead; no code) — gate for C2 and C3 — ✅ DONE 2026-10-26
**Done:** the lead's read-only capture (decision C, option b) of 7 UiTM offers and 10 STPM documents;
the wording, PII-free, is in the catalogue (UiTM) and the C3 brief (STPM).
- **Goal:** the fixed printed text of UiTM offers and STPM results (slip + certificate), taken from
  real documents we already hold.
- **How (decision C):** (a) the owner reads ~7 UiTM letters and ~5 STPM documents in the cockpit and
  types the fixed lines (free; how the catalogue was built on 8 Jul), or (b) the lead runs a read-only
  `fetch_corpus.py` download + paid `capture_ocr.py` (Cloud Vision, local snapshot files only, ≈15–20
  documents, a few ringgit).
- **Also here (free/cheap):** re-run the 3 unscored offers (UMS ×2, UMK, 24 Oct) from the cockpit.
- **Done when:** the wording for each family is written into `docs/scholarship/offer-letter-catalogue.md`.

### C1 — "We don't know this issuer yet" (safety net) + an honest private-college reason — ✅ LIVE 2026-10-26
**Done:** `1a2b4962` + `95131a65` (api-01144-sfg). Narrowed after review to a suspect-band letter with offer
wording and a letterhead issuer; owner ruling C (Kolej MARA public; KPTM / UniKL private). Retro
`docs/retrospectives/retrospective-2026-10-26-corpus-c1-c2.md`.
- **Goal:** an offer from a KNOWN public issuer we have not fingerprinted yet is stored as
  "not checked" — no genuineness penalty, never a block, reviewer checks by eye. A private-college
  offer gets a plain "private college" reason instead of the misleading nearest-family label.
- **Recognise by name:** Kementerian Belia dan Sukan / IKBN / IKTBN / ILKBS; MARA / TVETMARA / IKM /
  KKTM; JTM / ADTEC / ILP / JPK (decisions A and B decide the list and what "supported" means).
- **Scope:** `genuineness/results_doc.py` (the not-checked outcome; fix the stale 1.4.0 comment
  ≈191–194), the three places that fold "unrecognised" into suspect (`vision.py` ≈2175,
  `bands.canonical_status`, `pathway_engine.offer_official_status`), `offer_pathway._PATHWAY_FAMILY`
  (add `ilkbs` / `iljtm` / `kkom`), the officer-facing reason text, tests (`test_doc_signatures.py`,
  a `labels.json` entry), catalogue doc. **MODEL_VERSION → 1.8.0.**
- **Acceptance:** request #47's ILKBS letter reads "not checked", raises no "not official" request and
  no block; every fingerprinted family scores exactly as before (held-out check unchanged); a private
  college offer says "private college".
- **Complexity:** medium. **~8 h** incl. review. Gate: decisions A + B.

### C2 — UiTM in the public-university family — ✅ LIVE 2026-10-26
**Done:** `1accaab9` + `a781b49a` (MODEL_VERSION 1.8.2): all 7 letters genuine on OCR and text layer; no
`pathway_engine` change needed (UiTM's bare "Tarikh" is already allowed). Plus the C1 follow-up: an
officer's offer request is held for the officer, never closed by a "not checked" upload (TD-406 open).
- **Goal:** UiTM offers (Bahagian Pengambilan Pelajar) score as genuine when genuine.
- **Scope:** the public-university list in `results_doc.py` (alternative offer line + office line),
  `_FAMILY_ISSUER_SIG` / `_REPORTING_LABELS` (`pathway_engine.py` ≈270–290), tests, catalogue.
  **MODEL_VERSION → 1.8.1.**
- **Acceptance:** the 7 live UiTM letters' wording scores ≥ 0.70 in a synthetic test built from the
  C0 wording; the other 20 universities unchanged.
- **Complexity:** low. **~4 h.** Gate: C0 (UiTM wording).

### C3 — STPM results family (slip + certificate) — ✅ LIVE 2026-10-26
**Done:** `0ae5f431` (api-01147-9gw), MODEL_VERSION 1.9.0, `genuineness/stpm_doc.py`; owner rulings 1A (the
online checker page is not a result document) and 2A (a certified copy is). Retro
`docs/retrospectives/retrospective-2026-10-26-corpus-c3-c4.md`.
- **Goal:** STPM results (Majlis Peperiksaan Malaysia) are scored as STPM, not as a bad SPM slip —
  in the results slot and the semester-result slot.
- **Scope:** a new STPM list in `results_doc.py` registered in `_RESULTS_LISTS`; the results-slot
  genuineness (`vision.py` ≈2141) picks the family by best score as today; the semester-result slot
  gains the same check for STPM documents; tests; catalogue. **MODEL_VERSION → 1.9.0.**
  Coordinate with the third-route session: their S3b (`results_kind.py`) must not edit
  `results_doc.py`; whichever lands second rebases and re-runs both suites.
- **Acceptance:** the 40 live STPM documents' shape scores as STPM (synthetic tests from C0 wording);
  every SPM slip and certificate scores exactly as before (held-out check); a suspect STPM result
  no longer drops the Academic card one or two bands.
- **Complexity:** medium. **~12 h.** Gate: C0 (STPM wording).

### C4 — Live re-run of the affected documents (ops, no code) — ✅ DONE 2026-10-26
**Done (the lead):** 43 documents re-scored through the `release-decisions` job — 11 UiTM offers → genuine
(0.80–0.90), IKBN d3465 → not checked, 17 STPM documents → genuine (0.92–1.00), d3109 → suspect 0.36, the
checker page d3303 stays not a result document. ⚠ The first run lacked the service's genuineness flag and
wiped 16 scores (re-run with the flags; TD-407; retro).

**The arc is complete except the data-gated TVET families below.**
- **Goal:** the ≈30 documents scored under the old patterns are re-scored with the new ones.
- **How:** on the live service only — `reextract_offers` with a new `PASS_MARKER` (offers below 0.70)
  and `reextract_documents` (STPM results), or the cockpit Re-run. Paid (Gemini + Vision, a few
  ringgit). Before/after list shown to the owner first.
- **Gate:** decision D, after C1–C3 are live. **~2 h.**

### Later — TVET families (one per ministry), data-gated
- Belia & Sukan, MARA, JTM: ~1 day each, ONLY once we hold ≥3 genuine examples each (today 1–2).
  Until then C1's "not checked" covers them. Re-assess at each consolidation review.
- Not worth a family now: income-support letters (no fixed format), university/polytechnic semester
  slips (too varied).

## 2. Order and total

C0 (can start now) → C1 (independent of C0; starts on decisions A + B) → C2 → C3 → C4.
C1 and C0 run in parallel. **Total ≈ 26 h of build** (C1 8 + C2 4 + C3 12 + C4 2) plus the owner's
C0 time. TVET families later.

## 3. Risks

- C1 partly reverses the 1.4.0 decision (unknown issuers were dropped). The list is closed and named,
  so a forged letter from an UNNAMED issuer still scores as today.
- A forged letter using a named TVET issuer passes as "not checked" — the reviewer is the backstop,
  exactly as for any unscored document; the cockpit must show "not checked" plainly.
- C3 and the third-route S3b touch neighbouring code (`vision.py` results slot); sequence and rebase.
- Re-scoring is paid and live-only; nothing is re-read without the owner's yes.

## 4. Decisions for the owner

- **A.** Approve the "known public issuer, not yet checked" safety net (C1)? It partly reverses 1.4.0.
- **B.** Do TVET offers (ILKBS / IKBN / TVETMARA / ADTEC) count as supported official public offers?
- **C.** Wording: you read the letters (free), or a paid OCR capture of ≈15–20 documents?
- **D.** Approve the live re-run of the ≈30 affected documents once C1–C3 are live (C4)?
