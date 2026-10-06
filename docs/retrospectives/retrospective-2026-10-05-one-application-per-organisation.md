# Retrospective — one application per organisation (2026-10-05)

Sprint, three rounds: build; the lead's round-2 findings (the closed-link regression, TD-348); the
adversarial review's findings (round 3). Api + web. Built locally in the worktree
`feat/apply-one-per-organisation` (cut from `a3f56a44`), **not committed, not pushed, not deployed** —
the lead re-runs every gate before any push. The owner's ruling on TD-337 that this sprint builds is
recorded verbatim in `docs/decisions.md` (2026-10-05).

---

## 1. What Was Built

* **One rule, on the server.** `apps/scholarship/services/apply_gate.py`, in this order: an
  application in play (not rejected / withdrawn / closed / expired, by the student-facing status) in
  ANY organisation → `application_in_progress`; a non-expired application in the same round →
  `already_applied`; otherwise allowed. `IN_PLAY_STATUSES` and `FINISHED_STATUSES` classify all
  thirteen statuses, and a test holds them to an exact partition. ⚠ Stricter than the owner's
  per-organisation ruling ACROSS organisations, deliberately, until roadmap M2 (round 3; decisions.md
  item 1a).
* **The submit uses it.** `ApplicationListCreateView.post` replaced its inline per-round check with
  `apply_gate.apply_verdict` and answers 409 `{error, code}` (the old same-round sentence kept).
* **The page can ask.** `GET /api/v1/scholarship/apply-gate/?programme=<code>` (`views_apply_gate.py`,
  a thin door to `apply_gate.verdict_for_visit`) answers `{allowed, reason, application_id}`. A
  student in play is answered `application_in_progress` on EVERY visit — any code, unknown, closed,
  bare, nothing open; with nothing in play, an unknown and a closed code both answer allowed.
* **One home for the student-facing status.** The serializer's masking (embargoed decline → the stage
  it left; `recommended` → `interviewed`) moved verbatim to `apps/scholarship/student_status.py`;
  the serializer and the gate both call it.
* **The web obeys and keeps no rule.** `lib/useApplyGate.ts` asks (never for a signed-out visitor),
  re-asks whenever the gift in force changes; ONE function, `applyPageExit`, decides every redirect off
  the apply page (in progress → her application, first; then, once intake and gate have both answered,
  bare + nothing open → `/scholarship`). `useApplyGift` exposes `noneOpen` and never redirects. The
  already-applied card is `AlreadyApplied.tsx` (new). `lib/applyGate.ts` is deleted; the apply page no
  longer reads the application list.
* **The application page's "closed" card links back to the apply page** ("See programmes that are open").
* **TD-340.** A server refusal at submit lives in its own `serverError` and stays until the form
  changes or she submits again; `application_in_progress` / `already_applied` at submit are adopted
  by the gate.
* **Her CURRENT application answers the agreement read (round 3).** `BursaryAgreementView` reads
  `apply_gate.in_play_application` first, so an old signed agreement on a closed application no longer
  stands in for a new award's (net zero lines in `views.py`).
* **Sandbox.** `stubFetch.ts` answers the gate with "allowed", so the three apply surfaces still show
  the form.

## 2. What Went Well

* **Every status was classified before any code read it** — none was ambiguous; the partition test
  makes the next one a red test, not a guess.
* **The embargo was tested by building every reachable variant**, not one: a decline from each stage
  `admin_reject` accepts plus the legacy blank snapshot.
* **The invariant now proves the real claim (round 3).** The api half builds real rows for every
  in-play status and every embargoed shape beside every set of finished ones (102 cases), asks the gate
  over HTTP, and proves her served list carries the gate's `application_id` with an in-play status and
  every other row with a finished one; the web half proves `applicationScreen` then shows exactly that
  row (`kind: 'one'`, same id), at every position. Round 1's version passed on "several" or on the
  wrong row; bite (h) shows the new one does not.
* **Oversize files shrank** while the rule grew: `views.py` 2436 → 2434, `serializers.py` 1215 → 1204,
  `apply/page.tsx` 1070 → 1062.
* **Round-3 weight discipline.** Item 4a (gate the closed card's link on the intake) was built,
  measured at +28 gz bytes on a route with 0.323 kB of room, and taken back out rather than shipped
  under the 0.30 kB floor (TD-354).

## 3. What Went Wrong

**1. The builder was cut off by a usage limit in the middle of the bite-checks.**
*Symptom:* the session stopped just after bite-check (d) was announced.
*Root cause:* a long single session doing build, five bite-checks and the documents in one run.
*System change:* none in code — every fault was injected only after a scratch backup was taken and
hashed, so the lead could confirm both touched files byte-identical. Keep that discipline.

**2. A comment tripped the web's `any` count.** The scanner is textual and counts comments
("`mustLeaveApplyPage`: any application"); the comment was reworded. No suppression, no budget touched.

**3. `/scholarship/application` has little room.** 0.323 kB locally, about 0.26 at the deploy gate's
reading. It blocked item 4a (TD-354). The next change to that page should take weight off first.

**4. Round 1 broke the commonest visit of the year: an applicant on her own, CLOSED gift's link.**
*Symptom:* she was answered `allowed` (no open round) and shown "Applications closed" instead of her
application; on a bare visit with nothing open two redirects raced.
*Root cause:* the gate was written as the SUBMIT's question ("may she join this open round?") and
reused for the PAGE's ("where does this visitor belong?"), which has no round most of the year. The
round-1 report flagged it, but a page test pinned it with a stubbed gate instead of fixing it.
*System change:* the in-play half needs no open round; one pure function decides every redirect; page
tests assert exactly ONE `router.replace` and zero renders of the closed card, with the gate answering
after the intake. Lesson: a risk found in your own report is a defect to fix, not a test to write
around.

**5. Round 1 built the ruling literally, and the student side could not carry its consequence.**
*Symptom:* (adversarial review) "another organisation never blocks" made a SECOND LIVE application
reachable through the normal screens for the first time — `_current_application` 409s 13 endpoints,
the "several" card has no links, onboarding and the banner pick by position, and an embargoed decline
in A beside a live B behaves differently from a real in-process A, which leaks the decision.
*Root cause:* the brief asked whether the rule was right; nobody asked what each student-side read
does with the lists the rule newly allows. A rule that widens what the database can hold needs every
reader of that table checked against the new shapes.
*System change:* in play blocks everywhere until M2 (decisions.md 1a, TD-353); the invariant test
asserts the screen shows THE blocking application; item 3's grep of every student-side pick.

**6. TD-348 could not be closed in this sprint.** The fix moves the acknowledgement email to
`on_commit`, which splits `create_application`; out of bounds. The review's reading is recorded on the
row: the window is the gate's read to the INSERT; a script could hit it, a person realistically cannot.

**7. A semantic conflict with a parallel session's tests merged cleanly (rebase onto request #26).**
*Symptom:* after the rebase the web gates and the bundle passed, and only the FULL api suite went red:
five of request #26's new tests filed a second application for a student whose first was still in
play (`recommended`, or an offered award) and expected 201; the new rule answers 409.
*Root cause:* the two sessions changed one rule from opposite sides on the same day — #26 wrote tests
that ASSUMED "a second application to another round is allowed", this sprint removed that — and no
file conflicted, so git could not see it. A rebase is a textual merge; only the other side's tests
know what it assumed.
*System change:* after any rebase onto another session's work, run the FULL api suite before calling
the merge done (the lead did; it caught it). The five tests were re-expressed, not weakened: the two
Gap-A tests drive `create_application` directly on a frozen profile (the intake guard stays, defence
in depth) and pin the submit's new 409; the three first-application form tests arrive from a FINISHED
earlier application; and a guard pins that a finished application with no offered award is not frozen.

## 4. Design Decisions

Recorded in `docs/decisions.md` (2026-10-05, "One application per organisation"):
1. The rule as built and its order; 1a. in play blocks everywhere until M2 — stricter than the ruling
   across organisations, and why.
2. The embargo: the gate reads the student-facing status, from one shared function.
3. The web asks the server and keeps no copy; 3a. the in-play half needs no open round and the answer
   never depends on the code; 3b. one place decides the redirect; 3c. TD-348 left open.
4. The organisation is not read by the rule (round 1's null-organisation rule is gone).
5. Her CURRENT application answers student-side reads that pick one (the agreement).
6. Same-organisation multi-application ruled OUT by the owner; cross-organisation blocked as built
   until M2–M4.

Choices made by the builder where the brief left room:
* **`application_id` is returned for both refusals** (her own row).
* **The gate is keyed on the URL's code (`named`)**, resolved by the server exactly as the intake
  resolves it.
* **`AlreadyApplied` is not lazy** (~0.2 kB; a lazy boundary would flash on the screen that explains).
* **Any decided exit is drawn as "loading"**, so neither the form nor the closed card flashes.
* **In progress is acted on as soon as the gate answers**, without waiting for the intake — it is first
  in the order whatever the intake says; the landing redirect waits for both.
* **`in_play_application` takes the newest in-play application** if legacy data holds several.

## 5. Review findings and their answers

The adversarial review could not get two in-play applications in one organisation, could not leak the
embargo inside the apply flow, and found one redirect in every ordering. Its findings, as summarised by
the lead:

| # | Finding | Answer |
|---|---|---|
| 1 | "Another organisation never blocks" makes a second LIVE application reachable through the normal screens; `_current_application` then 409s (`application_ambiguous`) 13 student endpoints | **Fixed by design** — in play blocks everywhere until M2 (decisions.md 1a); TD-353 |
| 2 | With two live, the application page shows a linkless "several" card, and onboarding / `ScholarshipBanner` pick by position | **Fixed by design** (item 1 — one in play at a time); TD-341 updated |
| 3 | `_current_application` reads the RAW status, the screen the masked one: an embargoed decline in A beside a live B behaves unlike a real in-process A — the decision leaks | **Fixed by design** (item 1: the embargoed A is in play, so B cannot be filed) |
| 4 | Same organisation, old + new: `BursaryAgreementView` shows the OLD signed agreement to a graduate awarded on a new application | **Fixed** — answers for her current (in-play) application; tests both ways |
| 5 | The verdict-then-insert is not serialised (two rounds, one moment) | **Debt** — TD-348, with the review's reading and fix recorded |
| 6 | An in-play student could map her own organisation's codes (known code judged by organisation) | **Fixed** — in play answers `application_in_progress` on every visit, before the code is read |
| 7 | An application stuck in process blocks every later round with no word to the student | **Owner** — TD-352 |
| 8 | The closed card's "See programmes that are open" shows when none is | **Attempted, backed out** — +28 gz bytes put `/scholarship/application` under the 0.30 kB floor; TD-354 |
| 9 | The invariant test passed on `several` or on a different application from the one the gate named | **Fixed** — `kind: 'one'`, same id, over every list the rule can produce; bite (h) red |
| 10 | Pre-existing embargo leaks: a reopen clears the marker but leaves `rejected`; the release clears the marker before a send that may fail | **Debt** — TD-349 |

Also raised from the review: TD-350 (shortlisted decline → uploads 403 during the embargo), TD-351
(same-round double submit → 500).

## 6. Bite-checks

Each fault was injected after a scratch backup, the named tests run, and the original restored from
the backup with a matching SHA-256. None silent.

| # | Guard | Fault injected | Result |
|---|---|---|---|
| a | `test_apply_gate.py` | round 1: the gate ignores the organisation | **RED** — 4 failed |
| b | `test_apply_gate.py` | the gate reads the raw `status`, not `student_facing_status` | **RED** — 18 failed |
| c | `test_apply_gate.py` + `studentScreenDrift.test.ts` | `FINISHED_STATUSES` gains `submitted` | **RED** — api 7, web 1 |
| d | apply page tests | the page ignores the served verdict | **RED** — 11 failed |
| e | apply page tests | a generic server error goes back into `error` | **RED** — 3 failed |
| f (round 2) | `test_apply_gate.py` | the gate ignores a known CLOSED programme | **RED** — 5 + 9 subtests |
| g (round 2) | apply page tests | `useApplyGift` redirects to `/scholarship` by itself (the race) | **RED** — 2 failed |
| a′ (round 3, re-pointed) | `test_apply_gate.py` | the gate ignores applications OUTSIDE the target round's organisation | **RED** — 3 tests + 17 subtests (every in-play status in another organisation, the submit, over-rounds, legacy newest) |
| h (round 3) | `studentScreenDrift.test.ts` | `applicationScreen` shows `rest[0]` instead of the submitted row (still `kind: 'one'`) | **RED** — 16 failed |

Backups: round 1 `rule_bk_apply_gate.py` (149d9149…), `rule_bk_page.tsx` (5e5cded9…); round 2
`rule_bk2_apply_gate.py` (da032a5f…), `rule_bk2_useApplyGift.ts` (8140fed5…); round 3
`rule_bk3_apply_gate.py` (a03d7899…), `rule_bk3_applicationScreen.ts` (1102c802…). Faults f and g were
checked against round 2's code; round 3's rule answers before the code is read, so (f)'s branch no
longer exists and (a′) guards its successor.

## 7. Numbers

* jest: 232 suites / 3664 tests before → **233 / 3933** after round 3 (3895 round 1, 3901 round 2).
* api: 7845 passed, 3 skipped before → **7885 passed, 3 skipped** after round 3 (7874 round 1, 7888 round 2);
  `test_apply_gate.py` 40 tests (plus subtests: 102 cases in the invariant alone).
* typecheck clean; lint 0 errors (17 warnings, none in a touched file); `makemigrations --check` — no
  changes.
* First-load JS, exact (after round 3): `/scholarship/apply` 271.353 → **271.667 kB** (272; 0.333
  room), `/scholarship/application` 273.632 → **273.677** (274; 0.323), `/profile` 309.517 →
  **309.542** (310; 0.458), median 227.85 → **227.875** (229).
* Files: `apply/page.tsx` 1070 → **1062**, `lib/scholarship.ts` 1084 → **1084**, `views.py` 2436 →
  **2434**, `serializers.py` 1215 → **1204**. New: `apply_gate.py` 153, `views_apply_gate.py` 42,
  `student_status.py` 32.
* Debt: TD-337 and TD-340 closed; TD-341 and TD-346 updated; TD-348 raised (open); TD-349 to TD-354
  raised by the review (TD-352, TD-353 owner decisions).
