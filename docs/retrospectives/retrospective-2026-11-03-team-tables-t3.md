# Retrospective — Team tables T3 (Mentors under Team, mentor detail) — 2026-11-03

Live 2026-11-03: main 99d8ac1c; API build 76d2125e (live now api-01243-dzq); web went out in the Requests R1 build
2da37ff4 (web-01070-c44), because T3's own web build c013be40 failed on a flaky student test. No migration.

## What shipped
- Team → Mentors table (the old page's list and readers), Add Mentor, Stop mentoring / Deactivate on a Sheet; the old
  Mentors page redirects. Mentor detail page: scholars now and past, meetings in 90 days, average gap, concerns —
  never notes. A staff mentor who has signed in and holds no open case may leave their last staff table and become a
  mentor login.
- Owner scope addition: the person page's Permissions tab shows one section per table; Team tables lost the
  permissions column.

## What went well
- The adversarial review caught a real leak before the push: an admin with only money keys could read scholar names,
  standing and concerns on the mentor detail page. Fixed by the Scholars list's own read rule.
- The owner's alignment notes became a read-only investigation in parallel with the build, so T5 was decided the
  same day without blocking T3.

## What to improve
- A second flaky jest test (`page.gift.test.tsx` D4: a synchronous read of a prefill that can land late) failed a
  deploy build; the T2 builder had seen it fail "under load" and it was not fixed then. Fixed now (c166736a). Rule:
  a test that fails once under load is fixed in the same sprint.
- A new session (Requests) pushed during the T3 window without hearing the announcement; its build carried T3 web.
  Harmless here (T3 was approved), but announce to every HalaTuju session listed by ListAgents, not a fixed three.

## Next
T4 (Emails and Terms in three sections) or T5a (catalogue v2), on the owner's word.
