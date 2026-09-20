# Retrospective — Code health H18: two budgets, one of which found something

**Date:** 2026-09-20 · **Sprint:** code health H18 (Phase 5 closes) · **Cost:** ~7h against the
re-estimated ~9h.

Phase 5 asked what the product COSTS. H17 answered the download half and refused to write a
kilobyte budget it could not measure. H18 built the reader H17 said was missing, added the query
budget nobody had ever taken, and closed TD-280 by moving sixteen Malay words from the browser to
the payload.

**The sprint's real output is a finding, not a feature.** Opening one applicant on the officer
cockpit costs **315 database queries** — before that applicant has uploaded anything. The budget
that now holds that number is worth much less than the fact that somebody finally counted it.

---

## What Was Built

| | before | after |
|---|---|---|
| First-load JS budget | **none** — TD-281 said why | ledger + 300 kB ceiling + 256 kB median, read from a real `next build` **in the deploy gate** |
| Queries to open one applicant | **unmeasured since June** | **315** (no documents) / **385** (three), budgeted with ZERO slack |
| `/admin/scholarship/[id]` first-load JS | **389 kB** | **292 kB** (its own page chunk 132 → 34.8 kB) |
| Modules statically importing a catalogue | 3 | **2** — `lib/preUPlan.ts` deleted |
| Median route, 87 routes | 256 kB | 256 kB (unchanged — TD-280 touched one route) |

Three new files, sixteen edited, one deleted:

1. **`halatuju-web/scripts/bundle-budget.js` (new)** — reads `next build`'s route table on stdin,
   echoes it straight back out, and refuses a regression three ways: a route at or above the
   300 kB ceiling that is not in the ledger; a ledgered route past its own number; the median
   above 256 kB. It ratchets down only — an improvement fails with *"LOWER it to N"*.
2. **`halatuju_api/apps/scholarship/tests/test_query_budgets.py` (new)** — two readings through
   the real endpoint, built with the H5 factory, against `query_budgets` in the api ledger.
3. **`halatuju-web/src/app/admin/scholarship/[id]/view.preUTrack.test.tsx` (new)** — the rendered
   proof that the officer reads the same words after the label moved to the server.
4. **TD-280, served not mirrored** — `card_display.preu_track_malay` + a derived
   `ScholarshipApplication.pre_u_track_label` property (no migration, no column) + one
   `ReadOnlyField` on the cockpit serializer. `lib/preUPlan.ts` and its 393 kB import are gone.

---

## What Went Well

1. **The reader came before the number, and that ordering was the whole of TD-281.** H17's entry
   said: *"a budget nothing measures reads as enforced and is not."* The tempting shortcut was to
   write the kilobytes into `code-standards.json` and have jest assert `budget <= baseline`, which
   would have looked like a standard and measured nothing. Building the reader first forced the
   real question — **where does this run?** — and the answer (the deploy gate, because it is the
   only place that already builds) is the thing that makes the numbers bite.

2. **The half nobody would have written is the half that keeps it honest.** `codeStandards.test.ts`
   now asserts that `cloudbuild.yaml` still contains `npm run bundle-budget`. The script could be
   perfect and the ledger could be current and one tidy-up of the gate would turn both into
   decoration, silently. That assertion is four lines and it is the difference between a budget
   and a comment.

3. **Measure first was not a formality — it changed what the sprint did.** The brief allowed a
   fix only if it were a one-line `select_related`/`prefetch_related`. Measuring first showed
   that it cannot be: the repeated query comes from `.filter(...)` calls on a related manager
   inside pure helper functions, and a filtered related-manager call **ignores a prefetch cache**.
   Had the sprint reached for `prefetch_related('documents')` on the view's queryset it would have
   changed nothing, passed every test, and been written up as a fix.

4. **The standards refused this sprint's first two attempts, and they were right both times.**
   TD-280's obvious shape — a `SerializerMethodField` plus its method — put `serializers_admin.py`
   at 1,246 lines against an allowance of 1,234. The rule's own instruction is *"that allowance
   exists for a hotfix, not for new work; SPLIT THE FILE FIRST"*, and the honest response was to
   put the code where there was room: a derived model property, which is arguably where a derived
   attribute belonged anyway. Then `models/applications.py` came out at 920 against 919 and the
   docstring was trimmed twice. **A standard that never refuses anything is not a standard**, and
   this is the first sprint of the arc that had to change its design to obey one.

5. **`not_sure` was the detail that would have shipped a wrong screen.** The api's `_TRACK_LABEL`
   has five codes; the FE read six, because `messages/ms.json` carries
   `plan.stream.not_sure = "Belum pasti"` and the browser merged `stream` and `track`. Serving
   `_TRACK_LABEL` alone would have blanked the stream for every undecided STPM applicant. It is
   also why the cockpit map is a **separate** dict and not a sixth entry: on a sponsor card,
   "STPM · Belum pasti" reads as a specialisation, and `preu_label` must go on ignoring it.

6. **Eight bite-checks, all eight behaved. None was silent.** Byte backup, SHA-256 verified either
   side, needle proved unique, restore in a `finally`.

---

## What Went Wrong

### 1. The bite harness restored an intermediate state, and only the SHA caught it.

Bite (e) edits one file twice — remove the field from `Meta.fields`, remove its declaration. The
harness keyed its backups by path, so the second backup captured the file **with the first edit
already applied**, and the `finally` restored that. The tree was left with the declaration present
and the `Meta` entry missing: a state that fails at import, but only if something imports it.

It was caught in the next breath because the harness prints `sha_before` for every edit and
`sha_after` for every restore, and the two lines did not match the first `sha_before`. The file
was put back by hand and re-verified against the original digest before anything else ran.

**The lesson is not "back up by index".** It is that **the SHA print is not ceremony — it is the
only thing standing between a bite-check and a corrupted tree**, and a harness that edits the same
file twice is exactly where a restore goes wrong. Three of this arc's retrospectives describe a
bite that was assumed rather than proved; this is the first where the *restore* was the unsafe
part. Print the digest on both sides, always, and read it.

### 2. "Roughly the other routes' level" was optimistic, and the arithmetic was available.

The brief asked for `/admin/scholarship/[id]` to drop "to roughly the other routes' level". It
went 389 → 292 kB against a 256 kB median — a 97 kB fall, exactly the weight of `ms.json`, and
still 36 kB above the median. That 36 kB is the cockpit's **own** code: a 3,587-line view plus its
cards, which is genuine page weight and not a catalogue.

The number was knowable on day one: the route's page chunk was 132 kB, of which ~97 kB was the
catalogue, leaving ~35 kB of page. **H17's lesson for the third time** — *a target inherited from
a differently shaped predecessor needs its own arithmetic before it is accepted* — and H18 did the
subtraction after the build rather than before it. The route is no longer an outlier (`/course/[id]`
is 299, `/onboarding/profile` 296) and it is out of the ledger, which is the outcome that matters;
the sentence in the brief was still a claim nobody had checked.

### 3. The re-estimate's split was backwards, for a reason worth keeping.

H17 re-estimated H18 as ~6h of query work and ~3h of bundle work, on the grounds that "the
applicant-detail endpoint is unmeasured since June and is the sprint's real risk". The actual
split was closer to 2h query, 4h bundle, 1h TD-280.

**Measuring an N+1 is cheap; fixing one is not, and the brief only allowed the measurement.**
Thirty lines of `CaptureQueriesContext` and a fixture gave the number in an hour. Meanwhile the
bundle half — which H17 called "one afternoon of measurement plus a source guard" — cost more,
because the parsing was the easy part and *deciding where the reader runs, then proving the gate
still invokes it*, was the work. An estimate that prices a sprint by how alarming the subject is
will be wrong in both directions at once.

### 4. A test deleted is a test that has to be re-proved somewhere.

Deleting `lib/preUPlan.ts` meant deleting the four `preUTrackMalay` cases in `scholarship.test.ts`.
That is the H13/H15/H16 precedent — code that leaves takes its tests — but it is also the shape of
a sprint quietly reducing coverage to make a change pass. The expectations were rewritten in the
runtime that now owns the lookup (`TestCockpitTrackLabelParity`: the same six labels, the same
nulls, **plus** a parity guard against `messages/ms.json` that the FE version never had), and a
comment at the deletion site names where they went. **Net coverage rose.** It would have been very
easy to delete four tests and write none, and nothing in the gate would have said a word.

---

## Bite-checks

Eight, each with a byte backup, a SHA-256 verified before and after, a needle proved unique, and a
restore in a `finally`. All eight behaved; **none was silent.**

| | bite | expected | result |
|---|---|---|---|
| (a) | a catalogue import added to `lib/scholarship.ts` (H17's original regression), then a REAL `npm run bundle-budget` | the bundle gate RED, naming routes | **14 problems, exit 1.** Ten unlisted routes named over the ceiling (`/admin/scholarship/[id]` 389 kB, `/onboarding/profile` 393 kB …), three ledgered routes named over their own number (`/profile` 436 vs 339, `/scholarship/apply` 411 vs 314, `/scholarship/application` 402 vs 305), and the median at 257 vs 256. All three branches fired. |
| (b) | `/profile`'s recorded budget lowered 339 → 300, real build log | RED — proves the comparison is not a no-op | *"/profile: 339 kB of first-load JS, budget 300 kB — 39.0 kB over"*, exit 1 |
| (c1) | one extra query added to `AdminApplicationDetailView.get` | the query budget RED, naming the count | *"316 not less than or equal to 315"* **and** *"386 … budget 385"* — both fixtures |
| (c2) | the bare query budget lowered 315 → 310 | RED | *"315 not less than or equal to 310"* |
| (c3) | the bare query budget RAISED 315 → 400 (buying room) | refused twice | `test_query_budgets` tightness RED **and** `test_code_standards.test_no_budget_number_is_above_the_baseline` RED |
| (d1) | the served Malay label changed in `card_display._TRACK_LABEL` | the parity guards RED | 8 red, including `TestCockpitTrackLabelParity` (all three tests), the pre-existing `TestTrackLabelParity`, and `TestTheServedPreUTrackLabel` |
| (d2) | the cockpit made to render the suffix uppercased | the rendered test RED | `view.preUTrack` → 2 of 3 red, *"Unable to find an element with the text: · Sains Sosial"* |
| (e) | `pre_u_track_label` removed from the payload (both the declaration and `Meta.fields`) | a named test RED | `TestTheServedPreUTrackLabel`, both tests: *"'pre_u_track_label' not found in {…}"* |
| (f) | **NO-CRY-WOLF:** one extra space inside a comment in each tree | everything green | pytest **5,640 / 3 skipped** (scholarship app), `npm run gates` **2,958 / 163**, `npm run bundle-budget` **ok** — three separate runs, all exit 0 |

⚠ Bite (a) was run as a REAL build rather than against a doctored log, deliberately: a parser
proved only against text it was handed is a parser proved against its own assumptions. Bite (b)
used the real build log, because what it tests is the comparison, not the parse.

---

## Gates

| | |
|---|---|
| pytest | **7,053 passed / 3 skipped** (7,043 / 3 at baseline; **+10 new**, none removed) |
| jest | **2,958 / 163 suites** (2,954 / 162 at baseline; **+7 new, −3 deleted with their module**, +1 suite) |
| existing test expectations edited | **one fixture line.** `TestTheMoveArithmetic.base()` in `test_code_standards.py` gained `'query_budgets': {}` — `effective_baseline` returns one key per ledger, so a missing ledger would compare two different shapes. No assertion changed. The four `preUTrackMalay` cases were DELETED with the module they tested and re-proved in the api (see What Went Wrong 4). |
| `tsc --noEmit` | 0 |
| `next lint` | 0 errors; no new warning on any file touched |
| i18n check | 5,389 keys per locale, all three, 0 warnings |
| `next build` | exit 0, 88 routes (87 with non-zero first-load JS) |
| `npm run bundle-budget` | **ok** — 87 routes, median 256 kB, worst 339 kB, shared 87.2 kB |
| `manage.py check` | 0 issues |
| `makemigrations --check --dry-run` | *No changes detected* — TD-280 needed no migration (a derived property, not a column) |
| `code_health.py` (read-only) | **0 FAIL**, 6 WARN — H16/H17's set, unchanged: `fix%` 42, `big` 17, `long` 15, `dup` 4, `mirror` 3, `guard%` 20. `std` **ok**, `xapp` **45**, `hot#1` `officerCockpit.ts` 49 — all three unmoved. |

**`BASELINE_SHA256` was re-pinned in BOTH services**, deliberately and in the same commit as the
edit: the api's third re-pin (after H5's and H11's) and the web's first. Both are H5's case, not
H11's — **a new standard has to enter the frozen record or it has no baseline to be measured
against**, and `budget <= baseline` would be vacuous for it. Nothing was raised, no existing
number moved, and no existing ledger gained a member. Both `_history` / `last_tightened_on` notes
say so.

**Findings raised:** TD-282 (the applicant view is an N+1, 315/385/437 queries by document count,
NOT fixed, needs its own sprint and an owner's word) and TD-283 (`serializers_admin.py` and
`models/applications.py` are at their exact line allowances; the next change to either must split
it first).

---

## The deploy gate change, stated exactly

One block was added to `halatuju-web/cloudbuild.yaml`, inside the **existing** `test` step, after
`npm run gates`: an echo and `npm run bundle-budget`. Nothing else about the deploy changed — no
trigger change, no new substitution, no `machineType`, no timeout change, and **the `_SKIP_TESTS`
bypass still works exactly as before** (it exits the step before this line is reached, and the
loud banner is untouched).

**Cost in wall time: none, on a green run.** The `test` step runs in PARALLEL with `Build`
(`waitFor: ['-']` on both) and `Push` waits for the two. `docker build` alone averages 6.9 minutes;
`npm ci` + gates + one `next build` comes to roughly four. If the gates ever do overtake the image
build, the extra is the length of one `next build` — about a minute — paid only on builds that
were going to deploy anyway. The 30-minute timeout is unchanged and has ample room.

---

## For H19

1. **Ask every standard you move into a workflow: where does this RUN, and what turns red?**
   That question is what H17's refusal and H18's `cloudbuild.yaml` assertion are both made of, and
   it is the difference between a standard and a paragraph. H19's acceptance — a throwaway branch
   refused four times by four different tests — is exactly the right shape.
2. **The other four endpoints are cheap now.** The query-budget pattern is one fixture, one ledger
   key and ten lines. Applications list, student application, sponsor pool, Programme Overview.
   Expect findings; the first one measured was 315.
3. **Two api files cannot take another line** (TD-283). If H19 tightens `code-standards.json` "to
   the arc's targets", tighten those two entries DOWN to their real sizes and let the next sprint
   meet the wall honestly rather than inside a 20-line allowance.
4. **Nothing in this repository measures TIME.** Both of Phase 5's budgets count things. That is
   worth one sentence in whatever H19 writes into `sprint-close.md`, so the next person who says
   "the cockpit is slow" knows no gate would have told them.
5. **TD-282 is an owner decision, not an engineering one.** A per-request document cache through
   three engines is a sprint. It is also the single largest measured inefficiency in the product.
