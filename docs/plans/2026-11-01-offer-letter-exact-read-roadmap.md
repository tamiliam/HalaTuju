# Offer letters read exactly — roadmap (2026-11-01)

**Status:** APPROVED 2026-11-01 by the owner, with every recommended decision (D1–D6 option a). S1 in progress. Planned on main `c9a4612c` and checked against
`origin/main 23e058a8`. Builds on the offer realignment, the date rule and the offer link — all LIVE 2026-11-01
(main `9969c1f3`, api-01225-fxd; applied: 27 realigned, 9 linked). Retros
`retrospective-2026-11-01-offer-realignment.md` and `retrospective-2026-11-01-offer-date-rule-and-link.md`.

**Scope line.** This roadmap is about **reading** the letter (what the fields say). What happens *after* the read —
the catalogue matcher, campus naming (`offer_course_match.CampusReader`), realign and link — is the other
session's area and is NOT re-planned here. Its open debts stay where they are: TD-447 (confirm can keep a hostel
line), TD-448 (realign waits for a late genuineness score), TD-449 (offer-check queries outside the budget),
TD-451 (a short "KK …" / "POLY …" line can name another institution type), TD-452 (hand-written town words).
The correct answers made here give those debts a real test set for free (the printed institution line of every
letter), but fixing them is not in these sprints.
**No personal data appears in this file.** Every count below comes from the stored production reads in the gitignored
corpus `eval/fixtures/offer_letters_2026-11-01/`; no paid call was made.

---

## 0. What the owner asked, and what it means

"Train the model to read offer letters exactly." Nothing here trains a model; Gemini is a hosted model and we
cannot retrain it. What we can do is:

1. write down the **correct answer** for each real letter (ground truth);
2. **score** every reader against those answers, free and repeatably;
3. **change the reader** (the prompt, what it is shown, the deterministic parsers) and keep only changes that raise
   the score on letters it was **not** tuned on (a held-out set).

So step 1 is a **baseline score**, before any reader change.

---

## 1. How an offer letter is read today

| Step | Where | What happens |
|---|---|---|
| Upload | `DocumentListCreateView` → `vision.run_field_extraction_for_document` → `_run_field_extraction_impl` (`vision.py` ≈2064) | runs on the Cloud Run service on upload (or Re-run / sweep) |
| OCR | `vision.ocr_document_full` | a digital PDF with a usable text layer is read from that layer (free); anything else goes to Cloud Vision (paid, page 1) |
| Exact read (deterministic) | `offer_parse.parse_govt_offer` (`PARSER_VERSION` 1.3.0) | STPM / Matriculation / Polytechnic only, from the OCR text. Returns None (→ Gemini) unless name, NRIC, programme and intake all lock and no field looks like a date, ringgit amount or clause number. Its fields are **merged over the earlier read** (a "deterministic" record can still carry Gemini's older fields). Stored `capture='deterministic'`, `_offer_parser_version`. |
| AI read | `vision.extract_document_fields(image=…)` → `_call_gemini_json` | Gemini `gemini-2.5-flash` (cascade → `2.5-flash-lite`), temperature 0.1, JSON schema `_FIELD_SCHEMAS['offer_letter']`, prompt = generic preamble + `_WARNING_VOICE` + `_DOC_HINTS['offer_letter']`. **Image only: a PDF is rasterised to page 1** (`_as_image_for_gemini`) — the text layer and pages 2+ are never shown to Gemini. Stored `capture='ai'`, **with no reader/prompt version**. |
| Clean-up | `_sanitize_extracted_fields` (reporting date → "D Mon YYYY"), `_drop_expected_warnings` (drops "missing date/intake/stream" notes) | deterministic |
| Name verdict | `doc_student_verdict` | `ok` / `name_mismatch` / `wrong_doc` against the student's own name |
| Genuineness | `genuineness.assess('offer_letter')` → `results_doc.signature_genuineness` (`MODEL_VERSION` 1.22.0), OCR text only | `genuine` ≥0.70 / `suspect` / `not_offer_letter`, or `unchecked` (known TVET issuer). Flag-gated: `DOC_GENUINENESS_CHECK_ENABLED`. |
| Staff view | `pathway_engine.student_offer_check` (+ `offer_official_status`, `offer_band`, `offer_reporting_bonus`) | Name·IC chips, Pathway match (via `offer_pathway` + `offer_course_match` catalogue matcher), institution ticks, intake year vs cohort, reporting date |
| Follow-on writes | `services/offer_sync` (autofill, Bumi-only / old-pick realign, `PICKER_COMPLETE_AT`), `services/offer_link`, institution sync | a **changed read can move a student's pick** — any re-read is a live write |

**Fields read today:** candidate_name, candidate_nric, programme, institution, issuer, offer_date, intake,
candidate_address, stream, reporting_date, reporting_date_label, bidang_pengkhususan, elektif, aliran.
**Not read:** duration, fees, mode of study (the matric parser sees "Tempoh Pengajian" and "Yuran Pendaftaran"
labels but does not keep them).

**"Exact read" today** means only `capture='deterministic'` — the three government formats parsed from OCR.
There is no measure of whether *any* read, deterministic or AI, matches the letter.

---

## 2. Baseline from the stored reads (counts only, free)

**Corpus:** 287 letters from 251 applications — Sabah 158, flagship 128, GSS Ipoh 1. Files: 189 PDF, 94 JPG, 4 PNG.
Of the PDFs, 112 have one page, 76 have two or more, 1 is not a real PDF.

| Measure | Count |
|---|---|
| Name verdict | ok 278 · name_mismatch 8 · unreadable 1 (the not-a-PDF file) |
| Capture | AI 216 · deterministic 71 (Sabah: 148 of 158 AI; flagship: 61 of 128 deterministic) |
| Genuineness | genuine 237 · not_offer_letter 31 · suspect 17 · unchecked 1 · unscored 1 |
| Family (scorer's `doc_seen`) | university 149 (UiTM 18 of them) · polytechnic 43 · matriculation 39 · STPM 37 · PISMP 17 · TVET 1 · none 1 |
| Empty field | reporting_date 53 · offer_date 42 · candidate_nric 38 · programme 10 · intake 10 · institution 7 · issuer 7 · name 4 · (STPM/matric stream 6) |
| Read dates | Jun 23 · Jul 96 · Aug 3 · Sep 5 · Oct 160 |
| Genuineness versions on the stored reads | 22 different versions (1.1 → 1.22.0) |

**Free text we already hold:** 191 of 287 (134 PDF text layers + 57 earlier Vision OCR captures). The other 96
(47 photos, 49 scanned PDFs) need one Vision call each.

**Today's code replayed on the 191 (free):**
- The deterministic reader locks 41 (STPM 13, matriculation 15, polytechnic 13); 150 go to Gemini.
  On the 41: NRIC agrees with the stored read 41/41, name 40, stream 40, intake 39, reporting date 39,
  institution 37, programme 36, offer date 25 (15 stored-only — from the merged earlier Gemini read).
- Genuineness: 190 of 191 score as stored (1 suspect → not_offer_letter).

**Who has seen these letters before:** the old local corpus (`eval/fixtures/offer_letter/`, 95 letters) is 94
flagship letters, all also in the new set; 45 of them are the genuineness tuning set (`heldout_eval.CORPUS_IDS`).
**All 158 Sabah letters and 34 flagship letters are unseen.** No field-level correct answers exist for any offer
letter: `labels.json` has no `docs` entries and one offer regression (an ILKBS genuineness check).

### Provisional failure kinds (proxies — to be confirmed by the correct answers)
An empty field can be correct when the letter does not print it, so these are suspicions, not errors.

1. **No reporting date — 53 (18 %).** University 31, PISMP 8, polytechnic 7. Mostly one-page PDFs and photos, so
   only ~10 are explained by Gemini seeing page 1 only.
2. **No NRIC — 38 (13 %).** 30 are university letters read by Gemini.
3. **Not judged genuine — 48 (17 %):** not_offer_letter 31 (polytechnic 14, university 8, STPM 4, matric 4, PISMP 1),
   suspect 17. Some may be real letters the scorer rejects; some are rightly rejected (portal pages, private arms).
4. **Name mismatch — 8,** 6 of them university letters read by Gemini.
5. **Stale, mixed reads.** 216 AI reads carry no reader version; stored reads span 22 genuineness versions; a
   "deterministic" record can hold older Gemini fields. Today's parser differs from the stored read on 5 programmes
   and 3 institutions among its 41 locks.

### Corpus gaps found
- **Student context is missing for 216 of 287 letters** (191 of 251 profiles absent from `applicants.json`).
  Likely cause: `fetch_corpus.py` asks PostgREST for 5000 rows, but the server returns at most 1000 (Supabase
  default) and `api_student_profiles` is larger. Read-only fix: page through the profiles. This matters for the
  name/NRIC verdict layer, not for the correct answers (those come from the letter).
- 96 letters have no OCR text yet (above).

---

## 3. Tooling — what exists, what is missing

**Exists (reuse):** `fetch_corpus.py` (read-only download), `capture_ocr.py` (text layer free, else Vision; caches
`<key>.ocr.txt` / `.words.json` / `.meta.json`), `heldout_eval.py` (offer genuineness, and a paid local Gemini
extraction that prints but does not score), `regression_check.py`, `eval_doc_recognition` (verdict layer replay),
and the **STPM / matric / poly exact-read pattern**: hand-checked `<key>.expect.json` beside the snapshot plus a
`*_parse_check.py` that prints exact / fallback / WRONG per document — keys and field names only, never values.
Guard `test_no_gitignored_corpus.py` keeps tests off the corpus; committed tests use synthetic twins.

**Missing for offers:**
1. A **correct-answer format** for offer letters (`<key>.offer_expect.json`, gitignored).
2. A **scorer** (`offer_read_check.py`): per field and per letter, exact / blank-correct / missing / wrong / extra,
   by family, input kind (photo, scan, text PDF, multi-page), capture, programme and split.
3. A **held-out split**, committed as PII-free keys.
4. A **reader version** on AI reads.
5. A **fresh-read harness** that runs today's Gemini read on the local files and caches it (paid, local, no live write).

---

## 4. Correct answers — options

| | A. Lead agent drafts, owner spot-checks (recommended) | B. A person checks every letter |
|---|---|---|
| How | The lead agent reads each letter's image **before** looking at the stored read (to avoid copying it), writes the answer, marks anything unsure. Then compares with the stored read and re-looks at every disagreement. | A simple local form pre-filled from the stored read; the owner or a staff reviewer ticks or corrects each field. |
| Owner time | ~1 h: a random 30 letters + every "unsure" | 5–7 h (1–1.5 min × 287) |
| Cost | none (no paid API) | none |
| Risk | agent mistakes (measured by the spot-check; if more than 2 of 30 are wrong, widen the check); the letters are read inside the Claude session, as for the STPM corpus | fatigue; ticking a pre-filled wrong value ("anchoring") |

A third route — a second Gemini model (2.5 Pro, ~RM25–50 for 287) pre-labels and people check only the
disagreements — is cheaper in time than B, but two Gemini models share blind spots, so agreement is not proof.
Not recommended as the main route.

---

## 5. Cost

| Step | Paid? | Estimate |
|---|---|---|
| Scoring stored reads, deterministic replay, genuineness replay, labelling | Free | — |
| Vision OCR for the 96 letters with no text | Paid (tiny) | 96 pages × US$1.50/1000 ≈ US$0.15; inside Vision's 1000 free units a month |
| Gemini re-read, one letter (2.5 Flash, one page image) | Paid | input ≈ 2.5–4.5k tokens (prompt ≈1.2k + image ≈1.3–3k) at US$0.30/M; output ≈ 0.3k JSON + 0.5–3k thinking at US$2.50/M → **≈ US$0.003–0.01 (≈ 1–5 sen)** |
| Gemini re-read, all 287 | Paid | **≈ US$1–3 (≈ RM4–13)** per full pass; showing up to 3 pages roughly doubles the image part |
| Live re-read of affected records (end) | Paid | same rate per letter, plus Vision for photos |

Notes: the live usage meter records `candidates_token_count` only, so thinking tokens (billed as output) are
probably not counted — S3 measures the real figure on 10 letters first. Gemini is on **prepaid credit**; check the
balance before any run (the 2026-10-23 outage was the credit running out).

---

## 6. Rules that bind every sprint

1. **PII stays gitignored.** Letters, snapshots, answers, context live under `eval/fixtures/*` / `eval/snapshots/*`.
   Scripts print keys, field names and counts — never a value. Committed tests use synthetic twins
   (`test_no_gitignored_corpus.py`). No value in a commit, workflow, report or chat.
2. **Never re-extract from a local checkout against production** (no Storage locally; it overwrites good reads).
   Local paid runs read the fixture files and write only local gitignored caches.
3. **Version every recognition change:** `offer_parse.PARSER_VERSION` for the deterministic reader,
   `results_doc.MODEL_VERSION` (+ History line) for genuineness, and a new offer reader version for the Gemini
   prompt/schema/inputs (none exists today — S4 adds it).
4. **Re-reads through `release-decisions`** need `--update-env-vars=DOC_GENUINENESS_CHECK_ENABLED=1,BILLING_USAGE_ENABLED=true`
   (check the service's live flags first), `--task-timeout=3600s`, print `authenticity.status` per letter, stop on None.
   Cockpit Re-run for a handful.
5. **A re-read is a live write:** it can trigger autofill, realign (Bumi-only / old-pick under the live date rule),
   link and institution sync — all live since 2026-11-01. Dry-run the planners (`realign_bumi_offers`,
   `link_offer_courses`, `backfill_institution` report modes; realign before link, as their own command does) on
   the new reads, show the before/after list, and state the undo path in the same message that asks for the yes
   (the AUDIT lines carry every old course id). Message the session that owns the matcher before the run.
6. **Adversarial review before the push** for anything touching name, NRIC (identity), the offer-validity gate,
   the pathway verdict or a pick (eligibility).
7. **Dry-run any new flag or refusal on live stored data** before deploy, not only the corpus.
8. **Paid runs only on the owner's yes**, with the estimate stated; credit balance checked first.
9. **No second company reads student documents** (owner, TD-399 parked) — the reader stays Gemini + Vision.
10. **Known traps:** STPM `ua_offer` + `suspect` is often correct (Form 6 announcements); a HalaTuju push deploys;
    coordinate deploys and take version numbers at push time; keep the Bumi-blind column list in `fetch_corpus.py`.

---

## 7. Sprints

Small sprints. Sprint 1 ends with the baseline; no reader change before Sprint 4.

### S1 — Correct-answer format, scorer, held-out split → the BASELINE (medium, ~8 h + owner ~30 min)
- **Goal:** an exact-read score for today's stored reads on a held-out set nobody tuned on.
- **Scope:** `eval/offer_read_check.py` (new scorer; normaliser: case, spacing, punctuation, NRIC digits, dates
  → D Mon YYYY; "blank when not printed" counts correct); `eval/offer_split.json` (new, PII-free keys: ~90 letters
  drawn at random from the 193 unseen, stratified by family and programme, fixed seed); gitignored
  `<key>.offer_expect.json` for the ~90 held-out letters (route chosen in D1); `fetch_corpus.py` profile paging
  fix (read-only) and a `--metadata-only` refresh; the answer records the institution line **exactly as printed**
  (read accuracy) and, separately, the campus a person would pick (so the matcher's TD-451/452 can be measured on
  real lines later without re-labelling); `tests/test_offer_read_scorer.py` (synthetic twins: normaliser,
  scoring rules); `eval/README.md` section.
- **Owner steer (2026-11-01, during S1):** the held-out letters are drawn only from the unseen letters whose
  stored read is the AI reader's — the fixed-format locks (STPM / matric / poly) are already exact and covered by
  their parse checks, so they are not hand-labelled in S1. Pool 174 (193 unseen less 19 deterministic) → 90 held
  out. The scorer also prints the known-format-AI count (fixed-format family, AI read) for S5.
- **Acceptance:** one free command prints the baseline — % of held-out letters fully exact on the core fields, and
  per-field exact / missing / wrong — by family, input kind and programme; identical on re-run; prints no value;
  owner's spot-check done and its error rate written down; baseline recorded in this roadmap.
- **Owner:** decisions D1–D3; spot-check ~15 held-out answers. No paid call. No deploy.
- **Baseline (2026-11-01, stored reads, held-out 90).** Fully exact **21 of 90 (23.3 %)**. Right per core
  field: name 94.4 % · NRIC 98.9 % · institution 51.1 % · programme 73.3 % · intake 81.1 % · reporting date
  96.7 %. Not core: offer date 95.6 % · issuer 21.1 % · specialisation 4 of 4 (100 %; scored only where the
  answer has one). Identical on re-run; no value printed. (Before the owner's rulings below it read 22 of 90:
  the PISMP programme rule moves 4 PISMP programmes to wrong — the stored reads carry "PROGRAM … (PISMP)", not
  the degree title as printed — and the a405 reporting date became an extra.)
- **Owner spot-check (2026-11-01).** 32 held-out answers checked. Core-field labelling errors found: **1**
  (a405 reporting date — the printed date is a commencement date, not a reporting date; now null).
  Is-it-an-offer lines marked wrong: **3** (a13, a367, a413) plus a405 (a scope remark, see below); only a413's
  answer changed (yes → unsure: may not be post-secondary, MOE not MOHE). On a13 and a367 the answer already
  said yes and the owner agrees they are private-college offers — the "wrong" is against the stored genuineness
  verdict, which calls both `not_offer_letter` (an S6 input). a405 stays yes (a master's offer: outside the
  bursary's scope is an eligibility matter, not reading). The 14 intake and 2 PISMP programme corrections were
  **conventions, not errors**: intake keeps its label as printed (the scorer already drops it, so no score
  moved); PISMP's programme is the degree title, as for any university (the specialisation stays recorded,
  scored as a not-core field). The other 3 held-out PISMP answers were checked against the letter: 2 set to the
  degree title, 1 is not an offer (no programme).
- **Owner notes from the S1 check:**
  (a) the reporting date can be on page 2, or on an e-registration slip that sits in front of the offer →
  supports S4 (multi-page);
  (b) an offer with no offer date may be suspect → an S6 genuineness input;
  (c) when the reporting date is missing, Check 2 could ask the student for it (even an estimate) → a product
  idea for the owner, outside this arc;
  (d) postgraduate offers are outside bursary scope → an eligibility check, outside this arc;
  (e) the stored genuineness verdict calls 2 private-college offers (and the postgraduate one) not an offer
  letter, while the labellers had them right → in S2, the owner's check covers every not-offer answer AND every
  letter the stored genuineness calls not an offer;
  (f) dates are read without weekday or time (the scorer already ignores them).

### S2 — Dev-set answers and the failure map (low–medium, ~6 h + owner ~30 min)
- **Goal:** know which failures matter most, and which are old reads versus today's reader.
- **Scope:** answers for the dev letters **whose stored read is the AI reader's** (owner steer 2026-11-01: the known
  formats the fixed-format reader locked are already exact and covered by the stpm/matric/poly parse checks — not
  re-labelled); the scorer on dev; a failure table (wrong vs missing vs
  extra; by family, page count, photo/scan/text PDF, capture, stored version); replay of today's deterministic
  reader and genuineness on all free text; Vision capture for the 96 letters with no text (`capture_ocr.py`).
  Label "is this a real offer letter?" (yes / conditional / portal page / private) so genuineness is scored too.
- **Acceptance:** a ranked list of failure kinds with counts; each tagged "old read" or "today's reader too".
- **Owner:** yes to ~US$0.15 of Vision (likely free); spot-check ~15 dev answers.
- **DONE 2026-11-01.** 126 dev answers (the AI-read dev letters); 216 letters answered in all. Vision: 106 page calls
  (~US$0.16, inside the free tier, via gcloud ADC); every letter now has free text. Replay of today's free readers:
  51 of 287 lock, 235 fall back to Gemini, 1 no text; of the 71 stored deterministic reads, **21 would now fall back**
  (15 STPM photos + 1 poly photo rejected by a newer parser safety check; 5 matric text PDFs with no name/IC found)
  - a live re-read (S7) must not lose them. Known-format letters read by AI: 38, only 1 locks today (21 layout
  variants, 14 photo noise, 2 other) - S5's first job.
  **Scores under the S2 rules** (institution and campus split, intake labels): held-out 19/90 fully exact (21.1%),
  dev 31/126 (24.6%). Held-out right %: NRIC 98.9, reporting date 96.7, name 94.4, intake 81.1, programme 73.3,
  institution 46.7 (campus missing on every letter that prints one - the reader has no campus field yet).
  **Top failure kinds (216 letters):** institution = reporting venue 35; institution names a campus / branch the
  line does not 33; programme keeps a code 24; institution adds to the line 22; real offer judged not genuine 19;
  known format not locked 18; PISMP programme wrapper 16; programme adds words 16; intake drops Semester 11.
  **Owner's offer check (47 letters):** our is-it-an-offer labels 47/47 right; 8 live genuineness calls wrong (below).

### S3 — Today's AI reader, measured (low, ~4 h; paid)
- **Goal:** today's Gemini read scored on the dev set, and its true cost per letter.
- **Scope:** `eval/offer_fresh_read.py` (new, or `heldout_eval.py local` extended): today's prompt on the local
  files, cached as gitignored `<key>.fresh.json` with full token use incl. thinking; the scorer compares stored vs
  fresh. 10 letters first, then the dev set.
- **Acceptance:** fresh-read score on dev beside the stored score; measured cost per letter; a TD if the live meter
  under-counts thinking tokens.
- **Owner:** yes to ≈ RM3–9 (dev set, one pass).
- **DONE 2026-11-01.** `eval/offer_fresh_read.py` runs `vision.extract_document_fields` (the production AI read,
  same prompt / schema / cascade / page-1 image) on the local files, nothing persisted but the cache. All 216
  answered letters read once: **US$0.845 = RM3.72** (pilot RM0.15 + run RM3.57), US$0.0039 a letter, every call
  answered by gemini-2.5-flash, no 402/429. **Today's reader = the stored reads:** fully exact 53/216 fresh vs
  50/216 stored; institution 96 vs 99 right, programme 155 vs 152, intake 183 vs 184, name 208 vs 205 - the
  failures are the reader's, not old reads. **Every image is sent as 258 tokens** (a low-detail view of page 1,
  whatever its size) - an S4 input. **The usage meter drops thinking tokens** (~80-85% of the billed output):
  TD-459.

### S4 — Reader round 1: traceability and what Gemini sees (medium–high, ~10 h; production code)
- **Matcher contract (Cockpit session, 2026-11-01):** the offer matcher reads `fields.programme`, `fields.institution`,
  `fields.issuer` and `authenticity.status`. Any change to what those carry (e.g. the institution line instead of
  the reporting venue — the S1 baseline's biggest gap) is flagged to the session that owns the matcher BEFORE the
  push, with the dry-run of realign / link on the new reads (rule 5).
- **Institution / campus split (owner ruling 2026-11-01, option 1) — the shape agreed with the Cockpit session:**
  `institution` = the institution's name only, as printed; new `campus` = the campus / branch as printed (`''`
  when none); the hostel / residential college / reporting venue goes in NEITHER (a separate optional
  `reporting_venue`, or dropped); `issuer` unchanged (the letterhead body — the matcher falls back to it). The
  matcher reads these in `offer_course_match.match_offer_course`, `letter_place` and `CampusReader`, fed from
  `pathway_engine.student_offer_check`; catalogue rows are per campus for polys, KK, IPG, IKBN/IKM/KKTM but one row
  for UiTM / UM / UMS, so the matcher must join institution + campus for multi-campus families — **the Cockpit
  session makes that matcher change, and S4 does not push until it is live** (else multi-campus pins drop). Send
  Cockpit the dry-run of realign / link / ticks on the new reads before the push.
- **NRIC (owner 2026-11-01: belongs to this arc).** Map of 187 answered offers: 157 print it, 30 print none - every
  blank a correct blank (UNIMAS 12/13, UPSI 7/7, UUM 4/4, UTHM 4/4, AIMST, i-CATS, Cyberjaya). Stored reads: 155/157
  right, 2 blank, 0 wrong. **Real gaps = NRIC only inside the reference line:** UPM 2/2 ("[NRIC]/UP...") and
  Netherlands Maritime University College 1/1 ("Our Reference .../[NRIC]") - S4 reads it from the reference line.
  Politeknik/KK and STPM put it in the reference too but always print it elsewhere. Owner rule (2026-11-01): only the
  OFFER pages count - an NRIC on a filled acceptance form later in the same PDF is not "printed by the letter".
- **Goal:** fix the biggest S2 failure kinds that come from the AI read's inputs and prompt.
- **Scope (expected, confirmed by S2):** an offer reader version stamped on every read (AI and deterministic);
  Gemini sees up to 3 pages, and the text layer beside the image for a digital PDF; prompt fixes for the top
  measured kinds (e.g. the reporting date, the NRIC); `vision.py`, `pdf_pages.py`, tests on synthetic letters.
- **Acceptance:** dev score up on the core fields, no field down; then ONE held-out run — the held-out score must
  rise and no family may fall; cost per letter within the S3 figure × 2.
- **Owner:** yes to the paid dev and held-out runs (≈ RM5–15 in all); adversarial review; deploy go. No live
  re-read yet (S7).
- **Built (phase A, 2026-11-01, branch `offer-read-s1`, not pushed):** `apps/scholarship/offer_reader.py`
  (`OFFER_READER_VERSION` 2.0.0, stored as `vision_fields.offer_reader_version` + `offer_reader_inputs` on
  every AI offer read); `extract_document_fields(…, 'offer_letter', …)` routes there, so every caller and
  test patch is unchanged. Gemini sees up to 3 pages, one PNG each (`pdf_pages.pdf_page_pngs`), at
  `MEDIA_RESOLUTION_HIGH`, plus the PDF text layer of those pages (`pdf_page_text`, TD-411's
  `usable_text_layer`). **The 258-token image was `media_resolution`:** a synthetic A4 page measured 258 tokens
  at the default and at medium, 3,354 at high. Schema: `campus`, `reporting_venue`, `programme_code` added;
  `institution` = the name only; `issuer` unchanged. Clean-up: a code left in `programme` moves to
  `programme_code`; an IC read whose digits are not 11–13 is blanked (soft "unread", never a wrong-person red).
  Genuineness (`MODEL_VERSION`) untouched — it reads the OCR text, not these fields.
- **Pilot (2026-11-01, S3's same 10 letters — 5 dev, 5 held-out; US$0.0615 = RM0.27, gemini-2.5-flash, no
  402/429).** Fully exact **9/10** new vs 1/10 current (S3) vs 1/10 stored. Right: institution 9 vs 4, programme
  10 vs 6, intake 10 vs 8; name, NRIC, reporting date 10 each (unchanged); campus 9 vs 6; offer date 9 vs 9;
  issuer 4 vs 4 (one fixed, one broke; not core). No core field down. **Cost** US$0.00615 a letter vs US$0.00344
  (×1.79, inside the ×2 bar): input 3,935 vs 1,053, output 281 vs 218, thinking 1,707 vs 1,033. Projected:
  dev 126 ≈ US$0.78 (RM3.4), held-out 90 ≈ US$0.55 (RM2.4). **Finding:** high media resolution
  ("pan and scan") applies only to a one-image call — both 2-page PDFs came back as 2 × 258 image tokens, so a
  multi-page letter is still seen at low detail per page (the text layer carried them here). Options for the
  lead: tile each page into crops, or page 1 alone at high + pages 2–3 in a second call. The 5 held-out pilot
  letters must not be used to tune the prompt.
- **Every reader of the offer fields (sprint-start 3b), and what the new shape does to it** — updated to the
  matcher session's live joins: `offer_course_match.letter_institution` = institution + " " + campus (main
  `d08283f1`) and `programme_line` = programme with `programme_code` put back where the code tier reads it (main
  `cddb4661`, api-01233-pwg), both read inside `student_offer_check`; `align_institution_to_catalogue` reads the
  first, `promotion.is_pathway_switch` reads the printed codes first. A read with neither key reads as before.
  Tests: `tests/test_offer_reader_doors.py` (one per door).

  | Door | Reads | Effect of S4's shape (with the live join) |
  |---|---|---|
  | `pathway_engine.student_offer_check` (feeds every door below) | all fields | `institution` and `programme` = the joined lines again; S4 adds nothing here (633-line limit) |
  | Name / IC statuses → `verdict_engine`, `verdict_ladder`, `doc_red_keys.person_red` (gate), `resolution` (Action Centre), `help_engine` (Cikgu Gopal), `offer_sync`, `offer_link`, the confirm, `backfill_*`, `audit_pathway_ticks` | `candidate_name`, `candidate_nric` | same fields and rules; a reference-line IC reads `match` where it read `unreadable`; a non-IC number is blanked → `unreadable`, never `mismatch`; another person's IC is still `mismatch` |
  | `vision.doc_student_verdict` (extraction-time name verdict) | `candidate_name` | unchanged |
  | Matcher `match_offer_course` / `pinned_match` (realign, link, confirm), `letter_place` / `CampusReader` (ticks, `institution_agreement`, `offer_contradicts_course_institution`) | programme line, joined line, issuer | multi-campus pins and the printed-code tier both survive through the joins (tests); one-row universities resolve from the name; a hostel line now goes to `reporting_venue`, so the university name agrees without the issuer standing in |
  | `offer_sync.institution_fill` / `sync_institution_from_catalogue` (sponsor-facing must-fill) | joined line, issuer | the multi-campus fill survives through the join (test) |
  | `services/confirmation` (confirm label, `_confirmed_place`) | programme, joined line, issuer | the label carries the campus again (joined) |
  | `offer_reporting_bonus` (reads `issuer`, `institution`, `campus` — live), `private_arm_letter` (via the joined line) | | a private-arm tell in the campus line is seen |
  | `offer_pathway_switch`, `poly_institution_from_live_offer`, `backfill_pre_u_track`, `promotion.is_pathway_switch` | programme / institution | no loss (names keep their town; the switch test reads the printed codes first, live) |
  | Check 2 `offer_reporting_date_unknown`; `sync_reporting_date_from_offer` | reporting_date | a commencement-only letter now reads no reporting date → Check 2 asks the student (owner a405); a blank never clears a stored date |
  | Cockpit display (`checklistsPathway.tsx`: `chk.institution`, `chk.issuer`) | joined line | shows institution + campus, as before |
  | Student-facing text (`help_engine`, the Documents card) | name / IC statuses | unchanged |
  | `reporting_venue` | — | read by nothing yet (kept for the record and for TD-447) |
- **Matcher inputs, stored vs S4, on the 10 pilot letters (eval caches only, keys and fields only):** name and
  IC inputs unchanged on all 10; programme, joined line or issuer changed on 9; a `programme_code` present on 5.
  The realign / link / ticks dry-run itself needs the live catalogue and applications (below).
- **Full run (2026-11-02, the lead; RM5.23; caches `*.fresh_s4.json` for all 216).** Fully exact: **held-out
  66/90** (stored 19, current 18) and **dev 90/126** (stored 31, current 35). Right on held-out, stored → current
  → new: institution 42 → 41 → 84; programme 66 → 64 → 86; intake 73 → 76 → 83; reporting date 87 → 84 → 87;
  name 85 → 86 → 85; NRIC 89 → 89 → 88; campus 47 → 47 → 76; offer date 86 → 84 → 88; issuer 19 → 23 → 12.
  Dev: institution 57 → 55 → 114; programme 86 → 91 → 111; intake 111 → 107 → 118; reporting date 124 → 123 →
  123; name 120 → 122 → 119; NRIC 124 → 123 → 122; campus 69 → 69 → 111; offer date 122 → 123 → 123; issuer
  43 → 43 → 39. **Not every field rose:** name and NRIC fell by 1–3 against the current reader on both sets
  (held-out: one NRIC now wrong; dev: one NRIC read where the letter prints none), and the issuer fell (not
  core). Against the local profiles (where the corpus holds one), ONE held-out letter's name now reads
  `mismatch` where it read `match` — a new wrong-person signal. These are for the adversarial review; the
  held-out letters are not used to tune the prompt.
- **Production dry run (prepared, run by the lead):** `eval/offer_s4_dry_run.py` — for every letter with an S4
  cache, realign / link / institution fill / the ticks on the stored fields and on the S4 fields (in memory), in
  ONE transaction set READ ONLY at the transaction level and always rolled back; non-read SQL, Storage, Gemini
  and the meter refused. Prints ids and outcomes only. Tests: `tests/test_offer_s4_dry_run.py`.
- **Adversarial review (2026-11-02) blocked deploy; fixed in reader 2.1.0** (`d0b3f34e`) and `c4165cd2`:
  H1 page 1 alone at high detail for every identity field, pages 2-3 in a second call only to fill a blank
  reporting date / intake; H2 + M1 + M4 the IC guard (`offer_ic.guard_nric`: the reference line an explicit,
  corroborate-only exception; well-formed shape; not-on-page blanked; text-layer backstop only for the
  profile's own IC) and the text layer fenced as data; M3 issuer = a name, never an office alone; L1 / L2 / L3 /
  L6. **More doors (M2), tested in `tests/test_offer_reader_doors_more.py`:** `course_start_year` /
  `started_before_cohort` → `award.proposed_award_amount`, `award.course_start_unknown`, `epf_evidence` (MONEY:
  a `not_offer_letter` document no longer dates the course — a behaviour change on main for stored reads too,
  **needs the owner**); `blockers.document_unreadable_blockers`; the reporting bonus (`verdict_ladder`,
  `promotion._offer_quality`); the IC shown to the student (`serializers` → `checklistsPathway.tsx`); the
  intake-year chip; `offer_pathway_switch` across versions (a hostel-only old line vs the new name + campus
  reads as a switch with the SAME programme — documented, not changed; it needs a second upload);
  `promotion.is_pathway_switch` reads codes across versions (L4).
- **2.1.0 pilot (S3's same 10 letters; US$0.0558 = RM0.25).** Fully exact **6/10** (S4 2.0.0: 9/10). Name,
  NRIC, institution (9), reporting date (10) unchanged; campus 10 (S4 9); programme 8 (S4 10: two PISMP reads
  gained a leading "PROGRAM"); intake 9 (S4 10: a roman "I" read as "1"); issuer 3 (S4 4: the M3 rule drops the
  office the answers keep, e.g. "Bahagian Pengambilan Pelajar, Universiti Teknologi MARA" → "Universiti
  Teknologi MARA"). Both 2-page letters now send page 1 at 3,354 image tokens (was 258); no letter needed the
  later-pages call. Cost US$0.00558 a letter vs US$0.00615 (input 4,522 vs 3,935; output 305 vs 281; thinking
  1,384 vs 1,707). Projected re-run: dev 126 ≈ US$0.70, held-out 90 ≈ US$0.50 — ≈ US$1.2–1.35 (RM5.3–6) with the
  later-pages calls the full set will need. **Before that re-run** the issuer rule should keep the office WITH
  its institution ("never an office ALONE"), and the PISMP rule should say "without a PROGRAM wrapper"
  (dev evidence only; the held-out pilot letters are not used to tune).
- **Owner rulings 2026-11-02.** (1) *Superseded the same day: taken out of S4 and deferred to the money sprint below; S4 ships money exactly as main.* A document scored `not_offer_letter` never sets `course_start_year`, so it
  never feeds `award.proposed_award_amount`, `award.course_start_unknown` or `epf_evidence` (`docs/decisions.md`;
  stored reads too; the live reach is measured by the dry run, `not_offer_dated`). (2) The full re-run is
  approved, about RM6–7, hard cap RM9 for the tuning pilots and the run together.
- **Reader 2.2.0** — wording tuned on DEV letters only (5-letter dev pilot, US$0.0297): issuer keeps an office
  printed WITH its institution or ministry, never an office alone; PISMP programme without a "PROGRAM" wrapper;
  a programme stops before a faculty line; a Roman session numeral stays Roman.
- **Reader 2.2.0, full run (2026-11-02; 216 letters, `.fresh_s4c.json`; US$1.384 = RM6.09, plus the RM0.13 dev
  pilot = RM6.22 of the RM9 cap; US$0.00641 a letter; no 402/429; 1 letter unreadable — the not-a-PDF file).**
  Fully exact **held-out 63/90** (stored 19, S4 2.0.0 66) and **dev 91/126** (stored 31, S4 90). Right, stored →
  2.2.0 — held-out: name 85 → 87, NRIC 89 → 85, institution 42 → 81, programme 66 → 86, intake 73 → 81,
  reporting date 87 → 87, offer date 86 → 87, issuer 19 → 50, campus 47 → 80; dev: name 120 → 122, NRIC
  124 → 113, institution 57 → 116, programme 86 → 121, intake 111 → 117, reporting date 124 → 122, offer date
  122 → 123, issuer 43 → 46, campus 69 → 111.
- **Name / NRIC per letter vs stored.** Name: none worse (held-out +2, dev +2). NRIC: **16 letters worse, all
  exact → BLANK, none wrong** — held-out a184, a289, a365, a413; dev a102, a113, a121, a128, a137, a16, a181,
  a408, a4, a87, a8, a93. Downstream: each reads `unreadable` — a red Name·IC chip that the verdict ladder counts,
  never a wrong-person block (`person_red`), never a realign / link refusal (those refuse on `mismatch`). Why: 10
  are `blanked_uncorroborated` — the model gave a source other than "label" and the CORPUS holds no profile IC for
  them (the fetch gap, §2), so the guard could not corroborate; live, every application has its profile IC, so
  those that are the student's own would read `match`. 6 are a blank read (no IC returned; one has a profile
  and read `match` before). So the true loss live is likely ~6, and the source labelling needs a look first.
- **Reader 2.3.0 — the IC prompt only (owner GO 2026-11-02; guard and sources unchanged).** Look for the IC
  on page 1 including an unlabelled copy in the address block (source "other", still corroborate-only); when it
  is printed in the reference line and elsewhere, report the copy outside it. Dev-only 12-letter pilot
  US$0.0736: the model's own IC read equals the printed IC on 12/12. Full run (`.fresh_s4d.json`) US$1.3805;
  round total US$1.454 (cap US$1.80). Fully exact **held-out 63/90** (2.2.0: 63), **dev 89/126** (2.2.0: 91).
  Right, 2.2.0 → 2.3.0 — held-out: name 87 → 87, NRIC 85 → 84 (eval-time: no profile in the corpus), institution
  81 → 85, programme 86 → 84, intake 81 → 81, reporting date 87 → 88, offer date 87 → 87, issuer 50 → 49, campus
  80 → 78; dev: name 122 → 122, NRIC 113 → 115, institution 116 → 115, programme 121 → 118, intake 117 → 118,
  reporting date 122 → 123, offer date 123 → 125, issuer 46 → 46, campus 111 → 109. 40 per-letter field drops
  against 2.2.0 (issuer 17, campus 9, programme 5, institution 5, intake 3, name 1 — a121, NRIC 1 — a329 at eval
  time, reporting date 1, offer date 1); the list is in the S4 report. Run-to-run variance is of this order.
- **Production dry run on 2.3.0, the guard RE-APPLIED with the production profile IC** (`ic_guard reguarded`
  on 215, 1 letter unreadable): IC ticks **3 unreadable → match, 0 match → unreadable, 0 → mismatch**. All 16
  earlier IC losses read `kept_corroborated` / `kept_profile` live. Name ticks: 2 changes, both improvements
  (mismatch → match, mismatch → partial). Other ticks: reporting bonus False → True 21, pathway unknown → match
  3, chosen institution unknown → match 3 and unknown → clash 1 (a305), intake-year status 5. A live re-read
  would realign 3 (a239, a337, a362 — Bumiputera-only offers resolving) and link 2 (a278, a279); 22 letters
  still date the course from a not_offer_letter document before the owner's ruling ships (24 on stored reads).
- **Before the push:** the dry run's list goes to the matcher session (rule 5); adversarial review (identity:
  the IC guard, the reference-line IC, and the name / NRIC letters above); the owner's go.

### Money sprint (after S4; owner 2026-11-02) — the not_offer_letter ruling and the start-year amount
- **Why:** taken OUT of S4 (owner "1", 2026-11-02): S4 ships the reader only, money exactly as main.
- **Scope:** the deferred ruling (a `not_offer_letter` document never dates the course) together with TD-465:
  `course_start_unknown` has no caller, so a `None` start year pays STPM RM3,000 instead of RM1,000; QC and
  payments read `reporting_date` directly. Owner ruling: the reporting date answers only "already in college,
  or starting soon?"; the reviewer sets the amount from the time left (one year RM2,000, six months RM1,000); a
  start year never sets the amount by itself. App 329's 2024 from its own reporting date is correct.
- **Tools ready:** the money-reach check (old vs new course-start year, `course_start_unknown`, award amount per
  live application, read-only); the S4 branch's reverted change (`course_start.py`, commit `90fd9234`) as a
  starting point.

### S5 — Reader round 2: the Exact read covers more letters (medium, ~8 h; production code) — ✅ DONE, LIVE 2026-11-03 (main ae443f45; api-01240-cg2)
- **Result:** `PARSER_VERSION` 2.0.0 + `offer_exact.py` (the one entry point; the IC guard on the Exact path).
  Corpus locks 51 -> 96 of 287; 0 WRONG and 0 control locks on dev (86 EXACT) and held-out (10 EXACT; held-out run
  3 times — see the retrospective); pipeline fully exact dev 89 -> 92 / 126, held-out 63 -> 66 / 90; the 21 at-risk
  stored Exact reads 21 / 21 re-lock; dev real known-format 16 / 17. Production dry run: 87 live locks, 0 new red,
  0 intake-year change, 6 reporting dates changed (all matching the owner's answers). Two adversarial review rounds
  (2 High, 2 Medium, all fixed). Retrospective `docs/retrospectives/retrospective-2026-11-03-offer-exact-read-s5.md`;
  owner ruling decisions.md 2026-11-03 (the reporting date is the date only); TD-473 (Cockpit), TD-474.
  **S7 is now safe** for the 21 at-risk reads: its list = the 6 reporting-date letters + every live letter whose
  Exact read changed.
- **Goal:** more letters read by the free, deterministic reader, with no new errors.
- **Scope:** `offer_parse.py` — FIRST the 48 known-format letters (STPM 9, matriculation 17, polytechnic 22; 27 PDF,
  21 photo; Sabah 22, flagship 26) whose stored read is the AI reader's: find why the fixed-format reader did not
  lock them (a photo with no OCR text, a layout variant) and close that gap (owner steer 2026-11-01). Then the
  government families where the dev set shows Gemini fallback or a wrong field;
  a text-layer reader for any university template held by ≥5 letters (data-gated; skip if none). `PARSER_VERSION`
  bump; `eval/offer_parse_check.py` (exact / fallback / WRONG per letter, like `stpm_parse_check.py`).
- **Acceptance:** 0 WRONG on dev and held-out; lock rate up; held-out exact score not down.
- **Owner:** adversarial review (identity fields); deploy go.

#### Plan (2026-11-03)
Phase 1 (measure + plan) on `offer-read-s1` = origin/main `53f1d289`; free (cached text, no Gemini, no
Vision, no database). Keys and counts only. Builder: s5-builder. **Nothing built yet — owner approves first.**

**Baselines (measured 2026-11-03).**
- Tests: `python -m pytest apps/scholarship -q -p no:cacheprovider -n auto` (worktree, development
  settings): **9899 passed, 3 skipped, 5152 subtests passed** (26 min).
- Today's free readers on the cached text (`offer_replay.py`, PARSER 1.3.0): **51 of 287 lock** (STPM 13,
  matriculation 18, polytechnic 20), 235 fall back, 1 no text. Of the 71 stored Exact reads, 50 re-lock and
  **21 would fall back**. Locks among ANSWERED letters: **dev 1 of 126 (0 WRONG), held-out 0 of 90.**
- Production pipeline score (an Exact lock merged over the 2.3.0 AI read, else the 2.3.0 read): fully exact
  **dev 89/126, held-out 63/90** — S5 must not lower either.
- AI reader 2.3.0 on the fixed formats (all answered letters, portal pages and not-offers included): dev
  STPM 3/6 fully exact, matriculation 9/10, polytechnic 3/7; held-out 3/5, 4/5, 2/5. The Exact read has room.

**Why "48" and "38" differ.** 48 = family from the stored genuineness fingerprint (`doc_seen`); 38 = the
answer's family (the scorer's). 14 of the 48 are NOT fixed-format letters (private colleges / universities /
IKM / IKBN that the fingerprint calls polytechnic, matriculation or STPM — an S6 input) and 4 of the 38 are
fixed-format portal pages the fingerprint calls university. Of the 38: **11 must not lock** (portal pages 6,
not an offer 5), **1 locks today, 26 are real letters to close** (dev 17 incl. the lock: STPM 3, matric 9,
poly 5; held-out 10: STPM 2, matric 4, poly 4).

**Failure classes — the 26 real known-format letters that do not lock (keys in the scratch table; reason →
count → fix):**
| Class | n | Families / input | Fix (free) |
|---|---|---|---|
| A. STPM six-label block: section 2 prints 2.1-2.6 (Bidang, Pusat, Tarikh Lapor Diri, **Masa Lapor Diri, Dokumen diperlukan, Pakaian**); the parser knows 3, so the values start one block too early and "2.4." / "Masa Lapor Diri" land in stream / institution → the clause-number guard trips | 5 | STPM, all photos | label set = all six numbered labels; values paired after the LAST numbered label |
| B. Matriculation glued text layer: the whole letter on one line ("…K/P : <IC>NO MATRIK…", "Jurusan: X Tempoh Pengajian: …"); `\b` cannot see the IC, no label-only lines exist | 7 | matric, text PDF | glued-label reader: split on the known label sequence (as STPM #117 does) |
| C. Name not found: no parentage marker (a one-word name, a Chinese or East-Malaysian name, "BTE"), or the name sits below line 20 (phone status-bar noise) | 10 | matric 4, poly 6 (photo / scan / text PDF) | matric: the line directly above "K/P:"; poly: the "NAME (IC)" line without the marker; strict name shape |
| D. Polytechnic session numeral ("SESI 1:2026/2027") — `SESI\D{0,8}` cannot pass a digit | 3 | poly photos (1 also in C) | intake regex allows I / II / 1 / 2, output "SESI I : 2026/2027" (letters print Roman) |
| E. Block split or label variant: Vision splits the matric label block into two runs; poly "Tarikh Daftar" (no "dan Masa") is not a known label, so the block shifts | 2 | matric scan 1, poly photo 1 | pair alternating label-run / value-run blocks; add "Tarikh Daftar" / "Tarikh dan Masa Daftar" to the poly labels |
| Total | 26 | 5 + 7 + 10 + 2 (D only) + 2 = 26 unique | every class has dev examples; held-out text was opened only to confirm its class, never to tune |

**The 21 stored Exact reads that would now fall back** (S7 regression risk — a live re-read today sends them to
Gemini and loses "Exact"): 15 STPM photos = class A (the #47 clause-number guard of 2026-07-17 and the
date/money guard of 2026-09-10 came AFTER these were stored in June-July; 2 of the 15 stored reads still carry
the corrupt slot today); 1 polytechnic photo = class E (its stored read holds a date in institution and
programme); 5 matriculation text PDFs = class B (stored June-July, before the PDF library was pinned on
2026-09-18; today's pinned pypdf 5.9.0 returns the glued layer). All 21 are fixed by A, B and E. **S7 must
not re-read these before S5 ships.** Live stored Exact reads with a date / clause / ringgit in a text slot: 6.

**Wrong VALUES in today's locks (no answers exist for them — measured by rule):** polytechnic `offer_date` =
the registration date on 16 of 20 locks ("Tarikh dan Masa Daftar" matches the "Tarikh" offer-date rule; shown
in the cockpit); matriculation reporting date = the LAST day of a range ("8 HINGGA 9 JUN") on 2 locks
(the answers take the first day; feeds `sync_reporting_date_from_offer`). Convention gaps the scorer counts
as wrong: polytechnic programme keeps its code (18; S4's shape puts it in `programme_code`), polytechnic
intake drops the session numeral (14), STPM intake drops "Semester 1 Tahun" (13). Each keeps the year the
money path reads (`intake_year` = the first 20xx).

**What needs paid OCR: nothing.** Every letter in the corpus has text (S2's Vision capture); production
already runs Vision on every photo / scan before the parser (`ocr_document_full`, ~US$0.0015 a page), so a
photo never reaches the parser with no text. The 1 no-text letter is the not-a-PDF file. Each new lock
SAVES a Gemini call (≈US$0.0064 at 2.3.0).

**Then (government families / university templates).** Data gate: UMS has 64 letters (41 text PDFs, 20 dev),
UiTM 11 text PDFs, UM 6; but 2.3.0 is already fully exact on UMS dev 30/30 and UM dev 6/6 — a UMS reader would
only save ≈US$0.26 per corpus pass at new identity risk. PISMP has 5 text PDFs (3 dev) — under the gate.
**Recommendation: no university or PISMP reader in S5**; record UMS as the one candidate if cost ever
matters.

**Lessons and decisions that bind S5, and how the plan meets each.**
- Decision 2026-09-10 (a shifted block defers to Gemini; guard at the single exit, all three families; "revisit
  if the deferral rate climbs: per-label recovery written ONCE, shared") → S5 IS that revisit: one shared block
  reader, the exit guards untouched.
- Lesson "a guard in a per-family helper is not a guard" (#125 / #142) → new shape checks go at the exit or in
  the shared reader, never in one family's helper.
- Decision 2026-07-10 + lesson "merge-preserve before overwriting a field set" → reporting / offer date keep
  merge-preserve; the identity and shape keys the parser owns are written whole (step 4), so no stale AI value
  survives under an "Exact" chip.
- Decision 2026-09-10 (the matric "Program Matrikulasi (X)" bracket feeds five call sites; retire it only in
  its own measured change) → kept as is.
- Lessons on OCR-read identifiers (#36: never exact-compare a noisy IC; a wrong IC is worse than a blank) and
  S4's `offer_ic` rules → the Exact IC goes through `guard_nric`; a blanked IC defers instead of merging.
- Lesson "validate a heuristic on real documents, not only synthetic twins" + "validate on held-out" → the real
  corpus check (step 1) gates the build; held-out run once, at the end.
- Lesson "a parser fix does not recover the rows it already read" → the S7 list must include every live
  letter whose Exact read changes (the 21, the 2 range dates, the 16 poly offer dates, the code / intake
  convention moves), not only today's AI reads.
- Lesson "ask where the corrections go — version what is scored" + roadmap rule 3 → `PARSER_VERSION` 2.0.0,
  and the eval prints it.
- Rule 1 / `test_no_gitignored_corpus.py` → tests use synthetic twins; the check prints keys and field names.
- Rule 2 (never re-extract from a local checkout) → nothing in S5 writes to production.

**Steps.**
1. `eval/offer_parse_check.py` (new, hand-run, like `stpm_parse_check.py`): feeds each letter the text
   production feeds (`offer_replay.production_text`); per letter EXACT / FALLBACK / **WRONG** (a lock with a core
   field — name, NRIC, institution, programme/stream, intake, reporting date — that differs from the answer) /
   **CONTROL-LOCKED** (a lock on a letter whose answer family is not STPM / matric / poly, or whose
   `is_offer_letter` is portal_page / not_offer); by split, family, input kind; offer date scored, not core;
   `--split dev|heldout|all`; exit 1 on any WRONG or control lock; prints keys and field names only. Tests:
   `tests/test_offer_parse_check.py` (synthetic twins).
2. **Answers for the 71 stored Exact reads (dev; free, D1 route: drafted from the image before looking at the
   stored read, owner spot-check ~10).** Today no answer exists for any of them, so "0 WRONG on dev" could not
   be measured on the letters the parser already locks. All 71 are dev (the held-out was drawn from AI reads).
3. `offer_parse.py` — the fixes A-E, written ONCE in a shared block reader (the 2026-09-10 decision's
   "revisit if": per-label recovery shared across the three families), the single-exit guards kept; plus the
   two value bugs (offer date only from a "Tarikh :" line that is not "Tarikh dan Masa Daftar" / "Tarikh
   Daftar" / "Tarikh Lapor Diri", numeric dates accepted; a range's FIRST day) and the conventions (programme
   code → `programme_code`; intake with its session / semester words). The offer-title phrase becomes a lock
   requirement (portal pages and slips never lock). `PARSER_VERSION` 1.3.0 → **2.0.0** (output shape changes:
   `programme_code`, intake wording, `candidate_nric_source`). The matriculation `programme` bracket stays
   (decision 2026-09-10, five call sites).
4. **The IC guard on the Exact path** (new `offer_exact.py`, ≈60 lines): the parser labels its IC source —
   `label` for "No. Kad Pengenalan:", "K/P:" and the poly "NAME (IC)" line, `other` for the first-IC-anywhere
   fallback — and `offer_ic.guard_nric` runs on it with the profile IC and the page-1 text, exactly as on the
   AI path. **If the guard blanks the IC the letter is NOT locked** (→ the AI read, which has its own guard):
   a blank IC merged over a prior read would keep the prior AI number. Identity fields are read from page 1
   only (owner rule 2026-11-01). The merge moves here too: the parser OWNS name, IC + source, programme,
   `programme_code`, institution, `campus` (always ''), stream, intake (written even when blank, so a stale
   AI campus / code / IC source cannot survive under an Exact chip); reporting date and offer date keep the
   merge-preserve rule (lesson 2026-07-10). `vision.py` calls one function instead of its 13-line block.
5. Dev tuning loop: `offer_parse_check.py --split dev` + `offer_replay.py` until 0 WRONG / 0 control locks;
   then ONE held-out run for the final numbers. Synthetic twins for every class in `tests/test_offer_parser.py`
   (and a new `tests/test_offer_parse_glued.py` if that file passes ~600 lines).
6. Doors re-checked (below); adversarial review (identity); CHANGELOG, README section, decisions entry.

**Files.** `offer_parse.py` (365 → ≤ 560; if it would pass 560 the family readers move verbatim to a new
`offer_parse_families.py` first, a moves-only step), `offer_exact.py` (new), `offer_ic.py` (unchanged unless a
`source` value is needed), `vision.py` (offer branch only; **net lines ≤ 0**, `_run_field_extraction_impl`
budget 306 not grown), `eval/offer_parse_check.py` (new), `eval/offer_replay.py` (call the same entry point;
reason rules updated), `eval/README.md`, tests above. Budgets checked: `vision.py` is in `oversize_files`
(2321) and `long_functions` (`_run_field_extraction_impl` 306) — both must not grow (`code-health.md`: vision.py
is hot#1, 28.1); `offer_parse.py`, `offer_ic.py`, `offer_reader.py`, the eval files are in no ledger and must
stay under 600 lines / functions under 150. `pathway_engine.py` (613, ledger) is NOT touched.

**Doors (sprint-start 3b) — a lock sets name, IC, institution, programme, stream, intake, reporting date with
no model.** The parser's output enters through ONE door, `vision._run_field_extraction_impl` (upload, Re-run,
sweep, `reextract_documents`, `release-decisions`), and `offer_replay` (eval). Readers of the stored fields:
- **Identity:** `doc_student_verdict` (name, at extraction); `pathway_engine.student_offer_check` →
  `_name_status` / `_ic_status` → `verdict_engine`, `verdict_ladder` (+ `_OFFER_CHIP_RED`),
  `doc_red_keys.person_red` (wrong-person gate), `resolution` (Action Centre), `help_engine`, `blockers`,
  the IC shown to the student (`serializers` → `checklistsPathway.tsx`). Today the Exact IC skips
  `guard_nric`; step 4 adds it, so a deterministic IC can produce `match` or blank → AI, never a new
  `mismatch` from an unlabelled or not-on-page number. A well-formed labelled IC of another person still
  reads `mismatch` (that IS a wrong-person letter).
- **Pathway / picks:** `offer_course_match` (`letter_institution` = institution + campus, `programme_line` =
  programme + `programme_code`, `match_offer_course`, `pinned_match`, `letter_place`, `CampusReader`),
  `offer_pathway` (`parse_matric_track` reads the bracket), `offer_sync` (autofill, Bumi realign,
  `institution_fill`), `offer_link`, `services/confirmation`, `promotion.is_pathway_switch` (codes first),
  `offer_pathway_switch`, `poly_institution_from_live_offer`, `backfill_pre_u_track`. Step 3 moves the poly code
  into `programme_code` — the S4 joins put it back where the matcher reads it; to be proved by the S4 dry-run
  tool on the changed letters before the push (rule 5), and sent to the matcher session.
- **Money:** `intake` → `intake_year` → `course_start_year` / `started_before_cohort` → `award`,
  `epf_evidence`; `reporting_date` → `sync_reporting_date_from_offer`, Check 2 `offer_reporting_date_unknown`,
  `offer_reporting_bonus` / `verdict_ladder` / `promotion._offer_quality`. Every intake keeps its first 20xx;
  2 matric reporting dates move one day earlier (range first day) — listed for the owner.
- **The "Exact" chip:** `vision_fields.capture == 'deterministic'` (+ `offer_reader_inputs.reader`) →
  `DocumentsDrawer.tsx` (cockpit badge), `services/outage.gemini_read_outcome` (the Gemini health window and System health light skip Exact reads —
more locks = fewer Gemini samples),
  `reextract_documents` (prints it), `offer_read_check` / `offer_replay` (eval). `_offer_parser_version` is read
  by nothing live (traceability only).
- Display: `checklistsPathway.tsx` shows `offer_date` (fixes the 16 wrong poly dates).

**Acceptance numbers.** (1) 0 WRONG and 0 control locks on dev (126 answered + the 71 new answers) and on
held-out (90). (2) Lock rate: corpus 51 → **≥ 85 of 287**; the 21 at-risk reads re-lock ≥ 20; dev real
known-format ≥ 14 of 17. (3) Pipeline fully exact: dev ≥ 89/126, held-out ≥ 63/90, no core field down on
held-out. (4) The scholarship suite green, budgets unchanged or tighter.

**Risks.** (a) Relaxing the name anchor can read an address line as a name → a false `name_mismatch` (a
yellow/red chip, not a block); mitigated by the strict shape, the line-above-K/P anchor, and the 71 + 27 answer
checks; adversarial review. (b) Glued-text splitting is new parsing on the path that broke twice (#125, #142);
mitigated by the single-exit shape guards and the control set. (c) The poly code move changes what
`programme` holds for the matcher on live re-reads — the dry run before the push. (d) The held-out has 10
fixed-format letters only, so its lock number is small; dev must carry the evidence. (e) Live letters with
other layouts (a 2027 template) — conservative None remains the default. (f) Labelling 71 letters costs
~2-3 h of agent time and ~20 min of the owner's.

### S6 — Genuineness fixes, only if the answers prove a wrong call (medium, ~6 h; conditional) — BUILT 2026-11-03 on offer-read-s1 (not pushed)
- **Built (owner go 2026-11-03, Q1 / Q2 / the confirmation default — decisions.md):** three moves-only splits
  (`pathway_match.py`, `offer_signatures.py`, `offerFacts.ts`); `offer_rulings.py` + `MODEL_VERSION` 1.23.0 —
  `offer_genuineness_check.py` dev 197 / 197, held-out 90 / 90; the gate blocks only not_offer_letter; the ladder
  counts only Name / IC mismatch (`VERDICT_ENGINE_VERSION` 2026-11-03.1); chips to the owner's table; student
  notes en / ms / ta; confirmation letters never write a pick; `offer_s4_dry_run.py --s6` for the lead (GO /
  STOP). TD-481 (page-1-only scoring). See CHANGELOG. Stored statuses move only at S7's re-score.
- **Adversarial review (2026-11-03): 7 High, 2 Medium, 4 Low — all fixed in new commits, each with a synthetic
  regression (`tests/test_offer_s6_review.py`).** Dev stays 197 / 197 with exactly the 14 ruled moves.
  - Q2's genuine is narrower: an INSTITUTE (IKBN / IKTBN / IKM / KKTM / Kolej MARA / Kolej Profesional MARA / ILP /
    ADTEC / ILJTM) must be named — an agency (MARA, TVETMARA, JTM, JPK, the ministry, ILKBS) alone keeps the 1.8.0
    path; no private sign; below the suspect floor the BODY must name the candidate and the institute again (the
    typed fake stays a fail; app 329's letter, p 0.11, still qualifies). Sponsor words + PENAJAAN / DIBIAYAI /
    PEMBIAYAAN / BIASISWA; KUPTM / UPTM are MARA-owned private. The TVET slip test reads the letterhead only.
  - Confirmations: the issuer's own public mark (polytechnic: the ministry line; Form 6: the ministry / SMK /
    Kolej Tingkatan Enam; UMS: its letterhead), a student / programme line, a score floor (0.10; real ones 0.13-0.30),
    and no SWASTA / PERSENDIRIAN / Sdn Bhd / IPTS / MQA sign.
  - Printouts: portal-only furniture (never TAHNIAH / BERJAYA, never URL chrome) and never over a private sign.
  - The Sdn Bhd exemption needs the ministry line BEFORE the first "Sdn Bhd" (the review proposed "not on the
    letterhead"; the corpus polytechnic letter carries a company sign at char 263 of its letterhead, after the
    ministry line at 0, so the order test keeps it while the review's "ABC COLLEGE SDN BHD … with JPPKK" is vetoed).
  - Rule 2 / 7 fails a suspect-band offer only on POSITIVE private evidence (Sdn Bhd / Bhd / Swasta /
    Persendirian / IPTS / MQA / KPT-JPT, or a named MARA-owned private college: KPTM / KUPTM / UPTM / UniKL) or a CONDITIONAL offer from a letterhead naming no public body; Kolej
    Komuniti / Matrikulasi / Vokasional / ASWARA / ILKKM count as public words.
  - **Doors added:** (a) the officer's own offer request is NOT auto-closed by an offer the rulings (not a
    fingerprinted family) made genuine — a `tvet_*` or `confirmation_*` upload (`offer_issuers.officer_must_close`),
    as NOT CHECKED was; system / Check 2 requests close as before; (b) a confirmation letter gets no pathway hearing
    (`offer_hearing_ok`) and `services.confirmation.confirm_pathway` refuses one — it never writes the pick.
  - **M8, answered.** The production dry run is right: S6 newly blocks only an OPEN application whose stored call is
    not_offer_letter AND whose old band was Probable+ (only the date bonus did that); every other stored
    not_offer_letter on an open application was already blocked, and a submitted one (app 329) is never re-blocked
    (the gate reads `profile_completed_at`). The dry run now STOPs on a new block whose re-score would lift the fail
    and lists `blocked_on_a_stale_call` (blocked before and after, the re-score would lift it). **Proposal (not built):**
    ship S7's genuineness-only re-score of that list in the same release as S6 (text-layer PDFs free, photos one
    Vision page each), so no student waits on a stale call.
- **Second review (2026-11-03): M9 and H7 closed; H1-H4, H6 and an H5 follow-on fixed STRUCTURALLY** (owner: keep
  green, no hedging cap — decisions.md S6 item 4; `tests/test_offer_s6_review2.py`, the reviewer's own probes).
  - Text is NFKC-normalised (full-width letters are letters). The FIRST institution a page names is its issuer
    (`offer_rulings._first_institution`): a college / academy / tuition centre named before the TVET institute (or
    before a confirmation's public institution) is another institution — this closes the "accredited by JPK",
    "in collaboration with", "usahasama", "Pinjaman / Funded / Scholarship" tie-ups under a private letterhead.
  - A TVET genuine needs a real letter's STRUCTURE in a letter's order (`_letter_structure`): a reference line,
    a dated line, a candidate label, an offer title and a closing / signatory block after it, and no padding
    (unique lines ≥ 60 %, no token above 25 %). Order rather than "near the top": the held-out IKM photo holds two
    letters side by side (its offer title is line 60 of 107, below the other letter's closing) — **this was read
    off a held-out letter while shaping the rule, so held-out is not untouched for this rule; said so here and in
    the report.**
  - Confirmations: the public institution named first, its public mark (KPT / JPPKK for a polytechnic;
    `KEMENTERIAN PENDIDIKAN MALAYSIA`, not the bare `KEMENTERIAN PENDIDIKAN`, for Form 6), no private sign.
  - Printouts never lift a page with a private letterhead (`private_college_reason`).
  - The Sdn Bhd exemption: EVERY "Sdn Bhd" / "Sendirian Berhad" line must be incidental — a payment / bank /
    vendor line, or the ADDRESSEE's address below the letter's reference / date (the corpus polytechnic letter's
    company is the student's estate address) — with no institution word on it or the line before; "Sendirian
    Berhad" joins the private-arm phrases. Positive private evidence is read per line and never on a payment /
    address line; payment lines are not part of the letterhead; LEMBAGA / PERBADANAN / Kolej Kejururawatan are
    public words; sponsor words + KERJASAMA / USAHASAMA / COLLABORATION / PINJAMAN / FUNDED / SCHOLARSHIP; GMI is
    MARA-owned private (owner: the programme-subsidy test).
  - LEARNABLE: every lift's reason carries `[S6 ruling: <tag>]`; the check counts them (dev: tvet_offer 1,
    confirmation 2, printout 2, private_offer 1).
  - Dry run: an app with no corpus re-score is its own `no_rescore` bucket; the re-score map is keyed by
    DOCUMENT; every re-score lifted by a ruling is listed (`lifted_by_a_ruling`). A stale `pathway_confirm` on a
    confirmation letter is logged.
- **Third review (2026-11-03): H2 closed; the rest fixed** (`tests/test_offer_s6_review3.py`, the reviewer's probes).
  - The letterhead (the lines above the letter's first reference / date / title / candidate line / salutation)
    may name ONLY the allowed bodies — no other organisation noun once the allowed names are taken out (street
    names, web / e-mail / phone lines excepted), no partner wording (`_clean_letterhead`). A strict per-line
    allowlist was measured and rejected: on the real letters the "letterhead" region also holds the town / state,
    the ministry's English name, a building, crest noise and — on the IKBN photos — the addressee block, so an
    allowlist fails all eight real ruling letters; the noun test fails none.
  - The structure test now also asks for a candidate label WITH a value, an IC number, a course line, a reporting
    line (offers) and 12+ lines (offers); below the floor the body names the institute again. Measured on the three
    real TVET letters: every requirement costs nothing (107 / 60 / 60 lines, an IC, a labelled name, a course and a
    reporting line on each; the IKM photo names its institute in the body). The UMS text layers are one glued line,
    so a date's left edge is "not a digit" and a glued line's "RUJ" counts as the reference.
  - THE SAFETY RULE: a closed-list public body, no positive private evidence, one rule missed → suspect below the
    floor (NOT CHECKED in the suspect band, as 1.8.0) — never a fail. Another organisation named first → a fail by
    its private reason. Bank / insurer / co-operative lines excuse a "Berhad"; a fee "kepada X Sdn Bhd" does not;
    an address excuses a "Sdn Bhd" only in the candidate block. Akademi Binaan Malaysia (ABM) is public. A UniKL /
    KPTM / GMI LETTERHEAD fails; a mention in the body does not. UMS PPPL is a private wing (decisions S6 item 6).
  - Performance: `Counter` for the token share; 40 000 lines under one second (a timing test).
  - Dry run: `newly_blocked_no_rescore` vs `blocked_before_and_after_no_rescore`; `moves_by_ruling` lists every
    re-score move.
  - **Held-out, reported honestly: the round's final run read 89 / 90** — app 329's IKM photo fell to suspect
    (`tvet_unverified`) because its offer title spells out "Technical and Vocational Education and Training" and
    the new organisation nouns read EDUCATION / TRAINING as another institution named before IKM. Fixed by class
    (the spelt-out sector phrase names no institution; a training centre still does), dev unchanged, then a SECOND
    held-out run: 90 / 90. That letter has now steered two rules; held-out is not untouched for them.
- **Fourth review (2026-11-03): N1-N8 fixed** (`tests/test_offer_s6_review4.py`, the reviewer's probes).
  - Confirmations need 12+ lines — measured: the corpus's real ones hold 42 / 58 / 64 lines, and the two UMS glued
    text layers 15 / 16 segments once split on the labels they run together (`_unglued`) — and the candidate's
    labelled name and IC on lines of their own, never inside the title line.
  - Letterhead tie-up words: + KERJASAMA / USAHASAMA / COLLABORATION / ACCREDITED / DIIKTIRAF / ASSOCIATION /
    MEMBER. Organisation nouns match by STEM (CENTR…, ENTERPRIS…, EDU…, SERVIC…, CORP…, CONSULT…, plurals) + MAKTAB,
    INSTITUTION, PUSAT PENDIDIKAN / BAHASA, LTD / LIMITED / INC, PERSATUAN / PERTUBUHAN, ACADEMIC, VENTURES, TECH,
    KAMPUS, YAYASAN (TECH / KAMPUS / YAYASAN measured on dev: no letter moves). INSTITUSI is NOT one — real letters
    print it as a form label ("Institusi : Politeknik …"; it moved a dev IKBN letter when tried).
  - The letterhead skips a reference / date line instead of stopping at it; a "Sdn Bhd" on it still vetoes; a TVET
    letter now gets the incidental-company excuse (supplier, insurer, sponsor, the student's estate address in the
    candidate block) the ministry families had (`tvet_letter_naming_a_company`).
  - "TVET" spelt out is neutral only on a TITLE line, never on the letterhead.
  - A glued reference is "RUJ" not preceded by a letter (the UMS layers glue it to a phone number; "dirujuk" is
    not one); TAMAN / BANDAR / SEKSYEN / PRESINT street names and ISO / SIRIM lines name no organisation; a web
    tail is read even when OCR spaces it ("EDU M Y").
- **Fifth review (2026-11-03): the remaining Highs were wrong blocks of real public letters — fixed as a CLASS.**
  - **THE SAFETY RULE AT ONE EXIT** (`offer_rulings._safety_exit`; every `ruled_offer` result passes it): a page a
    ruling engaged on (a closed-list TVET body, or a confirmation-of-studies title) whose FIRST institution is an
    allowed public body (the TVET list, a polytechnic, UMS, a Form-6 / KPM school, a ministry / department) and
    which shows NO positive private evidence (a private sign off the excused lines, a private MARA-owned name on
    the letterhead, partner wording, a fee to a company) may read genuine or suspect — never `not_offer_letter`; a
    missed rule then reads `tvet_unverified` / `confirmation_unverified`. One test asserts it for every ruled kind
    (`tests/test_offer_s6_review5.py`).
  - A university's / institute's OWN unit (faculty, division, centre for …, unit, student services, campus)
    is not another organisation; English public names (Ministry / Department / Government; ADTEC, ILP, IKBN, IKM,
    KKTM in English; the ministry marks of a polytechnic / Form-6 confirmation in English).
  - The addressee block (a patronymic name line then a postcode, below the date) ends the letterhead and excuses a
    company name inside it unless an institution word sits beside it; a private name sharing a line with "Ruj" /
    the date is read (the part before them); partner words on any letterhead line, whole.
  - A glued text layer is split only when it holds 4+ kinds of label and little single-letter filler; a company
    excuse fails when its two-word name is on the letterhead, or a campus / technology word sits beside it, or on
    the next line; ISLAMIC is finance only beside BANK / BERHAD.
  - `offer_rulings.py` passed the 600-line standard: its page-reading helpers and word lists moved to
    `offer_reading.py` (every name re-exported through `__all__`). **CORRECTION (sixth review):** this line and
    commit f233d33c first said "moved verbatim"; that was wrong — 8 moved names changed and 7 were added inside
    the move. Not amended; recorded here and in the CHANGELOG. Moves and behaviour changes go in separate
    commits from now on.
- **Sixth review (2026-11-03): private letters escaped THROUGH the safety rule — fixed as one change.**
  - Positive private evidence (`_positive_private`) now includes an UNCLEAN letterhead (an organisation other than
    the closed-list bodies) and a non-empty `private_college_reason`; a TVET letter with an unclean letterhead
    returns to its band (no `tvet_unverified` lift).
  - `_public_first_names` holds only the closed-list bodies' NAMES (TVET names, POLITEKNIK / POLYTECHNIC, UMS, the
    Form-6 names): a generic KEMENTERIAN / JABATAN / MINISTRY / DEPARTMENT / KERAJAAN / GOVERNMENT line is skipped
    and the institution after it is the one named first.
  - `_first_institution` and `_clean_letterhead` share one test (`_outside_orgs` + `_excused`): a public or unit
    word excuses a line only when no organisation noun outside an allowed name comes BEFORE it and no institution /
    company name (`_HEAD_RE`) comes after it; campus words straight after an allowed name (`_UNIT_TAIL`) are its
    campus in both; a unit's describing words lead its match ("ACADEMIC SERVICES DIVISION").
  - A confirmation engages the rules (and the safety exit) only from `CONFIRM_MIN` and with its title at the top
    (`_confirm_titled`: before any offer title, within the page's first half or 400 characters). The round-5 test's
    thin confirmations at p=0.0 now fail by design; its unclean-letterhead TVET case moved to the private-evidence
    test.
  - Lows: POLYTECHNIC in `_NO_PRIVATE_WING`; the English polytechnic department blanked like JPPKK; a one-word
    company name on the letterhead keeps the veto; ISLAMIC is finance only beside BANK, or beside BERHAD with no
    organisation noun (`_incidental` and `offer_issuers._payment_line`).
- **Round 7 (2026-11-03): one High + Mediums again — the swing is stopped by NARROWING, not another patch round
  (owner option 1; `docs/decisions.md` S6 items 7 + 8).**
  - BASELINE = the pre-S6 call (`results_doc.baseline_genuineness`; `offer_issuers` restored to its pre-S6 code but
    for `officer_must_close`). It is the default for every page.
  - BLOCK (`private_offer`) only on letterhead proof (`offer_reading.private_proof` over `_letterhead_block`).
    LIFT (`tvet_offer`, `confirmation`, `incidental_company`) only with a closed-list name on the letterhead, named
    first, a clean letterhead, the full shape and no private marker anywhere (`_private_marker`). Rulings 3 / 6
    soften a fail (`printout`, `tvet_slip`). JMTI / CIAST join the institutes (owner).
  - Deleted: the safety exit and its `*_unverified` tags, unclean-letterhead-as-private, the conditional block,
    `confirmation_ua`, the S6 edits to `offer_issuers` and the private-arm phrases.
  - Measured: 13 corpus letters differ from the baseline, each tagged (dev 6, held-out 7); 274 equal the pre-S6
    engine (checked against a detached pre-S6 checkout). Dev 196 / 197: a391 (conditional private offer, no
    letterhead proof) keeps its baseline `suspect` — a coordinator / owner call whether its expected label moves.
- **Round 8 (2026-11-03): 3 High — both overlays made STRICTER and SIMPLER, no new guesses.** LIFT excuses only a
  closed-list bank's own "Berhad" line and the addressee block above the title (`offer_reading._bank_line`,
  `_in_addressee_block`); every other company line, SWASTA / IPTS, S/B / SDNBHD is a marker. BLOCK reads only the
  true letterhead (`_letterhead_block`: top → first postcode line, earlier stops at Ruj / date / title /
  salutation / Kepada / candidate / name line), skips sponsor lines, and counts a tie-up word only beside an
  institution or company (`_names_an_institution`). Corpus unchanged (13 tagged changes); doc 1810's prod move
  (suspect → not_offer_letter, untagged) is the pre-S6 engine's own call — baseline == S6 there.
- **Round 9 (2026-11-03): 2 High, 3 Medium, 3 Low — fixed within the contract, stricter.** TVET lift: the
  institute on the letterhead and an admission title; PUSAT BERTAULIAH private; Form-6 confirmations name Form 6;
  BLOCK proof only before the public name, the block stops at d/a / u.p.; contact lines read without their tokens;
  PPPL variants; the narrowed tie-up (anywhere on the page it stops a lift); S/B only after a name; the unit
  prefix bounded. COST, for the coordinator: a228 d3465 / d3466 and a329 (owner-ruled genuine, app 329 an
  acceptance letter) have only an agency / ministry name on the letterhead, so they keep their baseline now —
  dev 195 / 197, held-out 88 / 90.
- **Owner ruling (S6 item 9): the agency-letterhead lift** (`_agency_lift`; class `Round10AgencyLetterhead`). Built as
  ruled; clean MARA + IKM, TVETMARA + KKTM, KBS + IKBN and JTM/KSM + ILP admissions lift; the r9 financing / loan
  letters, parent mismatches, JPK / unlisted-ministry letterheads and a private body in the body do not. MEASURED:
  the three target letters still keep their baseline under condition 4 ("no other organisation named in the
  body"): a228 d3465 / d3466 each have one more "INSTITUT" phrase (four words, none a closed-list name) in the last
  paragraph; a329 has a bare "KOLEJ" ending a sentence ("… di institusi / kolej"), with no name after it on its
  line. The coordinator read them (generic lowercase words; the ILKBS umbrella) and refined condition 4: a noun
  is another organisation only when a name follows it (raw case, descriptor words skipped), and the umbrella
  names count as their agency. MEASURED: all three lift (`tvet_offer`, reason `agency_letterhead`); 13 tagged
  changes; dev 196 / 197, held-out 90 / 90.
- **Owner rulings 2026-11-01 (from the S2 offer check) - what the genuineness status MEANS:**
  1. `not_offer_letter` = a FAIL for the bursary. `suspect` = we are not sure (a person decides).
  2. An offer from a private college (IPTS), or from a public university's private wing (e.g. UTM SPACE), is
     `not_offer_letter` - it is not an offer from a public institution. Today's calls on these are right.
  3. An admission printout / portal page is `suspect`, never `not_offer_letter` - we cannot say outright it is
     not an offer.
  4. A confirmation-of-studies letter from a public institution with no private wing (UMS, polytechnics) is an
     acceptable alternative to an offer letter. Where the university has a private wing (UM, UKM...) confirm the
     student is on the government programme.
  5. Real offers from public skills institutes (IKBN, IKM) were called `not_offer_letter` - WRONG today (2 letters).
  6. A TVET slip that is not an offer letter is `suspect`, not a fail.
  7. A private-college conditional offer (e.g. Kolej UNITAR) is `not_offer_letter`, not `suspect`.
  8. **What `suspect` does (owner, 2026-11-01):** the student is told the document is not an offer letter and is
     urged to upload the offer letter if they have it - but it is NOT a blocker. Check 2 or a reviewer can get
     more details or ask the student for the offer letter. (`not_offer_letter` is the fail.)
  **S6 must first verify today's behaviour against rules 1-8.** Today `pathway_engine.offer_official_status`
  folds `suspect` into 'not_genuine' for gating, and its docstring says a private/IPTS offer is stored as
  `suspect` - both may disagree with rules 2 and 8. List every reader of the status (gates, student messages,
  Check 2, the cockpit) before changing anything (sprint-start 3b: every door).
  S6 is therefore confirmed in scope: rules 3-7 are the proven wrong calls to fix. The reading label
  (`is_offer_letter` in the answers) stays a DOCUMENT label (offer / portal page / not an offer); the bursary
  decision above is a separate layer.
- **Goal:** real letters that the scorer rejects (e.g. some of the 14 polytechnic not_offer_letter) score genuine.
- **Named case (2026-11-02, from the S4 money reach):** app 329, doc 3494 — a two-page photo (a TVETMARA
  confirmation and a MARA / IKM offer) scored `not_offer_letter` against the POLYTECHNIC fingerprint, though it IS
  an offer. It must score as an offer (public skills institutes are public offers, ruling 5).
- **Owner ruling 2026-11-02 — what a chip colour MEANS (the reviewer reads the chips):** green = fine, nothing to
  do; yellow = the reviewer should look (an edge case, or judgement needed); red = something is WRONG with the
  letter. Applied to the offer chips (S6 audits EVERY offer chip against this, every door first):
  - **Pathway:** green = the letter matches the student's choice, OR the student declared nothing and a GENUINE offer
    set it (`chosen_programme.source == 'offer_letter_auto'` on an empty declaration — today `_declared_pathway`
    drops that pick, so the tick reads `unknown`, painted red); yellow = the letter differs from the choice (the
    Check 2 `pathway_confirm` query) or nothing to compare; **never red** (a different pathway is not a fault in
    the letter).
  - **Official:** green = genuine; yellow = suspect (e.g. a portal page); red = not_offer_letter.
  - **Name / IC:** green = match; yellow = partial or unreadable; red = mismatch (another person).
  - **Reporting date:** green = read; yellow = not printed.
  App 329 after S6: Pathway green (declared nothing, the offer set it) and Official green (the genuineness fix).
- **Scope:** `genuineness/results_doc.py`, `MODEL_VERSION` bump + History line, tests from real wording.
- **Acceptance:** every letter labelled real and from a supported issuer scores genuine on dev and held-out;
  every rejected-rightly letter stays rejected. Dry run on live stored data first.
- **Owner:** decision D6; adversarial review (it gates submission); deploy go. Skipped if S2 finds no wrong call.

#### Plan (2026-11-03)
Phase 1 (measure + plan) on `offer-read-s1` = origin/main `3bbeda41`; free (cached corpus text, no Gemini, no
Vision, no database). Keys and counts only. Builder: s6-builder. **Nothing built yet — owner approves first.**

**Premise re-derived.** The roadmap's scope line is too narrow. Offer genuineness is held in FOUR places, not
one: `genuineness/results_doc.py` (the five family lists, the private-arm veto, `signature_genuineness`, and
`MODEL_VERSION`), `genuineness/offer_issuers.py` (the TVET net and the private-college reason), `bands.py` (the
three-way mapping) and `pathway_engine.offer_official_status` / `offer_band` (how the gates read it). The chips
are decided in a fifth and sixth: `verdict_ladder.py` (the band arithmetic counts red chips) and the web
`officerCockpit.documentFacts` (the colours). Three of the files are at their line limit (below).

**Baselines (measured 2026-11-03, this worktree).**
- `python -m pytest apps/scholarship -q -p no:cacheprovider -n auto` (from `halatuju_api`, development
  settings): **9997 passed, 3 skipped, 5152 subtests passed** (21 min 48 s).
- `npx jest --maxWorkers=2 src/lib/__tests__/officerCockpit.test.ts src/lib/__tests__/fieldVerification.test.ts
  src/lib/__tests__/codeStandards.test.ts src/components/ScholarshipDocuments
  "src/app/admin/scholarship/\[id\]/view.docFacts.test.tsx"` (from `halatuju-web`, node_modules linked from
  the main checkout for the run, link removed after): **13 suites, 376 tests passed.**
- Today's genuineness on the corpus (`genuineness.assess('offer_letter')` on `offer_replay.production_text`,
  MODEL 1.22.0, 287 letters): answer `yes` 254 → genuine 237, not_offer_letter 15, unchecked 2; portal page 13
  → suspect 11, not_offer_letter 2; not an offer 14 → not_offer_letter 13, suspect 1; conditional 4 → 2 / 2;
  unsure 2 → suspect 1, no text 1. Stored vs today: 2 differ (a stored suspect → not_offer_letter; a stored
  suspect → unchecked). Today's call is what S6 changes; the STORED status changes only when a letter is
  re-scored (S7).

**1. Today's behaviour against rulings 1-8 (corpus; keys in the scratch table, not committed).**
| Ruling | Letters | Right today | Wrong today | Family / issuer of the wrong ones |
|---|---|---|---|---|
| 2 IPTS / private wing = not_offer_letter | 10 (+1 SATU) | 10 + 1 | 0 | — (9 private colleges / universities, 1 UTM SPACE; UM SATU) |
| 3 portal page / admission printout = suspect | 14 | 11 | **3** | UPU result-check page, matric portal screen (dev); a UNIMAS e-Daftar slip on page 1 of a real offer (held-out) — all not_offer_letter |
| 4 confirmation of studies (public, no private wing) = acceptable | 5 | 0 | **5** | polytechnic 2, UMS 2, a Form-6 college 1 (+ its STPM slip) — all not_offer_letter |
| 5 IKBN / IKM real offers = public offers | 3 | 0 | **3** | MARA / IKM 1 (app 329, not_offer_letter); Belia & Sukan / IKBN 2 (unchecked — "no signal", Official chip absent) |
| 6 TVET slip that is not an offer = suspect | 1 | 0 | **1** | JPK UP_TVET offer slip (not_offer_letter) |
| 7 private conditional = not_offer_letter | 2 | 1 | **1** | a private college conditional offer (suspect) |
| 1 not_offer_letter is a FAIL — a real public offer must not get it | 254 `yes` | — | **1 more** | a real polytechnic offer vetoed by the private-arm test because "SDN BHD" appears in its body (p 0.72) |
| 8 suspect is NOT a blocker | every suspect | 0 | **all** | see below |
**14 letters change call** (dev 7: portal 2, confirmation 2, IKBN 1, private conditional 1, polytechnic 1;
held-out 7: e-Daftar 1, confirmation 3, IKM 1, IKBN 1, TVET slip 1). Left as they are, and why: an interview
slip (suspect) and two UPU application slips (not_offer_letter) — no ruling covers them; a public PISMP
conditional offer (suspect, rule 7 is private only); a master's offer (not_offer_letter at p 0.30 — the owner
ruled postgraduate an eligibility matter, outside this arc). Finding for later (TD to raise): production scores
a scanned multi-page PDF on page 1 only (`_pdf_first_page_png`), so a real offer behind an e-Daftar slip reads
genuine only on all pages (0.70) — S6 makes such a page suspect, not a fail; scoring page 2 needs a Vision call
per page and is out of scope.

**What `suspect` does today (rule 8 is broken).** `offer_official_status` folds suspect into `not_genuine`.
Its docstring says a private / IPTS offer is "stored as suspect" — untrue since 1.4.0 / 1.6.0 (they are
not_offer_letter), to be corrected. The ladder gives a suspect −1 (step) and a second −1 (the Pathway chip goes
red because the letter "establishes no pathway") = Unsure, so `services/blockers._offer_blocks` BLOCKS
submission (`offer_not_official`) unless the reporting-date bonus lifts it. The student sees the generic note
"This doesn't look like a genuine official document… Nothing is blocked" for both suspect and not_offer_letter
— wrong words for rule 8, and untrue for the fail.

**Every reader of the offer genuineness status.**
- Gates: `services/blockers._offer_blocks` → `consent_blockers` (`offer_not_official`, not-yet-submitted
  only; STPM exempt); `resolution.doc_match_verdict` (a not-genuine upload never closes an official-offer
  request); `offer_issuers.officer_must_close` / `hold_for_officer` (NOT CHECKED + an officer's request).
- Verdict: `verdict_ladder._genuineness_step`, `_pathway_effective_step`, `_pathway_red_chips`,
  `_add_genuineness_caveat` (step 2 → `offer_not_official`, an `award.CONFIDENT_DISQUALIFIERS` member →
  `views_admin/verdict.py`, `serializers_admin` no-amount reason; step 1 → `document_not_genuine`);
  `verdict_engine._verdict_pathway` (`offer_hearing_ok` → `pathway_type_switch` / `pathway_confirm` /
  `pathway_undeclared` — Check 2's student queries; `offer_issuer_not_checked`).
- Picks: `services/offer_sync` autofill (`offer_band == 'genuine'`), `services/offer_link` link /
  `fill_empty_pick` (not_offer_letter refused; an empty pick needs genuine), `promotion._offer_quality` (which
  offer is live), `offer_reporting_bonus` (reads `doc_seen` + `present`).
- Student: `serializers.get_authenticity` → `checklists.GenuinenessNote` (the note), `cards.docIsGenuine`
  (offer is not in `docDone`), `consent_blockers` copy (`offer_not_official`, en / ms / ta).
- Cockpit: `officerCockpit.documentFacts` (Official + Pathway chips), `fieldVerification` (`usableOffer` /
  `backingOffer`: a not_* offer gives no tick).
- Not readers (checked): `help_engine` (Gopal reads name / IC / pathway only), `anomaly_engine` (no offer
  type), `check2_queries` (reads the verdict's items, not the status).
- Ops / eval: `reextract_offers`, `release-decisions` (prints the status), `rescore_unscored_documents`,
  `offer_replay`, `offer_review_page`, `offer_s4_dry_run`, `heldout_eval`.

**2. The chip audit (reviewer chips: `officerCockpit.documentFacts`, rendered generically by
`DocumentsDrawer.factLine`; the band twin: `verdict_ladder._OFFER_CHIP_RED` / `_pathway_red_chips`).**
| Chip | Today | Owner's table | Wrong | Corpus letters (apps) |
|---|---|---|---|---|
| Name | match green · partial / pending amber · **unreadable red** · mismatch red | green / yellow partial-unreadable / red mismatch | unreadable | 4 (4) |
| IC | match green · **unreadable red** · mismatch red | same | unreadable — 35 of the 38 are letters that print NO IC (decisions 2026-11-01 rule 4: a blank is correct) | 38 (33) |
| Pathway | **red when the offer is not genuine** (suspect without the date bonus, or not_offer_letter) · match green · **mismatch red** · unknown grey | green match, or declared nothing + a GENUINE offer set it · yellow differs / nothing to compare · never red | three arms | not genuine: 48 (40); mismatch / unknown / auto-set: need live data (lead query below) |
| Official | **genuine: no chip** · suspect amber · not_offer_letter red · unchecked: no chip | green / yellow / red | genuine | 237 (223) gain a green chip |
| Reporting date | **no chip** | green read · yellow not printed | missing chip | 234 read (220) · 53 blank (44; 48 truly not printed) |
| (Intake year, Switched — not in the table) | green current / amber off; amber | — | unchanged | — |
App 329 (doc 3494) today: **Pathway red** (the offer is not_offer_letter, so it "establishes no pathway") and
**Official red** (not_offer_letter). After the build the Pathway chip is yellow at once (never red); both turn
green only once the letter is re-scored (S7, or a Cockpit Re-run on 329): Official green from the TVET ruling,
Pathway green from "declared nothing, a genuine offer set it" (`chosen_programme.source == 'offer_letter_auto'`
— lead to confirm on the live row). Live estimate: the corpus is the live offer set of 2026-11-01 (287 letters,
251 applications), so the counts above are the order of magnitude; exact live numbers come from the dry run.

**3. Doors (sprint-start 3b) — what puts an offer into a genuineness status, or a gate state, or takes it out.**
- Status writers: `vision._run_field_extraction_impl` offer branch (upload, cockpit Re-run, sweep,
  `reextract_documents`, `reextract_offers`, the `release-decisions` job); `bands.keep_stored_authenticity`
  (TD-407: a re-read with no fresh score keeps the old one — so a flag-off re-read keeps the OLD wrong call);
  `rescore_unscored_documents --apply` (unscored only); `offer_replay` (eval). **Deploying S6 changes no stored
  status**: the 14 corpus calls (and their live twins) move only when re-scored → S7's list.
- Gate doors that change AT DEPLOY on stored data: `_offer_blocks` (new rule: block iff not_offer_letter —
  rule 1 — and never on suspect — rule 8; STPM exemption and the not-yet-submitted grandfather kept); the
  ladder (Pathway chip no longer counted; Name / IC `unreadable` no longer red) → every pathway band, the
  Check 1 tile, `offer_not_official` disqualifier unchanged (still step 2 only); the chips; the student note.
  `resolution.doc_match_verdict` KEEPS refusing a suspect upload as the answer to an official-offer request
  (rule 8: "Check 2 or a reviewer can ask for the offer letter") — stated, pinned by the drift test.
- Pick doors: a genuine CONFIRMATION letter (rule 4) must never write a pick — `offer_sync` autofill,
  `offer_link` link / `fill_empty_pick` refuse a `doc_seen` of `confirmation_*` (a confirmation names the
  programme she is on, which can differ from her offer — seen on a dev letter). `promotion` may rank a genuine
  confirmation above a suspect offer (acceptable alternative — ruling 4).
- Hearing: `offer_hearing_ok` unchanged (genuine or suspect); a re-scored portal page moves from no hearing
  (not_offer_letter) to a hearing (suspect) — listed for S7.
- Money: none. `course_start_year` / `intake_year` do not read genuineness (TD-465 owns that; the deferred
  "a not_offer_letter document never dates the course" ruling stays deferred).
- The Pathway "set by the offer" green: a new `pathway_set_by_offer` flag on `student_offer_check` read ONLY
  by the chip — `pathway` itself stays `unknown`, so the Chosen-programme tick (`fieldVerification`), the
  verdict and Check 2 do not change (request #9's circular-tick guard holds).

**4. Files and budgets.** Three files S6 must change are at their limit, so three moves-only commits come first:
| File | Size / limit | Plan |
|---|---|---|
| `pathway_engine.py` | 633 / 613 + 20 (ledger) | **moves-only split first** (subsection below) → ~470; its `oversize_files` line LEAVES the budget (the tightness test asks) |
| `genuineness/results_doc.py` | 600 / 600 (any new line fails) | **moves-only split first**: the five offer family lists, `_UA_NAMES`, `_PRIVATE_ARM_PHRASES`, `_private_arm_offer` → new `genuineness/offer_signatures.py`, re-exported (`offer_issuers`, `pathway_engine`, `catalogue_levels`, `doc_signatures` import them from `results_doc`); ~480 after |
| `halatuju-web/src/lib/officerCockpit.ts` | 1657 / 1637 + 20 (ledger; hotspot #1, 28.2) | **moves-only first**: the `offer_letter` branch of `documentFacts` → new `src/lib/offerFacts.ts` (the `higherResultsFacts.ts` precedent), then every colour change lands there; the entry is lowered if the tightness test asks |
Then: `genuineness/offer_rulings.py` (new, ≤ 250) — the rulings, applied by ONE call inside the offer branch
of `signature_genuineness`: portal / admission printout → suspect (never below); public confirmation →
genuine (`doc_seen` `confirmation_polytechnic` / `confirmation_form6` / `confirmation_ua`), a UA with a private
wing → suspect; the closed TVET list on the letterhead with offer wording → genuine `tvet_*` (Q2), a TVET slip
→ suspect; a private conditional → not_offer_letter; the private-arm veto's "SDN BHD" arm ignored when a
family's own public-issuer line is on the page (`_private_arm_offer` itself unchanged — `catalogue_levels` and
`offer_reporting_bonus` gate 3b read it). **`MODEL_VERSION` 1.22.0 → 1.23.0** + History line (memory rule:
bump on ANY doc-recognition change). `verdict_ladder.py` (282: `_OFFER_CHIP_RED = {'mismatch'}`, the Pathway arm
removed) + **`VERDICT_ENGINE_VERSION`** bump (`verdict_engine.py` 984-entry file: one line). `services/blockers.py`
(557; ≤ 600). `services/offer_sync.py` / `offer_link.py` (one guard each). `serializers.py` (ledger 1195) NOT
touched — the flag rides `pathway_check`. Web: `offerFacts.ts` (Pathway never red; Official green; Reporting
date chip; Name / IC unreadable yellow), `checklists.tsx` (515: offer note keys), `checklistsPathway.tsx` (150:
the student's mismatch badge amber, not red — same meaning), `messages/{en,ms,ta}.json` (two cockpit fact
keys, two student note keys — Tamil per the style guide; review goes to Sol). **No DocumentsDrawer.tsx change**
(it renders whatever `documentFacts` returns; Mobile M6b can push first). **No Stitch screen**: a colour
mapping plus two chips in an existing chip row of the approved cockpit, existing tones (lesson: a design
standard that already covers the screen satisfies "prototype first"); a sandbox screenshot goes to the owner
with the build.
Eval: `eval/offer_genuineness_check.py` (new, hand-run: per letter EXPECTED bursary status vs today's call, by
split / family; exit 1 on any miss; keys only) + `eval/offer_genuineness_expect.json` (new, committed, PII-free:
key → expected status, from the answers and rulings 1-8); `offer_s4_dry_run.py` S6 mode (below); README.

**Pre-flight checks done.** Budget files grepped for every path: only `pathway_engine.py` (oversize 613) and
`officerCockpit.ts` (oversize 1637 + its in-file suppressions — the move must take none of them) carry keys;
`results_doc.py` and the rest carry none. Other tree: `halatuju-web/src/lib/scholarship.ts` names
`pathway_engine` in a comment only. Source-text guards: `test_superseded_documents.READ_MODULES` names
`pathway_engine.py` → **extended** to `pathway_match.py` (lesson: extend a guard on a move, never re-point);
`test_closed_case_writes` reads `officerCockpit.ts` for `CASE_CLOSED_STATES` (not moved).

##### The `pathway_engine.py` split (moves only — for Cockpit to check before any build; TD-473 lands on it)
- **New module `apps/scholarship/pathway_match.py`** — "the lenient offer-vs-declared matcher". Moved VERBATIM,
  in order: the comment block "Lenient offer-vs-declared pathway matcher", `_GENERIC_TOKENS`,
  `distinctive_tokens`, `_field_status`, `offer_pathway_match`, `_declared_pathway`,
  `catalogue_declared_institution` (today lines 23-190, ~168 lines). It carries its own
  `from __future__ import annotations`, `import re`, `from .school_names import school_name_core` (lesson: a
  module-wide directive is not in a body). Its two lazy imports stay inside their functions
  (`from .offer_pathway import parse_stpm_stream` / `sole_catalogue_institution`). It imports nothing from
  `pathway_engine`, `offer_pathway` or `offer_course_match` at module level — a leaf.
- **`pathway_engine.py` re-exports all six names** (`from .pathway_match import (_GENERIC_TOKENS,
  _declared_pathway, _field_status, catalogue_declared_institution, distinctive_tokens,
  offer_pathway_match)  # noqa: F401`), so `offer_course_match` / `offer_pathway` / `offer_link`'s
  `from .pathway_engine import distinctive_tokens`, `audit_pathway_ticks`' imports and the eight test modules
  keep working unchanged.
- **The live circular pair stays as is:** `student_offer_check` keeps its function-local `from
  .offer_course_match import letter_institution, programme_line` (and the two `offer_pathway` locals);
  `offer_course_match` / `offer_pathway` keep their top-level import of `distinctive_tokens` from
  `pathway_engine` (they may later import it from `pathway_match` directly — not in the moves commit).
- **Patch safety:** nothing patches a moved name (`mock.patch` targets on `pathway_engine` are
  `student_offer_check`, `offer_official_status`, `started_before_cohort` — all stay); `offer_pathway_switch`
  (stays) calls `_field_status` through the re-export.
- **What lands there later:** S6 adds nothing to the moved bodies; **TD-473 (Cockpit)** puts its level check in
  `pathway_match.offer_pathway_match` / `_field_status`, beside the matcher it changes.
- Result: `pathway_engine.py` ~470 lines (leaves `oversize_files`; budget line removed, baseline untouched, no
  `_moved` record — no ledger key is renamed); `pathway_match.py` ~175.

**Lessons and decisions that bind S6, and how the plan meets each.**
- Decision 2026-11-01 (a genuineness status is a bursary decision) + 2026-11-02 (chip colours) → they ARE the
  spec; `offer_genuineness_expect.json` encodes them per letter.
- Decision 2026-10-26 C1 (the TVET net is narrow on purpose: a typed fake, a skills certificate, a MARA loan
  letter, a "JTM" page, a MARA-sponsored private college read NOT CHECKED in its first cut) → Q2; whatever the
  answer, the C1 review's controls are kept as synthetic-twin tests (letterhead only, offer words, sponsor line,
  private MARA, bare acronyms).
- Decisions 2026-07-07 / 07-08 (the ladder stacks a not-official Pathway chip on the step; #31 suspect = Unsure)
  → SUPERSEDED by rulings 8 and 2026-11-02 ("Pathway never red", "suspect is not a blocker"): a suspect now reads
  Probable; a not_offer_letter still blocks, by rule 1 directly. New decisions entry says so.
- Decision S4 `offer_ic` (a guarded blank IC reads `unreadable` → red, `test_offer_reader_doors` line 100) →
  superseded by the chip table (unreadable = yellow); that test is re-pinned with the ruling cited.
- Request #9 / `_declared_pathway` #117 (c) circularity break → kept; the auto-set green is a chip-only flag.
- Lesson "a new shape needs every reader checked" + 3b → the reader list above; the adversarial brief carries
  it and asks for the missing door.
- Lesson "a moves-only split moves bodies; directives are not in a body" + "extend the guard on a move" → the
  split subsection.
- Lesson "a string added to a shared message file moves every route" → the two student note keys go in the
  slice the Documents page already loads; `npm run build` + the bundle budget before the push
  (`/scholarship/application` has ~0.23 kB of room, TD-433).
- Lesson "validate on held-out once" (S5 retro) → tune on dev (7 letters), ONE held-out run (7 letters), runs
  counted in the report.
- Lesson "a new refusal rule is re-measured on dev before it is reported" (S5 retro) → every new rule is run on
  all 287 before it is counted; a rule may not move any of the 237 genuine `yes` letters.
- Memory: bump `MODEL_VERSION`; adversarial review before the push (it gates submission); no re-extract from a
  local checkout (S6 writes nothing live).

**Steps.** (1) `pathway_engine` split, own commit, suite green. (2) `results_doc` split, own commit. (3)
`officerCockpit` offer-branch move, own commit, jest green. (4) `offer_genuineness_check.py` + expect file
(fails today on the 14). (5) `offer_rulings.py` + `MODEL_VERSION` 1.23.0; dev loop to 0 misses with the 237
genuine unmoved; one held-out run. (6) Gates + ladder + pick guards + `VERDICT_ENGINE_VERSION`; docstring of
`offer_official_status` corrected. (7) Chips + student note + copy. (8) `offer_s4_dry_run.py --s6` (the lead
runs it read-only on production): per live application, before / after on STORED data — pathway band, blocked
by `offer_not_official`, each chip's colour; and the corpus twin of the S7 effect. (9) Adversarial review
(gates, picks, chips) with the door list; CHANGELOG, decisions entry, README, TD for the page-1-only scoring.

**Live numbers the lead needs (read-only, before the push).** From the dry run: (a) not-yet-submitted
applications blocked today by `offer_not_official`, split suspect / not_offer_letter (suspect ones unblock);
(b) pathway band moves (expected: up only — a red chip is removed, nothing added); (c) Pathway chips today red
/ grey that become yellow / green, incl. the auto-set count; (d) live offers by stored status + `doc_seen`
(how many look like the 14 classes) → S7's re-score list; (e) app 329's `chosen_programme.source`.

**Acceptance.** (1) `offer_genuineness_check.py`: 0 misses on dev and held-out — the 14 move as ruled, the 237
genuine `yes` letters and every rightly-rejected letter unchanged. (2) Suite green, jest green, budgets
unchanged or tighter (three files smaller). (3) Dry run: no band falls, no new block; every unblock is a
suspect. (4) App 329 on its corpus twin: Official green, Pathway green.

**Estimated files touched: ~34** (API 18 incl. 3 new modules and ~6 test files; web 9 incl. 1 new module + test;
docs 7). **Recommended execution:** sequential, one builder (an Opus subagent builds; the lead verifies each
diff and re-runs the gates), because the three splits must land before the files they free are edited and
every later step reads the same gate semantics; no parallel agents (one shared `pathway_engine` /
`verdict_ladder` seam). Cockpit checks the split subsection first; Mobile M6b may push `DocumentsDrawer.tsx`
before or after — no overlap.

**Open questions for the owner (recommendation first).**
- **Q1. TD-473 (Cockpit's): a matriculation / STPM / Form-6 letter on a degree application** — recommended:
  `mismatch`, which under the new table is a YELLOW Pathway chip plus the Check 2 "is this your final pathway?"
  query to the student — never red, no band loss. (Alternative: `unknown` — yellow, but no query.) Cockpit's
  lean fits "Pathway is never red" once mismatch is yellow.
- **Q2. Public TVET offers (IKBN / IKM / ILP / KKTM, the closed list):** recommended: score them **genuine**
  (Official green, as you asked for app 329) when the institute is named on the LETTERHEAD and the page carries
  offer wording and no private / sponsor marker — 3 corpus letters. The cost: a well-typed fake naming an
  institute would show green until a reviewer looks (the 2026-10-26 review's worry; we hold too few letters per
  institute to fingerprint them). Alternative: keep "not checked" (no Official chip, the reviewer checks by
  eye) and only stop the false fail — then app 329's Official chip stays empty, not green.
Defaults taken unless you say otherwise: only UMS, polytechnics and Form-6 colleges count as "no private wing"
for a confirmation letter (any other university's confirmation → suspect); an interview slip stays suspect and
a UPU application slip stays not_offer_letter.

### S7 — Live re-read of the letters whose read changes (ops, ~3 h; paid)
- **Goal:** live records carry the improved reads.
- **Scope:** list the live offers whose read would change (from S4–S6 on the corpus) and what offer_sync / link /
  institution sync would then do (planners' report mode); re-read through the service with the flags (rule 4);
  after-list.
- **Acceptance:** every re-read letter prints a genuineness status; before/after list matches the dry run;
  no unexpected pick moved; any realign/link the new reads would cause is listed separately for the owner, since
  27 picks were realigned and 9 linked on 2026-11-01 from the old reads.
- **Owner:** yes to the list and the cost (≈ RM1–5); undo path stated with the ask.

### S8 — Keep it exact (low, ~3 h)
- **Goal:** future changes cannot quietly lower the score.
- **Scope:** sprint-close step for any offer-reader change: run the scorer, no held-out field may fall; a monthly
  `fetch_corpus.py` top-up with answers for new letters; README + workflow note.
- **Acceptance:** documented gate; one dry run of the gate.

**Total:** 8 sprints, ≈ 48 h of build (S6 conditional), owner ≈ 2 h of checking, paid runs ≈ RM15–40 in all.
S1–S3 are measurement only (no production change); S4–S6 change the reader; S7 touches live records; S8 keeps it.

---

## 8. Decisions for the owner (recommendation first)

- **D1. Who writes the correct answers?** (a) The lead agent reads each letter and writes the answer; you check 30
  at random plus any marked unsure (~1 h) — **recommended**. (b) You or a staff reviewer check all 287 in a
  pre-filled form (5–7 h).
- **D2. What counts as "exact"?** (a) The core fields — name, NRIC, institution, programme (stream for STPM /
  matric, specialisation for PISMP), intake, reporting date — after light tidying; a field the letter does not
  print counts as right when left blank — **recommended**. (b) Every field, including offer date, issuer and label.
- **D3. Duration and fees?** (a) Write them in the answers now (cheap while reading); decide later whether the
  reader should take them and where staff would see them — **recommended**. (b) Add them to the reader in S4.
- **D4. Where do paid measuring runs happen?** (a) On the local copies of the letters, writing nothing live, each
  run approved with its cost — **recommended**. (b) Only on the live service.
- **D5. Live re-read at the end?** (a) Only letters whose read would change, after a dry-run list — **recommended**.
  (b) Every live offer letter.
- **D6. Genuineness in scope?** (a) Label "is this a real offer?" now (free) and fix only proven wrong calls (S6) —
  **recommended**. (b) Reading only; leave genuineness alone.
