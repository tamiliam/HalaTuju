# Retrospective — Water-bill genuineness model (the electricity sibling) + Extraction-v2 (2026-07-10)

**Commits:** `c9433575` (water model + Extraction-v2 + wiring) · `da509949` (`_DOC_HINTS` de-dup).
**Migrations:** none. **MODEL_VERSION:** new per-family `water_doc.MODEL_VERSION = 1.0.0` (no
cross-family bump). **Tests:** 2311 scholarship pytest (+15) · 489 jest (FE change was comment-only).

## What Was Built

The water-bill sibling to the electricity genuineness model — but deliberately a *different shape*,
because water is structured differently from electricity.

1. **Genuineness signature model (`genuineness/water_doc.py`, `MODEL_VERSION 1.0.0`).**
   **GRAMMAR-first, operator-as-bonus** — the opposite of electricity's issuer-first cascade. Water
   is state-run with no dominant national operator (~13 utilities; the largest, Air Selangor, is only
   ~20% of the corpus vs TNB's ~92% for electricity), so the shared bill grammar (Bil Air / m³ /
   No. Akaun / Tunggakan / Tarif / Jumlah Perlu Dibayar) decides genuine / suspect / not_water_bill,
   and the operator identity only names the family. A bill from an unlisted operator still scores
   genuine (`unrecognised`). 13 operator families (air_selangor / sada_kedah / sains_ns / saj_johor /
   paip_pahang / pbapp_penang / samb_melaka + five East-Malaysia/small-state stubs).
2. **Symmetric swap catch.** Rejects an ELECTRICITY bill misfiled into the water slot (family
   `electricity_bill`) — closing the #83 / #35 / #110 "swapped bills" gap on BOTH slots. The reject
   fires only when NO water signal is present, so a genuine water bill that merely mentions "elektrik"
   is protected.
3. **Extraction-v2.** `usage_m3` (Penggunaan, m³) + `tariff` added to the water schema + prompt hint.
4. **`_DOC_HINTS` de-dup (`da509949`).** Fixed a latent duplicate-key bug found while wiring water:
   both `electricity_bill` and `water_bill` had two entries in the dict literal, so Python silently
   kept only the later — shadowing the electricity agent's detailed Extraction-v2 hint. De-duped both;
   grafted the correct `amount` rule (current Caj Semasa, not the arrears-inclusive total) into the
   surviving detailed electricity hint so nothing regressed.
5. **Wiring (SOFT):** `assess()` dispatch, `vision.py` genuineness branch → `authenticity`, serializer
   wrong-type allowlist. The cockpit utility branch already renders genuineness generically → no FE
   code change (one comment updated). Existing bills unscored → fail-open (natural rollout).

## What Went Well

- **Calibrate-on-real-OCR paid off twice.** OCR'd 28 live bills (one-time Vision call, ~4¢) and set
  every threshold from the data: water-term 96%, m³ 96%, NO AKAUN 96%, JUMLAH 100%. Result: **27
  genuine · 1 not_water_bill · 0 false-rejects.**
- **The address-state cross-check caught a labelling trap before it shipped.** A raw marker scan
  showed `lap_perak` hitting 5 bills — but that count was inflated by the bare substring `LAP`
  (matches "laporan" etc.). Cross-checking each operator label against the bill's address-state
  proved the real Perak bills land as `unrecognised` genuine (their distinctive header didn't OCR),
  and confirmed **zero mislabels** across all 28. Kept the operator markers conservative (distinctive
  multi-word tokens only: `AIR TERENGGANU`, not the bare `SATU` = "one").
- **The grammar-first call was validated by the 2 no-operator bills.** One was a genuine unlisted-
  operator bill (must pass — it did, as `unrecognised`); the other was a real TNB electricity bill in
  the water slot (must reject — it did). Exactly the two cases the architecture was chosen for.
- **The live test was the swap itself.** The single corpus reject (`a75`) is a real swapped bill —
  the model earned its keep on real data, not a synthetic input.

## What Went Wrong

- **A latent duplicate-key bug sat undetected in `vision._DOC_HINTS`.** *Symptom:* the electricity
  agent's detailed Extraction-v2 prompt hint (usage_kwh/bill_date guidance) was never actually live —
  a shorter duplicate key later in the same dict literal silently won. *Root cause:* Python keeps the
  last value for a duplicate literal key, and nothing (no linter, no test) flags a duplicate key in a
  hand-maintained config dict; it only surfaced because I happened to inspect both entries while
  wiring water. *Fix / prevention:* de-duped both keys this sprint; the durable prevention is a lint
  rule — enable `flake8-builtins`/`ruff F601` (duplicate-key-in-dict) or a tiny AST test over the
  config dicts in `vision.py`. Logged as a lesson.
- **The full-suite run failed the first time on a stale working directory.** *Symptom:* `pytest
  apps/scholarship` errored with "No module named 'halatuju'". *Root cause:* the preceding `npx jest`
  step left the shell cwd in `halatuju-web`; I ran pytest without resetting it. *Fix / prevention:*
  prefix every test/build command with an explicit `cd <component-root>` rather than relying on
  persisted cwd — cheap, and the shell drifts silently between the api and web trees.

## Design Decisions

See `docs/decisions.md` (×2): (1) water genuineness is GRAMMAR-first, operator-as-bonus (vs
electricity's issuer-first) — driven by the multi-operator corpus shape; (2) the water model closes
the bill swap symmetrically (electricity-in-water-slot backstop).

## Numbers

- 2 commits, 0 migrations. New: `water_doc.py`, `test_water_signatures.py` (15), `usage_m3`/`tariff`
  fields, `water-bill-catalogue.md`, 2 decisions. Fixed: the `_DOC_HINTS` duplicate keys.
- Corpus (28 OCR'd live bills): 27 genuine · 1 not_water_bill · 0 false-rejects; 0 operator mislabels.
- Cohort: 66 live water bills across 66 applications (unscored → fail-open until re-run).
- 2311 scholarship pytest + 489 jest.
