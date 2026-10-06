# Retrospective — Code health H19: the standards move into how every sprint is run

**Sprint:** H19, the nineteenth and last of the code-health arc (`docs/plans/2026-09-18-code-health-roadmap.md`).
**Date:** 2026-09-20. **Baseline:** `be270fdc`, working tree clean.
**Nature of the change:** documentation only. **No production code, no test file, no test
expectation, no migration, no `code-standards.json` edit, no `Settings/**` edit.**

The three previous sprints each left the repository better. This one leaves it *legible*: the arc
was kept alive by nineteen sprints having happened, and H19's job was to make it survive ordinary
work by ordinary means.

---

## What Was Built

| | before | after |
|---|---|---|
| The arc's lessons | **~150 entries in `docs/lessons.md`**, one per incident, newest first | **nine groups of short imperative rules** in `halatuju_api/CLAUDE.md` `## Code standards`, each with its reason — read at every sprint start. `lessons.md` untouched and still the evidence |
| The health pre-flight at sprint start | nothing | **written out in full for the lead to paste** into `Settings/_workflows/sprint-start.md` — measure your own baselines, read the hotspot list, grep both budget files and the other tree for every path you will touch, re-derive the plan's numbers and its premise |
| The close | takes a code-health reading (added 2026-09-18) | **written out in full** — run every suite whatever you touched and quote what you ran; `/code-review` on the diff and a bite-check on anything supposed to fail; a reading that moved because the sprint did the right thing is a finding about the TOOL |
| `docs/code-health.md`'s header | "H1–H12 are shipped" | the arc is CLOSED; what is enforced and where; **the three targets no ledger enforces, named with their real readings** |
| The arc's own record | nothing | **the closing retrospective**, the last section of the roadmap: the readings then and now, everything promised and not delivered, what is enforced and by what, what is open and whose it is |
| Enforcement gaps | unrecorded | **TD-284** |

**The nine groups**, in the order they sit in `CLAUDE.md`: a guard is only as strong as its
cheapest passing state · bite it or you do not know · a number you did not measure is a number you
do not have · when a reading punishes the right behaviour, fix the reading · a standard is the
thing that RUNS · "nothing uses this" is a claim about your search · measure before you reach for
the obvious fix · characterise before you change, and never edit an expectation · prose rots, write
it so it cannot.

**How they were chosen.** Every entry in `lessons.md` was read. An entry earned a rule only if it
(a) recurred — most of the nine were met three, four or five times across the arc — and (b) would
change what a future sprint DOES, not merely what it knows. Single incidents stayed in
`lessons.md`. The two classes that already had a section of their own — moving a file that is in a
ledger (TD-272), and a tree-walking guard needing a floor (TD-276) — were cross-referenced, not
repeated.

---

## What Went Well

**1. The workflows turned out to need less than the roadmap assumed, and something it had not
named.** H19's original scope listed five workflow files. Reading them against eighteen
retrospectives showed the two that matter are `sprint-start.md` and `sprint-close.md`, and the most
valuable single line is one the roadmap never mentioned: **measure both baselines yourself before
touching anything.** H13 was briefed at 2,913 jest against a tree standing at 2,900 with a whole
suite dead at import for two sprints, and that is the class the arc met most often — an inherited
number predating the thing that broke it. It is now the first bullet of the pre-flight.

**2. "Tighten the ratchet" turned out to be already done, and it was checkable in one command.**
The roadmap's last H19 line asked for "the last turn of the ratchet". The ratchet's third rule
(`budget <= actual + slack`) turns the gate red the moment a budget sits loose above reality, so
the turning happens in the sprint that earns it. Measured rather than assumed: **zero of 32 api
and zero of 17 web `oversize_files` entries sit more than ten lines above the real file.** A
ceremony at the end would have changed nothing and made the gate brittle. Reported instead of
performed.

**3. The gap that is left is the arc's own thesis, and it is now a TD entry rather than a silence.**
Three targets — `fix%`, `big`, `guard%` — are readings and not tests, and all three are the ones
that were missed or went the wrong way. That is not a coincidence to be embarrassed about; it is
the argument for the whole arc, restated by its exceptions, and TD-284 says so in those words.

**4. The arc's closing retrospective is checkable line by line.** Every number in it is a row of
the Trend table, a gate line in a named retrospective, or a count taken today. Where a figure is
not known — the hours, for fifteen of the nineteen sprints — it says so rather than inventing one.

---

## What Went Wrong

### 1. The acceptance's dry run was not performed, and the substitute is weaker in one specific way.

H19's acceptance asks for a throwaway branch that adds a 700-line file, a mirrored rule, a
hand-built fixture and a query in a loop, and is refused four times by four different tests.

**What happened.** The branch was not made. Each of the four refusals is already pinned by a named,
bite-checked test — `test_no_unlisted_source_file_passes_the_line_limit`, `codeStandards.test.ts`'s
*"a comment claiming a mirrored rule names the drift test that guards it"* (itself bitten by *"a
plain mirror claim is caught"*), `test_no_unlisted_test_file_hand_builds_an_application`, and
`test_query_budgets.py` at zero slack — so the dry run would re-prove on one branch what those
tests prove on every run. The brief also forbade new machinery and new test files.

**Why it is still a loss, stated plainly.** Those four tests each prove their own refusal in
isolation. **Nobody has watched all four fire against one branch in one run**, which is the only
thing that demonstrates the *system* refuses a careless sprint rather than four tests refusing four
things. The claim in the roadmap is "each refusal is proven"; it is not "the dry run passed", and
the two are not the same sentence.

**What prevents it recurring.** It is written as a *not delivered* line in H19's roadmap section
rather than left out, so the next reader can do it in twenty minutes if they want the stronger
evidence.

### 2. The roadmap's H19 scope had a line that could not be executed as written, and nobody checked it when it was written.

*"Tighten `code-standards.json` to the arc's targets — the last turn of the ratchet."*

**What happened.** Two of the arc's three outstanding targets (`fix%`, `guard%`) are not in a
ledger and cannot be put in one without changing the tool; the third (`big`) duplicates an existing
ledger at a different threshold. The budgets that DO exist were already tight.

**Why it happened.** The line was written on 2026-09-18, before `code-standards.json` existed —
H4 built it the next day. It was a reasonable sentence about a file nobody had seen yet, and it
survived unexamined into the sprint that had to execute it. **This is the arc's own recurring
finding — a plan's premise ages, not just its file table — arriving on the last day, in the plan
that recorded the finding.**

**What prevents it recurring.** The proposed `sprint-start.md` pre-flight ends with *"re-derive the
plan's numbers and its premise"*, and names the three sprints (H14, H16, H17) that each accepted an
inherited acceptance and missed it on the last day.

### 3. The harvest is long, and length is a real cost in a file loaded every session.

**What happened.** `## Code standards` gained about 130 lines. `halatuju_api/CLAUDE.md` is already
long, and a rule nobody reads is worth nothing.

**Why it was accepted rather than trimmed further.** Each of the nine groups is a class that cost
this project real time at least twice; cutting to five would have meant choosing which recurrence
to forget. The mitigation is structural rather than editorial: the groups are numbered and
headed in bold, so the section is scannable, and each rule leads with the instruction and follows
with the reason, so a reader can stop after the first clause.

**What would be better.** If it is still unread in three months, the honest fix is not to shorten it
but to find out which rules never fire and delete those — which needs the evidence a few more
sprints will produce.

### 4. Two workflow files the roadmap named got a proposal each and no more thought than that.

`small-change-lane.md` (the third consecutive accept of the same WARN becomes a TD entry) and
`system-audit.md` (a hotspot read-through every fifth sprint) are both one-paragraph additions,
proposed to the lead. Neither was weighed against how those workflows are actually used, because
this sprint could not edit them and the brief did not ask. **The third-accept rule already exists
in `code-health-audit.md` under "Failure modes", which nobody reads at the moment of accepting** —
that is the real finding, and the proposal moves it into a step rather than leaving it as a warning.

---

## Bite-checks

**None. This sprint added no guard, no test and no machinery**, so there was nothing whose failure
could be injected. Said explicitly because "no bite-checks" and "the bite-checks were skipped" read
identically in a report, and the arc met that exact ambiguity twice (an empty result line reading
as a pass).

The one claim in this sprint that *could* be checked mechanically was checked: **the ledgers have
no headroom**, measured by reading every `oversize_files` entry against the real file's line count
in both services. Zero of 49 entries sit more than ten lines above reality.

---

## Design Decisions

**1. The harvested rules went into `CLAUDE.md`, not into `lessons.md` or a new file.**
`lessons.md` is the evidence and is read at sprint start by a workflow step that asks *"is this
relevant to this sprint's scope?"* — a question nobody can answer honestly against 150 entries.
`CLAUDE.md` is loaded every session whether anybody asks or not. A third file would have been a
second home for the same rule, which is the failure Phase 3 spent four sprints removing.

**2. `lessons.md` was left completely untouched.** Pruning it would have destroyed the evidence
behind the rules that were just written, and the arc's own record says an entry's story is what
makes a rule believable when somebody wants to argue with it. `system-audit.md` step 3 is where
lessons get pruned, and it has its own cadence.

**3. The workflow text was written out verbatim in the report rather than summarised.** The lead
applies it; a summary would have made the lead re-derive wording this sprint had already reasoned
about, and the arc's record is full of instructions that changed meaning in the retelling.

**4. Nothing was deleted anywhere.** The roadmap's original H19 scope is kept below the delivered
block, marked as the original; the superseded claims in `docs/code-health.md`'s header were
rewritten rather than dropped. A reader six months from now needs to see what was planned as well
as what happened.

---

## Numbers

| | |
|---|---|
| pytest | **7,053 passed / 3 skipped** — measured at `be270fdc` before any edit, and again at close. **IDENTICAL.** No test added, removed or edited |
| jest | **2,958 passed / 163 suites** — measured before any edit, and again at close. **IDENTICAL** |
| Both baselines vs the brief | the brief stated 7,053 / 3 skipped and 2,958 / 163. **Both agree.** |
| `manage.py check` | 0 |
| `makemigrations --check --dry-run` | `No changes detected` |
| `npm run gates` | tsc 0 · lint 0 errors · i18n 5,389 keys per locale · jest 2,958 |
| `npm run bundle-budget` | ok — median 256 kB, worst 339 kB, shared 87.2 kB |
| `npx next build` | exit 0 |
| `code_health.py` (read-only) | **0 FAIL, 6 WARN** — `fix%` 42, `big` 17, `long` 15, `dup` 4, `mirror` 3, `guard%` 20; `std` ok |
| Production code changed | **none** |
| Test files changed | **none** |
| `code-standards.json` changed | **none, in either service** |
| `Settings/**` changed | **none** — read-only by the brief; the workflow text went to the lead |
| Ledger headroom, measured | **0 of 32 api and 0 of 17 web `oversize_files` entries** more than ten lines above the real file |
| TD raised | **TD-284** — `fix%`, `big` and `guard%` have targets and no enforcement |
| Files written | `halatuju_api/CLAUDE.md`, `docs/plans/2026-09-18-code-health-roadmap.md`, `docs/code-health.md`, `docs/technical-debt.md`, `CHANGELOG.md`, this file |

---

## The one sentence for the owner

**Everything that prevents a bug reaching production is now a test that runs before every deploy,
and the three things that are still only measurements are exactly the three that slipped — which is
the arc's whole argument, written by the exceptions rather than by me.**
