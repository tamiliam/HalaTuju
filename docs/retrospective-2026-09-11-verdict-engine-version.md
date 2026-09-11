# Retrospective — the predictor now says which predictor it was

**Date:** 2026-09-11 · **Branches:** `feat/verdict-engine-version` (`8a02f8c7`, `af4b108f`) ·
**Worktree:** `.worktrees/verdict-version` · **Deployable:** api + web ·
**Migration:** `0156_verdict_engine_version` · **Data step:** 88 live rows stamped

---

## What was built

The four-fact verdict engine — the thing that predicts whether a student qualifies — now carries
`VERDICT_ENGINE_VERSION`, stamped onto each prediction as it is captured.

| Piece | Where |
|---|---|
| The version | `verdict_engine.VERDICT_ENGINE_VERSION = '2026-09-11.1'`, bump rule at the constant |
| The stamp | `ScholarshipApplication.ai_verdict_engine_version`, written beside `ai_verdict_snapshot` |
| The disclosure | `audit.override_metrics` → `engine_versions`; `AiReliabilityCard` warns when > 1 |
| The past | 88 decided rows stamped `pre-versioning` |
| The repair's door | `CronRunView.JOBS`, write switch `BACKFILL_VERDICT_VERSION_APPLY=1` |

## What prompted it

I was asked whether a change needed a "model bump" and answered by enumerating the version
constants that exist — `MODEL_VERSION` (document genuineness), `PROMPT_VERSION`, `PARSER_VERSION` —
concluding, correctly on those terms, that none applied. The owner rejected the frame:

> *"I understand the version more wholistically. The model is what predicts whether a student
> qualifies. Genuineness of the document is one stage, but it not all. Otherwise where does the
> learning from predicting and being corrected sit?"*

It sits in `ai_verdict_snapshot` against `officer_verdict`: **88 prediction/correction pairs banked
2026-06-17 → 2026-09-01**, compared per fact by `audit.compute_overrides` and shown to officers as
the AI's reliability. **It had no version.** Every generation of the predictor was averaged as one
model — and `_declared_pathway` had changed the previous day, so the mixing was already real.

## Design decisions

Recorded in full in `docs/decisions.md` (2026-09-11). In short:

- **A sibling column, not a key inside the snapshot.** Four readers iterate `ai_verdict_snapshot`
  as a list of facts; a wrapper would be a data migration plus four call sites for a value that is
  not a fact.
- **Disclose the blend, do not split the roll-up** — the owner's call (*"A now, and B in future"*).
  With 88 under one version and none under any other, per-version rates would be noise for months.
  Logged as **TD-243**.
- **Never re-run `build_verdict` over old snapshots.** A snapshot is the record of what the AI
  asserted at the time; regenerating replaces evidence with today's answer.
- **Not `MODEL_VERSION`, not `ai_registry`.** The former versions whether one document looks
  genuine; the latter answers which LLM a job would call now and *"resolves, never records"*. This
  engine calls no model at all.

## What went well

- **The owner's reframing was accepted on evidence rather than argued with.** Querying the loop
  turned an abstract disagreement about the word "model" into 88 rows and a missing column.
- **The dangerous operation was fenced before it was written.** `test_THE_SNAPSHOT_IS_NEVER_
  REGENERATED` uses a fixture snapshot the engine could never produce, so any attempt to regenerate
  shows up as the real verdict coming back. Bite-checked.
- **The deferred half was logged, not forgotten** — TD-243, with the condition that decides when.
- **Digest-matching caught what "latest revision" would not.** Other agents deploy this repo; the
  serving revision was verified against this commit's image digest, not against being newest.

## What went wrong

**1. I deployed code before its migration.**

- *What happened:* pushed `8a02f8c`, both builds SUCCESS, revisions ready, site 200, no ERROR logs —
  and `ai_verdict_engine_version` did not exist on production. `record-verdict` and
  `verdict-metrics` would both have 500'd.
- *Why:* this project is **migrate-first via Supabase MCP, then push** — stated four times in
  `halatuju_api/CLAUDE.md` — and I read past it. Worse, my own gate list ended at
  `makemigrations --check`, which compares migration FILES to MODELS and knows nothing about what
  production has recorded. **Every signal I check said "verified".** The error log was empty
  because nobody clicked, not because it worked.
- *System change:* `sprint-close.md` **step 3a already exists for this** and I had not run it. Two
  concrete fixes: (a) the deploy step for any push carrying a migration now means *apply the DDL
  and verify the column exists BEFORE the push*; (b) lessons.md carries the general form — **a
  green deploy proves the container started, not that the schema it expects is there.**

**2. I called the backfill reachable when it was only listed.**

- *What happened:* wired `backfill_verdict_engine_version` into `CronRunView.JOBS`, the door test
  passed, and I reported it runnable. It was not: the door calls a command with **no arguments**,
  and the write switch was `--apply`, so the door could only ever print.
- *Why:* I satisfied the guard instead of the thing the guard protects. `test_repair_commands_have_
  a_door` checks **registration**; the defect it was written for — *finished and unreachable looks
  exactly like finished* — reproduced one layer in, where the guard cannot see.
- *System change:* the write switch is now the env-var shape this repo prescribes for a dangerous
  one-off (*"a door you can close"*), explicitly **not** `(command, ['--apply'])`, which would make
  every call to the door write. Three tests: the env var alone writes; only the literal `'1'` opens
  it; the registered job passes no flags. Bite-checked.

**3. The backfill ran via MCP, not via its own command.** A consequence of (2), and recorded in the
command's own docstring so the next reader is not misled about what has been exercised in anger.

## Numbers

| | |
|---|---|
| pytest | **6436** (rebased onto S6) — zero failures |
| jest | **2059** / 128 suites |
| tsc | **24** — TD-221 baseline, unchanged |
| next lint | **0 Errors** |
| check-i18n | **5047 × 3** |
| `next build` | exit 0 |
| `makemigrations --check` | clean |
| migration ledger vs production | **156 files / 156 recorded — no gap** |
| bite-checks | 3, all bit |
| Data step | 88 rows → `pre-versioning`; 55 undecided left empty |

**Serving:** `halatuju-api-01030-hcf` (digest matched to `af4b108f`), web `00877-bgv`.

## What to watch

- **TD-243** — the rate still blends; split per version once a second bucket is comparable.
- **The caveat has never rendered in production.** With one bucket it cannot. Its first real test
  is the next officer decision, which will create the second version.
- ⚠ **ms and ta on `reliability.mixedEngines` are first drafts**, the Tamil especially.
