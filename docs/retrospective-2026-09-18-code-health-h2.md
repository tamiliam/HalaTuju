# Retrospective — Code health H2: the tests run before every deploy

**Date:** 2026-09-18 · **Roadmap:** `docs/plans/2026-09-18-code-health-roadmap.md` · **Sprint:** H2 of H19
**Built by:** an Opus 5 agent (the two config files, rollback artefacts, docs); the lead kept every
step that touches production — the spikes, the trigger switch, the push and the watch.
**Freeze status:** in force. Two of the ten sprints to *stabilised* are done.

## What Was Built

- **`halatuju_api/cloudbuild.yaml` and `halatuju-web/cloudbuild.yaml`.** Each reproduces its live
  inline trigger steps — the argument lists were compared programmatically and are **identical** —
  and adds a `test` step that runs **in parallel** with the image build. `Push` waits for both
  `test` and `Build`; `Deploy` waits for `Push`. A red suite means the image is never pushed.
  - api: `manage.py check`, `makemigrations --check --dry-run`, `pytest -q -n auto` on SQLite.
  - web: `npm ci`, `npm run gates` (typecheck, lint, i18n parity, jest).
- **Both Cloud Build triggers now read those files** instead of holding an inline config. Every
  other trigger field is unchanged: substitutions, `includedFiles` / `ignoredFiles`, service
  account, tags. The filters are written into each file's header, so they exist in the repo for the
  first time.
- **An escape hatch.** A manual run with `_SKIP_TESTS=1` skips the gate and prints a banner that
  says so. A flaky test must never be the reason a hotfix cannot ship.
- **Rollback artefacts:** `docs/infra/cloudbuild-trigger-{api,web}-inline-2026-09-18.yaml`, each
  headed with the one command that restores it.

## What Went Well

- **The spike did its job twice.** Both spike builds (test + image build, no push, no deploy)
  failed on the first run, for two different reasons, and nothing was deployed. Both were fixed and
  seen green before a trigger was touched. The production switch then worked first time.
- **The agent caught what the brief missed:** `build.tags` would have been silently dropped by the
  move to `filename:`. It reproduced them. It also kept the exported step ids, so build history
  reads as it always has.
- **The accidental bite-check was a real one.** In the first web spike the `test` step failed and
  Cloud Build **cancelled** the parallel `Build`. That is the gate working.

## What Went Wrong

**1. A web test had only ever run on the wrong Node.**
- *Symptom.* `screenshotInput.test.ts` — 6 failures, `ReferenceError: File is not defined`.
- *Root cause.* `File` is a browser global that Node gained in version 20. The dev box runs Node 24;
  the production image, and therefore the gate, runs **Node 18**. The suite had been green on
  every machine that ever ran it and would have failed on the one that builds the app.
- *System change.* The test borrows `File` from `node:buffer` (available since 18.13) when the
  global is absent; proven under a real Node 18.20.8 as well as 24. **The gate itself is the
  lasting fix** — the suite now runs on the production Node version on every deploy. Filed as
  TD-255: Node 18 is past end of life, and dev and production are six major versions apart.

**2. The first api spike failed because of how the lead packaged it, not because of the code.**
- *Symptom.* Three tests failed: `FileNotFoundError: /workspace/docs/technical-debt.md`.
- *Root cause.* The lead archived only `halatuju_api/` and `halatuju-web/` for the spike. A test
  in the api suite reads the debt register under `docs/`. The real trigger clones the whole repo.
- *System change.* Spike re-run from a full `git archive HEAD`. The finding underneath is kept as
  TD-256: **an api test depends on a file the api trigger ignores.** An edit to
  `docs/technical-debt.md` can break `test_technical_debt_register.py` without starting a build;
  the *next* api deploy then fails on a docs edit nobody connects to it.

**3. The agent stated a fact about Cloud Build that was wrong.** It wrote that the inline builds
"inherited the 10-minute default" timeout. The default is 60 minutes. The explicit `timeout: 1800s`
it added is right; the comment explaining it was corrected by the lead. An agent's report is
evidence, not truth — the diff was read before anything was committed.

**4. The triggers were briefly in a half-way state.** They pointed at files that were not yet on
`main`. The lead pushed straight after switching rather than stop for a separate word, because the
owner had approved the switch itself, the push changed no application code, and a trigger aimed at
a missing file is a worse place to pause than either side of it. Recorded so the owner can disagree.

## Numbers

| | Before | After |
|---|---|---|
| Tests run before deploy | none | **6,714 pytest + 2,354 jest, every deploy** |
| api build | 3.9 min avg | **8 min 18 s** (pytest 3 min 57 s inside it, parallel to the image build) |
| web build | 6.9 min avg | **11 min 44 s** |
| Build minutes / month (30-day rate: 80 api + 101 web) | ~1,016 | **~1,850 projected**, free tier 2,500 |
| Deploys this sprint | | 1 per service, no retry |

Serving: **`halatuju-api-01051-nvm`**, **`halatuju-web-00902-w7z`**. Site 200; admin endpoint 401
unauthenticated; zero ERROR lines on the new api revision.

⚠ **The budget is at ~74 % of the free tier, and the freeze lowers the deploy rate.** If a month
runs hot, the first lever is the web step (jest competes with `next build` for 2 vCPUs):
run it after the build instead of beside it, or drop `lint` from the gate since `next build` lints.
Do not set `machineType` — that leaves the free tier.
