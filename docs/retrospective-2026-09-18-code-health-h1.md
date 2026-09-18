# Retrospective — Code health H1: one-word gates and a frozen production lock

**Date:** 2026-09-18 · **Roadmap:** `docs/plans/2026-09-18-code-health-roadmap.md` · **Sprint:** H1 of H19
**Built by:** an Opus 5 agent to a written brief; verified, corrected and closed by the lead.
**Freeze status:** in force. Closer to *stabilised* by one sprint of ten.

## What Was Built

- **Web — one command for every check.** `npm run gates` runs typecheck, lint, the i18n parity
  script and jest, in that order. Before today the four gates existed only as lines in `CLAUDE.md`,
  and `package.json` had no `test` script at all.
- **Web — four unused packages removed:** `next-intl`, `react-hook-form`, `tailwind-merge`,
  `@supabase/ssr`. Each verified to have zero imports first. `next build` still exits 0.
- **Api — `requirements.lock`.** 92 exact pins, a **freeze of what the production image installed
  on 2026-09-18** (read from that build's own log), not a fresh resolve. All 24 top-level packages
  fall inside their `requirements.txt` ranges. The Dockerfile installs the lock; `requirements.txt`
  stays as the statement of intent.
- **Api — `requirements-dev.txt`.** `pytest`, `pytest-django`, `pytest-xdist`, `openpyxl`. For the
  first time a fresh clone can run the suite: proven in a clean virtual environment, 6,714 passed.
- **Api — `.dockerignore`.** Tests, `conftest.py`, the eval image corpus and local state no longer
  enter the production image. Each exclusion was proven unreachable from runtime code first.
- **Tests that could not fail, fixed:** the STPM golden master's dead `skip` branch is gone; the
  email golden's regenerate mode now **fails** the run instead of skipping it; `--strict-markers`.

## What Went Well

- **The brief carried the one dangerous input.** A lock file resolved "fresh" would have changed
  what production runs while claiming to change nothing. The lead read the 92 installed versions
  from the last production build log *before* delegating, and handed them to the agent as a file.
- **The agent proved each `.dockerignore` line before writing it** — and kept two things the brief
  would have let it drop: `_test_fixtures.py` and `eval/` are imported by a management command.
- **All 92 Linux/Python-3.11 pins installed cleanly on Windows/Python 3.13**, so the lock is usable
  on the dev box as well as in the image.

## What Went Wrong

**1. A flaky test had been in the suite for weeks, and only a clean-room run found it.**
- *Symptom.* `test_the_ENDPOINT_carries_no_path_and_no_engineer_hours` failed once in the fresh
  environment and passed when re-run alone.
- *Root cause.* It asserted the string `'7.5'` (the engineer's hours) appears nowhere in the
  response. The response carries `created_at` with microseconds; `…:37.520596Z` contains `7.5`.
  The test failed roughly one run in twenty for a reason unrelated to what it guards.
- *System change.* Sentinel changed to a value no clock field can contain. **And the first fix was
  itself wrong in a way only a second assertion caught:** the lead chose `'83.25'`, added a line
  proving the *owner's* view does carry the sentinel — and that line failed, because hours are
  stored to one decimal place (`'83.2'`). Without it, the "must not leak" assertion would have
  passed for ever against a value that never existed. Now `'83.5'`, with the proving line kept.
  The lesson is in `docs/lessons.md`. This matters more from H2 on: a flaky test then blocks a deploy.

**2. Docker is not installed on the dev box, so the image itself was never built locally.**
- *Symptom.* The `.dockerignore` and the lock could not be tested as an image.
- *Root cause.* No local Docker; the only real build is Cloud Build's.
- *What stood in.* A simulated tree with the ignore rules applied: `manage.py check` clean, all 246
  non-test modules import, and the Dockerfile's own `collectstatic` step reproduces. That is good
  evidence, not proof. **The proof is the deploy build, watched to the end** — and the rollback is
  one revert commit.

**3. The brief's acceptance line was slightly wrong.** It expected the runtime skip count to fall.
It could not: neither changed test was skipping at run time. What fell is the *static* count of
skip sites (2 → 0), which is what the reading measures. The three remaining runtime skips are
"real corpus not present on this machine" — honest, environment-conditional.

## The deploy — the proof the local box could not give

Pushed on the owner's word. Both builds **SUCCESS** at `3b21722`. Serving:
**`halatuju-api-01050-kw2`** and **`halatuju-web-00901-r9l`**, each the latest ready revision.
The api build log shows pip installed **92 packages at the locked versions** — the image is what
the lock says it is. Site 200; the admin applications endpoint answers 401 unauthenticated; zero
ERROR lines on the new api revision. One deploy per service; no retry.

## Numbers

| Gate | Result |
|---|---|
| `npm run gates` | tsc 0 · lint 0 errors · i18n parity ok (5,353 keys × 3) · jest **2,354 / 140 suites** |
| `next build` | exit 0 · shared first-load JS 87.1 kB |
| pytest, fresh venv from the lock, `-n auto` | **6,714 passed, 3 skipped, 0 failed** · 2 min 59 s (serial: ~5 min) |
| Code-health reading | `unused` **4 → 0** · `skip` **2 → 0** · `tsc` 0 · everything else unchanged · 0 FAIL |
| Files | 11 changed, 3 new |

`pytest -n auto` at under three minutes is the number H2 needs for its build-minutes budget.
