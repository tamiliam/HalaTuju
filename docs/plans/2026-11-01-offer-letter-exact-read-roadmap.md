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

### S3 — Today's AI reader, measured (low, ~4 h; paid)
- **Goal:** today's Gemini read scored on the dev set, and its true cost per letter.
- **Scope:** `eval/offer_fresh_read.py` (new, or `heldout_eval.py local` extended): today's prompt on the local
  files, cached as gitignored `<key>.fresh.json` with full token use incl. thinking; the scorer compares stored vs
  fresh. 10 letters first, then the dev set.
- **Acceptance:** fresh-read score on dev beside the stored score; measured cost per letter; a TD if the live meter
  under-counts thinking tokens.
- **Owner:** yes to ≈ RM3–9 (dev set, one pass).

### S4 — Reader round 1: traceability and what Gemini sees (medium–high, ~10 h; production code)
- **Goal:** fix the biggest S2 failure kinds that come from the AI read's inputs and prompt.
- **Scope (expected, confirmed by S2):** an offer reader version stamped on every read (AI and deterministic);
  Gemini sees up to 3 pages, and the text layer beside the image for a digital PDF; prompt fixes for the top
  measured kinds (e.g. the reporting date, the NRIC); `vision.py`, `pdf_pages.py`, tests on synthetic letters.
- **Acceptance:** dev score up on the core fields, no field down; then ONE held-out run — the held-out score must
  rise and no family may fall; cost per letter within the S3 figure × 2.
- **Owner:** yes to the paid dev and held-out runs (≈ RM5–15 in all); adversarial review; deploy go. No live
  re-read yet (S7).

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
- **Goal:** real letters that the scorer rejects (e.g. some of the 14 polytechnic not_offer_letter) score genuine.
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
