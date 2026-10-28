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
- **Render the document before trusting the price.** Three faults in the invoice engine, and then
  the tax leak, were found by printing real documents from real figures into a throwaway database.
  None was visible from reading the code: the code was correct, the OUTPUT was wrong. For anything
  that ends up on paper in front of a customer, produce the paper first. (back-issue invoices +
  grouped lines, 2026-10-28/29)
- **When a value has three opinions, write down which one may touch money.** A request carries
  `ai_draft_kind` (Gemini's guess), `kind` (what the submitter filed) and `triaged_kind` (the
  owner's ruling). Bug work is free, so whichever field the biller reads IS the price. Reading the
  wrong one lets an AI guess decide what a customer pays — and on production `triaged_kind` had
  silently come to read 'feature' for all 16 finished requests, including 7 filed as bugs, exactly
  as the model's own comment warned. Name the authoritative field in the function that bills, and
  test both directions. (grouped development lines, 2026-10-29)
- **A rate's NOTE is a specification.** "The margin should help cover bug fixing which is not
  billed separately" had been sitting in `BillingRate.note` since 2026-09-11. It is the reason bug
  hours must be free, and the invoice had been charging them as features the whole time — collecting
  twice for the same work. Read the notes on the rows before changing how the rows are used.
  (grouped development lines, 2026-10-29)
- **Searching a whole HTML file for a leaked word finds words the stylesheet owns.** A guard
  asserting the document never says "margin" failed on `@page { margin: ... }`. Strip `<style>` and
  the tags, then search the text a reader actually sees — a guard that cries wolf teaches people to
  ignore it. (grouped development lines, 2026-10-29)
- **A budget that counts a literal string counts it in prose too.** The suppression-count guard
  reads source for the marker text, so a COMMENT explaining why a suppression was avoided tripped
  the guard by containing the marker. Describe such a marker rather than spelling it. The same
  shape as the stylesheet-`margin` false alarm above: a guard matching text, not meaning.
  (grouped development lines, 2026-10-29)
- **Re-export by binding names through the module, not by importing them.** `from .leaf import a, b`
  in a module that does not call `a` or `b` reads as an unused import and needs a suppression — and
  the suppression count is a budget that may not rise. `from . import leaf` then `a = leaf.a` uses
  the import, needs no suppression, and still answers `mock.patch.object(parent, 'a')`.
  (grouped development lines, 2026-10-29)
- **A pill that shows a different field from the one that prices is a lie the reader cannot see.**
  The request screens printed `kind` (what the organisation filed) while the invoice priced on
  `triaged_kind` (what triage adjudicated). The owner opened request 5, read "Bug report", and
  reasonably concluded it was free; it was being billed. Neither field was wrong and neither screen
  had a bug — the DISAGREEMENT was invisible. Where two fields can differ and one of them decides
  money, show the deciding one and name the other when they diverge. (grouped development lines,
  2026-10-29)
- **Never bite-check while ANY suite is running, including across languages.** The lesson above
  about pytest sharing one test database is narrower than the real rule: a jest bite-check that
  injects a fault into a `.py` file collides with a pytest run just as badly, because the
  source-reading guards read from disk. The run had to be thrown away and repeated. One fault
  injection at a time, with nothing else running. (grouped development lines, 2026-10-29)
- **A parse that can grab the wrong line is worse than no parse.** A drift test matched the first
  `return` after a `def` and silently captured an early-exit `return 'feature'`, then failed
  claiming the rule had changed. It reported a drift that did not exist, which is how a guard
  teaches people to ignore it. Read the whole function body, and assert the parse found what it
  expected. (grouped development lines, 2026-10-29)
