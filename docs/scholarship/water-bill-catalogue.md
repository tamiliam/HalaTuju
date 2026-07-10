# Water-bill catalogue — categories, signatures & variables

**Status: BUILT + corpus-validated + WIRED (2026-07-10).** Scorer
`apps/scholarship/genuineness/water_doc.py` (`MODEL_VERSION 1.0.0`); scored at extraction →
`vision_fields.authenticity` (vision.py, behind `DOC_GENUINENESS_CHECK_ENABLED`, already ON); the
cockpit renders the wrong-type reject (`ApplicantDocumentSerializer.get_authenticity` allowlist —
`not_water_bill` → red chip, `suspect` hidden as amber noise; the cockpit utility branch is generic
so it needed no FE code change). **Extraction-v2** added `bill_date` / `account_no` / `usage_m3` /
`tariff` to the water-bill schema + prompt. Sibling to `electricity-bill-catalogue.md` and
`salary-signature-model.md`; per-family `MODEL_VERSION`. **SOFT:** feeds the officer chip + the
keep-better ranking (`_doc_genuine_rank` reads `authenticity.status`); it does NOT gate submission.
**Existing bills are unscored → fail-open** (a re-score / re-extraction pass on the live service
activates them + populates the new fields; never re-extract locally —
`halatuju_never_reextract_locally`).

## Why water differs from electricity — GRAMMAR-first, operator-as-bonus

Electricity has a near-monopoly (TNB ~92% of the corpus), so its model is **issuer-first**: recognise
the header and you're done. **Water has no single national operator** — it is state-run, so ~13
utilities issue bills and the largest (Air Selangor) is only ~20% of the corpus. Copying the
issuer-first shape would send every bill from an unlisted operator (or a mis-OCR'd header) to amber
"suspect" — a false-suspect flood. So water mirrors the **salary model's shape instead**: the shared
**water-bill grammar decides** genuine / suspect / not_water_bill, and the **operator identity is a
bonus** — it names the family for the officer and lifts confidence, but never gates `genuine`. A bill
from an operator we haven't catalogued still scores genuine as family `unrecognised`.

## Corpus & calibration

**Corpus-derived 2026-07-10** from the live `applicant_documents` water-bill corpus (101 rows / 66
applications, 66 live); the model was calibrated on **28 of them OCR'd read-only** via
`eval/capture_ocr.py water_bill` (2026-07-10) — hit-rates below are on n=28. Operator prevalence was
first estimated from the extracted `address` field (water is state-run, so the state ≈ the operator),
then confirmed against the OCR headers.

### Scorer output on the real corpus (n=28, `MODEL_VERSION 1.0.0`)

`water_genuineness()` over the 28 OCR'd bills: **27 genuine · 0 suspect · 1 not_water_bill** —
**0 false-rejects**. The single reject is a **TNB electricity bill misfiled into the water slot**
(family `electricity_bill`) — the reverse of the #83 swap, caught symmetrically. Two genuine bills
(a PBAPP and a SAMB) that merely *mention* "elektrik" were correctly kept (their water term anchors
them). Family split of the 27 genuine: air_selangor 6 · sada_kedah 5 · sains_ns 4 · saj_johor 3 ·
paip_pahang 3 · pbapp_penang 2 · samb_melaka 2 · unrecognised 2 (a Perak + a Pahang bill whose
operator header didn't OCR distinctively — grammar carried them). **Every operator label matched the
bill's address-state — zero mislabels.**

## Categories (families)

By prevalence in the corpus, each an operator identity marker (bonus signal only):

| Family | Operator | State(s) | n/28 |
|--------|----------|----------|------|
| `air_selangor` | Air Selangor / (legacy SYABAS) | Selangor, KL, Putrajaya | 6 |
| `sada_kedah` | SADA (Syarikat Air Darul Aman) | Kedah | 5 |
| `sains_ns` | SAINS (Syarikat Air Negeri Sembilan) | Negeri Sembilan | 4 |
| `saj_johor` | SAJ / Ranhill | Johor | 3 |
| `paip_pahang` | PAIP (Pengurusan Air Pahang) | Pahang | 3 |
| `pbapp_penang` | PBAPP / PBA | Penang | 2 |
| `samb_melaka` | SAMB (Syarikat Air Melaka) | Melaka | 2 |
| `lap_perak` | LAP / Air Perak | Perak | 0* |
| `aksb_kelantan` | Air Kelantan | Kelantan | 0† |
| `satu_tganu` | Air Terengganu | Terengganu | 0† |
| `pba_perlis` | Air Perlis | Perlis | 0† |
| `jans_sabah` | Jabatan Air Negeri Sabah | Sabah | 0† |
| `laku_sarawak` | Kuching Water Board / LAKU / Sibu Water | Sarawak | 0† |
| `unrecognised` | (genuine water grammar, operator not identified) | — | 2 |
| `electricity_bill` | (reject — an electricity bill in the water slot) | — | 1 |
| `not_water_bill` | (reject — MyKad / junk) | — | 0 |

\* Perak bills appear in the cohort but their header OCR'd as `unrecognised` (the distinctive
`LEMBAGA AIR PERAK` / `AIR PERAK` tokens didn't land; the raw scan's earlier "5" was inflated by the
bare substring `LAP`, deliberately dropped to avoid false matches). Grammar-first passes them anyway.
† Future-proof stubs (0 in the current cohort) — distinctive multi-word markers only, so they can't
collide with ordinary Malay words (`AIR TERENGGANU`, not the bare `SATU` = "one").

## Signatures

**Water-type terms** (separate a water bill from an electricity bill — the swap backstop):
`BIL AIR`, `BEKALAN AIR`, `METER AIR`, `CAJ AIR`, `PENGGUNAAN AIR`, `AIR TERAWAT` — **96%**.

**Usage unit** — m³ / meter padu (water's kWh; NFKD folds `³`→`3`, so `M³` reads as `M3`): **96%**.

**Bill-field grammar** (each group counts once; hit-rates n=28):
`NO AKAUN`/`NOMBOR AKAUN` **96%** · `JUMLAH PERLU DIBAYAR` **100%** · `TUNGGAKAN`/`BAKI TERTUNGGAK`
**93%** · `TARIF` **82%** · `SILA BAYAR SEBELUM` **71%** · `TEMPOH BIL` **61%** · `CAJ SEMASA`
**54%** · `BACAAN METER` **29%** · `TARIKH BIL` **25%**.

**Note on `TARIKH BIL` (25%):** water bills rarely print a point-in-time bill date — they lean on
`TEMPOH BIL` (the period). So utility currency stays **period-anchored** upstream (`_bill_as_of`
prefers `bill_date` when present, else `billing_period`); nothing here changes that.

## Decision cascade

`score_markers()` → `{operator, labels, water, m3, electricity, mykad}`. `is_water = water or m3 or
operator` — **any water signal guarantees the doc is never rejected** (mirrors electricity's
"issuer ⟹ never rejected"; every genuine bill in the corpus carried one).

1. **Reject floor** (only when NOT `is_water`): a MyKad with no fields → `not_water_bill`; an
   electricity signature → `not_water_bill` family `electricity_bill` (the swap); `< 2` bill fields →
   `not_water_bill`.
2. **Operator recognised:** `labels ≥ 2` → `genuine` (family = operator); thin → `suspect`.
3. **No operator but water grammar:** `labels ≥ 2` → `genuine` family `unrecognised`; thin →
   `suspect`.

Probability: genuine-with-operator `min(0.95, 0.65 + 0.05·labels)`; genuine-unrecognised
`min(0.90, 0.60 + 0.05·labels)`; suspect ~0.45–0.55.

## Variables (Extraction-v2 schema)

`name` · `address` · `amount` (current charge only, not the arrears-inclusive total) ·
`unpaid_balance` (Tunggakan) · `billing_period` (Tempoh Bil) · `bill_date` (Tarikh Bil, if printed) ·
`account_no` (No. Akaun) · `usage_m3` (Penggunaan, m³) · `tariff` (Tarif / premise class).

## The symmetric swap win

Before this model, a wrong-type was caught in the *electricity* slot but the *water* slot showed
"Verified" even when it held an electricity bill — exactly the #83 / #35 / #110 swaps. With the water
model's electricity-in-water-slot backstop, a swap is now caught in **either** slot (`a75` in the
calibration corpus is a live example).

## Wiring

- `genuineness/water_doc.py` — `water_genuineness(ocr_text)`, `score_markers()`, `MODEL_VERSION`.
- `genuineness/__init__.py` — import + `__all__` + `assess()` dispatch (`doc_type == 'water_bill'`).
- `vision.py` — genuineness branch (`elif doc.doc_type == 'water_bill'`) → `vision_fields.authenticity`;
  `usage_m3` / `tariff` added to the water schema; the water extraction hint describes m³ + operators.
- `serializers.py` — `get_authenticity` allowlist + surface only the `not_water_bill` wrong-type reject.
- `officerCockpit.ts` — the utility branch already renders genuineness generically (no code change; a
  comment updated to note the symmetric swap).
- Tests: `apps/scholarship/tests/test_water_signatures.py` (15).
