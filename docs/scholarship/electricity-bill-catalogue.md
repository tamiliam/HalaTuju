# Electricity-bill catalogue — categories, signatures & variables

**Status: BUILT + corpus-validated + WIRED (2026-07-10).** Scorer
`apps/scholarship/genuineness/electricity_doc.py` (`MODEL_VERSION 1.0.0`); scored at extraction →
`vision_fields.authenticity` (vision.py, behind `DOC_GENUINENESS_CHECK_ENABLED`, already ON); the
cockpit renders the wrong-type reject (`ApplicantDocumentSerializer.get_authenticity` allowlist —
`not_electricity_bill` → red chip, `suspect` hidden as amber noise). **Extraction-v2** added
`bill_date` / `account_no` / `usage_kwh` / `tariff` to the bill schema + prompt. Pairs with
`salary-signature-model.md` and the framework in `genuineness/` (per-family `MODEL_VERSION`). **SOFT:**
feeds the officer chip + the keep-better ranking (`_doc_genuine_rank` reads `authenticity.status`);
it does NOT gate submission (utility bills are soft signals). **Existing bills are unscored →
fail-open** (a re-score / re-extraction pass on the live service activates them + populates the new
fields; never re-extract locally — `halatuju_never_reextract_locally`).

**Corpus-derived 2026-07-09** from the live `applicant_documents` electricity-bill corpus (88 rows /
68 applications, all scanned; 70 live); the signature model was calibrated on **27 of them OCR'd
read-only** via `eval/capture_ocr.py electricity_bill` (2026-07-10) — hit-rates below are on n=27.
This is the authoritative reference for (a) the bill categories we see, (b) the signatures that
identify a genuine bill and its category, and (c) the variable set. Closes the utility-bill
**positive genuineness fingerprint** gap (bills previously had `_dedup_clean_rank` + `utility_check`
but **no** signature model / stored `authenticity`).

## Scorer output on the real corpus (n=27, `MODEL_VERSION 1.0.0`)

`electricity_genuineness()` over the 27 OCR'd bills: **27 genuine (tnb) · 0 suspect · 0
not_electricity_bill** — **0 false-rejects** (every genuine bill carried a TNB issuer marker + ≥2
field labels). The reject floor is validated on synthetic wrong-type inputs (a MyKad → reject; a
water bill in the slot → reject `water_bill`; empty/junk → reject) and a thin myTNB screenshot (issuer
+ amount, no labels) → `suspect` (not rejected). Conservative by design (mirrors salary): a
thin/cropped read lands in `suspect` (officer confirms), never a false `genuine` or a false reject.
Its value is catching the **wrong-type-in-slot** case — the #47 analog for bills.

## The corpus, in one line

**~96% TNB Peninsular residential.** Of 70 live bills: 67 Peninsular (TNB), 0 SESB (Sabah), 0 SESCO
(Sarawak), 1 company/landlord account. Holder split: 45 patronymic individuals · 14 other
individuals · ~8 name-unread · 1 company. **So we do NOT categorise by issuer — one issuer dominates.
We categorise by PRESENTATION**, which is what varies and what a recogniser must survive.

## Categories (by presentation)

| # | Category | Corpus n (approx) | Capture | Period it yields |
|---|---|---|---|---|
| C1 | **TNB e-bill — native PDF** (myTNB / email download) | 15–21 | deterministic | exact `DD.MM.YYYY–DD.MM.YYYY` |
| C2 | **Bill photo** (paper or screen, camera) | ~36 | AI | often month-only or blank |
| C3 | **myTNB app / portal screenshot** | ~3 | AI | month-only / blank |
| — | *Other-PDF* (scanned/printed to PDF) | ~12 | mixed | mixed → folds into C1/C2 by markers |

**Two cross-cutting FLAGS (tags, not categories):**
- **Undated** (~8 live) — no machine-readable billing period. The class that loops the student
  (the stale/undated re-ask; #130, and app #63 Jayashree 2026-07-09).
- **Company/landlord account** — holder is `SDN BHD` / `ENTERPRISE` / `TRADING` etc., not the family
  (rented premises; the bill is the landlord's). ~1 live (EXCELCROP SDN BHD, app #63).

## Signatures

### Shared TNB authenticity signatures (the fingerprint base — present on every genuine bill)
- **Issuer marks:** `TENAGA NASIONAL`, `TNB`, `Bil Elektrik Anda`
- **Malay field labels:** `No. Akaun`, `Caj Semasa`, `Baki Terdahulu` / `Tunggakan`,
  `Jumlah Perlu Dibayar`, `Tarikh Bil`, `Tarif`, `Kegunaan` / `kWj`
- **Account number:** 12-digit contract account (present in the filename on 23/70 — the C1 downloads)
- **Amount:** `RM` + 2 decimals. Corpus: **all 65 readable amounts are 2-dp**; the `RM` prefix is
  present on only 43 → the reader must **normalise** (prefix optional).
- **Billing period:** `DD.MM.YYYY–DD.MM.YYYY` **or** a `Bulan / Month YYYY` label (see below)

### Category discriminators
| Category | Distinguishing signatures |
|---|---|
| **C1 native PDF** | Deterministic-parseable label block · QR / barcode · due-date `Sila bayar sebelum` · full tariff table · filename `<12-digit acct>_<contract>_<month>.pdf` |
| **C2 photo** | Physical bill layout, often angled / cropped · AI-parsed · period frequently degrades to month-only or blank |
| **C3 screenshot** | `myTNB` wordmark / app UI chrome · summary "amount due" card · **no** tariff table |

### Billing-period shapes (the load-bearing "currency" signature)
The corpus shows exactly **two** real shapes — the parser/normaliser must handle both plus blank:
1. **`DD.MM.YYYY` range** (~23): `17.02.2026 - 16.03.2026`. Separator varies — ` - `, single space,
   or bare `-`. Cycle is ~1 month. The C1 canonical read.
2. **Month label** (~35), **mixed EN / Malay**: `May 2026` / `Mei 2026`, `June` / `Jun`, `Julai`,
   `April`, `Jan`, `Feb`. What a photo/screenshot degrades to. **Datable to month → still yields a
   currency**; only the ~8 blanks are truly undated.

## Variables

### Currently extracted (validated present in the corpus)
| Variable | Non-empty / 88 | Role |
|---|---|---|
| `name` (holder) | 79 | holder-vs-family match (`_utility_name_unrelated`) |
| `address` | 85 | premises-vs-declared match; region |
| `amount` | 83 | current charge / total (`utility_check` reasonableness) |
| `billing_period` | 80 | currency (stale / undated logic) |
| `unpaid_balance` | 59 | arrears / financial-stress signal |

### Proposed additions (each reliably printed on a TNB bill; each earns its keep)
| Variable | TNB label | Why it earns its place |
|---|---|---|
| **`account_no`** | `No. Akaun` (12-digit) | Stable **premises** join-key (the bill's "NRIC"): ties a household's bills together across months, and catches a re-used / stranger account. |
| **`bill_date` / `due_date`** | `Tarikh Bil` / `Sila bayar sebelum` | A robust currency anchor **even when the period reads month-only or blank** — a bill date is printed even when the period label isn't. **Directly dissolves the undated/stale loop** (#130, #63). |
| **`usage_kwh`** | `Kegunaan` / `kWj` | Feeds the "unreasonably high usage vs declared income" query (owner ask 2026-07-08). |
| **`tariff` / premise class** | `Tarif A` (domestik) vs komersial | Domestic confirms it's a *home*; commercial + company holder = the landlord case, flagged automatically. |
| **`issuer`** | logo / header | Future-proofs East Malaysia (SESB / SESCO) if the cohort ever includes it. |

## Remaining operational step (owner-gated)

The scorer + Extraction-v2 are **built, wired, and live in code**, but existing bills carry no
`authenticity` and none of the new fields yet — they populate only on a fresh read. So:

- **Re-score / re-extraction pass on the LIVE service** (per-doc cockpit Re-run, or a batch job like
  `reextract-offers`) activates the genuineness chip on existing bills AND populates
  `bill_date`/`account_no`/`usage_kwh`/`tariff`. **NEVER re-extract locally** (no Storage access →
  reads "no text" → destroys `vision_fields`; `memory/halatuju_never_reextract_locally.md`). New
  uploads are scored + fully extracted automatically.
- `bill_date` only starts anchoring currency (`income_engine._bill_as_of`) once a bill has been
  (re-)extracted under Extraction-v2; until then the currency logic falls back to the period, which
  already works (the 3-ask/6-accept window shipped 2026-07-09).

## Build history

- **DONE 2026-07-09 — Extraction currency fix** (separate, shipped): ask-3/accept-6 window +
  `bill_date`-preferred currency (`_bill_as_of`), backward-compatible via the period fallback.
- **DONE 2026-07-10 — Extraction-v2 + genuineness fingerprint** (this doc): `electricity_doc.py`
  (`MODEL_VERSION 1.0.0`, per-family), wired at extraction + the cockpit wrong-type chip; the new
  fields added to the schema + prompt. Calibrated on 27 live OCR'd bills (0 false-rejects).
- **Normalisation note (still open, minor):** billing-period separators + month language (EN/Malay)
  and the optional `RM` prefix are inconsistent across the corpus — a normaliser would tidy display;
  the currency + scorer already tolerate the variance.

<!-- superseded build order (both slices now done): the bill genuineness fingerprint (family scorer
over the captured OCR text → genuine / suspect / not_electricity_bill) and Extraction-v2 are both
implemented as described above. -->

