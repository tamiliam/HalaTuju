# Lessons Learned

- A bare `N.N.` numbering token (e.g. `2.4.`, `2.5.`) is NEVER a field value — it is an offer body's
  section-clause header, and a label-anchored parser can latch it as the stream/institution (#47:
  a Form-6 offer whose `2.4. Bidang` / `2.5. Pusat Tingkatan Enam` labels landed as the values).
  Defend at BOTH ends: reject at READ (offer_parse defers the whole offer to Gemini) AND sanitise at
  WRITE (`card_display.sanitise_offer_slots` / autofill), mirroring the #125 date/mis-slot guard. The
  shared detector is `card_display.looks_like_clause_number`.
- When investigating data coverage or completeness, always query production Supabase directly — test fixtures are for logic testing and will show misleading zeros. (Ranking Improvements Sprint)
- **Never run a bite-check while a test suite is running.** Both are pytest and they share ONE test
  database. The collision does not look like a collision — it looks like a real, interesting bug in
  the code just written, which is how it cost a wrong report to the owner before it cost a re-run.
  Finish the suite, then bite-check. (billing settings homes, 2026-10-28)
- **A guard that asks you to SPLIT a file is not asking you to trim it.** The 600-line standard
  exists so no human or agent has to hold a file in one head; shortening the newest prose until the
  number passes leaves the file exactly as hard to read and removes the signal. Split the file, or
  put the content where it belongs. (billing settings homes, 2026-10-28 — a FAQ entry was shaved to
  603 lines before the point landed; TD-413)
- **A fixture that happens to agree proves nothing.** Two tests asserted that two months carry
  different readiness problems, and that July already had warnings — neither was true of the
  fixture, so one passed vacuously and one failed. If a test needs two states to DIFFER, make them
  differ in the test and assert the difference before relying on it. (back-issue invoices,
  2026-10-28)
