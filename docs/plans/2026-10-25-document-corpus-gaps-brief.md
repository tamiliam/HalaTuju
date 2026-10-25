# Document corpus gaps — research brief (2026-10-25)

**Status:** research done, read-only. Not started. Owner hands this to a dedicated agent.
**Origin:** org request #47 (an ILKBS/IKBN offer letter marked "suspect" because no pattern exists for it).
The owner asked: compare the documents we receive with what our genuineness corpus covers, find the
families we receive but do not cover, and propose how to add them.

**Related work (separate):** the third results route (Matriculation / Asasi / Diploma) and the
higher-results upload — `docs/plans/2026-10-25-third-results-route-roadmap.md`. That roadmap keeps
plain type DETECTION (is this an STPM / Matriculation / Asasi / Diploma result?) for routing; the
genuineness FAMILIES below belong here.

**House rules that apply:** any doc-recognition change bumps `MODEL_VERSION` with a History line
(memory `feedback_doc_recognition_versioning.md`); never re-run extraction or call Gemini/Vision
from a local checkout (`halatuju_never_reextract_locally.md`); STPM `ua_offer` + `suspect` is often
correct (`feedback_stpm_announcement_suspect_correct.md`); eligibility rules get an adversarial
review before push (`feedback_adversarial_review_before_ship.md`).

## 1. What "the corpus" is

- **Patterns:** fixed lists of printed text in `halatuju_api/apps/scholarship/genuineness/results_doc.py`
  - SPM slip and certificate (≈96–135); birth certificate (≈147); EPF (≈168)
  - Offer letters: STPM ≈203, Matriculation ≈221, Polytechnic/JPPKK ≈239, PISMP ≈260, 20 named public
    universities ≈282–312; registered at ≈359–361
  - Three STR forms ≈321–352
- **Family choice:** every list is scored, best wins (`score_signatures` ≈441–453). No "none fits"
  outcome for offers: `signature_genuineness` ≈549–551 bands 0.70+ genuine, 0.35–0.70 suspect,
  below 0.35 `not_offer_letter`.
- **1.4.0** dropped the offer issuer check (≈58–66). The comment at ≈191–194 still says unknown issuers
  go to a holistic check; that stopped being true then.
- **Pattern-scored elsewhere:** salary, electricity, water, school-leaving certificate
  (`genuineness/__init__.py` ≈40–61).
- **Real examples:** `apps/scholarship/eval/` (gitignored, local, last refreshed 10 Jul): 95 offer and
  97 results OCR texts; zero UiTM, Belia & Sukan, MARA or Sumber Manusia letters; one STPM (MPM)
  document. Issuer catalogue: `docs/scholarship/offer-letter-catalogue.md`.
- **The database does not store OCR text**, only the lists of patterns found and missing.

## 2. Coverage by document type (live data, 2026-10-25)

| doc_type | total / last 90 days | Check | Outcome mix |
|---|---|---|---|
| offer_letter | 223 / 109 | patterns (5 families) | 170 genuine, 23 suspect, 27 fake, 3 unscored |
| results_slip | 225 / 119 | patterns (SPM only) | 121 genuine, 37 suspect, 11 fake (+ older holistic reads) |
| ic / parent_ic | 216 / 238 | holistic image read | mostly genuine |
| str | 174 / 65 | patterns, then holistic | 124 genuine, 8 suspect, 12 not STR |
| salary_slip | 213 / 94 | patterns | 82 genuine, 26 suspect, 8 not |
| electricity / water | 170 / 165 | patterns | mostly genuine; "not" = bills in the wrong slot |
| epf | 95 / 22 | patterns | 32 genuine, 26 not EPF |
| birth_certificate | 93 / 34 | patterns | 83 genuine, 6 suspect, 4 not |
| school_leaving_cert | 58 / 32 | patterns | 48 genuine, 6 unrecognised (testimonials) |
| semester_result | 23 / 15 | none | unscored (11 are STPM slips) |
| income_support_doc | 15 / 11 | none | unscored (penghulu/JKKK letters) |
| bank_statement, guardianship_letter | 9 / 2 | none | unscored |

## 3. Received but not covered

| Cluster | Docs (live) | Issuers | Today | Harm |
|---|---|---|---|---|
| STPM results (Majlis Peperiksaan Malaysia) in the results slot | 40 (24); 38 in 90 days | 1 | scored as SPM: 32 suspect (0.39–0.52), 2 fake, 5 genuine | High: latest results doc for 18 applications (16 active); Academic card drops one or two bands |
| UiTM offers (Bahagian Pengambilan Pelajar) | 7 (7), all 15–22 Oct | 1 | public-university family at 0.40 (name + finality found; "Tawaran Kemasukan" line and office line not) | High: "not official" fires the official-document request; risk of the submission block |
| Belia & Sukan (IKBN/ILKBS) — request #47 | 3 (1), one applicant | 1 | suspect 0.40 vs university family; a JPK letterhead copy scored fake 0.06 | Medium: `ilkbs` is a selectable pathway; reason names the wrong family |
| MARA TVET (TVETMARA) | 1 (1) | 1 | nearest Polytechnic: fake 0.11 | High per document |
| Polytechnic letters on the college's own letterhead | 3 (2) | 3 | fake 0.17–0.20 | Eyeball first; may not be offers |
| University faculty-office / logo-only letters (UMS, UNIMAS, UTM) | 4 (3) | 3 | fake 0.07–0.30 | Eyeball first |
| Form 6 letters issued by the school | 4 (3) | 3 | suspect / fake | Not a gap (owner ruling: announcements; STPM exempt from the block) |
| Private colleges/universities (8 issuers) | 8 (8) | 8 | fake 0.06, labelled "polytechnic" | Correct under policy; the label misleads |
| Unscored offers (UMS ×2, UMK, 24 Oct) | 3 (3) | 2 | no score → unknown (never blocks) | Low; a live rescore clears it |

**Root cause for all:** an offer that matches no pattern is compared with the nearest pattern and
banded by score; it never says "we do not know this issuer".

## 4. Recommendations

**Interim safety net (≈1 day + adversarial review):** a "known public issuer, not yet fingerprinted →
not checked" outcome. Recognise by name: Kementerian Belia dan Sukan / IKBN / IKTBN / ILKBS;
MARA / TVETMARA / IKM / KKTM; JTM / ADTEC / ILP / JPK. Stored as unrecognised, no genuineness penalty,
gating treats it as unknown (no block), reviewer checks by eye. Everything else keeps today's bands.
Three places fold "unrecognised" into suspect and need changing: `vision.py` ≈2175,
`bands.canonical_status`, `pathway_engine.offer_official_status`. Bump MODEL_VERSION (→ 1.8.0).

**Families, in priority order:**
1. STPM results (slip and certificate, scored like SPM; also for the semester_result slot) — one
   national issuer, uniform layout. ≈1–1.5 days. Also needed by the third-route roadmap's
   higher-results upload.
2. UiTM wording in the public-university family (alternative offer line + "Bahagian Pengambilan
   Pelajar"). ≈½ day.
3. TVET families (one per ministry) — ≈1 day each, only once ≥3 genuine examples each (we have 1–2).
4. A clear "private college" reason instead of the nearest-family label. Small.
5. Not worth a family: income support letters (no fixed format); university/polytechnic semester
   slips (too varied for now).

**What adding a family needs:**
- Wording from real letters: (a) owner reads the letters and supplies the fixed text (free; how the
  catalogue was built on 8 Jul), or (b) read-only download with `fetch_corpus.py` + paid
  `capture_ocr.py` (Cloud Vision, local snapshot files only — owner approval needed).
- Code: the list in `results_doc.py` registered in `_OFFER_LISTS` / `_RESULTS_LISTS`;
  `_REPORTING_LABELS` and `_FAMILY_ISSUER_SIG` (`pathway_engine.py` ≈270–290); add
  `ilkbs` / `iljtm` / `kkom` to `offer_pathway._PATHWAY_FAMILY` (missing today → unknown family);
  update the catalogue doc.
- MODEL_VERSION bump + History line in the same change.
- Tests: synthetic letters in `test_doc_signatures.py`, a `labels.json` regression entry, a held-out
  check; adversarial review (eligibility rule).
- Rescoring: OCR text is not stored, so a rescore is a re-extract ON THE LIVE SERVICE (cockpit Re-run,
  or `reextract_offers` with a new `PASS_MARKER` — targets docs below 0.70; `reextract_documents` for
  results slips). ≈30 documents, paid Gemini + Vision reads. Never locally.

## 5. Decisions for the owner

1. Approve the "known public issuer, not checked" safety net? (Partly reverses the 1.4.0 decision.)
2. Do TVET offers (ILKBS / IKBN / TVETMARA / ADTEC) count as supported official public offers?
3. Example wording: owner reads the letters (free) or a paid OCR capture of ≈15–20 documents?
4. Approve a live-service re-run of the ≈30 affected documents once the families ship.

(STPM results are accepted as the academic document for STPM and STPM-equivalent applicants — owner
ruling 2026-10-25, see the third-route roadmap.)
