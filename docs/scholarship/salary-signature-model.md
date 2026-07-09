# Salary-slip signature model — spec (design)

**Status:** BUILT + corpus-validated + WIRED (2026-07-09). Scorer: `apps/scholarship/genuineness/salary_doc.py`
(`MODEL_VERSION 1.0.0`). Live wiring: scored at extraction → `vision_fields.authenticity` (vision.py,
behind `DOC_GENUINENESS_CHECK_ENABLED`, already ON); the #47 gate fix
(`income_engine.usable_salary_slip` used by `member_cluster_complete` + `services.income_doc_blockers`);
the officer cockpit chip already renders it (`officerCockpit.genuinenessFact`: not_salary→red,
suspect→amber). **Soft:** the income verdict cap deliberately excludes the salary route
(`verdict_engine._income_genuineness_docs`), so this NEVER auto-downgrades income — it surfaces to the
officer + the gate only. **Existing 100 slips are unscored → fail-open** (a re-score pass activates
them on the live service). This is the reference the scorer is written against. Pairs
with `docs/scholarship/str-proof-spec.md`, `docs/scholarship/verdict-confidence-bands.md`, and the
existing signature framework in `genuineness/results_doc.py` (weighted signature families →
`score_signatures` → `bands.py`).

The salary slip answers ONE question for the B40 means-test: **is this a genuine payslip for the
tagged household earner, and what does it say they earn?** Today salary slips are the one standard
income document with **no genuineness signature model** (`authenticity` is null on every salary_slip
row) — deliberately, because unlike EPF/STR/JANM there is no single issuer with a fixed letterhead.
This spec closes that gap using a different fingerprint: **statutory payroll grammar**, not letterhead.

**Motivating gap (#47):** a MyKad was uploaded into the salary-slip slot and a payslip into the EPF
slot; the salary-route submission gate passed on slot *presence* (`.exists()`) without ever asking
"is this actually a payslip?" (see `income_engine.member_cluster_complete`). A C0 reject signal
(below) is what catches this.

## Method (how this was calibrated — reproducible)

- Corpus: **100 live salary_slip documents** pulled read-only via `eval/fetch_corpus.py --types
  salary_slip`; **99 OCR'd** via `eval/capture_ocr.py salary_slip` (gcloud ADC; 4 HEIC/corrupt
  failed). Cached to `eval/snapshots/salary_slip__*.ocr.txt` (**gitignored — real PII**).
- Signatures were derived by measuring candidate-token **document-frequency per category** over the
  real OCR text. All figures below are hit-rates on n=99. No PII in this document — only category
  counts and boilerplate tokens.
- Cases referenced by application number, no PII.

## The core discriminator — statutory scaffold

A genuine Malaysian private payslip carries statutory-deduction lines; a typed/informal one usually
does not. Counting `{KWSP/EPF, PERKESO/SOCSO, EIS/SIP, PCB}` markers splits the corpus cleanly:

| Statutory markers | Docs | Meaning |
|---|---|---|
| **≥2** | 51 | genuine **private** payslip (≈ all of C2) |
| 0–1 | 48 | govt (pension, not EPF) · Singapore (CPF) · informal · gig · reject |

`≥2` statutory markers ⟹ private-genuine, with no observed false positives across 99 docs. Govt and
Singapore slips legitimately score 0 here (civil-service pension; CPF not EPF) → they get their **own
families**, not the private one.

## The six families (validated, n=99)

`source_type` (proposed new field) ∈ {`private`, `govt`, `singapore`, `gig`, `informal`, `not_salary`}.

### C1 `govt` — JANM / civil-service e-Penyata Gaji (n≈10)
Single standardised format; **high confidence**. Note: **no EPF** (KWAP pension), so it must NOT be
scored by the private family — caught after it.
**Signature:** the title **`PENYATA GAJI`** (10/99 files — a genuine private slip says "Slip Gaji"/
"Payslip") + civil-service issuers (`PERKHIDMATAN AWAM`/`AKAUNTAN NEGARA`/`JANM`).
**Correction from first-cut analysis:** `GRED` looked like a 10/10 marker but was an artefact of a
loose token group — it is in only **1/99** files on exact match, so it is NOT used; `PENYATA GAJI`
is the reliable discriminator.

### C2 `private` — company payslip, Sdn Bhd/Berhad (n=53, the bulk)
Fingerprint = **statutory scaffold + wage-label grammar**, NOT issuer identity.
**Signatures:** `PERKESO/SOCSO` 49/53 · `KWSP/EPF` 49/53 · `Potongan` 45/53 · `Gaji Pokok`/`Basic`
42/53 · `Gaji Bersih`/`Net` 42/53 · `Pendapatan`/`Earnings` 41/53 · `EIS/SIP` 39/53 · `Jumlah`/`Gross`
27/53 · `PCB` 22/53.
**Rule:** ≥2 statutory markers AND ≥1 wage label → genuine.

### C3 `informal` — enterprise / sole-proprietor / hand-made (n=18)
`Pendapatan` 18/18 · `Bulan` 15/18 · `Slip Gaji` 11/18 — but **statutory scaffold essentially
absent**. **No reliable self-signature → LOW confidence ceiling by design.** Genuineness must lean on
the cross-doc chain (`income_engine.chain_verified_earner` — IC number ↔ EPF) and amount plausibility,
never on the slip's own boilerplate. Never auto-reject a C3 (a genuinely poor family often has only an
informal slip).

### C4 `gig` — platform earnings (Grab, etc.) (n=3)
`platform brand` 3/3 · `Pendapatan` 3/3. Treat as **declared-income evidence**, not a formal payslip
(pairs with the 2A declared-informal-income path).

### C5 `singapore` — SGD / Pte Ltd payslip (n=7)
`CPF` 5/7 · `Pte Ltd` 5/7 · `Net Pay` 5/7 (the `S$` glyph is often not OCR'd → 2/7). Genuine → convert
SGD→MYR before the B40 band (existing `SGD_TO_MYR_RATE` path).
**Rule:** CPF AND/OR Pte Ltd + wage labels → genuine (SG family).

### C0 `not_salary` — wrong-type / unreadable (n=8)
MyKad markers (`KAD PENGENALAN`/`WARGANEGARA`/`PENDAFTARAN NEGARA`) 2/2 — **the #47 class** — plus 6
low-text/cropped. **Rule:** MyKad markers present, OR no wage-grammar at all → `not_salary`.

## Variables to extract (per category)

Shared core (already extracted today): `name · nric · period · employer · gross_income ·
net_income · gross_income_ytd · currency`. Category-specific additions worth capturing:

| Category | Add |
|---|---|
| C1 govt | `Gred`, `No. Gaji`, per-line `Pendapatan`/`Potongan` |
| C2 private | statutory-deduction amounts (EPF/SOCSO/EIS/PCB), Basic + Allowances |
| C4 gig | platform name, payout period, net earnings |
| C5 singapore | `CPF`, currency=SGD, Basic Pay / Net Pay |

## Proposed scorer + wiring

**New module `genuineness/salary_doc.py`** mirroring `results_doc.py`: one weighted signature list per
family (`(label, [OCR variants], weight, 'text')`), a `score_families(text)` picking the best-fit
family + probability, and a canonical status `{private|govt|singapore|gig|informal|not_salary}`.
Bands via `bands.py` (genuine ≥0.70 / review 0.35–0.70 / suspect <0.35). Bump `MODEL_VERSION` on ANY
signature/weight/gate change (same discipline as `results_doc.py`).

**Wired SOFT — never a new hard wall:**
1. **C0 `not_salary` → the #47 fix.** `income_engine.member_cluster_complete` currently accepts a
   salary_slip on `.exists()` alone. It should additionally require the slip is not `not_salary`
   (wrong-type/empty). A genuine-but-OCR-failed slip must NOT trap the family → the miss becomes an
   auto-raised Check-2 "we need your father's payslip" item, not a hard block (owner's standing
   "never trap a genuine student" rule).
2. **Officer cockpit chip** — a per-family genuineness chip on the salary-slip row (mirrors the
   EPF/STR chips), so a `not_salary`/informal slip reads amber/red, never a false green.
3. **C3 informal / C4 gig** — low ceiling; corroborate via the IC-number/EPF chain + amount, don't
   score the slip alone.

## Scorer output on the real corpus (n=99, `MODEL_VERSION 1.0.0`)

`salary_genuineness()` over the 99 OCR'd slips:

| status | n | families |
|---|---|---|
| **genuine** | 65 | private 47 · govt 11 · singapore 6 · gig 1 |
| **suspect** | 26 | informal (wage labels, no statutory scaffold) |
| **not_salary** | 8 | MyKad-in-slot (3, incl. the #47 class) + 5 no-payslip-fields |

Conservative by design: an OCR-degraded private slip whose statutory lines didn't read lands in
`suspect`/informal (soft officer confirm), never a false `genuine`; the reject floor only fires on a
MyKad or a doc with no payslip fields at all.

## Open items before build

- **Re-capture on change:** OCR text is cached; re-run `capture_ocr.py` if the extraction prompt
  changes. Never re-extract locally into `vision_fields` (see `halatuju_never_reextract_locally`).
- **4 HEIC/corrupt files** didn't OCR — re-capture after a HEIC→JPEG pass, or accept the gap.
- **6 low-signal (cropped) slips** in C0 want a human eyeball to confirm they're truly wrong-type vs
  just cropped (a cropped genuine slip should coach a re-upload, not reject).
- **Token hygiene:** anchor the SG `OW/AW` probe on word boundaries (`ORDINARY WAGE`/`ADDITIONAL
  WAGE`) — the bare substrings false-hit govt slips; immaterial to the design, matters in the scorer.
- **Held-out validation:** label a `counter_examples/salary_slip/` set (known fakes / MyKads) and run
  `calibrate_signatures.py salary_slip` to confirm the `not_salary` floor separates them, before the
  flag goes on.

## Calibration reproduction

```bash
cd halatuju_api
# read-only pull (needs SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY):
SUPABASE_URL=https://pbrrlyoyyiftckqvzvvo.supabase.co \
  python apps/scholarship/eval/fetch_corpus.py --types salary_slip
python apps/scholarship/eval/capture_ocr.py salary_slip          # Vision OCR (ADC), idempotent
python apps/scholarship/eval/calibrate_signatures.py salary_slip # once salary_doc.py exists
```
