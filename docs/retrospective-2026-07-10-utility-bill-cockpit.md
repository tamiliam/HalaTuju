# Retrospective — Utility-bill officer-review polish (2026-07-10)

**Commits:** `97cd7704` (3-tier recency) · `f28d1785` (key values + reviewer notes) · `f9130a3b`
(values under facts, drop Account) · `3250f2fb` (MMM YYYY period) · `3ab3a6cb` (LAP meter-date via
Gemini) · `c9172da0` (Air Selangor bill-date via the deterministic parser). **Migrations:** none.
**MODEL_VERSION:** unchanged (display + extraction only; no signature-model change). All owner-driven,
each shipped and verified before the next.

## What Was Built

A run of tightly-scoped improvements to how the officer cockpit shows water/electricity bills, each
prompted by the owner looking at a real bill.

1. **3-tier recency traffic light** (`income_engine._utility_currency`). Was binary (green ≤3mo /
   amber older). Now **green `current` (≤3mo) / amber `ageing` (3–6mo) / red `stale` (>6mo) / grey
   `unknown`** — the chip now encodes the existing ASK (3mo) and RE-ASK (6mo) lines, and the label
   changes with the tier (`Current`/`Ageing`/`Outdated`) so a red chip never reads "Current".
   Re-ask behaviour is unchanged (still only >6mo). New `utilityCurrencyFact` + i18n.
2. **Key values inline** (`officerCockpit.utilityBillValues`). **Amount · Period · Arrears** under the
   facts so the reviewer needn't open the document. Rendered directly under the facts (all notes fall
   below, consistent for both bills); Account no dropped as not decision-relevant.
3. **Period standardised to `MMM YYYY`** (`utility_check.bill_month`), formatted from the SAME
   `_bill_as_of` the recency chip uses — so the shown month can never disagree with the tier, and it
   works on every bill live (no re-run: `utility_check` is computed per request).
4. **Reviewer-facing extraction notes.** The Gemini `warnings` were surfaced verbatim in engineer
   register ("the 'amount' field…", "left empty as per instructions", OCR mechanics). Fixed at the
   source (a `_WARNING_VOICE` prompt clause) + a `_drop_expected_warnings` utility branch for legacy
   notes.
5. **Bill dating for the two extraction paths.** A dateless bill read grey/undated and looped
   (#130). **LAP** (no "Tarikh", goes via Gemini) → the prompt now dates it from the latest
   meter-reading date. **Air Selangor** (clean PDF → the *deterministic* `_parse_water`, capture
   "Exact") → now reads the "Tarikh" header (not the due/last-payment date), calibrated on the real
   OCR corpus.

## What Went Well

- **Calibrate-on-real-OCR held up for a regex, not just thresholds.** The Air Selangor `bill_date`
  extractor was measured on 6 real bills before shipping: 5/6 dated, **0** ever confused with the
  ~1-month-later due date. The one miss (a 2022 bill with heavily interleaved OCR) falls back to
  dateless — no wrong month. The "don't grab the due date" guard fell straight out of the data.
- **Deriving display from the decision source prevented a class of bug.** The Period (`bill_month`)
  and the recency tier both read `_bill_as_of`, so they cannot show a month that disagrees with the
  chip. Same instinct as the 3-tier chip encoding the accept/re-ask boundary rather than inventing a
  third threshold.
- **A preview-backed layout choice avoided a wasted deploy.** The key-values line went out in the
  labelled-inline form the owner picked from an `AskUserQuestion` mock, not a guess.
- **Verified on live data each time.** #95 (Air Selangor → `bill_date 29/05/2026` → May 2026 Current)
  and #130 (LAP) were confirmed against the prod DB, not just tests.

## What Went Wrong

- **The first date fix "had no effect" because the bill used the OTHER extraction path.** *Symptom:*
  after shipping the LAP Gemini-hint fix, the owner re-ran an Air Selangor bill and nothing changed.
  *Root cause:* a water bill can be read by EITHER the deterministic parser (`doc_parse._parse_water`,
  capture "Exact") OR Gemini (capture "ai") — I fixed the Gemini prompt, but the Air Selangor PDF
  locked onto the deterministic parser, which the prompt never touches. I diagnosed from the bill's
  content without first checking WHICH path read it. *Fix / prevention:* the diagnosis must start from
  the stored `capture` field — deterministic vs ai decides which fixer applies; the two paths are
  independent and a fix to one is invisible to the other. Logged as a lesson.
- **The key-values line needed two follow-up tweaks after owner feedback** (drop Account; move the
  values above the notes for consistency). *Root cause:* I confirmed the *layout* via a preview but
  not the *field set* or the note ordering, so the first cut carried a field the owner didn't want and
  an inconsistency between the two bill types. *Prevention:* when adding an at-a-glance summary,
  confirm the exact field list and where it sits relative to existing notes, not just the visual form.

## Design Decisions

See `docs/decisions.md` (×3): (1) the recency chip is a 3-tier traffic light that *encodes* the
existing 3mo/6mo lines rather than adding a threshold; (2) the displayed Period is derived from the
same `_bill_as_of` as the chip so they can't diverge; (3) water bills are dated per extraction path —
the deterministic parser reads the "Tarikh" header, Gemini reads the meter date when there's no
"Tarikh" (LAP).

## Numbers

- 6 commits, 0 migrations, no MODEL_VERSION change. New: `utilityCurrencyFact` / `utilityBillValues`
  (FE), `bill_month` / `_bill_month_label` / `_WARNING_VOICE` / `_water_bill_date` (BE), i18n
  `fact.ageing`/`stale` + `billValue.*` (en/ms/ta). Fixed: the utility warnings register + filter.
- Air Selangor `bill_date` calibrated on 6 real OCR bills (5/6 dated, 0 due-date confusion).
- Verified live: #95 (Air Selangor) + #130 (LAP).
