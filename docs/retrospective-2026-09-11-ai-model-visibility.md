# Retrospective — Which AI version are we running, and which actually ran?

**Date:** 2026-09-11 · **Branch:** `feat/ai-model-visibility` · **Worktree:** `.worktrees/ai-models`
**Base:** `origin/main` @ `1c38a90d` · **Migration:** none

---

## What Was Built

The owner asked whether an organisation could choose its AI version per task, so versions could be
tracked and upgraded periodically. The survey came back with a better first move than the feature.

**The survey (2026-09-11):**

| Finding | Number |
|---|---|
| AI jobs on the platform | **19** |
| Shared seams carrying most of them | **2** (`_call_gemini_json`, `_call_gemini_text`) |
| Jobs with their own client and setting | 6 |
| Jobs with the model hardcoded | 2 (batch commands) |
| Models that have EVER run on production | **2** — flash (353 calls), pro (72) |
| Fallback models that have ever fired | **0** |
| `*_MODEL` env vars set on the live service | **0** |
| Metered AI events since 2026-07-24 | 1,101 |

**And the finding that set the sprint:** `UsageEvent.model` is written on every AI call and
**nothing ever read it back** — `monthly_usage` grouped by organisation and service only. The
owner's "keep track of the versions" was already collected, just invisible.

**Shipped:**

1. `halatuju/ai_registry.py` — every job with its model, **resolved live**, never stored.
2. A staleness guard that counts the AI seams and fails if one is unregistered.
3. `monthly_usage` groups by model within a service, with first/last seen.
4. The billing page renders both; the job list is super-only.

Plus one live bug fixed that the sprint did not go looking for — see below.

---

## What Went Well

- **Reading the data changed the recommendation.** "Should organisations pick a model?" is a
  design argument; "two models have ever run and no fallback has ever fired" is a fact, and it
  turned a sprint-sized feature into a half-day of visibility the owner actually wanted.
- **The registry resolves rather than records**, so the screen cannot drift from the engine. The
  test that proves it overrides a setting and watches the answer move.
- **The staleness guard works by counting.** It found nothing missing today, and a bite-check
  (deleting one job) proved it names the exact file.
- **Two of the two shared seams carry twelve of the nineteen jobs.** That is the sprint's most
  useful output for the owner's actual question: an upgrade is usually two edits, not nineteen.

---

## What Went Wrong

**1. My own new date field had the TD-209 bug, and my own new test caught it within a minute.**

- *Symptom:* `test_it_says_WHEN_a_version_was_last_used` failed: `'2026-09-10' != '2026-09-11'`.
- *Root cause:* `created_at` is stored UTC. I took `.date()` off it while the month grouping
  around it uses `created_at__year`/`__month`, which Django evaluates in the project timezone. At
  01:40 Malaysian time those disagree by a day.
- *System change:* `timezone.localtime()` before `.date()`, with the reasoning in the docstring.
  Cheap because the test asserted against `timezone.localtime()` rather than a hardcoded string —
  which is the only reason it failed at all.

**2. The same bug was live in somebody else's module — and another agent fixed it an hour before I did.**

- *Symptom:* the full-suite run failed on `test_spend_sponsor.py`, in the sponsor spending arc,
  which this sprint does not touch.
- *Root cause:* `spend_sponsor.sponsor_card()['as_at']` did `newest.date().isoformat()` on a UTC
  timestamp. **A sponsor was shown yesterday's date for the eight hours between midnight and 08:00
  Malaysian time.** Not a flaky test — a wrong date on a live screen, a third of every day.
- *Why nothing caught it:* the existing test compared against `timezone.localtime().date()` — the
  **same moving clock as the bug**. It agreed with the fault for sixteen hours a day and disagreed
  for eight, so it went green on every CI run and failed only because an unrelated sprint happened
  to run its suite at 01:40. **A test that reads the clock the code reads cannot see a clock bug.**
- *System change:* fixed with `timezone.localtime()`, and the test replaced with one that PINS the
  clock — an import at 22:00 UTC must report 2026-07-05 in Malaysia, whatever time the test runs.
  Bite-checked against the old code.
- *Scope note:* outside this sprint's plan and fixed anyway — one line, the identical fault, in
  the file next door. Flagged rather than folded in quietly.
- *And then it collided.* Another agent hit the same bug the same evening (their deploy crossed
  midnight; my suite ran at 01:40) and landed on `main` first. The merge kept THEIR fix — the code
  line was byte-identical — dropped my duplicate test, and repaired their docstring, which had
  lost two backticked names before it was committed and read *"` is stored UTC. A bare  on it is
  YESTERDAY`"*. The one thing my version carried that theirs did not is now in it: that the OLD
  test could never have caught this, because it read the same clock as the bug.
- *The real signal:* **two agents, neither looking, found the same class of fault within an hour.**
  That is not luck, it is the frequency of the pattern — which is why the lesson filed is a
  mechanical tell (`.date()` on a stored datetime) rather than "remember timezones".

**3. TD-209 is now three-for-three, which makes it a pattern rather than a bug.**

- Three separate `.date()`-on-UTC faults in the same codebase: the original TD-209, mine today,
  and the sponsor card. Each was written by somebody who knew the project stores UTC and displays
  Malaysian time.
- *System change:* the lesson filed today is not "remember the timezone" — it is the mechanical
  tell (`.date()` on a model datetime is almost always wrong here) plus the test shape that can
  actually catch it (pin the clock; never compare against `timezone.localtime()`).

---

## Design Decisions

Logged in `docs/decisions.md`:

- **An organisation may NOT choose its AI model** — the owner's call, with reasons recorded so it
  is a decision rather than a gap: the config tab is a catalogue of values we defined, a model name
  is a platform internal, and these prompts are tuned per model, so a tenant choosing a cheaper one
  would silently degrade document reading and it would read as an engine fault.
- **The registry resolves, never records.**
- **The job list is super-only; the per-model usage split is the tenant's.**
- **Grouped by model, not by job**, because that is the shape an upgrade is planned in.

---

## Numbers

| Gate | Result |
|---|---|
| pytest | **6411** passed (+16) |
| jest | **2055** passed (+9), 128 suites |
| `tsc --noEmit` | **24** — unchanged baseline (TD-221) |
| `next lint` | **0** errors |
| `check-i18n` | ALL PASSED, **5046 × 3** |
| `next build` | exit 0 |
| `makemigrations --check` | No changes detected |
| Migrations added | **0** |
| Bite-checks | 4, all bit |

**Files touched: 13.** No AI behaviour changed — no model, setting or cascade moved.
