# Retrospective — Team tables T5a (permission catalogue v2 + aliases) — 2026-11-03

Live 2026-11-03: main 55de0610 (feat 3e232021); api-01245-mrb, build passed first time. No migration, no endpoint,
no web change. No gate converted.

## What shipped
- `apps/courses/staff_permissions_v2.py`: 35 page keys in four groups (Organisation, Programme, Engagement, Money),
  tier rules and Engagement dependencies as data, the alias table from today's keys, and `effective_v2()` — a
  read-only answer to "which v2 keys does this person hold today". Nothing calls it to decide access yet.
- `test_permission_catalogue_v2.py`: golden v2 set per live shape, `resolve()` pinned to today, and a coverage test
  that asks 29 real gates per shape and checks a v2 key covers every open door.

## What went well
- The builder asked before guessing on two scope points. The lead's answer kept scholar data off `team.view`: the
  scholar mentoring tab got its own `mentoring.view/.edit` (needs `students.view`).
- The coverage test was proved by breaking the code on purpose twice.
- The investigation's errors were reported, not copied: the admin-inactive shape, the mentoring tab, and the one
  unmapped door (the graduation-messages list).

## What to improve
- The full pytest run took 37 minutes under load (9 minutes when the machine is quiet). Run the long gate while
  no other session is building.

## Next
T5b (QC self-sufficient + widened self-QC guard; adversarial review), on the owner's word. T5c must decide the
graduation-messages list's key.
