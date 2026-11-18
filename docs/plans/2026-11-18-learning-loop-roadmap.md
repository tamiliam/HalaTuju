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

---

## Sprint LL1 — Scoreboard on

**Goal.** Staff see, on the Organisation Overview and the Programme Overview, how well the AI predicts, and how that moves with time.
The message: the AI prediction matters.

**Why first.** The data exists. No reviewer work. No database change.

**Scope.**
- [audit.py](../../halatuju_api/apps/scholarship/audit.py) — extend `override_metrics`. Keep every existing key. Add:
  - per fact: `green`, `green_failed` (wrong green), `unsure`, `unsure_passed` (too careful);
  - `by_version`: the same four counts for each engine version;
  - `by_month`: the same four counts for each month of decision (this is the trend line);
  - `by_reviewer`: the same four counts for each reviewer. The endpoint returns this key to leads only (super admin, org admin; confirm the permission key at sprint start);
  - `doubt_codes`: for each `unresolved` code in the stored snapshot, how many times the human passed and failed that fact.
  - `qc_agreement` (owner note 3): how often the QC accepted the reviewer's decision, and how often he sent it back or rejected it. Total and for each month.
    Source: `StaffActivity` rows with verb `qc_decision` (`meta.decision` = accept / reopen / reject). The data exists today. Confirm the organisation scope at sprint start.
- [views_admin/verdict.py:472](../../halatuju_api/apps/scholarship/views_admin/verdict.py#L472) `AdminVerdictMetricsView` — no logic change. It already returns `override_metrics(rows)`.
- [admin-api/verdict.ts:14](../../halatuju-web/src/lib/admin-api/verdict.ts#L14) `VerdictMetrics` type — add the new keys.
- [cockpitVerdict.ts:239](../../halatuju-web/src/lib/cockpitVerdict.ts#L239) `verdictReliability` — map the new keys.
- [AiReliabilityCard.tsx](../../halatuju-web/src/components/AiReliabilityCard.tsx) — show two numbers for each fact, the doubt table, and the count behind each number.
- Placement (owner, 2026-11-18): a new "AI prediction" section on **both** Overview pages:
  - Programme Overview: [admin/programme/overview/page.tsx](../../halatuju-web/src/app/admin/programme/overview/page.tsx), as a new entry in `SECTION_RENDERERS` (`src/components/admin/overview/OverviewSections.tsx`), so it also works with `CustomiseLayout`. It reads `verdict-metrics/?cohort=`.
  - Organisation Overview: `/admin/organisation/programmes` ([ProgrammesLanding.tsx](../../halatuju-web/src/components/admin/ProgrammesLanding.tsx)). (`admin/organisation/page.tsx` is only a redirect.) It reads the same endpoint with no cohort.
  - The old hidden mount at [admin/scholarship/page.tsx:31](../../halatuju-web/src/app/admin/scholarship/page.tsx#L31) and `:338` is deleted.
- Check at sprint start: the roles that can open each Overview page against the roles that the endpoint permits. Partner and finance stay refused.
- `src/messages/{en,ms,ta}.json` — keys under `admin.scholarship.reliability`.
- Stitch screen first (HalaTuju Stitch project `10844973747787673276`). Owner approves the picture before template code.

**Design rules.**
- Always show the count, not only the percent ("6 of 84").
- Under 30 decisions for a row: show the label "few cases". No colour.
- The trend line shows one point for each month, with its count. Some months are small (September 2026 had 2 decisions).
- Everyone who can open the Overview sees the AI trend. The numbers for each reviewer are for leads only.
- Until LL2b is live, the section carries one line: "Facts not yet checked by the QC."
- The section shows one more line from day one: "The QC agreed with the reviewer's decision in 63 of 70 cases." This is the number that the funder cares about.
- Keep the two layers apart on the page: "facts" (AI against the human) and "decision" (reviewer against the QC). Do not mix them into one percent.
- Risk to watch: a reviewer who sees "the AI is right 96%" can stop checking. LL2b measures this (reviewer against the second look).
- The doubt table answers "which doubts do humans always pass?" with zero reviewer effort.
  Example from live data: `str_not_current` → 30 pass, 3 fail. `academic_missing_subjects` → 9 pass, 0 fail.

**Acceptance.**
- New pytest cases in [test_verdict_audit.py](../../halatuju_api/apps/scholarship/tests/test_verdict_audit.py): the four counts, `by_version`, `doubt_codes`, old 2-tuple callers still work.
- New jest cases in `src/lib/__tests__/officerCockpit.test.ts`, plus the first render test for the card.
- Role tests unchanged and green (`test_oversight_list_role_gates.py`, `test_org_fence.py`).
- On the live site the card totals equal a read-only count query (692 fact decisions on 2026-11-18, more later).
- Trailers: `Services: both`. No migration.

**Complexity.** Medium. About 14 files. Sonnet builds. Fresh Sonnet reviewer.

**LL1 as built (18 Nov 2026).**
- Server: `audit.py` (pure counting) and a new `prediction_metrics.py` (the database part). Section key `ai_prediction` on the Programme Overview, and the same object from `verdict-metrics/`. Counts carry green, green_failed, green_agreed, unsure, unsure_passed, rates and a `few` flag (under 30 cases). Also `fact_counts`, `by_version`, `by_month` (Asia/Kuala_Lumpur, oldest first), `doubt_codes`, `qc_agreement` and `by_reviewer` (leads only). Roles with no B40 scope get no key and no data. The section is fixed, so an organisation cannot switch it off. No migration, no new route.
- Web: `AiPredictionSection.tsx` and `AiPredictionTables.tsx`, mounted on the Programme Overview and on `/admin/organisation/programmes` (silent on 403). `AiReliabilityCard.tsx` is deleted. 36 new keys in en, ms and ta. The browser only formats.
- Two differences from the approved picture: the trend chart has no 80% axis start and no grey points (the shared `LineChart` has neither); a "few cases" month shows a pill in the values row under the chart.
- Scope: a `reviewer` (scope `assigned`) sees numbers for their own assigned applicants only, on both surfaces. The rule is in `prediction_metrics.metrics()`; the served key `counted_scope` is `"all"` or `"assigned"`, and the web shows "Your assigned applicants only." from it.
- The staff-name lookup for "By reviewer" is fenced to the caller's own organisation (a super is unfiltered); an unmatched recorder is a neutral row; no email is served. The staff Guide and FAQ are updated (English only).
- Two follow-ups (numbers taken at the push to main): `programme_overview.py` is at its growth cap and needs a split before its next change; there is no dedicated query-budget test for the `ai_prediction` section.
- Status: built in branch `ll1`. Not merged to `main`. Not published. The owner decides both.

---

## Sprint LL2 — One clear question + one-tap reason on "green → fail"

**Goal.** Every reviewer reads the tap the same way. When a human fails a fact that the engine called green, the human gives the cause with one tap.

**Owner ruling (2026-11-18, option A).** The tap is about the **student**: "Is this fact true?"
It is not a rating of the AI. The system works out if the AI was right.
The stored value does not change, so the 173 old answers stay valid.

**The clear question (new).**
- Change the box title `admin.scholarship.recordVerdict.rateTitle` (today "Rate AI Prediction") to words about the student. Draft: "Check the four facts".
- Add one help line under the title. Draft: "Pass = this fact is true for the student. Fail = it is not true, or not proven."
- The owner approves the final words in en, ms and ta before the build.
- A soft warning when a fact is Fail and the decision is Accept: "One fact failed. Do you want to accept?" It warns. It does not block.
- Files: [RateAndEstimate.tsx:52](../../halatuju-web/src/app/admin/scholarship/%5Bid%5D/view/RateAndEstimate.tsx#L52), `view/DecisionCard.tsx`, `src/messages/{en,ms,ta}.json`.

**Why only this case.** It is about 4 in 100 fact decisions. It is the dangerous error.
The opposite case ("too careful") needs no tap. The doubt table in LL1 already explains it.

**Scope.**
- Reason codes (one per failed green fact):
  `engine_wrong` (the rule is wrong) · `read_wrong` (the document was read wrong) ·
  `new_information` (interview, call, outside the documents) · `programme_rule` · `other`.
- Storage: a new key `fail_reasons` inside the existing `officer_verdict` JSON, for example `{"income": "new_information"}`. No migration.
  Checked: every reader of `officer_verdict` (9 Python files, 4 web files) reads named keys only. A new key breaks nothing.
- [views_admin/verdict.py:84](../../halatuju_api/apps/scholarship/views_admin/verdict.py#L84) `AdminRecordVerdictView.post`:
  - accept top-level `fail_reasons` in the payload; unknown code → 400;
  - keep a reason only where the human said fail **and** the server's own fresh `build_verdict` says `verified`; drop the rest;
  - a missing reason still saves. The **web** makes the tap compulsory, the server does not.
    Reason: an old browser tab, or a document that changed after page load, must never block a decision.
- Web: [RateAndEstimate.tsx](../../halatuju-web/src/app/admin/scholarship/%5Bid%5D/view/RateAndEstimate.tsx) (five chips under the fail toggle), `view/useVerdict.ts` (`failReasons` state; clear it when the fail is undone; load it in `loadVerdictState`), `RecordVerdictPayload` in [admin-api/verdict.ts:147](../../halatuju-web/src/lib/admin-api/verdict.ts#L147), the detail type in `admin-api/applications.ts`, and the locked view (show the chosen reason).
  Reuse the key → i18n label convention of `REQUEST_CATEGORIES` in `view/shared.tsx:47`.
- `audit.py` + card: count the reasons for each fact.
- i18n en/ms/ta, about 8 keys. Reviewer Guide + FAQ updated in the same change (standing rule).

**Acceptance.**
- pytest: valid code saved; bad code → 400; payload with no `fail_reasons` still saves; reasons appear in the metrics.
- jest: chips show only when engine = green and human = fail.
- Owner phone check before publish (the reviewer flow changes).
- Trailers: `Phone-check:`, `Services: both`. No migration.

**Complexity.** Low. About 14 files. Sonnet builds. Fresh reviewer.

---

## Sprint LL2b — Human check (a second look)

**Goal.** The QC checks the facts that are in doubt, inside the QC step that he already does. We then know when the first human was wrong, and when the AI was wrong.

**Why.** 6 of 23 reviewers made all 21 "wrong green" taps. One reviewer made 10. Only a second look can say who was right.

**Who (owner, 2026-11-18).** The second person is the QC. Today the QC is also the principal funder and the organisation admin.
He backs each decision with money. One person made all 70 QC decisions so far.
So the design rule is: **cost him almost nothing.** No new page. No new list to work through.

**Two layers (keep them apart).**
- **Decision** (accept, decline, send back): the funder's choice. His QC decision is the true answer for this layer. The data exists today (LL1 shows it).
- **Facts** (identity, academic, pathway, income): the documents decide. The QC's view is the best check that we have. It is still a check against the documents, not a matter of taste.
  Reason: the need signal must stay on evidence that an auditor can read.

**Scope.**
- On the QC panel (`view/QcPanel.tsx`), show a short "facts in doubt" block. It shows only:
  1. each fact where the engine said green and the reviewer said fail;
  2. each failed fact when the reviewer's decision is "accept".
  Most cases have no such fact. Then the block does not show.
- Default = agree. When the QC accepts the case and does not touch the block, the system records "QC agreed" for each fact that the block showed.
  The panel says so in one line, so the meaning is honest. One tap on a fact records "I do not agree".
- A fact that the block did not show gets no QC answer. The system does not claim that he checked it.
- A case that never reaches QC gets no second look. Decide at sprint start if a small sample of those cases is needed.
- Server: `AdminQcDecisionView` (route `admin/scholarship/applications/<pk>/qc-decision/`) accepts the fact answers with the QC decision.
- Storage: prefer a key in existing JSON (no migration). Decide at sprint start from the reader check.
- `audit.py` + the Overview section gain "checked" numbers:
  - AI against the QC (label it "checked by the QC", not "true");
  - each reviewer against the QC (leads only).
- First batch: the 21 + 5 cases that exist on 2026-11-18, plus the 7 cases where the QC did not agree with the decision. A lead can open each one from a list link. No bulk screen.
- More than one organisation: the QC and the numbers are for each organisation. One funder's choice never trains another funder's score.
- Reviewer Guide + FAQ updated in the same change.

**Known limit (accepted).** Nobody checks the QC on the facts. He carries the money, so his answer stands. The page says "checked by the QC", so no reader takes it for more.

**Not in scope.** The second look does not change a student's decision. A wrong decision goes through the normal re-open route, by a person.
The engine does not learn "what the funder likes". It learns facts. The funder's choice is a number on the page, not a rule in the engine.

**Acceptance.**
- pytest: the block holds the two groups; a silent QC accept records "agreed" only for the shown facts; a tap records "not agreed"; the "checked" numbers use it; the existing QC separation rule still refuses a person's own case.
- Role tests: only QC and leads can record a second look.
- Owner phone check before publish.
- Trailers: `Phone-check:`, `Services: both`.

**Complexity.** Medium. About 15 files. Opus builds (it touches the decision flow). Adversarial review before push.

---

## Sprint LL3 — Version guard + one version register

**Goal.** A logic change without a version change fails the tests. One file lists every model and its version.

**Scope.**
- New module `apps/scholarship/model_registry.py`: one entry per model — name, where the version constant lives, the source files that can change its answers.
  Models: verdict engine; genuineness families (`results_doc`, `salary_doc`, `electricity_doc`, `water_doc`, `school_leaving_doc`, `sample_stamp`); `offer_reader`; parsers (`offer_parse`, `stpm_parse`, `matric_parse`, `poly_diploma_parse`).
- New tracked folder `apps/scholarship/model_versions/`: **one JSON file per model**, append-only:
  `{version: {digest, note, also_ok: [], py: "3.11"}}`. This folder is also the one version register and change log.
- Fingerprint (`digest`) = sha256 of `ast.dump` of each listed file, after the test drops docstrings and the line that sets the version constant.
  So comments, blank lines and the bump itself do not count.
  `ast.dump` differs between Python versions. Docker and Cloud Build both pin 3.11. On another version the test skips with a message.
- Verdict engine file list (explicit): `verdict_engine.py`, `verdict_identity.py`, `verdict_academic.py`, `verdict_income_salary.py`, `verdict_income_str.py`, `verdict_pathway.py`, `verdict_caps.py`, `verdict_ladder.py`, `start_year.py`, `higher_results.py`, `requirements.py`, `document_snapshot.py`, `genuineness/bands.py`, `income_engine/*.py`.
- AI-backed scorers also list `halatuju/ai_registry.py`. A switch of the Gemini model then forces a version change (the admitted miss of 2026-11-16 was this case).
- New guard test `apps/scholarship/tests/test_model_versions.py`, built like `TestTheRegistryCannotGoStale` in [test_ai_registry.py](../../halatuju_api/apps/scholarship/tests/test_ai_registry.py):
  - the current version of each model has an entry, and its digest (or one `also_ok` digest) equals today's source;
  - completeness: an `ast.walk` over `verdict_engine.py` finds every lazy `from .x import`; each module must be in the list or in a reasoned `_NOT_LOGIC` set;
  - "guard the guard": the walk must find `verdict_ladder` and `income_engine`;
  - paths start from the test file's own folder (a worktree copy under `.worktrees/` must not be read by mistake).
  - A change with no behaviour change adds an `also_ok` digest with a written note.
- Merges: two branches that bump the same model collide in one file. That is loud, and that is correct. Two branches that change logic with no bump merge clean, then the test fails. That is also correct.
- Models with no version today:
  - `genuineness/stpm_doc.py` joins the file list of `results_doc.MODEL_VERSION` (it already shares that version). No new constant.
  - `genuineness/ic.py` and `genuineness/supporting_doc.py` get `MODEL_VERSION = '1.0.0'` under the same guard, and add `model_version` to the result they return. The result is stored whole in `vision_fields['authenticity']` (confirm in `vision/ic.py` at sprint start).
- A new test under `apps/scholarship/tests/` runs in Cloud Build with no extra wiring.
- `docs/technical-debt.md` — close or update TD-243.

**Not in scope.** No back-fill of the 1,053 old ID-card results. They stay "no version". Never re-run document reads to add a stamp.

**Acceptance.**
- Change one logic line in a registered file with no version change → the guard test fails with a plain message that says what to do.
- Change only a comment → the guard test passes.
- New ID-card and supporting-document results carry `model_version`.
- Trailers: `Services: api`. No migration.

**Complexity.** Medium. About 10 files plus one JSON per model. Opus builds (it touches identity scoring files). Adversarial review before push.

**LL3 as built (19 Nov 2026).**
- Register: `apps/scholarship/model_registry.py` lists 14 models, each with its version constant, its source files and its cross-file pins. The pins cover the Gemini model cascades in `profile_engine` and some helpers. One append-only JSON log per model in `apps/scholarship/model_versions/` (version, digest, note, `also_ok`). The planned `py` field was dropped, because the digest no longer depends on the Python version.
- Digest: a sha256 of cleaned source text (comments, docstrings and blank lines removed, except inside multi-line strings; the version line dropped). It is NOT `ast.dump`: this machine runs Python 3.13 and production runs 3.11, and `ast.dump` differs between them. Cleaned text lets the guard run on every Python version.
- Guard: `tests/test_model_versions.py` fails when a registered source or pin changes without a new version and log line, and when a `*VERSION` constant in the app is neither registered nor given a reason. Changing only a comment passes.
- Known gap: about 30 helper modules imported by the verdict engine's files are not in its digest. They are listed with reasons in the guard, so a change there can still ship under the old version.
- The guard has run on Python 3.13 only. Cloud Build runs after a push to `main`, so it is not a before-merge check: its first run on 3.11 is the proof, and it fails closed (the build goes red, nothing wrong ships). A hand run on a 3.11 interpreter before merge is better if one is available. A pinned sample in the test (cleaned text and digest) makes any difference show at once. The 72 registered and pinned files were scanned: none has a multi-line f-string, a BOM or a form feed, so the digests should match.
- Review round (19 Nov 2026). Pins now follow their own imports: the walk that covers model files also covers each pin, so a pinned helper that imports another file fails the guard until that file is pinned or recorded with a reason. This added pins to `matric_parse` (`academic_engine._group_rows`), `offer_reader` (name and IC helpers in `vision/names.py`, `vision/judge.py`, `name_order.py`) and `school_leaving_doc` (`bands.GENUINE_MIN`, `stpm_doc.STPM_LISTS`). The version line must now be one plain string on lines of its own, set once; anything else is an error, because dropping it could hide logic. A pin drops the pinned module's own version line, so a `results_doc` bump no longer turns `school_leaving_doc` red. A module that changes a pinned name after defining it (`C += ...`, `C.insert(...)`, `C[k] = ...`) is refused. The seeded digests of `matric_parse`, `offer_reader` and `school_leaving_doc` were updated in place: nothing is live yet.
- Gaps the guard still cannot see (listed with reasons in the guard, `_KNOWN_GAPS_OUTSIDE_THE_WALK`):
  - settings that switch model behaviour outside any digest: `OFFER_RETRY_MODEL`, `SGD_TO_MYR_RATE`, `SAMPLE_CHECK_ENABLED`;
  - decision logic in files no model registers: `genuineness/__init__.assess` (which scorer each document goes to, and the STR fallback to the holistic read) and `vision/authenticity.py` (an old 'unrecognised' offer stored as 'suspect'; an empty OCR gives no signal);
  - the logs are append-only by convention plus two checks (last entry = current version; no repeated keys). Editing the current entry's digest in place, deleting old entries, or a version that goes backwards is caught by review only;
  - the `*VERSION` census only sees names ending in VERSION inside `apps/scholarship`;
  - the glob `income_engine/*.py` also reads untracked local files, so a scratch file there turns the guard red on that machine only;
  - the "pinned name changed later" refusal covers import-time, module-level statements only. It does NOT see a change made inside a function that is then called (`def _init(): CASCADE.append('b')`), a `global` rebind inside a function, an alias (`ALIAS = CASCADE; ALIAS.append(...)`), or `globals()[...]` / `setattr(...)`.
- Review round 2 (19 Nov 2026). A pin now refuses a name it uses that is set only inside a top-level `if` / `try` / `with` / `for` block (`try: LIMIT = 0.7` then `CASCADE = [LIMIT]`), since the pin would not read it. The `misfiled_as` exemptions now excuse only that pin's closure, not the whole `school_leaving_doc` model. The digest tests moved to `tests/test_model_digest.py` to keep both test files under the 600-line cap. No digest moved.
- ID card and supporting documents: `genuineness/ic.py` and `genuineness/supporting_doc.py` registered as `ic` and `supporting_doc` at 1.0.0; each new result carries `model_version`. Storage confirmed: the ID-card result is stored whole in `vision_fields['authenticity']` by `vision/ic.py`; the supporting-document result reaches storage through `vision/authenticity._auth_str` (STR holistic fallback), which dropped the version until a small fix in this sprint. Every Python and web reader reads named keys only, so the new key is harmless.
- No back-fill of old ID-card results. They stay "no version".
- Status: built in branch `ll3` (on top of `ll1`). Not merged to `main`. Not published. The owner decides both.

---

## Sprint LL4 — Record what fed each decision

**Goal.** At decision time, store a PII-free record of the inputs. Later we can tell "same evidence" from "evidence moved".

**Scope.**
- At save time in `AdminRecordVerdictView.post` (near [verdict.py:127](../../halatuju_api/apps/scholarship/views_admin/verdict.py#L127)), next to `ai_verdict_snapshot`, store:
  - for **every live document** of the application (one query): document id, `doc_type`, family member, upload time, stored genuineness status, `model_version`, reader/parser version.
    All documents, not only "documents used": some engine helpers run their own queries, so a "used" list would miss some.
  - the version of every model in the LL3 register;
  - one **evidence fingerprint**: a keyed hash (HMAC) over the sorted documents and a short fixed list of the declared fields that the engine reads.
- No names. No NRIC. No income figures. Ids, types, statuses, versions and a hash only.
- Storage: one new JSON column `ai_verdict_context` on `ScholarshipApplication` in [models/applications.py](../../halatuju_api/apps/scholarship/models/applications.py), beside `ai_verdict_engine_version`.
  Not inside `ai_verdict_snapshot`: the web shows each list element as a fact tile, so a fifth element makes a ghost tile.
  One additive migration (next number after `0213`). The owner applies it **before** the publish (a write to a missing column fails).
- New pure helper `apps/scholarship/verdict_context.py` builds the record.
- If the record cannot be built, the decision still saves. The error goes to the log with no PII.
- Not now: the confidence band (Certain / Probable / Unsure). The web computes it. The snapshot already holds every input, so it can be computed later.
- Schema documentation updated.

**Acceptance.**
- pytest: the record is built; it holds no PII field (an explicit allow-list test); the fingerprint is stable for the same evidence; it changes when a document is replaced.
- Old decided rows stay valid with an empty record.
- Trailers: `Migration: <name> (additive)`, `Services: api`.

**Complexity.** Medium. About 10 files. Opus builds. Adversarial review before push.

---

## Sprint LL5 — Replay: score each version against human answers

**Goal.** One PII-free report: for each engine version, "wrong green" and "too careful" on the same set of past cases.

**Scope.**
- Do **not** build a second harness. Add one lens to the A5 replay harness
  ([2026-11-13-a5-replay-design.md](2026-11-13-a5-replay-design.md); code at `halatuju_api/apps/scholarship/eval/replay/`).
- The lens runs today's engine over decided cases whose evidence fingerprint (LL4) did not change, and compares the result with `officer_verdict`.
- Same five read-only safety layers as A5 (read-only role, `BEGIN READ ONLY`, always roll back, statement filter, no keys). Session pooler port 5432, never 6543.
- Where a second look by the QC exists (LL2b), the report uses it as the checked answer. The report shows both scores.
- Output: counts and hashes only.
- When it runs: after a release that changes a model version, and once a week. Not before every publish.
  Reason: production data cannot be copied to a home machine, and the candidate code is not on a server before `live` moves.
- A short workflow note says how to read the report and when a result blocks the next release.

**Depends on.** A5 sprints R1 and R2 (on the advisor queue) and LL4.
Cases decided before LL4 have no fingerprint. They enter the report as "evidence state unknown".

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
