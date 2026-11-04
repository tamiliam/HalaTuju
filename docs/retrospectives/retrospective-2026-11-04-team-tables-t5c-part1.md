# Retrospective — Team tables T5c part 1 (pages open by keys) — 2026-11-04

Live 2026-11-04: main ac68a361; api halatuju-api-01251-l9v, web halatuju-web-01081-957. Both Cloud Builds passed
first time. No migration, no new endpoint (P4a adds one field to `admin/role/`). No live access moved, on the server
or in the console.

## What was built
- Page doors open by v2 keys: `staff_tables.DOOR_KEYS` maps each door to its key, and `opens_door` reads the key.
- `admin/role/` serves `page_keys`, so the web reads the same keys the server uses to open a door.

## What went well
- Three fresh reviews passed.
- The adversarial review (SHIP) checked 13,884 server shapes and 4,770 web payloads: 0 mismatches.

## What went wrong
- **(a) TD numbers collided with parallel sessions three times.** Symptom: our debt numbers were taken by other
  sessions' pushes, so ours went 489 → 492 → 496, and the final range is TD-496..499. Root cause: each session took
  "highest + 1" on its own branch before pushing, so two branches picked the same number. Fix: a session claims a TD
  range in its first announce message (e.g. "Maintenance takes TD-500..509"). Added to `docs/lessons.md`.
- **(b) Two builders passed the 120k helper limit (P1 189k, P4 190k).** Symptom: both helpers ran far past the
  budget in `credit-discipline.md`. Root cause: the phase brief covered too many doors and files in one go. Fix: one
  door group per builder, and the planner counts the doors before briefing a phase.
- **(c) P4 web had to stop: the server did not serve the v2 keys.** Symptom: the web phase found that `admin/role/`
  did not return the keys the web expected, so it could not open the pages. Root cause: the plan did not check the
  server → web payload before the web phase was briefed. Fix: a web phase brief starts by naming the payload it
  reads.

## Design decisions
- Doors are keyed, not role-named: the server decides which keys a person holds, and the web only reads them.
- The key table is one module (`staff_tables.DOOR_KEYS`), so a new door is added in one place with its test.

## Numbers
- api: 12,362 passed, 3 skipped (`pytest -n auto`).
- web: 413 suites / 6,458 jest passed; `next build` and bundle budget passed. Median bundle headroom is only about
  0.1 kB, so the next web phase must lazy-load before it adds weight.

## Open debt
- TD-487 and TD-488 (owner's rulings, from the TD-481 adversarial review).
- TD-496 (graduation list), TD-497 (mentors list key), TD-499 (finance and QC pairing question).

## Next
T5c P5: the Programmes landing (design approved; plan and owner rulings in `RUN_STATE.md`). The owner's phone check
comes before it goes live, because P5 changes what reviewers and mentors can open.
