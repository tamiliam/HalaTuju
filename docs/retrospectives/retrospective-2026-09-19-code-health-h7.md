# Retrospective — Code health H7: `_money` was eight functions doing three jobs

**Date:** 2026-09-19 · **Roadmap:** `docs/plans/2026-09-18-code-health-roadmap.md` · **Sprint:** H7 of H19
**Built by:** an Opus 5 agent (in the background, while the lead shipped TD-254); the lead re-ran
the full suite, checked the golden fixture and the change set, and closed.
**Freeze status:** in force. Seven of the ten sprints to *stabilised*. Run under the owner's
standing word. **Five findings in money code are reported, not fixed — TD-261, the owner's call.**

## What Was Built

**No behaviour change, proven.** 417 characterisation assertions were written against the
*untouched* tree first, and pass unchanged after.

- **`apps/scholarship/money.py`** — `parse_money` and `format_money`, with parameters designed
  *from* the real behaviours. Four parse callers keep their own exception, code and message through
  a two-line wrapper named for what it reads (`_invoice_amount`, `_receipt_amount`,
  `_payment_amount`, `_monthly_amount`). Three format callers keep their own answer for an absent
  figure — `'0.00'`, `''`, `None` — all correct, all different, which is why the shared name had to
  go. `doc_parse._money`, which shared only the name, is `_first_rm_figure`.
- **`_norm` ×4 and `score_markers` ×3 RENAMED, never merged.** One string, four answers:
  `'Café 2'` reads `caf 2` / `CAF` / `café 2` / `CAFE 2`. `MODEL_VERSION` deliberately not bumped —
  a rename must not trigger a cohort-wide re-score.
- **True duplicates given one home:** `_ids` ×4 and the digit reader → `apps/scholarship/text.py`;
  `_any` ×4 → `results_doc._any_token`, beside the normaliser it depends on.
- **`apps/scholarship/gemini.py`** — one single-model, no-fallback, metered call instead of three
  copies. All three `_gemini_generate` seams stay **by name**: tenancy rule 6 names them and ~30
  `patch()` strings point at them.
- **The standards ledger tightened:** six names left `duplicated_names`. Four remain on purpose
  and say why. **`dup` 10 → 4.**

## What Went Well

- **Characterise first, then move.** The rule "no expected value may be edited" turned every
  surprise into a pinned row instead of a silent "fix": `'1,2,3'` parses as 123; `payments` rounds
  a third decimal where `invoicing` refuses it; the Vircle import accepts a negative amount.
- **The agent refused a merge the brief invited.** `_digits` ×3 looked identical. They are not:
  `re.sub(r'\D')` drops a superscript `³`, `str.isdigit()` keeps it — and `offer_parse`'s copy reads
  raw OCR on the way to an **NRIC**. Two were merged; the third kept its own function and its reason.
- **It corrected the survey four times** — including a **ninth** money formatter nobody had
  counted (`views_admin._invoice_money`), byte-identical in behaviour to a nested one written days
  apart, invisible to the duplicate scan only because its name differs.
- **Eight bite-checks, eight red** — each flip in the new shared code turned a *caller's* test red.

## What Went Wrong

**1. Pinning today's behaviour found five defects in money code — TD-261.**
- `doc_parse._first_rm_figure` **drops a minus sign** (`-5.00` → `RM5.00`: a credit on a bill reads
  as a charge) and **drops the decimals of a one-decimal figure** (`1234.5` → `RM1234`).
- `'Infinity'` in the receipt box, and `'NaN'` on a payment-run line, escape as a raw
  `decimal.InvalidOperation` — **a 500 where a 400 `bad_amount` belongs** — because the range check
  sits outside the parse guard. Both reachable from an admin request body.
- `sponsor_comms.render` can leave a raw `{student_cards}` in a sponsor email where
  `partner_comms.render` cannot. Four tests prove the leak **and** that no production path reaches
  it today.
- *Root cause, all five:* helpers written once per module, each tested (if at all) on the happy
  path; nobody had ever put the same awkward inputs through all of them side by side.
- *System change:* the characterisation table is now permanent — 417 assertions that any future
  change to these helpers must answer to. The fixes are the owner's: they change what money code
  returns.

**2. The agent wrote a CHANGELOG entry it was told not to.** It is accurate, and was kept after
reading. Noted because a brief's "the lead writes X" is a boundary, and boundaries that are
silently crossed when the result is good get crossed again when it is not.

**3. One deliberate widening:** the Vircle CSV digit reader no longer raises `TypeError` on a
non-string. No caller can pass one. Recorded in the characterisation file with its reason — the
only expected value relaxed in the sprint.

## The deploy

api only. **`halatuju-api-01056-cwx`**, first attempt; 6,894 pytest passed inside the build. Site
200; admin endpoint 401; no ERROR lines.

## Numbers

| | Before | After |
|---|---|---|
| pytest `-n auto` | 6,857 | **6,894 passed · 3 skipped · 0 failed** (lead's re-run: 125 s) |
| `dup` reading | 10 | **4** — the four declared exceptions |
| Characterisation assertions | 0 | **417** |
| `big` · `std` | 25 · ok | unchanged · ok (`sponsorship.py` held at 999 lines) |
| Email golden | | byte-unchanged; `UPDATE_EMAIL_GOLDEN` never set |
| Migration | | none |
