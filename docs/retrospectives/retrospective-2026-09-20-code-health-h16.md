# Retrospective — Code health H16: `emails.py`, `income_engine.py`, and the thing only the golden could see

**Date:** 2026-09-20 · **Sprint:** code health H16 (Phase 4, moves only — **the last one**) ·
**Cost:** ~7h against the ~7h estimate.

The two files were 7,430 lines between them: the largest and the second largest left in the
repository, and `income_engine.py` was its worst hotspot. They are now 40 modules and two
re-export shells. Nothing about the product changed, no migration was created, **the email golden
master is byte-unchanged**, and no file that imports either one was edited.

Phase 4 is complete. The closing summary — what the six sprints delivered, what is still over a
thousand lines and why, and what Phase 5 should expect — is in the roadmap, not here.

The interesting part of this sprint was **a path built from `__file__`**. Every suite was green.
The golden master was not.

---

## What Was Built

| | `emails.py` | `income_engine.py` |
|---|---|---|
| before | 4,242 lines | 3,188 lines |
| shell (`__init__.py`) | **134 lines**, re-export only | **132 lines**, re-export only |
| modules | **21** (4,228 moved lines) | **19** (3,155 moved lines) |
| largest module | `interview_mail.py` 464 | `identity_checks.py` 377 |
| names re-exported | 195 | 188 |
| lines NOT moved | 14 (the header) | 33 (the header) |

Every moved line is byte-identical to the line it came from. As at H15 that is asserted by the cut
itself: the generator sliced the original file's own lines, compared each written line back against
its source before the file was allowed to exist, and a second assertion proved that every line of
the original was either moved or declared not-moved and that every declared line was blank or part
of the header.

**Two declared edits, both to keep behaviour identical rather than to change it**, and both of a
kind: a body that moves one level deeper takes its address with it.

1. `emails/shared.py` — `logging.getLogger(__name__)` became
   `logging.getLogger('apps.scholarship.emails')`. In the old file `__name__` *was* that string.
2. `emails/vircle_install.py` — the installation-guide asset path gained one `os.path.dirname`.
   See What Went Wrong 1.

Twenty-seven lazy relative imports had their level bumped from 1 to 2, found by AST — an
`ImportFrom` of level 1 inside a slice — never by regex.

**A third module was written, and it is the back-edge:** `apps/scholarship/constants.py`, holding
the six plain numbers `apps/courses/org_config.py` reads across the app border. Each moved
verbatim with the comment it carried; each old home re-exports it, so every existing reader is
untouched. The module imports nothing and never will, which is the whole design — every one of
those six reads carried a comment saying the import had to be lazy *because it would be circular*,
and a leaf cannot be.

---

## What Went Well

1. **The free-name analysis that bit H15 was fixed at source, and found nothing to fix
   afterwards.** H15's one bug was a scope-blind pass: a lazy `from django.utils import timezone`
   inside one function made the name look satisfied for a second function that had no such import,
   and only the suite caught the `NameError`. H16 computed free names with `symtable`, which is
   scope-aware — a lazy import binds LOCALLY in that function, so a sibling's use of the name still
   reads as a free global and the header import is still asked for. **Forty modules, zero missing
   imports, and the suite found none.** The right lesson from H15 was not "be more careful"; it was
   "use the tool that knows about scopes".

2. **Cycles were found before a file was written, and each one named the single function in the
   wrong place.** Two appeared. `_send_plain` sat with the reviewer mail it serves but reads
   `_interview_unsub_headers`, so it moved to `sending`. `_name_bucket`, `_nric_bucket` and
   `_combine_relationship` sat with the document checks that use them, but `relationships`,
   `identity_checks` and `str_route` read them too, so they became `buckets.py`. Neither was a
   failure of the domain split; each was the split telling us where one function actually belongs,
   and both modules say so in their own docstrings.

3. **The api-side cross-tree guard caught a web guard, from the api gate, with no jest involved.**
   `strCoachDrift.test.ts` reads `income_engine.py` by path from the web tree.
   `test_web_guards_read_live_paths.py` — written the day before, in the guard-floor sprint that
   closed TD-269 — failed with the web file and the api path both named in the message. This is the
   exact failure H11 and H12 shipped twice with every api gate green, now caught by a directory
   listing against a list of strings. **The repair worked on the first sprint that could test it.**

4. **`income_engine` moved without a verdict moving.** It is eligibility, and the whole risk of
   the sprint was that something in it would change by accident. Nothing did: every eligibility
   suite is green on identical counts, `VERDICT_ENGINE_VERSION` was not touched, and a bite-check
   proved a one-character change in a moved income function goes red in a named test. The
   `incomeWizard.ts` mirror and its three parked `unguarded_mirrors` entries were left exactly
   where TD-262 left them.

5. **`xapp` FELL.** H12 warned H15 and H16 to expect a rise; H15 held at 46; H16 went 46 → **45**,
   across a forty-module split. TD-268's edge counting is the reason, and the fall is real: the
   last module-level cross-app import became a lazy one whose edge another file already had.

---

## What Went Wrong

### 1. A path built from `__file__` — and only the golden master could see it

`emails.py` resolved the Vircle installation-guide PDF like this:

```python
_VIRCLE_GUIDE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'assets', 'vircle-installation-guide.pdf')
```

The asset lives at `apps/scholarship/assets/`. One level deeper, that single `dirname` answers
`apps/scholarship/emails/`, and the file is not there.

**Nothing raised.** `vircle_guide_attachment()` is best-effort by design: it logs a warning and
returns `None`, and `send_vircle_install_email` sends the email without its attachment. A student
would have received a correct-looking installation email with the guide missing, and the only
signal would have been a warning line in Cloud Logging that nobody reads unless they are already
looking.

`manage.py check`, `makemigrations --check` and every ordinary test were green. **The email golden
master failed**, because it pins attachment *filenames* alongside the rendered bytes — a decision
made in platform Sprint 5 for a different reason entirely, which is what caught this.

This arc has a written, enforced rule about `__name__` in a moved module: H11 wrote the guard, H15
proved it was package-specific and generalised it, and H16's brief named it as a trap. **It had no
rule about `__file__`, and the two are the same rule.** A move one level deeper changes what the
module knows about itself; a logger name and an asset path are two faces of that, and a dependency
graph cannot see either.

The fix is one extra `dirname`, declared in the file with the reason written where the next person
will read it before editing rather than after.

### 2. Thirty-six failures after the cut, and every one was a patch target, a guard, or the ledger

That sounds like a clean run, and by the numbers it was. But the shape is worth writing down,
because it is the same shape for the third sprint running and it is now the *dominant* cost of a
split:

| what failed | how many | why |
|---|---|---|
| `patch.object(emails, '_send_html' / '_send_plain')` | 14 | a send primitive is now an attribute of the module that READS it |
| `patch('apps.scholarship.income_engine.<name>')` | 18 | same hazard, dotted-string form, in eligibility code |
| guards reading a moved file by path | 3 | `test_branding_guard`, `test_superseded_documents`, `strCoachDrift` |
| the ledger ratchet | 1 | two entries had to leave `oversize_files` |

**Not one of them was a real defect, and not one of them was avoidable by being careful.** They are
the mechanical consequence of a package boundary appearing where there was none. What *is* avoidable
is the next sprint paying the same price by hand, which is why `tests/package_patch.py` exists.

### 3. `patch.object(emails, ...)` is a shape that fails in two different ways, and one is quiet

H12 and H15 both wrote down that a dotted patch string may stop resolving. Both were describing the
**loud** case: the attribute is gone, `mock.patch` raises `AttributeError`, you fix it.

H16 met the other case. The shell re-exports what the old module *defined*, so
`emails._send_html` still exists — patching it succeeds, rebinds an attribute nothing calls, and
**the real send primitive runs**. Here that was loud (`assert_called_once` failed with a puzzle
rather than a reason), but it was loud by luck: a test that patches a sender only to keep mail out
of the way, and asserts nothing about the mock, would have gone on passing while posting real mail
in the suite.

`patch_engine` answers both: it patches every scope that holds the name — through the package, from
a sibling's import header, and in its own home — with one shared mock, **and it asserts it patched
at least one.** A name nobody holds any more is a move nobody followed, and that now fails with a
sentence instead of yielding a context manager that does nothing.

### 4. The sprint brief was wrong about the ledger, and the ledger is the thing to trust

The roadmap said `income_engine.py` "carries `long_functions` entries as well as its size entry —
grep both `code-standards.json` files for every path before planning the cut". The grep took two
minutes and the answer was **no**: neither file had a `long_functions`, `runtime_skips` or
`hand_built_application_fixtures` key. Only the two size entries, and both of those left the budget
outright.

The instruction was right and the fact was wrong, which is the best possible version of that
mistake. It is worth noting only because the opposite — believing a brief that says there is
*nothing* to grep — is how H14 lost a deliverable.

---

## The Bite-Checks

Seven, each with a byte backup restored in a `finally` and verified by SHA-256, and each needle
proved unique in its file before the edit was made.

| | bite | result |
|---|---|---|
| (a) | drop `send_invoice_email` from the `emails` shell | **RED** — `test_invoicing.py::TestSend`, 3 tests |
| (b) | drop `income_established` from the `income_engine` shell | **RED** — `test_one_clean_cluster.py`, 10 tests |
| (c) | one character in a moved email renderer (`ACK_BODIES` en, *received* → *recieved*) | **RED** — the golden master, naming `ack.en` |
| (d) | one character in a moved income function (`salary_income_satisfied`: `any` → `all`) | **RED** — `test_one_clean_cluster.py`, 4 tests |
| (e) | point the floored `TestStaticReadGuard` back at `income_engine.py` | **RED** — naming the path and why it is read |
| (f) | NO-CRY-WOLF: one extra blank line in a moved module a WEB guard reads | **GREEN** — 7,043 pytest and 2,934 jest, both suites |
| (g) | a moved `emails` submodule takes `logging.getLogger(__name__)` | **RED** — `AuditLoggerNameTest`, subtest `apps.scholarship.emails` |

**(c) is the one that matters most.** It proves the golden master still *sees* the moved code — so
"byte-unchanged" is a measurement and not a hope. Without it, a golden that passes after a split
proves only that the split did not break the import.

**(g) is the one H15 could not get.** The same bite came back SILENT there, in a second package,
for H11's reason: `assertLogs` on a parent records whatever propagates up from its children. H15
generalised the guard to a list of packages; H16 added `apps.scholarship.emails` to that list with
a floor of 10, and the bite is red. **A warning from a previous sprint answered by a guard rather
than by care is the arc working.** `apps.scholarship.income_engine` is deliberately NOT on that
list: it is a pure rule engine and logs nothing, and a floor of zero is the thing the guard exists
to refuse.

**No bite came back silent.** The one real hazard this sprint found was not found by a bite at all
— it was found by the golden master during the build, which is What Went Wrong 1.

---

## Design Decisions

1. **The shells re-export what the old module DEFINED, not what it imported** — H15's rule,
   unchanged. That is why `EmailMessage` is no longer an attribute of `emails` and one patch string
   had to follow it into `invitation_mail`. The alternative, re-exporting the import header too,
   would make every one of those patch sites *silently* useless instead of loudly wrong.

2. **`income_engine/evidence.py` carries the eligibility warning at the top of the file.** The
   owner rulings that settled this code — TD-262 chunks 1–3, rule-4 items 1 and 1b, F8, and the
   2026-09-20 ruling that the cash door stays off the STR route — are named where the next person
   reads them before editing rather than after. The package shell repeats it.

3. **`buckets.py` and `sending.py` hold one function each that a domain split would have put
   elsewhere**, and both docstrings say which cycle that decision broke. A module whose reason for
   existing is undocumented gets merged back by the next person who tidies.

4. **`constants.py` is a leaf and says so in its own docstring.** The value of the module is
   entirely in what it does *not* import; a future engineer adding one import to it would undo the
   sprint without noticing, so the file says that in the second paragraph.

5. **The back-edge target was reported, not engineered.** The acceptance said "`xapp` back-edge
   under 20" and it finished at 30. Six constants are six distinct names and therefore six edges
   whichever module holds them; consolidating three source modules into one leaf changes which
   module is named, not how many names cross. Getting under 20 means `courses` owning its own
   defaults, or the numbers being served rather than imported — both behaviour changes, and Phase 4
   is moves only. Raised as **TD-278** with the arithmetic. H12's precedent: argue with numbers,
   never quietly re-scope the acceptance.

6. **`apps/scholarship/constants.py` shares a basename with `services/constants.py`, knowingly.**
   H15's note 4 asks for unique module basenames under `apps/scholarship/**`, and this breaks that
   for the first time since. The roadmap named the file explicitly, `constants` is the conventional
   name, and the one basename-keyed guard H15 left (`test_verdict_item_i18n.py`) is an *inclusion*
   test on `verdict_engine.py`, not an exemption allowlist, so the collision is inert today.
   Raised as **TD-279** rather than resolved by inventing a name, so the next person sees the
   choice rather than guessing at it.

---

## Numbers

**Baselines measured before touching anything** (the brief's instruction, and worth the ten
minutes): pytest **7,043 passed / 3 skipped / 811 subtests**, jest **2,934 / 160 suites** — both
agreeing with the brief exactly. ⚠ H15's TD-275 (two order-dependent flakes under full parallelism)
did **not** reproduce, in the baseline run or in any of the four full runs since.

**Held:** pytest **7,043 passed / 3 skipped** — identical, no test added or removed (subtests
811 → 813, the two new `AuditLoggerNameTest` checks for the `emails` package) · jest **2,934 /
160 suites** — identical · `manage.py check` 0 · `makemigrations --check --dry-run`
**`No changes detected`** · **the email golden master byte-unchanged, and its fixture file is not
in the diff** · tsc 0 · lint 0 errors · i18n ok (5,389 keys × 3) · `npx next build` exit 0 ·
code_health **0 FAIL, 6 WARN** (the same six), `std` **ok**, **`big` 19 → 17**,
**`hot#1` `income_engine.py` 95.6 → `officerCockpit.ts` 49**, **`xapp` 46 → 45**, `supp` 139,
`skip` 0, `dup` 4, `mirror` 3, `guard%` 20 — nothing worse.

**Ledger:** two `oversize_files` entries REMOVED (`emails.py`, `income_engine.py`);
`counts.courses_to_scholarship_module_level_imports` ratcheted **1 → 0**. **No `_moved` record was
needed and none was added** — the frozen `baseline` is untouched and `BASELINE_SHA256` was not
re-pinned. No ledger gained a member.

**Diff:** 64 paths — 2 deletions, 40 new modules, 2 shells, 2 new helper modules
(`constants.py`, `tests/package_patch.py`), 5 api source files, 7 api test files, 1 web test file,
`code-standards.json`, and the docs. **No importing file changed.**

**Findings raised:** TD-278 (the back-edge acceptance is unreachable by a move — the arithmetic,
and what would actually reach it), TD-279 (a basename collision, low).
