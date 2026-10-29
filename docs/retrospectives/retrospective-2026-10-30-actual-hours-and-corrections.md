# Bill the hours we told them, and correct a wrong month in the next one — 2026-10-30

## What Was Built

The owner audited every billed request — 3, 5, 10, 12, 14, 18, 27, 28, 29, 30, 31, 33, 38, 39, 42, 44 —
and found five wrong: **10, 14, 28, 30, 31**. None was an arithmetic mistake. Development billing charged
`quote_hours`, the PLAN, while the closing report had already published a different number to BrightPath:

| req | quoted | spent | billed | the closing report said |
|-----|--------|-------|--------|--------------------------|
| 10 | 15.0 | 11.5 | **15.0** | re-scoped downward |
| 14 | 2.0 | ~5.0 | **2.0** | *"None of it is charged"* |
| 30 | 7.0 | ~4.0 | **7.0** | *"Planned: 7 hours. Actual: about 4 hours"* |

**The owner's ruling, which is the whole sprint:** *"It is not what is calculated internally. What matters
is, what was communicated back to the requester."*

- **The published figures became columns.** `OrgRequestAnalysis.actual_hours` / `charged_hours` /
  `charge_note` (migration 0187). `charged_hours` is what reaches the invoice; `0.0` is a real answer —
  request 14, exactly — and is not NULL. **Nothing parses the prose**, and nothing should.
- **`closing_report()` / `billable_hours()`** — the latest approved, un-superseded analysis that carries a
  figure. The unbilled panel now proposes the ACTUAL with the quote beside it, and offers no number at all
  where none was published.
- **`actual_hours_missing`** — an ABSOLUTE readiness refusal. A finished request with no closing figure
  stops the month; "bill it anyway on the quote" is not on offer.
- **`record_hours()` + `POST requests/<pk>/analysis/<aid>/hours/`** (super only), with a reason required
  whenever charged differs from actual in EITHER direction: absorbed (#14) or an accepted extra (#38).
- **`OrgBillingCorrection`** — a signed amount with a REQUIRED reason printed on the tenant's invoice,
  applied **after** the discount, frozen onto the invoice at issue. Plus `POST`/`DELETE
  billing/corrections/` and a form on the charge card.
- **Both audiences see the FINAL label**, so a charge links to a request labelled the way it was billed.
  Nine requests were mislabelled on the organisation's side.
- **Screens:** one hours panel under the quote; the correction as its own line with its reason, on screen
  and in the PDF, for both audiences.

## What Went Well

- **The owner's audit beat every test we had.** Sixteen requests read by hand found five wrong; the suite
  was green throughout. That is the honest ranking of evidence here.
- **Migrate-first held.** 0187 was rendered offline for Postgres, applied by hand, verified column by
  column, Security Advisor clean, and only then did the code deploy.
- **Bite-checks earned their place.** Twelve guards, every one proven to turn red — and one genuine gap
  found that no test had covered.
- **Cross-session coordination worked.** Four sessions were pushing to the same repo; a migration number
  collision (two 0186s) was caught and renumbered before either reached production, and the one commit
  nobody here owned was verified deployed before being carried.

## What Went Wrong

1. **I diagnosed the billing defect too shallowly, and the owner corrected me.**
   *Symptom:* my first fix read the latest analysis's `estimated_hours` instead of the quote.
   *Root cause:* I looked for the nearest INTERNAL number that was better than the quote, instead of asking
   what we had actually told the customer. Both are figures we compute; only one was ever sent.
   *System change:* the lesson "the authority for a charge is what we TOLD the customer" is in
   `docs/lessons.md`, and the refusal is absolute so the question cannot be skipped next time.

2. **A green test was defending the defect.**
   *Symptom:* `test_a_finished_quoted_request_is_reported_as_unbilled` asserted `hours == 7.5` — the quote —
   and had been green since September.
   *Root cause:* it was an accurate test of the wrong behaviour. Nobody re-reads a passing test.
   *System change:* lesson recorded — when a bug report contradicts a green test, read the test FIRST; if it
   asserts what the owner just called wrong, the test changes first and the change says what it used to claim.

3. **Three defects in the money path that no test would have caught, found only by reading my own diff.**
   *Symptom:* a `DELETE` to the collection URL raised a 500 on a money route; the charge-note box survived
   the figures being made equal, so a write-off could be reversed with its explanation attached; and the
   Record handler sent `row.hours ?? '0'`, which would have billed ZERO hours for real work.
   *Root cause:* every test used the right method on the right URL, and every test reached the handler
   through a button that was never rendered. The tests described the happy path precisely.
   *System change:* three lessons recorded; the `?? '0'` became a shared type guard that the compiler
   enforces.

4. **I read two bad bite-checks as sleeping guards.**
   *Symptom:* three bites "stayed green". Two were my own invalid injections — one swapped `a - b + c` for
   `a + c - b` (the same arithmetic), one blanked a field the test never reads.
   *Root cause:* I injected into the line the guard lives on rather than into the value the test asserts.
   *System change:* lesson recorded — a bite that cannot change an asserted value is UNPROVEN, the same as a
   needle that did not land. Both were re-run properly and both went red.

5. **The hours panel asked for the same work twice, and said something false while doing it.**
   *Symptom:* the owner opened request #3, recorded the figures, and a second card went on saying *"No hours
   recorded yet — the invoice for this month will refuse until they are."*
   *Root cause:* I rendered a claim about the REQUEST on every approved analysis card. Request #3 has two.
   The sentence was true of neither card once one carried figures.
   *System change:* one panel, under the quote — the owner's own suggestion, and structurally one rather than
   computed. Lesson recorded about per-row status lines that make whole-record claims.

6. **Two files grew back over the 600-line standard mid-sprint.**
   *Symptom:* `platform_cost.py` hit 646 having LEFT the ledger that same morning; the billing page hit 736.
   *Root cause:* I added to files that were already at their limit, twice, without checking first.
   *System change:* both split (`charge_adjustments.py`; `ChargeCard.tsx` + `ChargeCorrections.tsx` +
   `UnbilledSection.tsx`), and the billing page now leaves the web oversize ledger entirely. No ledger entry
   was added or loosened.

## Design Decisions

Recorded in full in `docs/decisions.md` (2026-10-30): the published figure as the authority; corrections
after the discount; the final label for both audiences; and the hours panel under the quote.

## Numbers

- **Backend:** 10,302 pytest / 3 skipped / 5,008 subtests, via the deploy gate's own `pytest -q -n auto`.
- **Web:** 4,972 jest / 319 suites before the panel move; re-run after it.
- **New tests this sprint:** 24 (`test_request_actual_hours.py`) + 12 corrections-endpoint + 10 corrections
  + 2 readiness + 2 document + 2 payload backend; 16 `RequestHoursForm` + 14 `ChargeCorrections` +
  6 `hoursAnalysisId` + 3 `canRecordUnbilled` + 4 `splitSignedMoney` + 4 billing-page web.
- **Bite-checks:** 12 guards injected, 12 red. Three needed a second, valid injection.
- **Migration:** 0187 — 5 nullable columns, 1 new table, RLS on, **0 rows backfilled**.
- **Production ledger:** 188 rows, 188 distinct numbers, no gaps; every table and column the last three
  migrations promised exists.
- **Deploy:** `d602faaf`, api + web SUCCESS, revision `halatuju-api-01192-m29` on 100% traffic.
- **Files over 600 lines:** net **one fewer** on the web side.

## Still Open

- The owner records the five audited figures on screen: 10 → 11.5/11.5, 14 → 5.0/0.0, 28 → 5.0/5.0,
  30 → 4.0/4.0, 31 → 5.0/5.0.
- October's **−RM126.50** credit (5.5 h × RM23.00), reason naming requests 10 and 14.
- The published actuals for #38, #39, #29, #33, #42, #44. October cannot issue until they exist — which is
  the guard working, not a fault.
