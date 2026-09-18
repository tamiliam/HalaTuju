# Retrospective — Code health H3: the guards the splits will lean on

**Date:** 2026-09-18 · **Roadmap:** `docs/plans/2026-09-18-code-health-roadmap.md` · **Sprint:** H3 of H19
**Built by:** an Opus 5 agent to a written brief; the lead verified the diff, re-ran the guards,
checked production, and closed.
**Freeze status:** in force. Three of the ten sprints to *stabilised* are done.

## What Was Built

- **TD-219 closed — `test_endpoint_exercise.py`.** Every route wired in `apps/scholarship/urls.py`
  must be driven by at least one HTTP request somewhere in the suite. Nothing is hand-listed: the
  guard reads every test module with `ast`, rebuilds each request path (f-strings, constants,
  `_url()` helpers, test-local `_get`/`_post` wrappers) and resolves it through Django's own
  router. **200 routes, 178 exercised, 22 in a `NOT_YET_EXERCISED` ledger that may only shrink.**
  Its blind spots are written in its docstring: it reads no assertions, no HTTP method, no roles.
  It is a floor, not coverage.
- **TD-240 closed — the org fence now scans `views_sponsor.py`.** The sponsor fence speaks its own
  vocabulary (`pool.for_sponsor(...)`), so the guard learnt it. Every database read in the file was
  audited (table in the agent's report, summarised in TD-258). `NOT_YET_SCANNED` is now **empty**.
- **TD-250 closed — the admin route-drift test walks nested routes.** 15 nested routes found; zero
  were missing from the registry. A detail page (`[id]`) is excused from having its own menu row
  by a **rule**, and a second test makes sure the section above it *is* a menu destination.
- **The fence is package-aware.** A `SCANNED` entry may be a file or a package directory. H11 can
  turn `views_admin.py` into `views_admin/` without blinding the guard. Proven with a fake package
  in `tmp_path`: a pragma-free query two folders down is reported, at the right path and line.

## What Went Well

- **The brief told the agent what to do on finding a real hole: stop, and report.** It did exactly
  that, with the finding at the top of its report, a precise account of what leaks, and an honest
  note of the one fact it could not check (a production flag). Nothing was papered over with a
  pragma.
- **Fifteen bite-checks, both directions, none silent.** Eleven faults went red with the right test
  named; four harmless changes (whitespace, comments, a CRLF file) stayed green.
- **The agent did not stop at the first plausible number.** A naive scan said 107 of 200 routes
  were unexercised. Following constants, helpers and wrappers brought it to 22, and every one of
  those spot-checked as genuinely untested. A ledger five times too long would have read as noise.

## What Went Wrong

**1. The guard found a live hole in the sponsor money path — TD-258.**
- *Symptom.* `SponsorFundView.post` reads `ScholarshipApplication.objects.filter(id=pk)` — by bare
  id, outside `pool.for_sponsor()`, which `pool.py` calls *"the ONE seam"* for sponsor visibility.
- *What it allows.* An approved sponsor can probe any application id on the platform and tell
  "no such row" from "exists" from "exists and is fundable". No name or detail leaks. Separately,
  `SponsorDonateView` — a **mock** donation endpoint, labelled "dev/dummy only" — is live in
  production behind only the pool flag, and mints a confirmed, programme-less donation on request.
- *Root cause.* The fence guard had never scanned this file (TD-240, open since July). The fund
  view predates the programme fence and was never brought through the seam; the mock endpoint was
  never given a gate of its own. Both are **convention, not choke-point** — the recurring class.
- *What the lead checked in production (read-only):* `SPONSOR_POOL_ENABLED=true`; **0** mock
  donations ever; **0** programme-less applications (the only thing fake balance could buy);
  **0** students currently fundable; 10 approved sponsors. **No harm done and money cannot move
  this way today.** It is still a hole in a money path, so the fix is the owner's call, not a
  silent patch inside a guards sprint.
- *System change.* The guard now watches the file, the finding sits in a `KNOWN_UNFENCED` ledger
  that fails the build when fixed-and-forgotten, and TD-258 carries the fix shape.

**2. Twenty-two wired endpoints have never been driven by a test — TD-257.** Twenty are writes; two
release or schedule **money** (disbursements); two are the cool-off brakes. This is the debt TD-219
suspected, now counted. It is scheduled with Phase 2, where the factory makes each test cheap.

**3. TD-250 found nothing, and that is a finding about the TD entry.** It predicted the recursive
walk would surface unguarded routes. There were none: longest-prefix matching had covered all 15
by accident. The hole was real; the drift had not happened yet. One blind spot remains and is
written down — a new child under a prefix-matched section inherits its parent's row.

## Numbers

| Gate | Before | After |
|---|---|---|
| pytest `-n auto` | 6,714 passed · 3 skipped | **6,722 passed · 3 skipped · 0 failed** |
| jest | 2,354 / 140 suites | **2,356 / 140** |
| tsc · lint · i18n | 0 · 0 errors · ok | unchanged |
| New guard runtimes | | endpoint-exercise 2.6 s · org-fence 10.6 s · navigation 0.4 s |
| Code-health reading | | nothing worse; `td_open` moves with the register (3 closed, 2 raised) |
| App code changed | | 3 comment lines (`views_sponsor.py`) |
