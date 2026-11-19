# HalaTuju learning loop — roadmap for steps 1 to 3

Status: APPROVED by the owner on 2026-11-18. Nothing is built yet. The owner sets the start date of each sprint.

Updated 2026-11-18 (same day, two owner ideas, owner chose option A):
1. Humans make mistakes too. The tap means "is this fact true for the student?" (owner ruling A). The words on the box change (LL2). A second person checks a small list (new sprint LL2b).
2. The scoreboard is a trend line on the Organisation Overview and the Programme Overview (LL1), not a hidden card for the super admin.

Updated 2026-11-18 (third owner note): the QC is also the principal funder and the organisation admin. He backs his decision with money.
3. The second person in LL2b is the QC. His second look rides on the QC step that he already does. No new page. Almost no new taps.
4. Two layers stay apart. The **facts** come from the documents. The **decision** belongs to the funder. The scoreboard also shows how often the QC agrees with the reviewer's decision (LL1).

## Context

The owner asked for an audit of the HalaTuju prediction chain (2026-11-18).
The chain decides four facts for each student: identity, academic, pathway, income.
The design intent was a model that learns from each human decision.

The audit found that the system **stores** the lesson but does not **use** it.

| Finding (live counts, 2026-11-18) | Number |
|---|---|
| Decided applications (engine answer + human answer both stored) | 173 |
| Fact decisions | 692 |
| Engine said green, human said fail ("wrong green") | 21 of 541 (3.9%) |
| Engine was not sure, human said pass ("too careful") | 133 of 151 (88%) |
| Scoreboard card | Built, but hidden since 2026-06-13 |
| Structured reason when a human fails a green fact | None (free text only) |
| Inputs of a decided case | Not frozen. Documents change after the decision. |
| Version bump when logic changes | Habit only. No check. One admitted miss. |
| Stored ID-card results with no version | 1,053 |
| Reviewers who made the 21 "wrong green" taps | 6 of 23 (one reviewer made 10) |
| Cases with a failed fact, but the student was accepted | 5 |
| Cases with all four facts passed, but the student was declined | 39 (can be normal: merit, interview) |
| QC decisions so far | 70, all by 1 person (the funder) |
| QC agreed with the reviewer's decision | 63 of 70 (24 recommended, 39 declined) |
| QC did not agree | 7 of 70 (6 sent back, 1 rejected) |

**The human answer is not always the true answer.** The box title is "Rate AI Prediction" and the buttons say "Pass" / "Fail".
The code reads the tap as "this fact is true for the student". A reviewer can read it as "the AI did well".
The stored data cannot tell the two readings apart. So the 3.9% is not a safe number until a second person checks a sample.

So today we cannot say: "version X is better than version Y".
We also cannot trace an error to the version that made it, in every case.

**Outcome wanted:** each model version gets a score against real human answers.
A logic change cannot ship without a version change. Reviewers do almost no extra work.

The owner approved a plan for steps 1 to 3 of the audit list:
1. Turn the scoreboard on.
2. One-tap reason when a human disagrees.
3. Freeze the inputs. Replay each new version. Force the version change.

## Roadmap in one view

Six small sprints. Code name **LL** (learning loop).

| Sprint | Deliverable | Audit step | Size | Reviewer sees a change? | DB migration |
|---|---|---|---|---|---|
| LL1 | Scoreboard on: trend line on the two Overview pages | 1 | Medium | Yes (a new section to read) | None |
| LL2 | One clear question + one-tap reason on "green → fail" | 2 | Low | Yes (new words, one rare tap) | None |
| LL2b | Human check: the QC checks the facts in doubt, inside the QC step | 2 | Medium | QC only (one small block) | Decide at sprint start |
| LL3 | Version guard + one version register | 3 (force) | Medium | No | None |
| LL4 | Record what fed each decision | 3 (freeze) | Medium | No | One additive |
| LL5 | Replay: score each version against human answers | 3 (replay) | Medium | No | None |

**Why six:** each sprint is one deliverable that the owner can check alone.
Each sprint touches fewer than 20 files. LL1, LL2 and LL3 do not depend on each other.
LL2b needs LL2 (the question must be clear before a second person judges the answers).
LL4 needs LL3. LL5 needs LL4 and the A5 replay harness.

```
LL1 ──────────────────────┐
LL2 ──► LL2b ─────────────┤
LL3 ──► LL4 ──► LL5 ◄── A5 replay harness (sprints R1, R2 — already designed)
```

### Status and plan forward (2026-11-19)

**Built.** LL1, LL2, LL2b, LL3 and LL4 are built and reviewed. They were saved to `main` on 2026-11-19
(landing order: the Requests work, then the OCR-first work, then this stack). Nothing is published.
Before a publish the owner applies migration `0218_application_verdict_context` by hand and does the phone checks.
**Left.** LL5 only; it starts when LL4 is live.

**Who owns what (owner ruling 2026-11-19).**
- The **HalaTuju lead session** owns the A5 replay: branch `a5` (R1 + R2, built 13-14 Nov) and the R3 run.
- The **learning-loop session** owns this stack and LL5. It does not touch `a5`.

**Order of work.**
1. DONE 2026-11-19: the stack was brought up to date with `main` and saved to `main` (not published).
2. Owner applies the migration 0218 SQL by hand, does the three phone checks, then says "publish".
   The publish goes in a release slot **outside** the A5 replay window (rule: no deploy during the replay).
   The learning-loop session sends the commit list to the HalaTuju lead before the publish.
3. The HalaTuju lead (its plan, 2026-11-19): bring `a5` up to date with `main` and land R1 + R2 on `main` **before** the run;
   then a new step **R2b** (add the engine changes made after 14 Nov to the ruling catalogue; check the 25 adapters
   that were tested on made-up data only; confirm the readers accept the new 0218 column); then R3 with the owner.
   **The R3 date is not set.** The owner picks it after `a5` is on `main`. Until the HalaTuju lead sends the date, there is no no-deploy window.
   Steps 1-2 and step 3 do not depend on each other; only the publish and the replay run must not overlap.
   Whoever lands on `main` second brings their branch up to date. The overlap should be docs only (`CHANGELOG.md`, `docs/technical-debt.md`).
4. LL5 starts when the replay code (R1 + R2) is on `main` (the HalaTuju lead sends word) and LL4 is live.
   It adds one lens; it builds no second harness.

**For the replay.** This stack changes no scoring logic and no engine answer, so it should add no old-vs-new difference.
After migration 0218 the application table has one new column (`ai_verdict_context`).

**Aligned with the OCR session (2026-11-19, on the owner's word).** The OCR session leads `docs/plans/ocr-first-roadmap.md`. Its open branch is `ocr-visible`: a PDF with an invisible text layer is read from the visible page (Cloud Vision), not from its hidden text.
- **Objectives fit.** The OCR work makes the reader better. This stack measures it: LL3 and LL4 record which model version each verdict saw; the LL2 reason `read_wrong` and the LL2b QC disagreement are the **one** human feed for "the reader was wrong". The OCR session builds no feedback store of its own. LL5 will report the feed per model version.
- **Overlap, measured with git.** Only `CHANGELOG.md` is changed by both. No shared code file. No migration clash (`ocr-visible` has none; the LL migration stays here, renumbered 0218 after the requests work landed on main).
- **The one real link is the LL3 guard.** `ocr-visible` moves genuineness `MODEL_VERSION` 1.29.0 to 1.31.0 and `OFFER_READER_VERSION` 2.6.0 to 2.7.0, and edits helper files that other models' digests may follow (`pdf_pages.py`, `spm_cert_parse.py`, `vision/ocr.py`, `vision/field_extraction.py`). Whoever lands on `main` second runs `test_model_versions.py` and `test_model_digest.py`, and for each model the guard names, bumps the version and its `model_versions/<model>.json` entry. Never re-seed a digest without a version bump.
- **Answers do change on their side, for a narrow set** (new reads of invisible-layer PDFs; no automatic backfill). LL4 needs no change: the version bump is the marker. The OCR session tells the HalaTuju lead for the replay catalogue.
- **Order.** `ocr-visible` aims for `main` around 20 Nov. Whoever lands second brings their branch up to date. This session tells the OCR session when LL3 is on `main`.

---

## Sprint LL1 — Scoreboard on — DONE (2026-11-18; saved to `main` 2026-11-19, not published)

Built: an "AI prediction" section on the Programme Overview and the Organisation Overview (`/admin/organisation/programmes`): green and too-careful counts per fact, by engine version, by month (trend), the doubt table, how often the QC agreed with the reviewer, and by reviewer (leads only). Counts always shown; under 30 cases reads "few cases". A reviewer sees assigned applicants only. The old hidden card is deleted. No migration. Detail: `CHANGELOG.md` (LL1 entry), the Guide and FAQ ("What does the AI prediction block mean?"), `halatuju_api/apps/scholarship/prediction_metrics.py` and `audit.py`.

Open known gaps:
- Two differences from the approved picture: the trend chart has no 80% axis start and no grey points (the shared `LineChart` has neither); a "few cases" month shows a pill under the chart.
- The Programmes landing shares one payload and keeps the all-programmes note, so the assigned-only note shows on the Organisation Overview surface only.
- `programme_overview.py` is at its growth cap (839 lines); it needs a split before its next change. Tracked as TD-675.
- No dedicated query-budget test for the `ai_prediction` section. Tracked as TD-674.
- Guide and FAQ are English only (they have no ms/ta copy).

---

## Sprint LL2 — One clear question + one-tap reason on "green → fail" — DONE (2026-11-19; saved to `main` 2026-11-19, not published)

Built: the rating box reads "Check the four facts" with a one-line help (the tap is about the student, owner ruling A). Failing a fact the engine showed green asks "Why is this fact not true?" with five reasons (`engine_wrong`, `read_wrong`, `new_information`, `programme_rule`, `other`), stored in `officer_verdict.fail_reasons`; a soft warning shows when a fact failed and the decision is accept. The reason counts show on the AI prediction card. No migration. The server never refuses a missing reason; the web holds Save. Detail: `CHANGELOG.md` (LL2 server and web entries), `apps/scholarship/fail_reasons.py`, the Guide and FAQ. The approved strings are in the message files.

Open known gaps:
- A recorded decline from before LL2 with a failed green fact cannot be re-saved until a reason is picked (web only). Tracked as TD-683.
- The warning says "One fact failed" for two or more failed facts. Tracked as TD-682.
- Guide and FAQ are English only.

---

## Sprint LL2b — Human check (a second look) — DONE (2026-11-19; saved to `main` 2026-11-19, not published)

Built: the QC (also the funder) checks the facts in doubt inside the QC step. A "Facts in doubt" block shows on the QC panel only when a fact is in doubt (AI green and reviewer fail, or a failed fact with an accept); doing nothing agrees with the reviewer, one tap disagrees (`officer_verdict.qc_fact_checks`, and the `qc_decision` activity meta). The AI prediction card shows the "checked by the QC" counts, and leads see them by reviewer. The second look never changes a decision. No migration. Detail: `CHANGELOG.md` (LL2b entries), `apps/scholarship/second_look.py`, the QC Guide section "Facts in doubt", `docs/decisions.md` (2026-11-19).

Open known gaps:
- A QC tab loaded before the reviewer re-recorded the same facts in doubt can still save "agreed" (fix: send `verdict_decided_at`). Tracked as TD-671.
- A verdict record that is not a dict is skipped with no log line. Tracked as TD-672.
- Not confirmed: what `reopen_decision` does to `verdict_decided_at` for the second look. Tracked as TD-673.
- The QC panel does not show the stored answers after the decision; on Reopen or Reject silence records nothing; a reviewer re-record drops the answers, so sent-back cases are undercounted on screen (LL5 counts them from the activity meta). Tracked as TD-681.
- The first batch of old cases (21 + 5 + 7) was left out by the owner on 2026-11-19. Build it only if the owner asks; it then needs a picture first. No sample of cases that never reach the QC.
- The block shows "Recommend" where the Guide says "Approve" (the cockpit's own key). Change that key separately if "Approve" is wanted.
- No two-fact QC surface in the mobile sandbox: a new surface needs mobile-check baselines.
- A super's numbers are platform-wide (as LL1). Nobody checks the QC on the facts (accepted; the page says "checked by the QC").

---

## Sprint LL3 — Version guard + one version register — DONE (2026-11-19; saved to `main` 2026-11-19, not published)

Built: `apps/scholarship/model_registry.py` lists 14 models (version constant, source files, cross-file pins); `apps/scholarship/model_versions/<model>.json` is one append-only log per model; `tests/test_model_versions.py` and `tests/test_model_digest.py` fail when a registered file or pin changes without a new version and log line, or when a `*VERSION` constant is neither registered nor excused. The digest is a hash of cleaned source text (not `ast.dump`, which differs between Python 3.11 and 3.13). `genuineness/ic.py` and `supporting_doc.py` now carry `MODEL_VERSION = '1.0.0'` and each new result stores it; no back-fill. Brought up to main's verdict-engine bump before the first merge; two digests were re-seeded with dated notes (main moved the IPTS reason texts into constants, same text). Detail: `CHANGELOG.md` (LL3 entry), `docs/decisions.md`, `docs/technical-debt.md` (TD-243, still open until live).

Open known gaps:
- About 30 helper modules the verdict engine's files import are not in its digest (listed with reasons in the guard). Held by TD-243. The PDF text-layer modules added by main (OCR S-visible) are unpinned too: TD-685.
- The IPTS names the verdict engine reads through `offer_private` are a known gap, not pinned. Tracked as TD-677.
- Outside the guard's walk (`_KNOWN_GAPS_OUTSIDE_THE_WALK`): the settings `OFFER_RETRY_MODEL`, `SGD_TO_MYR_RATE`, `SAMPLE_CHECK_ENABLED`; `genuineness/__init__.assess` and `vision/authenticity.py`; the logs are append-only by convention plus two checks; the `*VERSION` census sees only `apps/scholarship`; the glob `income_engine/*.py` also reads untracked local files; a pinned name changed inside a called function, by `global`, an alias or `setattr`. Tracked as one row, TD-684.
- The guard has run on Python 3.13 only. Its first run on 3.11 is Cloud Build after the push; it fails closed.
- `model_registry.py` is at 599 of 600 lines: split before the next model. Tracked as TD-676 (with `applications.ts`, now exactly 600).

---

## Sprint LL4 — Record what fed each decision — DONE (2026-11-19; saved to `main` 2026-11-19, not published)

Built: `apps/scholarship/verdict_context.py` builds a PII-free record `{schema, documents, models, fingerprint, key_check}`, stored in `ScholarshipApplication.ai_verdict_context` in the same save as `ai_verdict_snapshot`. The fingerprint is an HMAC over the live documents, the declared fields, the profile fields, the intake rules and the stage facts the engine reads (key derived from `SECRET_KEY`, no new env var). A record that cannot be built never blocks a decision (`{schema, error}`). No serializer lists the column. Old rows keep `{}` (no back-fill). Migration `0218_application_verdict_context` (additive, hand-written SQL in its docstring): THE OWNER APPLIES IT BEFORE THE PUBLISH, otherwise every application load fails. Detail: `CHANGELOG.md` (LL4 entry), the model's `help_text` and the migration docstring (there is no separate schema document).

Open known gaps:
- The fingerprint covers this application's documents only; some helpers read the student's OTHER applications. Tracked as TD-679.
- The clock is not in the fingerprint (salary-slip age and date checks). LL5 sets today to `verdict_decided_at`. Tracked as TD-679.
- The live programme catalogue (when no `requirements_snapshot`) and the course catalogue (the IPTS rule) are not in the fingerprint. Tracked as TD-678.
- Settings that switch model behaviour (LL3's gaps) and `SGD_TO_MYR_RATE` are not in the fingerprint. Tracked as TD-678 and TD-679.
- The stage facts move at QC accept or reject (in review to decided). LL5 must hash under the stage as at the decision (`evidence_fingerprint` takes the stage), or report those cases apart.
- A `SECRET_KEY` rotation makes older fingerprints impossible to compare (`key_check` tells it apart). LL5 must run where the production key is.
- The `_CODE` mask lets a single word of up to 40 characters through; the real protection is the fixed choice lists. Backstop only.

---

## Sprint LL5 — Replay: score each version against human answers

**Goal.** One PII-free report: for each engine version, "wrong green" and "too careful" on the same set of past cases.

**Scope.**
- Do **not** build a second harness. Add one lens to the A5 replay harness
  ([2026-11-13-a5-replay-design.md](2026-11-13-a5-replay-design.md); code at `halatuju_api/apps/scholarship/eval/replay/`).
- The lens runs today's engine over decided cases whose evidence fingerprint (LL4) did not change, and compares the result with `officer_verdict`.
- Same five read-only safety layers as A5 (read-only role, `BEGIN READ ONLY`, always roll back, statement filter, no keys). Session pooler port 5432, never 6543.
- Where a second look by the QC exists (LL2b), the report uses it as the checked answer. The report shows both scores.
- LL2b's numbers undercount overturned facts on sent-back cases (a reviewer re-record drops the answers); count those from the `qc_decision` activity meta (`qc_disagreed`, `doubt_*`), which survives.
- Output: counts and hashes only.
- When it runs: after a release that changes a model version, and once a week. Not before every publish.
  Reason: production data cannot be copied to a home machine, and the candidate code is not on a server before `live` moves.
- A short workflow note says how to read the report and when a result blocks the next release.

**Depends on.** A5 sprints R1 and R2 and LL4. R1 and R2 are built on branch `a5` (13-14 Nov), not on `main`.
The HalaTuju lead session owns `a5` and the R3 run (owner ruling 2026-11-19). LL5 starts when that code is on `main`.
Cases decided before LL4 have no fingerprint. They enter the report as "evidence state unknown".
The replay runs with "today" set to `verdict_decided_at` and the stage as at the decision (LL4 known gaps: the clock and the stage), or reports the clock-dependent cases apart.

**Acceptance.**
- A dry run on a local test database gives the expected counts.
- The owner runs the job once. The report shows a score for each version.
- No PII in the output (test).

**Complexity.** Medium. About 10 files. Opus builds.

---

## Models for the build (house standard: `Settings/_workflows/credit-discipline.md`)

Every agent call names its model. The lead stays thin. One phase for each build agent. At most 2 builders at once in the project.

| Job | Model |
|---|---|
| Explore the code, run the gates and the test queue | Haiku |
| Build LL1 and LL2 (routine: display, words, one tap) | Sonnet |
| Build LL2b, LL3, LL4, LL5 (decision flow, identity scoring files, replay safety) | Opus |
| Read the diff of LL1 and LL2 (a fresh agent, not the builder) | Sonnet |
| Read the diff of LL2b, LL3, LL4, LL5 (fresh agent, adversarial review before the push) | Opus |
| Look at a picture or a PDF (Stitch screen, screenshot) | A short-lived agent |

## Owner steps (the only work for the owner)

1. Approve this roadmap.
2. LL1: approve the Stitch picture. Say yes to the publish.
3. LL2: approve the new words (en, ms, ta). Phone check. Say yes to the publish.
4. LL2b: the second person is the QC (settled 2026-11-18). Phone check. Say yes to the publish.
5. LL3: say yes to the publish.
6. LL4: apply one migration by hand. Say yes to the publish.
7. LL5: run the replay job. Read one report.

## Not in this plan

- Audit step 4 (weekly list of new document shapes) and step 5 (proven green facts skip the human tick).
- Any change to a rule that decides eligibility or money.
- Any paid AI call. Any re-read of stored documents.
- Back-fill of old rows.

## Verification (end to end)

- While building: targeted tests only (`pytest apps/scholarship/tests/test_verdict_audit.py`, the new guard test, the jest file).
- Once before each push, through the queue:
  `python Settings/_tools/test_queue.py -- <full pytest command>` and `python Settings/_tools/test_queue.py -- npm run gates`.
- After each publish: read the Cloud Build status. Then compare the card with one read-only count query (counts only, no names).
- LL3: prove the guard by hand once (edit a logic line, see the test fail, undo).
- LL5: compare the replay counts with the LL1 card for the same versions.

## After approval

- Add LL1–LL5 (and LL2b) to the HalaTuju queue. The owner sets the dates.
- Start LL1 with `Settings/_workflows/sprint-start.md`.
