# Retrospective — Code health H12: the only deletion in the phase was not dead

**Date:** 2026-09-20 · **Roadmap:** `docs/plans/2026-09-18-code-health-roadmap.md` · **Sprint:** H12 of H19
**Built by:** an Opus 5 agent to the same brief and the same hard rules as H9, H10 and H11. The
lead reads the report, pushes and watches the deploy.
**Outcome: `views_admin/__init__.py` (5,093 lines) is 154 lines of re-export. The package is thirty
modules, none over 600. No behaviour changed — all twenty moved bodies are byte-identical to the
lines they came from, proved mechanically.**
**Every gate is green: 0 code_health FAILs, `std` ok, `big` 25 → 24, pytest unchanged at 7,021.**

## What Was Built

- **Twenty modules, 4,914 lines, cut by line range from the file's own bytes.** The nineteen
  domains the roadmap named, plus one split the 600-line standard forced (`reviewers` /
  `invitations`).

  | module | lines | what it holds |
  |---|---|---|
  | `applications.py` | 467 | the cockpit list, the detail read, the officer actions on one application |
  | `verdict.py` | 468 | the verdict audit, the QC gate, reopening, the metrics |
  | `reviewers.py` | 475 | the workload maths, the roster, pause/programme, a reviewer's own profile |
  | `sponsors.py` | 429 | the queue, the NRIC lock, the review decision, the detail payload |
  | `billing.py` | 346 | the tenant usage screen, the platform cost ledger, the rate card |
  | `org_config.py` | 341 | the layered org and programme settings |
  | `lifecycle.py` | 326 | witness, disbursements, closure, maintenance, scope, assignable staff |
  | `org_emails.py` | 301 | the partner and sponsor email templates an officer authors |
  | `theme.py` | 267 | draft tokens, contrast checks, publish and revert |
  | `interviews.py` | 246 | the Check-3 agenda, the findings, the session |
  | `spending.py` | 210 | the officer's spending screen |
  | `sources.py` | 203 | the referral organisations a student arrives through |
  | `invitations.py` | 195 | inviting, listing and revoking an admin |
  | `overview.py` | 187 | the Overview panels and their order |
  | `credits.py` | 174 | a sponsor donation recorded, signed off or cancelled |
  | `profiles.py` | 173 | the vision re-run, the AI blurb, what a sponsor may see |
  | `sponsorships.py` | 168 | a sponsor's memberships, award amounts and sponsorships |
  | `graduation.py` | 141 | the moderation queue and the bursary countersignature |
  | `resolution.py` | 113 | requesting more from a student, and what comes back |
  | `interview_slots.py` | 98 | the times an officer offers and the student books |

  The package root is **154 lines** and holds no code: thirty `from .<module> import ...` lines
  and a header explaining what is no longer an attribute of it.

- **23 `mock.patch(...)` strings re-pointed at the module that now holds the code**, because the
  root's import block is gone and `build_verdict`, `refine_sponsor_profile`, `timezone` and
  `send_request_info_email` are no longer attributes of the package.

- **`TD-267` resolved** — the three dead imports left alone at H11 went with the header, in the
  sprint that entry named.

- **One finding raised and not fixed: TD-268**, with its arithmetic under `## Reviews` in
  `docs/code-health.md`.

## What Went Well

- **Reading the target before cutting paid for itself a second time.** A `symtable` pass — not an
  AST name walk — produced, for every candidate module, exactly the names it reads from module
  scope, distinguishing a base class or decorator read at import time from a local variable inside
  a method. That is what made every generated import header right on the first `manage.py check`,
  with no undefined name and no unused import to clean up afterwards. An `ast.walk` over `Name`
  nodes (the obvious approach, and the one this sprint started with) reports every local variable
  in every method as a free name and is useless for the job.
- **The mechanical proof is now routine and still finds things.** Twenty modules were read back
  off disk and compared line by line with `git show HEAD:…`, and the checker also reported which
  original lines had NOT been moved: exactly one, `logger = logging.getLogger(__name__)`, left
  behind on purpose. A count that says "everything is accounted for except this one line, and here
  it is" is worth more than twenty YESes on their own.
- **The line-endings trap was caught by a bite-check, not by a reviewer.** Two bites came back
  "needle not unique (0 occurrences)" — the repo's working tree is CRLF and the needles were
  written with `\n`. That sent me to check the twenty new files, which were correct (the cutter
  sniffs the original's endings), and then to check the eleven test files edited by hand, three of
  which the editor had silently normalised to LF. Restored before the close. **A bite-check that
  cannot find its own needle is a fact about the tree, not a nuisance.**
- **Every gate held.** 7,021 passed / 3 skipped — the same number as H11, with no test added and
  none removed. `std` read ok, which is the lead's post-H11 tool fix working on a real split: the
  oversize entry was removed rather than renamed, and `loosened()` passed it in silence.

## What Went Wrong

**1. The phase's one permitted deletion was of a function that is called on every cockpit load.**
- *Symptom.* The brief, the roadmap and `halatuju_api/CLAUDE.md` all say `interview_agenda_full`
  "has zero callers outside one test — confirm dead, delete (the only deletion in the phase)".
  One grep says otherwise: `serializers_admin.py:756` imports it lazily and
  `serializers_admin.py:542` lists `interview_agenda` in the served fields. It is typed in
  `halatuju-web/src/lib/admin-api.ts:1066` and rendered at `view.tsx:1052`. **It is served on
  every admin application detail load.**
- *Root cause.* The claim is what a naive symbol search returns. `interview_agenda_full` is
  imported INSIDE a serializer method, four lines below the string `interview_agenda` — so a
  search for the function name finds the definition, one test, and a lazy import that reads like a
  test helper, while the thing that proves it live (a `SerializerMethodField` in a `fields` tuple,
  named without the `_full`) is a different string in a different file. **A lazy import is
  invisible to the mental model "who imports this module?"** — and this codebase uses lazy imports
  heavily and deliberately, to keep the app boundary narrow. The survey that produced the claim
  did not distinguish "no module-level importer" from "no caller".
- *System change.* Two. The roadmap's H12 section and `CLAUDE.md` are corrected in this sprint's
  close, so the claim cannot be inherited a third time. And the general rule, which is the bigger
  half: **before deleting anything, grep for the name AND for what it produces** — the field it
  serves, the URL it answers, the setting it reads. Here one grep for `interview_agenda` (without
  `_full`) settles it in five seconds and returns four files in two languages. This is lesson
  `feedback_absence_is_a_query` in its own back yard: a claim that something is unused is a query,
  not a memory.

**2. A pure file split raised the cross-app import count, and there is no honest way to split it
that does not.**
- *Symptom.* `xapp` 133 → 135. Every test green, `TOL_COUNT` is 2 so nothing FAILed, and the
  change is real.
- *Root cause.* H11's lesson was applied and removed nothing: every one of the package's other 22
  `apps.courses` imports already sits inside the function that uses it, each header import was
  checked against its own body before it was written, and nothing was left behind in the root
  (which now has no imports at all). The residue is arithmetic. The old root had **two**
  module-level cross-app statements serving **four** call sites; the split put those four call
  sites in four modules, so the same dependency reads as four statements. `m_cross_app_imports`
  counts statements per file, so **the more faithfully a package is decomposed, the worse it
  reads.**
- *System change.* **TD-268**, proposing the metric count distinct `(app → app, name)` edges
  instead — a reading that is 133 both before and after. Recorded with the full arithmetic under
  `## Reviews` in `docs/code-health.md` and ACCEPTED rather than engineered away. Two ways to hold
  the number at 133 were considered and rejected in writing: re-exporting `PartnerAdmin` through
  `base.py` (hiding a real dependency behind the org-fence module) and regrouping four unrelated
  views into one 640-line module to share an import line. **A number held by hiding the thing it
  measures is worse than a number that went up honestly**, and Phase 4 has four sprints left in
  which to be tempted.

**3. The editor silently rewrote three files' line endings, and nothing in the gates would have
said so.**
- *Symptom.* `test_factories.py`, `test_helper_characterisation.py` and `code-standards.json` came
  out of a two-line string edit as pure LF in a CRLF working tree. `git diff --stat` printed a
  warning; the suite, `manage.py check` and code_health were all perfectly happy.
- *Root cause.* The edit tool writes back what it read, normalised. It is invisible because
  `core.autocrlf` stores LF in the index either way, so the COMMIT is identical and only the
  working tree diverges — until the next person's checkout rewrites all three files and a later
  diff shows a file "changed" with no change in it.
- *System change.* An explicit byte-level check after editing — count `\n` against `\r\n` for every
  file in `git diff --name-only` — and restore any file that flipped. Done here before the close.
  The same check was run over all thirty package modules: all CRLF, all consistent.

## Design Decisions

- **Twenty modules, not nineteen, and the 600-line standard is again the reason.** H4's ledger is
  frozen and may not gain a member, so a new file over 600 lines has nowhere to be recorded. The
  reviewers domain is 640 lines including `AdminInvitationsView`, so invitations became its own
  module — which is honest anyway: inviting an admin of any role is not a reviewer concern.
- **Two modules hold two non-adjacent spans, and each says so in its own docstring.** `interviews`
  takes lines 138-143 (the two finding-vocabulary constants, which sat at the top of the old file
  only because that is where you write constants) and 735-952. `reviewers` takes 2285-2681 and
  3492-3538 (`ReviewerProfileView`, a reviewer's own credentials, which sat between the interview
  slots and the graduation queue for no reason at all). Everything else is one contiguous span, so
  the diff reads top to bottom. **Contiguity is a reviewing convenience; it is not worth putting a
  reviewer's own profile in a file called `interview_slots`.**
- **`interview_agenda_full` was NOT deleted, and the permitted deletion was not spent elsewhere.**
  The phase allows one deletion. It was allocated to a specific function on a specific claim; the
  claim was wrong, so the allowance lapses rather than transferring. Nothing else was deleted.
- **The frozen baseline was NOT touched this time.** H11 re-pinned `BASELINE_SHA256` because a
  path rename left a key describing a file that no longer existed. H12's root is simply under the
  standard, so `test_a_listed_file_that_shrank_has_its_entry_lowered` asks for the budget line to
  be REMOVED — an ordinary tightening, in `budget` only. **H11's re-pin was the exception it said
  it was, and the arc has not acquired a habit of editing frozen records.**
- **The root's header documents what is no longer an attribute of it.** The most likely future
  mistake is somebody writing `mock.patch('apps.scholarship.views_admin.<dep>')` from memory or
  from an old test. That now raises `AttributeError` rather than patching nothing, and the reason
  is written where they will be looking.

## Numbers

| | Before | After |
|---|---|---|
| `views_admin/__init__.py` | 5,093 lines | **154 lines** of re-export, no code |
| the package | 11 files, 8,792 lines | **31 files, 9,181 lines** — none over 600 (largest `requests.py` 480, H11); the +389 is thirty generated headers |
| moved this sprint | — | **4,914 lines in 20 modules** (avg 246, max 475) |
| Moved bodies vs the original | — | **byte-identical, all twenty**; exactly one original line not moved (`logger`), on purpose |
| `patch(...)` strings re-pointed | — | **23** (+1 reflection target, +1 docstring) |
| `urls.py` | — | **byte-identical** (absent from `git diff --stat`) |
| pytest `-n auto` | 7,021 / 3 skipped | **7,021 passed · 3 skipped · 0 failed** — no test added, none removed |
| `manage.py check` / `makemigrations --check` | 0 / clean | **0 issues · no changes detected** |
| `big` | 25 | **24** — the package root left the list |
| `xapp` | 133 | **135** — accepted, with the arithmetic (TD-268) |
| `std` | ok | **ok** — the lead's post-H11 tool fix works on a real split |
| `hot#1` | 107.1 `admin-api.ts` | **107.1** — unchanged, and still not evidence (H11 note 3) |
| every other code-health reading | | unchanged · **0 FAIL, 6 WARN** |
| Bite-checks | | **5 run, 5 behaved**, all restores sha256-verified |
| Behaviour changed | | **none** |
| Migration | | none |
| Deletions | | **none** — the phase's one permitted deletion was of live code (see What Went Wrong 1) |
| Findings raised / resolved | | **TD-268 raised · TD-267 resolved** |
