# S16 Retrospective — Phase A deterministic anomaly engine (2026-05-29)

## What Was Built

First slice of the post-shortlist vision
(`docs/scholarship/post-shortlist-vision.md`). One commit (`886968e`):

- **`apps/scholarship/anomaly_engine.py`** — pure module, 10
  `_detect_*` functions registered in a `_DETECTORS` tuple, plus one
  `detect_anomalies(application)` aggregator returning JSON-ready
  `{code, params}` dicts. Null-safe over missing profile / docs /
  funding_need. **No LLM calls, no model writes**, all deterministic.
- **10 rules** as agreed after the user calibrated my first draft (3
  reframed, 2 new, 1 dropped):
  - `vision_nric_mismatch`, `vision_name_mismatch` — built on S13's
    OCR verdicts.
  - `address_state_mismatch` — Vision-OCR'd state ≠
    `profile.preferred_state` (W.P. prefix normalisation).
  - `jkm_high_income` — `receives_jkm=true` AND `household_income >
    RM3000`; question reframed to acknowledge JKM-for-disability /
    caregiving (JKM is family-applied, not student-applied).
  - `household_size_one`,
    `first_in_family_with_siblings_studying` (question preempts the
    school-vs-university distinction).
  - `funding_other_without_note`, `declaration_name_mismatch`
    (token-set via `vision.name_match`).
  - `str_claimed_no_doc` — new rule.
  - `device_in_funding` — new rule (RM 3,000 won't cover a laptop
    alongside other costs).
- **Three rules deferred to Phase B** (need Gemini multimodal):
  utility-bill amount vs household size, SOI content-derived questions,
  "wrong" supporting doc detection.
- **Admin UI** (`admin/scholarship/[id]/page.tsx`): new "Pre-interview
  flags" card above verify-&-accept; amber-tinted list, fact + asked
  question per entry, count chip in header, honest empty state.
- **Backend wiring**: `AdminApplicationDetailSerializer` adds
  `anomalies = SerializerMethodField`. Read-only; computed per GET (no
  cache, function is cheap and pure).
- **Frontend type**: `AdminAnomaly { code, params }` + array on
  `AdminScholarshipDetail`.

## Numbers

- 8 files changed (+708 / -3).
- Backend tests: **1211 / 1211 pass** (+23 from 1188). Composition: 20
  per-rule (1 positive + 1 negative each) + 3 integration shape tests
  (empty input, dict shape, ordering stability).
- Frontend tests: **110 / 110 pass** (no new — admin UI rendering
  not covered by jest in this repo).
- i18n parity: **1336 × en/ms/ta** (+26 keys: 5 UI scaffolding +
  10 facts + 10 questions + 1 askLabel).
- Next build: EXIT=0.
- Deploys: **1** (under the 2-deploy guideline).
- No migration, no backfill.

## What Went Well

- **The user's calibration loop was tight and high-signal.** My first
  draft taxonomy had 3 wrongly-framed rules (STR/JKM as student
  actions, when both are family-applied) and missed 3 genuinely useful
  rules (STR-claimed-no-doc; device-in-funding; utility-bill amounts).
  The user caught all of them in one round. **Worth noting**: the
  *interpretation* of what counts as "anomaly worth asking about" is
  the actual product call here — the engine code is mechanical, the
  taxonomy is judgement. Shipping the taxonomy as 10 numbered cells in
  a markdown table for sign-off (before any code) saved a re-write.
- **Plain dict + i18n-key contract works cleanly.** Backend returns
  `{code, params}` only; frontend resolves both `fact` and `question`
  text from the i18n bundle keyed by the code. Server stays locale-
  agnostic, the human copy lives in one place (and is editable without
  a backend deploy), and adding a new rule = one Python function +
  two i18n keys per locale + one test.
- **Pure rule + pure aggregator = great test surface.** 23 tests
  written in one pass; all green first try. Each detector is a small
  function over a single `application` object; no mocking needed for
  the core (only the IC document helper needed a tiny convenience
  factory).
- **Honest deferrals.** The user surfaced three good ideas that
  genuinely need Gemini (utility-bill OCR-then-extract, SOI text
  reading, wrong-doc detection). Rather than half-build them with
  brittle regex, I named them as Phase B deferrals in the same
  response. Keeps Phase A focused and honest about its scope.

## What Went Wrong

1. **Tamil queue is now 8 batches / ~85+ strings.**
   - **Symptom:** Every sprint that adds user-facing strings adds
     Tamil first-draft mirrors. S15 close flagged 7 batches; this
     sprint added another (26 strings).
   - **Root cause:** No batching gate. Each sprint ships its Tamil as
     "first-draft for refine" and the pending list grows; the user
     has to context-switch into language work at unrelated times.
   - **System change:** carrying this forward as a flag at every
     sprint close (already done). The next concrete action: offer to
     surface the full English+Tamil side-by-side as a single review
     artefact on demand before the next sprint lands. If the user
     doesn't want to refine yet, they're explicitly opting in to one
     more batch.
2. **No frontend test coverage for the new admin UI card.**
   - **Symptom:** The /admin pages don't have jest tests; the new
     "Pre-interview flags" card is render-only TS that's verified by
     `next build` (TypeScript + linting) but not by behaviour tests.
   - **Root cause:** The repo's jest tests focus on `lib/` pure
     functions, not React components. This is a longstanding gap.
   - **System change:** not addressing now — adding a component-test
     harness for admin pages is its own sprint. Mitigated by: the
     engine itself (where bugs would actually live) is 100% covered;
     the UI is just rendering server-provided data.

## Design Decisions

See `docs/decisions.md` (new entry: "Anomaly serialisation = code +
params, with copy in i18n bundle, not server").

## Carried into next sprint

- **Phase C** is the natural next slice from the vision doc: admin
  role categories (`PartnerAdmin.role`) + `assigned_to` on Application
  + `InterviewSession` model + capture UI for structured per-flag
  findings. That's the unlock for Phase D (Gemini v2 refine using
  interview findings).
- **Phase B** (Gemini gap-spotting + the 3 deferred Phase A rules
  that need multimodal) is lower priority — the deterministic engine
  likely covers 70-80% of the value; better to validate with real
  interviews on the deterministic flags before adding LLM cost.
- **Tamil-pending** queue: 8 batches / ~85+ strings. Worth a single
  refine session before more sprints land.
