# HalaTuju: OCR first, AI as the fallback, and retiring Gemini 2.5 (roadmap)

**Status:** APPROVED by the owner, 18 Nov 2026. The owner also said yes to **way C** (keep each new upload's OCR text from now on), to start at once as **S0b**. Q1(a) (the one-off live capture, way B) is still open.
**Format:** `Settings/_workflows/implementation-planning.md`.
**Read from:** main 1956e5866, plus the branches `reader-260` (offer reader 2.6.0, 9be194f1a) and `offer-course-proof` (7fee23c0e). The live database was read only, and only for counts.
**No personal data appears in this file.**

---

## 1. What the owner asked for, in one paragraph

Read documents with OCR text and fixed rules first, and use AI only when the rules cannot answer with confidence. Set a measured **threshold** that decides which way each document goes. Start with university offer letters: there are only about 20 public universities, and we now hold more than 400 letters. Match each letter's university and course against the catalogue, the way we already do for Poly, Matric and Form 6. The 2.6.0 reader (a stricter schema plus one 3.8 retry) is the **immediate fix**. Once rules are reliable, it becomes the fallback step. Gemini 2.5 has a retirement date, so nothing may rely on it in the long run.

**Owner rule on course codes (18 Nov):** "The course code is an additional information only, and could be used." A printed UPU code is **supporting evidence, never a requirement**. A letter that names the course without a code can still match.

---

## 2. Phase 0: the free dry run (Sprint 0)

### Is the OCR text of live documents stored? **No.**

- `applicant_documents` has no OCR-text column. It holds only `vision_fields` (JSON), `vision_nric`, `vision_name`, `vision_address` and `read_state`.
- `field_extraction._store_field_read` writes the answer fields. It never writes the text they came from.
- The only `text` key in `vision_fields` belongs to the 135 statements of intent, which are typed by students and are not scans.
- An SPM slip whose parse fails keeps its word boxes for diagnosis (`_slip_ocr_diag.capture`). That is a partial exception, and only for failures.
- The project memory already says so: "The OCR text of offers is NOT stored (only vision_fields.fields)."

So a dry run "on the stored OCR text of live docs" is not possible today. The cheapest ways to get the text, in order:

| Way | What it gives | Cost | Needs |
|---|---|---|---|
| **A. The local eval corpus (use first)** | **Offer letters:** 287 (286 with `ocr.txt`), 287 hand-checked expected answers (`offer_expect`), 287 stored replays, 216 fresh 2.6-era reads. **SPM slips:** 98 cached. **Electricity bills:** 90. **Salary slips:** 99. **Water bills:** 28. **STR / birth certificate:** 28. **EPF:** 13. | **Free.** No model call and no fetch. | Nothing |
| **B. Capture live text without AI (a read-only job)** | For live documents the corpus lacks: **parent ICs (none in the corpus)**, TNB bills beyond the 90, EPF beyond the 13. A digital PDF's own text layer is free. Photos and scans go through Cloud Vision OCR at one call per page (the same method as `capture_ocr.py`). This is **not a Gemini call**. | About 1,100 pages. The first 1,000 a month are free, then about US$1.50 per 1,000, so **US$0 to US$2**. | The owner's yes (it downloads stored files: **Q1**) |
| **C. Keep the text from now on** | On each new read, store the OCR text in a private column that is deleted with the document. Future dry runs then grow for free, and drift can be watched. | Free to run. One additive migration. | The owner's yes on keeping the data (**Q1**) |

### What Sprint 0 builds

- **The tool:** `halatuju_api/eval/ocr_first_dryrun.py`. It uses only the existing pieces: `offer_parse*`, the new university parsers as they arrive, `offer_course_match.match_offer_course`, `doc_parse` / `doc_parse_epf`, the slip parser and `offer_read_check`'s scorer.
- **Its input:** cached OCR text (way A, later B or C).
- **What it compares against:** two answers:
  1. the hand-checked expected answer (`offer_expect`), where one exists. **This is the truth.**
  2. the stored AI answer from the replay, which shows agreement only. The AI is not the truth.
- **Its output:** counts only, with no names or ICs.
  - **Agreement %** per document type and per issuer (offer letters: per university; bills: TNB format A or B; EPF layout).
  - **A per-field breakdown**, using the existing scorer's buckets: exact / blank_correct / missing / wrong / extra. The core offer fields are name, IC, institution, programme, intake and reporting date. The course match is scored separately: unique / none / refused.
  - **A lane table:** which (type, issuer) pairs pass the threshold below, which fail, and why.
- **It uses the held-out split** (`offer_split`, about 90 letters). Rules are tuned on the dev split and judged on the held-out split.
- **Complexity:** medium. **Paid calls:** none.

### The proposed THRESHOLD rule (two gates; both must pass)

**Gate 1, per lane: is this (doc type, issuer) allowed to use rules alone?** Run on the held-out dry run:
- **Sample size:** at least 20 documents in the lane. A smaller lane stays on AI until it grows. Sample size counts only documents the rules locked.
- **Core-field agreement:** at least 98% exact or blank-correct against the hand-checked answer.
- **Zero WRONG** on name, IC, institution and course. (A blank is acceptable, because the document then goes to AI. A wrong value is not acceptable.)
- **Course match:** never wrong. "A wrong course_id is worse than none" still holds: a course is set only when exactly one course qualifies.
- **Switch:** each lane has its own switch (a setting) and starts **off**. It is turned on only in a publish the owner has approved.

**Gate 2, per document: is THIS document trusted to rules alone?** Every condition must hold, or the document goes to the AI fallback (the 2.6.0 reader):
1. The parser recognises the layout (its markers lock).
2. Every required field is filled. For offers: name, IC, institution, programme, intake, and a reporting date or the "to be announced" wording.
3. The IC guard passes (`offer_ic.guard_nric` against the profile).
4. The catalogue match is **unique**, for both the institution and the course. A printed UPU code counts as extra evidence only.
5. The values make sense: dates fall in the intake window, and the issuer is one of the 20 public universities.

**Every read records** `capture: 'deterministic'` with a `rules_lane` and the reason it went to AI when it did. That lets LL1 (the learning loop) count each lane's later reviewer overturns. **A lane is switched off again** if reviewers overturn more than 2% of its facts in a month.

**Optional shadow check (Q2):** for the first month, every 10th rules-only document also gets the AI read, kept for comparison only. That is about 30 calls a month, roughly US$0.15.

---

## 3. Sprints in priority order

**Dependency (from the coordinator, 18 Nov):** the offer-letter sprints (S1 to S3) build on the branch **`offer-course-proof`** (7fee23c0e). That branch already contains reader 2.6.0 (`reader-260`) and the new bracket-menu rule in `offer_course_match.py`: a letter that names only the course can match a catalogue "[a / b / c]" menu course, either on the base name alone or on the base name plus exactly one listed option, and a printed UPU code is extra evidence. **S1 starts only after that branch is merged to main.** If it is still on a branch when S1 begins, S1 is cut from it and rebased later.

**Order:** the owner's value × sample size × feasibility. S0 comes first, because every later gate needs it. **S4 (the slip gate) touches different files from S1 to S3, so it can run alongside them** (at most 2 builders).

### S0: the Phase 0 dry-run harness (free)
- **Goal:** measure, per lane, how often rules alone already agree with the truth.
- **Scope:**
  - `eval/ocr_first_dryrun.py` (new) and `eval/README.md`.
  - The lane-threshold function, as a pure function: `scholarship/ocr_first_gate.py` (new). It decides yes or no for a lane from the dry-run counts and is reused by S1 onwards.
- **Tests:** `test_ocr_first_gate.py`, covering threshold edges (19 vs 20 documents, 97.9 vs 98%, one WRONG). Plus a harness smoke test on 3 synthetic fixtures, with no personal data.
- **Gate:** it runs on the corpus with no network, and the lane table is produced.
- **Stays AI:** everything (it is measurement only).
- **Complexity:** medium.

### S0b: keep the OCR text of each new upload (way C; owner's yes, 18 Nov)
- **Why:** without the text, the learning loop cannot re-test new rules on live documents for free. With it, the dry-run set grows by itself and drift can be watched.
- **Scope:**
  - One **additive** migration: a private OCR-text store for `applicant_documents` (a nullable column or a 1:1 side table; the builder picks the one with the smaller blast radius and says why). It is deleted with the document (cascade).
  - Write the text at read time, wherever the read pipeline already has it (a PDF text layer, Cloud Vision OCR output). **No new model call and no new OCR call** just to fill it.
  - Never shown in any API response, admin list or export. Not copied into `vision_fields`.
  - Record the text's source (text layer / Vision) and a version.
- **Tests:** the text is stored on a new read (mocked); the document delete removes it; no serializer or export carries it; a read with no text stores nothing and does not fail.
- **Version:** no reader behaviour change, so no `OFFER_READER_VERSION` bump.
- **Release:** `Migration: additive`. Personal data at rest, so an **Opus build and an Opus adversarial review** before the push.
- **Stays AI:** everything (storage only).
- **Complexity:** medium.

### S1: UMS offer letters, rules first (with the catalogue match)
- **Why first:** UMS is the largest group of AI-read letters (about 92). About 40 of them record a **hostel** (a "Kolej Kediaman" type name) as the institution. That is a wrong fact today, and rules fix it for free.
- **Scope:**
  - **New `offer_parse_university.py`:** a UMS layout reader that takes name, IC, programme, faculty / campus, intake and reporting date by their printed labels.
  - **`offer_course_match.py`:** add the UMS hostel names to `letter_place`, so the issuer (UMS) stands in for a hostel line, and match on the **base name / bracket menu** (from the base branch). The UPU code is extra evidence only.
  - **`catalogue_levels.py`:** refusals for level and specialisation stay as they are.
  - **`offer_exact.py`:** route ua_offer letters from UMS through the parser before AI.
  - **`field_extraction._read_offer_letter`:** check the gate, then use the rules or fall back to `read_offer` (2.6.0).
- **Version:** `OFFER_READER_VERSION` 2.6.0 → **2.7.0**. Record `rules_lane='ua:UMS'`.
- **Tests:** a parser unit test (synthetic text), a hostel-to-issuer test, catalogue uniqueness (menu base / one option / two options → none), a gate fall-through test, and regression on the existing offer tests and the A34 golden verdicts.
- **Gate:** the S0 harness on the UMS held-out letters passes Gate 1. `offer_parse_check` and `offer_genuineness_check` are unchanged on the other families.
- **Stays AI:** UMS letters that fail Gate 2, and every other university.
- **Complexity:** high (it feeds the pathway and eligibility).

### S2: the next four universities (UPSI, UUM, UiTM, UM)
- **Size:** about 28, 28, 22 and 22 AI-read letters respectively.
- **Scope:**
  - A layout reader for each university in `offer_parse_university.py`.
  - UiTM's own local course code is already handled in `offer_course_match`, and is extra evidence only.
  - Each lane is switched on only if it passes Gate 1 with at least 20 held-out letters. A lane short of 20 stays AI and is listed.
- **Version:** 2.8.0.
- **Tests and gate:** as for S1, for each lane.
- **Stays AI:** lanes under the threshold, private universities and the PISMP letters (deferred).
- **Complexity:** medium.

### S3: the remaining public universities (UKM, UTHM, UTeM, UNIMAS, UMK and the rest of the 20)
- **Scope:** the same pattern. Most of these lanes have **fewer than 20 letters**, so the likely result is "built, measured, stays AI until enough letters arrive". The sprint ships the readers with their switches off, plus a monthly line in the dry-run report showing when each lane reaches 20.
- **Version:** 2.9.0.
- **Complexity:** medium. **Option:** drop or postpone this sprint if S2 shows small lanes are not worth it.

### S4: the SPM slip gate fix (free, rules)
- **Problem:** 115 of the 158 AI-read SPM slips never reach the parser. `field_extraction._extract_slip_deterministic` (lines 32-34) returns `not_spm_exam` whenever the student's profile `results_held` is not 'spm'. The **document** is an SPM slip, even when the profile says otherwise (for example, a STPM or diploma student uploading their SPM slip).
- **Scope:**
  - Decide by what the slip itself says: the parser's own SPM markers. Use `results_held` only as a hint.
  - Keep `not_spm_exam` for slips that really are not SPM.
- **Version:** bump the slip read's version stamp and `results_doc` MODEL_VERSION (currently 1.29.0) if the verdict reads the slip's capture.
- **Tests:** an SPM slip with a non-SPM profile reaches the parser; a non-SPM slip is still refused; regression on the slip matrix (F1).
- **Gate:** the S0 harness on the 98 cached slips plus the **137-slip answer key** (grades typed by the student and confirmed by a reviewer). Zero wrong grades on documents the rules accept.
- **Stays AI:** slips the parser cannot lock (photos at an angle, partial slips).
- **Complexity:** low to medium. **It can run in parallel with S1.**

### S-visible: the visible page judges (owner decision 18 Nov)
- **Rule:** a PDF page whose text is invisible (scanner-app OCR overlay, render mode 3 / 7) has no text layer; the read goes to Cloud Vision (page 1) like a scanned PDF. Drawn text keeps its free layer. Detection failure goes to Vision. Central in `pdf_pages.pdf_text_layer` / `pdf_page_texts`, so every reader follows it.
- **Versions:** MODEL_VERSION 1.31.0, offer reader 2.7.0, SPM slip reader 1.2.0.
- **Corpus:** 303 layered PDFs, 16 invisible (one Vision call each), 287 drawn (no new call).

### S5: SPM slips off 2.5 (the AI fallback moves to 3.8)
- **Problem:** `vision/gemini_read.py:86` `PINNED_25_DOC_TYPES={'results_slip'}` keeps slips on 2.5, because 3.8 returned malformed grades on **26 of 98** slips ("Aplus", stray JSON, tab or CJK characters).
- **Fix, in three layers:**
  1. **Parser first** (S4), so fewer slips reach AI at all.
  2. **A stricter schema** for the slip in `vision/schemas.py`:
     - each grade is an **enum**: A+, A, A-, B+, B, C+, C, D, E, G, TH, plus empty;
     - `required` on the subject list and on every grade key;
     - an empty string is valid, a missing key is not (the 2.6.0 pattern).
  3. **A clean-up and one retry:**
     - `vision/sanitize.py` maps the known variants (Aplus → A+);
     - anything still outside the enum marks the slip as a failed read;
     - **one** 3.8 retry on the image, never 2.5 (the same pattern as the offer reader 2.6.0);
     - empty `PINNED_25_DOC_TYPES`.
- **Version:** bump the slip read version.
- **Tests:** enum and required-schema tests, sanitiser cases taken from the 26 failure shapes (synthetic), and the retry path.
- **Gate (paid, owner's yes):** re-run the 98 cached slips plus the 137 answer key on 3.8 with the new schema. 3.8 must score **at least as well as 2.5** on the answer key, with **0 malformed grades**. The owner's goal is "better than 2.5, not equal".
- **Stays AI:** the fallback, on 3.8 only.
- **Complexity:** medium.

### S6: TNB electricity bills and EPF statements, rules first
- **Size:** TNB has 142 live bills, 77% read by AI. EPF has 24 AI reads that look like parser cases.
- **Scope:**
  - `doc_parse.py` electricity format A (full bill) and format B (myTNB Express Payment): widen the markers and labels for the layouts the dry run shows failing, and add a gate per format.
  - `doc_parse_epf.py`: relax the all-or-nothing reading of the CARUMAN SEMASA rows, so that a split total still parses. Add the missing header variants.
- **Version:** bump `electricity_doc` MODEL_VERSION (1.0.0) and any EPF stamp the verdict reads.
- **Tests:** a synthetic example of each failing layout.
- **Gate:** the dry run on the 90 cached bills and 13 EPF statements, **plus way B (live capture) for more EPF and TNB samples: owner's yes, Q1**. Each lane must reach at least 20 documents.
- **Stays AI:** non-TNB providers (Sabah and Sarawak electricity), water bills apart from Air Selangor, and EPF photos that will not lock.
- **Complexity:** medium.

### S7: the parent IC (MyKad rules first, checked against the student)
- **Size:** 506 live parent ICs, 82% read by AI. The AI second opinion fires because the free MyKad read is "shaky", and for a parent nothing typed is there to compare it with.
- **Scope:**
  - For a parent IC, do not count "nothing to compare with" as shaky.
  - Add free consistency checks:
    - the 12 IC digits and their check pattern;
    - a birth date that is plausible for a parent (at least about 15 years older than the student);
    - the parent's name matching the student's parentage marker (the A/L or BIN surname) where the student's IC or birth certificate gives one.
  - Call Gemini only when one of those checks fails.
  - Files: `vision` IC read (`_should_gemini_ic`), `genuineness/ic.py` (unchanged model), and the parent-match code in the verdict.
- **Gate:** way B capture for the parent ICs (there are none in the corpus). Zero wrong IC numbers among the documents the rules accept. **Identity:** Opus build, Opus adversarial review, owner's phone check.
- **Stays AI:** the IC genuineness check (S8 moves it off 2.5), and blurred or angled cards.
- **Complexity:** high.

### S8: the genuineness jobs off 2.5
- **Scope:** four call sites move from `FLASH_25_CASCADE` to 3.8 with a `required` schema and one retry on a malformed answer:
  - `genuineness/ic.py:48`
  - `genuineness/results_doc.py:387`
  - `genuineness/supporting_doc.py:70`
  - `genuineness/sample_stamp.py:69`
- **Versions:** bump `results_doc` MODEL_VERSION (1.29.0), `SAMPLE_CHECK_VERSION` (1.0.0), and the new MODEL_VERSION that LL3 gives to `ic.py` / `supporting_doc.py`. If LL3 has not landed, add those versions here.
- **Gate (paid, owner's yes):** the genuineness verdicts on 3.8 must match the stored 2.5 verdicts or the reviewer's decision. No new "suspect" on a document a reviewer accepted, and no "genuine" on a known fake (the typed-fake fixtures).
- **Stays AI:** all four checks (they are judgements about images, not text).
- **Complexity:** high (it feeds verdicts).

### S9: retire the remaining 2.5 cascade tails
- **Scope:** the AI fallback models.
  - `profile_engine.py:58` `FLASH_25_CASCADE` and `:63` `MODEL_CASCADE` (its tail reaches about 15 jobs).
  - `reports/report_engine.py:36-37`
  - `courses/management/commands/map_course_careers.py:35-36`
  - `courses/management/commands/generate_stpm_headlines.py:16`
  - the registry mirror `halatuju/ai_registry.py:49-51, 91-103`
  - cosmetic mentions: `reports/views.py:45`, `models/billing.py:44` help text, web `billingUsage.ts:105`, the fixture in `contractTermsDrift.test.ts`.
- **The replacement tail:** the next non-2.5 model on Google's current list (to be confirmed then). With no second model, a 3.8 outage has no fallback, so the "AI unavailable" path must already behave safely.
- **Also:** read the **live** Cloud Run values of `CONTRACT_QUIZ_MODEL`, `APPLY_COPY_DRAFT_MODEL`, `REQUESTS_TRIAGE_MODEL` and `OFFER_RETRY_MODEL`, not the settings defaults, to prove none is set to 2.5.
- **Gate:** a smoke test only, with no paid eval: these are fallbacks or non-document jobs, and their prompts do not change. A test fails the build if any `gemini-2.5` string remains outside the tests and docs.
- **Complexity:** low.

**Total: 10 sprints (S0 to S9).**
- **Why this split:** one reviewable deliverable each; offer letters split by sample size; identity (S7) and genuineness (S8) kept separate because each needs its own Opus review and phone check.
- **Smallest useful set:** S0, S1, S2, S4 and S5 (S3 is optional).

---

## 4. The Gemini 2.5 retirement track

**10 functional uses on main.** Use 6 is already retired on the `reader-260` / `offer-course-proof` branch, so **9 remain once that merges**.

| # | Where (file:line, main) | What it does | Replacement | Paid eval? | Rough cost | Sprint |
|---|---|---|---|---|---|---|
| 1 | `vision/gemini_read.py:86` `PINNED_25_DOC_TYPES` | Reads the SPM results slip | Parser first (S4), then 3.8 + grade enum + required + one retry | **Yes** | 235 slips × up to 2 calls ≈ 470 calls ≈ **US$2** | S4 → S5 |
| 2 | `genuineness/ic.py:48` | IC genuineness markers | 3.8 + required + one retry | **Yes** | about 100 ICs ≈ **US$0.50** | S8 |
| 3 | `genuineness/results_doc.py:387` | Results slip QR and crest markers | the same | **Yes** | about 100 slips ≈ **US$0.50** | S8 |
| 4 | `genuineness/supporting_doc.py:70` | Supporting-document genuineness | the same | **Yes** | about 60 docs ≈ **US$0.30** | S8 |
| 5 | `genuineness/sample_stamp.py:69` | The "SAMPLE" stamp check | the same | **Yes** | about 40 docs ≈ **US$0.20** | S8 |
| 6 | `offer_reader.py:117` (+297-299, 306, 357) | Re-asks 2.5 for a missing reporting date | **Already replaced in 2.6.0:** a 3.8 retry, and 2.5 is refused | Done (the 2.6.0 eval) | US$0 more | Base branch |
| 7 | `profile_engine.py:58, 63` | The 2.5 tail of `MODEL_CASCADE` (about 15 jobs) | A non-2.5 fallback model | No (fallback only) | US$0 | S9 |
| 8 | `reports/report_engine.py:36-37` | The counsellor report's own cascade | the same | No | US$0 | S9 |
| 9 | `courses/.../map_course_careers.py:35-36` | The career-mapping command | the same | No | US$0 | S9 |
| 10 | `courses/.../generate_stpm_headlines.py:16` | The STPM headline command | the same | No | US$0 | S9 |

**Also:** the registry mirror (`ai_registry.py:49-51, 91-103`) follows uses 1-7. The 4 cosmetic mentions go in S9.

**Order:** 6 (with the base branch), then 1, then 2-5, then 7-10.
- **If Google announces a firm retirement date earlier,** S5 and S8 jump ahead of S2 and S3. Nothing else changes.
- **The slip fix (use 1)** works at three levels: fewer slips reach AI (S4); the schema makes a malformed grade impossible to pass silently (enum + required); and a single 3.8 retry deals with what is left. It is proved on the 137-slip answer key against 2.5's own score.

**Prices are assumed:** 3.8 Flash has no row in our price table (`offer_fresh_gemini.PRICES`). The figures assume 3.8 costs no more than twice 2.5 Flash. The base figure is the Phase 2 eval: US$2.04 for 479 documents, about US$0.004 each.

---

## 5. Rules for every sprint

- **Bump the version** wherever recognition changes: `OFFER_READER_VERSION` (2.7.0, 2.8.0, …), the slip read stamp, the genuineness `MODEL_VERSION` / `SAMPLE_CHECK_VERSION`. Record `rules_lane` on each read.
- **Adversarial review before the push.** Document recognition feeds eligibility. S1, S7 and S8 are built by Opus and reviewed by Opus; the rest are built by Sonnet and reviewed by a fresh Sonnet. The reviewer reads the diff and is not told our conclusion.
- **Paid evals only on the owner's yes,** each run cache-first, stopping on a 402 or 429 error. The owner sees the cost before each one.
- **Never re-extract locally.** Rules-first applies to **new uploads** only. Existing documents keep their stored reads. Any backfill goes through the release-decisions job with the service flags, on the owner's yes.
- **The release train:** at most 3 publishes a day (11:00 / 16:00 / 21:00 MYT), one batch, one owner yes. A push to main saves only; publishing is a separate yes. Each lane's switch is turned on in a publish, never in a push. Eligibility, identity and money changes get the owner's phone check.
- **One deliverable per sprint,** with targeted tests while building and the full suite once before the push. Personal data stays in the scratchpad corpus and never in reports, fixtures or commits.

---

## 6. Risks

1. **The AI answer is not the truth.** A lane can "agree with AI" and still be wrong. The gate scores against the hand-checked answers (`offer_expect`, the 137-slip answer key), uses the held-out split, and keeps the reviewer-overturn switch-off rule.
2. **Small lanes and new layouts.** Universities change their letter templates each intake. A strict per-document gate (markers lock + unique match) sends any new layout to AI by default, and the monthly dry-run line shows the drift. Without way C (keeping the text), that line can only use the local corpus.
3. **Data and branch dependencies.** The corpus holds personal data locally (scratchpad, to be deleted after tuning). Parent ICs have no corpus at all. S1 depends on `offer-course-proof` merging first. S8 overlaps LL3's MODEL_VERSION work. A short gap in the fallback is possible if 2.5 retires before S9 names a replacement tail.

---

## 7. Questions for the owner (3)

- **Q1.** May we (a) run a one-off **non-AI** OCR capture of the live parent ICs, TNB bills and EPF statements the corpus lacks (about 1,100 pages, US$0 to US$2), and (b) keep each new upload's OCR text in a private column deleted with the document, so future checks are free?
- **Q2.** Is the threshold right: **at least 20 documents per university or issuer, at least 98% agreement on the core fields, and zero wrong names, ICs, institutions or courses** on held-out letters? And should every 10th rules-only document also be checked by the AI for the first month (about US$0.15 a month)?
- **Q3.** May the two paid evals run when their sprints reach the gate: **slips about US$2 (S5)** and **genuineness about US$1.50 (S8)**? And should S5 and S8 jump ahead of the offer work if Google confirms a 2.5 retirement date?

---

## 8. Cost estimate (paid calls per phase)

| Phase | Paid calls | Rough cost |
|---|---|---|
| S0 dry run (corpus) | 0 | US$0 |
| Way B live capture (Cloud Vision, not Gemini; Q1) | about 1,100 pages | US$0 to US$2 |
| S1 to S3 offers (dry run on stored reads + hand answers) | 0 | US$0 |
| S4 slip gate | 0 | US$0 |
| S5 slip 3.8 eval | about 470 | about US$2 |
| S6 TNB / EPF (dry run) | 0 (after way B) | US$0 |
| S7 parent IC (dry run) | 0 (after way B) | US$0 |
| S8 genuineness eval | about 300 | about US$1.50 |
| S9 tails (smoke test only) | under 10 | under US$0.05 |
| Optional shadow check (Q2), first month | about 30 | about US$0.15 |
| **Total paid evals (Gemini)** | **about 800** | **about US$3.50 to US$4 (about RM 16 to RM 18)**, plus US$0 to US$2 for Vision |

**Running cost after the work:** each document that rules read saves about US$0.004 and one AI call. The bigger gains are certainty (the same answer every time), a hostel no longer recorded as the university, and no dependence on 2.5.
