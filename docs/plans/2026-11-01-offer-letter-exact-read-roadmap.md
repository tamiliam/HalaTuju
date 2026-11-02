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

### S5 — Reader round 2: the Exact read covers more letters (medium, ~8 h; production code)
- **Goal:** more letters read by the free, deterministic reader, with no new errors.
- **Scope:** `offer_parse.py` — FIRST the 48 known-format letters (STPM 9, matriculation 17, polytechnic 22; 27 PDF,
  21 photo; Sabah 22, flagship 26) whose stored read is the AI reader's: find why the fixed-format reader did not
  lock them (a photo with no OCR text, a layout variant) and close that gap (owner steer 2026-11-01). Then the
  government families where the dev set shows Gemini fallback or a wrong field;
  a text-layer reader for any university template held by ≥5 letters (data-gated; skip if none). `PARSER_VERSION`
  bump; `eval/offer_parse_check.py` (exact / fallback / WRONG per letter, like `stpm_parse_check.py`).
- **Acceptance:** 0 WRONG on dev and held-out; lock rate up; held-out exact score not down.
- **Owner:** adversarial review (identity fields); deploy go.

### S6 — Genuineness fixes, only if the answers prove a wrong call (medium, ~6 h; conditional)
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
- **Scope:** `genuineness/results_doc.py`, `MODEL_VERSION` bump + History line, tests from real wording.
- **Acceptance:** every letter labelled real and from a supported issuer scores genuine on dev and held-out;
  every rejected-rightly letter stays rejected. Dry run on live stored data first.
- **Owner:** decision D6; adversarial review (it gates submission); deploy go. Skipped if S2 finds no wrong call.

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
