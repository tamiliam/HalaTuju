# Retrospective — Code health H15: `models.py` and `services.py`, and the guards that did not follow

**Date:** 2026-09-20 · **Sprint:** code health H15 (Phase 4, moves only) · **Cost:** ~7h against
the ~8h estimate.

The two files were 7,702 lines between them — the second and fourth largest in the repository.
They are now 33 modules and two re-export shells. Nothing about the product changed, no migration
was created, and no file that imports either one was edited.

The interesting part of this sprint was not the move. It was that **three separate guards had been
reading these files by a path, and none of them would have told us it had stopped.**

---

## What Was Built

| | `models.py` | `services.py` |
|---|---|---|
| before | 4,756 lines | 2,946 lines |
| shell (`__init__.py`) | **81 lines**, re-export only | **109 lines**, re-export only |
| modules | **15** (4,715 moved lines) | **18** (2,890 moved lines) |
| largest module | `applications.py` 899 | `blockers.py` 430 |
| lines NOT moved | 41 (13 header + 28 blank separators) | 56 (23 header + 5 deliberate re-export + 28 blank) |

Every moved line is byte-identical to the line it came from. That is asserted by the cut itself,
not claimed afterwards: the generator sliced the original file's own lines and compared each
written line back against its source before the file was allowed to exist, and a second assertion
proved that **every line of the original was either moved or declared not-moved, and that every
declared not-moved line was blank or part of the header.** Without that second check a section
banner sitting in the gap between two modules would have vanished with nothing to notice — and the
gaps are exactly where the banners live.

### The one edit made to a moved body, and why it is not optional

60 lazy `from .foo import bar` statements in `services/`, and one in `models/`, had to become
`from ..foo import bar`. A body that moves one level deeper takes its relative imports with it, and
the dot count is part of the address, not part of the code. They were found **by AST** — an
`ImportFrom` of level 1 with a non-zero column offset, i.e. indented, i.e. inside a body — never by
regex, so a matching string literal or comment could not be hit. Each one is listed in the build
log by module, line, before and after.

One further header import was added by hand: `services/blockers.py` needed
`from django.utils import timezone`. See What Went Wrong 1.

---

## What Went Well

1. **`makemigrations --check --dry-run` reported `No changes detected` on the first run after the
   cut, and on every run since.** This was the sprint's real acceptance and it was never in doubt,
   for a reason worth writing down: **all 63 models declare `db_table` explicitly** (checked
   mechanically: 63 classes, 63 `db_table` lines). Not one table name was implicit, so not one
   could drift with the module name even in principle. `app_label` comes from the app registry —
   every module is still inside `apps.scholarship`, so `get_containing_app_config` still answers
   `scholarship` — and migrations address models by `(app_label, model_name)`, never by module
   path. There are no signal receivers and no custom managers in this app, so nothing depended on
   the file being imported as one unit.

2. **TD-272's `_moved` mechanism worked exactly as designed, on its first real use.** Two records:
   `models.py`'s size entry relabelled onto `models/applications.py` (and ratcheted 4756 → 899),
   and `services.py::autofill_pathway_from_offer` onto `services/offer_sync.py`. **The frozen
   `baseline` was not edited and `BASELINE_SHA256` was not re-pinned** — the thing H11 had to do by
   hand, and the thing H14 gave up a whole deliverable rather than do. `std` read **ok**, in both
   the in-repo test and the external tool.

3. **`xapp` did not rise.** H12 warned H15 and H16 to expect a rise and to say what it was made of.
   It held at 46, because TD-268 landed first and the metric now counts app-to-app *edges* rather
   than import statements. A warning from a previous sprint that was answered by a tool fix rather
   than by an excuse is the arc working.

4. **The dependency graph was computed, not guessed.** A free-name pass over each planned slice
   said exactly which names it would need from outside, which produced both the import headers and
   the module order. It found the one genuine cycle in advance: `completeness` needs
   `income_doc_blockers` and `blockers` needs `application_completeness`. Rather than break the
   move to dodge it, the single offending function — `consent_blockers`, the only thing in the
   blockers region that reads completeness — got a module of its own, which its docstring says.

5. **`application_completeness` was moved and not touched.** It is in `services/completeness.py`,
   byte for byte, with the H8 ruling restated at the top of the file where the next person will
   read it before editing rather than after.

---

## What Went Wrong

### 1. The free-name analysis under-reported one name, and only the suite caught it

`services/blockers.py` came out missing `from django.utils import timezone`, and
`reprocess_unread_ic_documents` died with `NameError` the first time it ran.

The cause is a real limitation of how the slices were analysed. The pass treated a name as *bound*
if anything anywhere in the slice bound it — and another function in that same slice has its own
lazy `from django.utils import timezone`. So the name looked satisfied when only one of its two
readers was satisfying it. The analysis was scope-blind on purpose (that is what made it
conservative in the other direction, correctly leaving 60 lazy imports alone), and this is the
price.

**What actually caught it was the test suite, not the tool**, and that is the honest lesson: a
generated cut is a hypothesis until the suite runs. `pyflakes` would have caught it in a second and
is not installed here.

### 2. THREE guards were reading these files by path, and two of them would have failed SILENTLY

This is the part worth the sprint.

- **`test_verdict_item_i18n.py` walked `apps/scholarship/` with `glob('*.py')`, not `rglob`.** The
  moment either file became a package, that scan stopped looking inside it — and went on passing.
  It never appeared in a failure list because a scan that finds less asserts less. Now recursive,
  with a floor.
- **`test_wallet_credit.py` allowlisted `models.py` and `sponsorship.py` by BARE FILE NAME.** This
  one did fail, loudly, and the naive fix — allowlist `funding.py` instead — would have been a
  genuine weakening, because a basename allowlist exempts *any* file of that name anywhere in the
  app, for ever. It is now keyed on the path relative to the app, with a floor on modules scanned.
- **Six web drift tests read `models.py` / `services.py` by path from the web tree.** These were
  known: H13 raised TD-269 after H11 and H12 killed `officerGateDrift` between them with every api
  gate green. They failed loudly here because `readApi` throws by design. **They were found by
  grepping the web tree before the cut was planned, as the brief instructed, and that ten minutes
  is the only reason this sprint did not repeat H11.**

### 3. The `patch.object` shape was missed by the grep that found the patch strings

Searching for `apps.scholarship.services.<name>` found nine patch strings that had to follow their
dependency into a submodule. It did not find
`mock.patch.object(services, 'switch_income_route')` — the same trap wearing different clothes.
Two of those, in `test_income_route_reconcile.py`, failed in the suite and were fixed. **A search
for patch targets must cover both shapes**; the string form and the object form are the same
hazard.

### 4. Four new module names collided with existing top-level module names

The first cut produced `models/money.py`, `models/contracts.py`, `models/org_requests.py` and
`models/email_templates.py` — and `apps/scholarship/` already had a `money.py`, a `contracts.py`,
an `org_requests.py` and an `email_templates.py`. Python did not care. The basename-keyed guard in
What Went Wrong 2 did, and any future one would too. Renamed to `funding`, `agreements`,
`tenant_requests` and `comms_templates`, so **every module name under `apps/scholarship/**` is
unique again**. Cheap to do at cut time; expensive to discover later.

---

## The Bite-Checks

Six, each with a byte backup restored in a `finally` and verified by SHA-256, and each needle
proved unique in its file before the edit was made.

| | bite | result |
|---|---|---|
| (a) | drop `ScholarshipCohort` from the `models` shell | **RED** — `test_open_cohort_scope.py` errors at import |
| (b) | drop `admin_reject` from the `services` shell | **RED** — `test_org_reject.py` fails |
| (c) | one character in a moved body (`consent.py::age_from_nric`) | **RED** — `test_consent.py` fails |
| (d) | a moved model given a wrong `db_table` | **RED** — `makemigrations --check` writes a migration |
| (e) | NO-CRY-WOLF: a whitespace-only edit to a moved module | **GREEN** — 72 tests, all pass |
| (f) | a moved submodule switched to `logging.getLogger(__name__)` | **GREEN — SILENT BITE** |

(d) is the one that matters most: it proves the migration check can *see* a table change at all,
so `No changes detected` is a measurement rather than a hope.

**(f) came back silent, and the missing guard was written.** `AuditLoggerNameTest` existed — H11
added it for exactly this — but it was hard-coded to `apps.scholarship.views_admin`. Switching
`services/assignment.py` to `__name__` turned nothing red, **including the one
`assertLogs('apps.scholarship.services')` site**, because `assertLogs` on a parent records whatever
propagates up from its children and that test then matches on the message. This is H11's finding,
word for word, in a second package: the belief that the suite was holding the audit stream together
was wrong again, in a new place, for the same reason. The guard now takes a list of packages with a
floor for each, and its docstring asks the next person to add to that list when another file
becomes a package. Re-run after the fix: **RED**.

---

## Design Decisions

1. **The shells are re-export and no code, and they do NOT re-export their old dependencies.**
   `services.py`'s import header used to put `timezone`, `parse_date`, `timedelta`,
   `ScholarshipApplication` and five `send_*_email` senders into the module namespace, and patch
   strings addressed them there. Those now live in the module that reads them (H12's rule), which
   is why nine patch strings moved. The two that look the name up *through* the package at call
   time — `serializers_admin` re-imports inside the method, the cron dispatcher does
   `getattr(services, job)` — still work untouched, and were left alone rather than "tidied".

2. **`from . import requirements` and the `shortlisting` re-export STAYED in the shell**, because
   the comment above them says in so many words that they are there for callers that import them
   from `services`. A deliberate re-export is not a dependency.

3. **Three web guards walk the package; three name a module.** The split is not arbitrary. A guard
   that selects a block **by content** and asserts *exactly one match* — "the one `KIND_CHOICES`
   containing `weekly_summary`", "the OrgRequest-shaped `STATUS_CHOICES`" — must keep seeing the
   whole surface, or it silently gives up the half of the rule that says no second one exists.
   Those three got `readApiTree()`, which walks the package and **throws if it finds fewer modules
   than a stated floor**. A guard that takes the *first* match of an ambiguous name
   (`pyChoiceValues(src, 'STATUS_CHOICES')`, and `STATUS_CHOICES` is on nine models) must not walk,
   because the answer would then depend on the order files happen to sort in; that one names
   `models/applications.py`, and `readApi` throws if it moves again.

4. **`models/` is imported in dependency order, not alphabetically.** Nine ForeignKeys name their
   target class rather than a string, so the defining module has to be imported first. The shell
   says so, and says the order is acyclic and must stay that way.

5. **`applications.py` is 899 lines and that is not a failure to finish.** `ScholarshipApplication`
   is one class of 847 lines and 159 fields. No move divides a single class; splitting it is a
   schema change, not a move, and Phase 4 is moves only. Its ledger entry followed it there through
   a declared `_moved` and was ratcheted down to its real size. It is under 1,000, so it does not
   appear in `big`.

---

## Numbers

**Baselines measured before touching anything** (the brief's instruction, and worth the ten
minutes): pytest **7,037 / 3 skipped**, jest **2,929 / 159 suites** — both agreeing with the brief
on the totals. Both, however, showed **one pre-existing failure under full parallelism** that the
brief did not mention and that is not ours:
`test_sponsor_detail.py::TestMoneyIsOrgFenced::test_the_other_tenants_money_never_appears` under
`pytest -n auto`, and `src/app/admin/spending/page.test.tsx` under an unbounded `jest`. Both pass
in isolation (5/5 and 53/53) and both passed in the final gate runs. Raised as **TD-275**.

**Held:** pytest **7,037 passed / 3 skipped** — identical, no test added or removed (the two
generalised logger checks became subtests, 807 → 811) · jest **2,929 / 159 suites** — identical ·
`manage.py check` 0 · `makemigrations --check --dry-run` **`No changes detected`** · tsc 0 · lint 0
errors · i18n ok (5,389 keys × 3) · `npx next build` exit 0 · code_health **0 FAIL, 6 WARN**,
`std` **ok**, **`big` 21 → 19**, `hot#1` holds at `income_engine.py` 95.6, **`xapp` 46 → 46**,
`supp` 139, `skip` 0, `dup` 4, `mirror` 3, `guard%` 19 — every one unchanged.

**Diff:** 50 paths — 2 deletions, 33 new modules, 2 shells, 5 api test files, 7 web files,
`code-standards.json`, and the docs. **No importing file changed.**

**Findings raised:** TD-275 (the two parallel-order flakes), TD-276 (a source guard that scans a
directory must be recursive and floored — two were not), TD-277 (a basename-keyed allowlist in a
source guard silently widens as the tree grows). **TD-269 discharged** for these two files; the
systemic half of it stays open.
