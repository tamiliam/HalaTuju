# Retrospective — Code health H11: the split is easy, the guards around it are not

**Date:** 2026-09-20 · **Roadmap:** `docs/plans/2026-09-18-code-health-roadmap.md` · **Sprint:** H11 of H19
**Built by:** an Opus 5 agent to the same brief and the same hard rules as H9 and H10. The lead
reads the report, pushes and watches the deploy.
**Outcome: `views_admin.py` (8,556 lines) is a package of eleven files. No behaviour changed —
the ten moved bodies are byte-identical to the lines they came from, proved mechanically.**
**One gate is not green: `std`, and it is the tool reading a rename as a new exemption.**

## What Was Built

- **`apps/scholarship/views_admin/` — a package whose root re-exports all 142 names**, so
  `urls.py` is byte-identical and no importer, test or `patch(...)` string was touched. Six
  domains moved out as ten modules:

  | module | lines | what it holds |
  |---|---|---|
  | `base.py` | 332 | `_AdminBase` (the org fence), `_MONTH_RE`, `_org_or_none` |
  | `payments.py` | 377 | payment runs |
  | `invoices.py` | 466 | tenant invoices, receipts, build hours |
  | `contracts.py` | 436 | contract templates |
  | `requests.py` | 480 | a request and its conversation |
  | `requests_delivery.py` | 391 | the analysis, the quote, the schedule, attachments |
  | `sponsor_terms.py` | 300 | sponsor terms authoring |
  | `gifts.py` | 315 | gift + intake-year readers and row builders |
  | `gift_programmes.py` | 315 | the `Programme` endpoints |
  | `intake_years.py` | 287 | the `ScholarshipCohort` endpoints |

  The package root is 5,093 lines — wave 2's work, untouched.

- **A guard on the audit logger's name**, in `test_access_audit.py`, written because a bite-check
  came back silent (see What Went Wrong 1). Two tests: every module in the package logs under
  `apps.scholarship.views_admin`, and a floor so the scan cannot go vacuous.

- **`test_org_fence.py`'s `SCANNED` tuple changed by one character** — `views_admin.py` →
  `views_admin/` — which is precisely what H3 built `scan_targets()` for, three sprints early. It
  worked first time and the static guard now walks the package recursively.

- **The oversize ledger key followed the file** in `halatuju_api/code-standards.json`, baseline
  unchanged at 8,547 and budget lowered to 5,093, with `BASELINE_SHA256` re-pinned in the same
  change and the reason written in both files.

- **Two findings reported and not fixed: TD-267**, and two shortcomings in the sprint-close
  reading tool, recorded under `## Reviews` in `docs/code-health.md`.

## What Went Well

- **The mechanical proof was cheap and it paid for itself.** The bodies were cut by line range
  from the file's own bytes rather than retyped, and a second pass read all ten modules back off
  disk and compared them, line by line, with the original at `HEAD` — un-bumping the one
  transformation the move requires (`from .x` → `from ..x`, because every module is one level
  deeper now). Ten YESes. That check also caught the thing a diff would have hidden: the number of
  relative imports bumped per module matched, exactly, the number an AST walk had found before any
  file was written.
- **Reading the target BEFORE cutting is what made the seams obvious.** An AST pass produced, for
  each candidate block, the names it defines, the names it needs from outside itself, and every
  import written inside it. The dependency graph that came out was already a clean DAG with one
  edge in the wrong direction (`_org_or_none` sitting in the contracts region while only billing
  and invoices read it) and two shared constants with two homes. All three were settled on paper,
  in about twenty minutes, instead of being discovered by a circular import at hour three.
- **Three of the four named trip-wires behaved exactly as the roadmap said.** The fence test was
  package-aware; the private helpers needed re-exporting and were re-exported wholesale (every
  module-level name of every moved module, not the eight the survey found, so the question cannot
  arise again); the nineteen `patch` strings still resolve because `build_verdict` and
  `refine_sponsor_profile` and the code that reads them all stayed in the root, as planned.
- **The test count held at 7,019 for every pre-existing test.** The first full run after the cut
  was 7,017 passed + 2 failed — the two failures being the code-standards ledger, which is the
  suite doing its job, not the move doing damage.

## What Went Wrong

**1. A trip-wire the whole sprint was planned around does not exist, and never did.**
- *Symptom.* Bite (c) — switch one submodule to `logging.getLogger(__name__)`, expect an
  `assertLogs` test to go red — came back **GREEN**. The brief, the roadmap and the survey before
  it all say twelve `assertLogs('apps.scholarship.views_admin')` sites break on a new logger name.
  None of them does.
- *Root cause.* `assertLogs(parent)` attaches its handler to that logger and records everything
  that **propagates up from its children**, and `apps.scholarship.views_admin.intake_years` is a
  child. Every one of those twelve tests then matches on the message text — `'intake_year_requirements_set' in m` —
  never on the logger. So all twelve would have sat green while every audit line in the package
  quietly moved to a logger name the Cloud Logging scrape metric does not count. The belief that
  the suite was holding the audit stream together was inherited, plausible, and wrong.
- *System change.* `AuditLoggerNameTest` in `test_access_audit.py` asserts it directly, at runtime,
  over every module in the package, with a floor test so it cannot go vacuous. The general rule,
  and it is the bigger half: **a trip-wire named in a brief is a hypothesis until a bite proves
  it.** H10 ran 36 bites and all 36 behaved, which is a pleasant result and also the one that
  teaches nothing; this sprint's single silent bite was worth more than the other four together.

**2. The ratchet tooling refuses the one operation the standard's own failure message prescribes.**
- *Symptom.* `test_no_unlisted_source_file_passes_the_line_limit` says, in its failure text,
  *"SPLIT IT into modules under 600 lines, in its own commit with no behaviour change. Do NOT add
  it to the ledger."* Doing exactly that made two tests red — the old key names a file that no
  longer exists, and the new package root has no key — and then `Settings/_tools/code_health.py`
  reported `std: FAIL — a NEW entry`.
- *Root cause.* Both guards compare ledgers key by key, and a key is a **path**. A split renames
  one. `loosened()` sees a key disappear (silent, a tightening) and a key appear (reported, an
  addition) and cannot tell that pair from somebody quietly buying an exemption. The in-repo test
  has a documented escape — edit the baseline deliberately and re-pin its SHA in a second file a
  reviewer cannot miss — and that was used, with the reason written in three places. The
  sprint-close tool has no escape at all.
- *System change.* Recorded as a decision under `## Reviews` in `docs/code-health.md`, with the fix
  proposed: pair a removed key with an added one whose value is lower and report a rename, or read
  the JSON's own `_history` for a declared one. **This sprint could not make it —
  `Settings/_tools` was out of scope — so H12, H13, H15 and H16 will each FAIL `std` for the same
  reason and each will need the same paragraph. Four acceptances in a row for a guard that is
  wrong every time is how a guard stops being read**, and that is the real cost, not the FAIL.

**3. A naive split widened the app boundary by four, and the reading caught it, not the tests.**
- *Symptom.* `xapp` 133 → 137. Every test was green.
- *Root cause.* Three new modules each got a module-level
  `from apps.courses.models import PartnerOrganisation` in their header — written because a static
  pass said the name was referenced, without checking that each of those references already sits
  under a local import inside the very function that uses it. A fourth came from moving
  `PartnerAdminMixin` into `base.py` while leaving the original line in the root, where nothing
  reads it any more. **An import repeated in ten modules makes a boundary read ten times wider
  while nothing about it has changed**, and the app-boundary standard counts lines, not edges.
- *System change.* The three redundant headers were deleted and the root's dead `PartnerAdminMixin`
  line removed, so `base.py` is the only new module importing from `apps.courses` and it does so
  with the line the root gave up: 133 → 133. The rule for the next split, now in the roadmap's
  H12 estimate: **budget an hour for the app-boundary count, and check every "this module needs
  name X" against whether the body already imports X itself.**

**4. One full-suite run produced a failure that has never reproduced, and its name was not kept.**
- *Symptom.* The first no-cry-wolf bite reported `1 failed, 7018 passed`. Three subsequent runs of
  the identical command on the identical tree — two with the bite applied, one without — were all
  clean.
- *Root cause.* The bite harness printed only the run's last line, so the `FAILED` name was thrown
  away and the flake cannot now be identified. A one-off in a 7,000-test suite is not news; **a
  one-off nobody can name is**, because the next person to see it has no way to tell whether it is
  the same one.
- *System change.* The harness now prints every `FAILED` line before the summary, which is how
  round two identified its own results in one pass. Reported to the lead as an open, unexplained
  one-off rather than written off.

## Design Decisions

- **Ten modules rather than six, and the 600-line standard is why.** H4's ledger is frozen and may
  not gain a member, so a new file over 600 lines is refused by the gate with nowhere to record
  it. `requests` (833 lines) and the gift domain (868) could not be one module each. The splits
  were made at the seams the code already had — a request and its conversation apart from its
  analysis, quote and delivery; the gift readers apart from the `Programme` endpoints apart from
  the `ScholarshipCohort` endpoints — and every module is contiguous in the original file, so the
  diff reads top to bottom.
- **The root's import block was left exactly as it was, dead names and all.** Nine of those names
  are now read only by a submodule. Each is still an attribute of `apps.scholarship.views_admin`,
  which is what nineteen `patch(...)` strings and several lazy importers address, so deleting one
  is a change to the module's public surface rather than tidying. They go in wave 2 with the code
  that needed them; the reason is written above the package's import block so nobody reads them as
  an oversight.
- **`_MONTH_RE` and `_org_or_none` moved to `base.py`, though neither is a base class.** Each is
  read by a moved module AND by the package root. Leaving either behind would have made a
  submodule import from the package that imports it — a cycle — and copying it would have put a
  rule in two homes, which is the thing Phase 3 just finished removing.
- **The baseline block was edited, deliberately, for the second time in the arc.** H5 set the
  precedent. The number did not move (8,547, the same file at a new path); only the key did, and
  `BASELINE_SHA256` was re-pinned in the same change with a nine-line comment saying why. A path
  rename is the one case where a frozen record must follow, because a key naming a file that no
  longer exists describes nothing at all.

## Numbers

| | Before | After |
|---|---|---|
| `views_admin` | 8,556 lines, one file | **5,093 + 3,532 in ten modules** (avg 370, max 500) |
| pytest `-n auto` | 7,019 / 3 skipped | **7,021 passed · 3 skipped · 0 failed** — every pre-existing test unchanged; +2 is the new logger guard and its floor |
| `urls.py` | — | **byte-identical** (absent from `git diff --stat`) |
| Moved bodies vs the original | — | **byte-identical, all ten**, relative-import depth aside |
| `manage.py check` / `makemigrations --check` | 0 / clean | **0 issues · no changes detected** |
| `hot#1` | 273.8 (`views_admin.py`) | **107.1** (`admin-api.ts`) — ⚠ overstated, the tool does not follow a rename |
| `big` | 25 | **25** — one oversize file swapped for another; the root leaves the list at H12 |
| `xapp` | 133 | **133** (137 on the first cut — see What Went Wrong 3) |
| Every other code-health reading | | unchanged · **`std` FAIL, accepted with a reason** |
| Bite-checks | | **6 run, 5 behaved, 1 silent** → the silent one became a test |
| Behaviour changed | | **none** |
| Migration | | none |
| Findings raised | | **TD-267**, plus two tool shortcomings in `docs/code-health.md` |
