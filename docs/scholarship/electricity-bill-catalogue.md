# Electricity-bill catalogue — categories, signatures & variables

**Corpus-derived 2026-07-09** from the live `applicant_documents` electricity-bill corpus (88 rows /
68 applications, all scanned; 70 live). The authoritative reference for (a) the bill categories we
actually see, (b) the signatures that identify a genuine bill and its category, and (c) the variable
set — current + proposed — that a richer extraction should read. This is the design spec for the
future utility-bill **positive genuineness fingerprint** (the noted doc-recognition gap: bills today
have `_dedup_clean_rank` + `utility_check` but **no** signature model, no stored `authenticity`).

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

## Implementation constraints (honest — read before building)

1. **The extraction stores only the 5 fields above + `capture` — no raw OCR text, no `authenticity`
   for bills.** A signature genuineness model (scoring over text, like `genuineness/results_doc.py`)
   AND the new variables both require the **OCR text captured + the prompt/parser extended**.
2. That is a **re-extraction** — owner-triggered, on the **live service, NEVER local** (a local
   re-extract has no Storage access → reads "no text" → destroys `vision_fields`;
   see `memory/halatuju_never_reextract_locally.md`).
3. A new `electricity_bill` fingerprint follows the `genuineness/results_doc.py` `_FAMILIES` /
   `MODEL_VERSION` pattern → **bumps `MODEL_VERSION` → cohort re-run** (the deliberate versioned-brain
   gate).
4. **Normalisation is warranted regardless of the model:** billing-period separators + month language
   (EN/Malay), and the optional `RM` prefix, are inconsistent across the corpus.

## Suggested build order (when the owner greenlights a sprint)

1. **Extraction v2 (no MODEL_VERSION change):** add `account_no`, `bill_date`/`due_date`, `usage_kwh`,
   `tariff` to the bill prompt/parser + a billing-period/amount normaliser. Re-extract on the live
   service. This alone fixes the undated/stale loop (`bill_date` anchors currency) and enables the
   high-usage query — **the highest-value, lowest-risk slice**.
2. **Bill genuineness fingerprint (bumps MODEL_VERSION):** a `_FAMILIES['electricity_bill']` signature
   list from the shared TNB marks above, scored over the now-captured OCR text →
   genuine / suspect / not_electricity_bill, with the C1/C2/C3 discriminators as category tags. Cohort
   re-run under the new version.
