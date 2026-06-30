# STR-proof verification — canonical spec

**Status:** Accepted design (2026-06-29). This is the single reference the code alignment is built
against. Supersedes scattered notes in `vision.py`, `income_engine.py`, and prior CLAUDE.md entries
where they disagree. Pairs with `docs/scholarship/verdict-confidence-bands.md` (the four-band colour
model) and TD-151 (document-extraction robustness).

The STR (Sumbangan Tunai Rahmah) document answers ONE question for the B40 means-test: **is this
household a current, approved STR recipient?** An approved current STR is the government's own
means-test — it positively proves B40. Everything below is about reading that honestly, failing it
decisively when it isn't there, and falling through to the salary route when it fails.

Worked against the held-out eval corpus (`apps/scholarship/eval/fixtures/str/` + `.../snapshots/*.ocr.txt`).
Cases referenced by application number (no PII).

---

## 1. The three recognised STR formats (and their signatures)

`source_type` ∈ {`letter`, `semakan_status`, `dashboard`, `unknown`}. Only the first three are STR
proof. **`unknown` is the single most important gate: anything not one of the three formats is NOT an
STR.**

### `letter` — official Kementerian Kewangan STR approval letter
**Signatures:** Jata Negara crest · "KEMENTERIAN KEWANGAN MALAYSIA" · "No. Rujukan" · "SUMBANGAN TUNAI
RAHMAH (STR)" · the approval sentence "Sukacita dimaklumkan bahawa permohonan STR …" · "Status terkini
STR" · "Sekiranya terdapat pertanyaan lanjut berhubung kelayakan STR".
**It is the only self-dating format** — it carries a letter date / cycle year.

### `semakan_status` — MySTR "Semakan Status" check page
**Signatures:** "Semakan Status" · "Maklumat Pemohon" · "Status Pedalaman" · "Status Permohonan
**Semasa**" · "Fasa Bayaran" (a phase table) · "Jumlah Telah Dibayar" · "Jumlah Bayaran Keseluruhan
STR" · "Sumbangan Asas Rahmah" section · a "Maklumat Pembayaran" section.

### `dashboard` — MySTR mobile-app home
**Signatures:** the app nav (Dashboard / Jadual Perkhidmatan / Kaunter / Soalan Lazim (FAQ) / Panduan
Pengguna / Borang) · a profile card with the name + IC in brackets · "Status Permohonan STR" cards ·
"Status Kelayakan SARA" · "Jumlah Telah Dibayar" / "Jumlah Bayaran Keseluruhan STR".

> **Known classifier gap (TD-151):** in production every dashboard is currently mis-classified as
> `semakan_status` (the `dashboard` bucket is empty). The signatures above are the discriminator the
> classifier must use: Semakan has "Maklumat Pemohon" + "Status Permohonan **Semasa**" + "Fasa
> Bayaran"; Dashboard has the nav menu + "Status Permohonan STR" + "Status Kelayakan SARA".

---

## 2. Per-format variables (required + optional)

All formats share one extraction schema, but the *meaning* and *requirement* differ by format. "Required"
= what the verdict needs; nothing is hard-required at the JSON-schema level (absent → empty string).

| Variable | `letter` | `semakan_status` | `dashboard` | Role |
|---|---|---|---|---|
| `source_type` | `letter` | `semakan_status` | `dashboard` | **Required** — the format gate; `unknown` → 🔴 |
| `recipient_name` | "Nama Penerima" | "Nama" | profile-card name | **Required** — identity (whose STR; matched to the earner IC) |
| `recipient_nric` | IC on letter | "No Pengenalan" / "No. MyKad" | number in brackets | **Required** — identity |
| `status` | from "diluluskan" | "Status Permohonan **Semasa**" → value | value **under** "Status Permohonan STR" | **Required, decisive** — the approval word |
| `date` (letter only) | letter date / "STR 2026" | — | — | **Currency** — pins the cycle |
| `payment_date` | — | "Maklumat Pembayaran" → Tarikh Bayaran (if open) | — | **Currency** — pins the cycle when present |
| ~~`amount`~~ | "Jumlah … STR" | "Jumlah Bayaran Keseluruhan STR" | "Jumlah Bayaran Keseluruhan STR" | **NOT a variable — it is a signature** (used to recognise the format, never read as data) |

Notes:
- **Only the letter self-dates.** Semakan can pin the cycle *only* if the student opens "Maklumat
  Pembayaran" (the dated payment phases); collapsed, it has no date. Dashboard never has a date.
- **`status` is the value, never the label.** "Status Permohonan STR" is a *label*; the status is the
  word on the next line (Lulus / Ditolak / Dalam proses). Returning the label fragment `"STR"` as the
  status is the #112 bug — forbidden.
- The "Jumlah …" lines and "Fasa Bayaran" are **signatures** that identify the format, not values to
  capture.

---

## 3. Document-level STR status (🟢 / 🔵 / 🟡 / 🔴)

The status chip on the document card. The **format gate runs first**: not one of the three → 🔴, full
stop. Only a recognised format proceeds to the status/currency assessment. The Recipient / IC-No chips
are a **separate identity axis** and NEVER rescue a red STR (a perfectly-matched IC on a payslip is
still not an STR).

| Status | Condition |
|---|---|
| 🔴 **Not a valid STR** | `source_type = unknown` — SALINAN / borang permohonan / SARA letter / PERKESO statement / salary slip / any non-STR document |
| 🔴 **Rejected** | a recognised format showing **Ditolak / Tidak Layak / Gagal** |
| 🟢 **Lulus (current)** | recognised format + approved + **dated current** (letter date, or Semakan payment date, ≥ cohort year) + recipient = earner |
| 🔵 **Lulus (currency unconfirmed)** | recognised format + approved but **no date** (dashboard, or collapsed Semakan) — probably current |
| 🟡 **Incomplete / out of date** | recognised format but **status unreadable** (cropped) **or stale** (readable prior-year date) |

`SARA` deserves a one-line callout: **SARA (Sumbangan Asas Rahmah) is a different programme from STR.**
A SARA-only document (e.g. a Perdana Menteri congratulation letter) is `unknown` → 🔴 as STR proof.
SARA "Layak" is NOT an STR approval word.

---

## 4. Verdict copy — decisive, one state → one sentence

The current word-salad ("…may be a SALINAN with no status, an out-of-date STR, or one we couldn't
read…" + "may not be a genuine official original — confirm at interview") collapses five different
situations into one. Split it:

| State | Verdict line |
|---|---|
| 🔴 wrong-type (salary slip) | "This is not an STR document — it's a salary slip. Assessing on the salary route." |
| 🔴 wrong-type (SARA/SALINAN/other) | "This is not an STR document (it's a {SARA letter / application record / …}). Assessing on the salary route." |
| 🔴 rejected | "The STR application was rejected (Ditolak) — not an approved STR." |
| 🟡 unreadable (cropped) | "This MySTR page is cropped — the status line isn't visible. Re-upload the full page (open Maklumat Pembayaran to show the dated payments)." |
| 🟡 stale | "This STR is from a prior cycle ({year}). Upload the current cycle's status." |
| 🔵 unconfirmed (real STR, no date) | "Approved (Lulus), but the page shows no payment date. Open Maklumat Pembayaran (Semakan) to confirm the current cycle, or it's accepted on the live-portal status." |
| 🟢 current | (no caveat — green) |

The SALINAN / "ask for your Lulus" paragraph is **reserved strictly for the genuine
recognised-but-unconfirmed case** — never for a wrong document. **Delete the "may not be a genuine
official original" caveat for a wrong-type document** — a genuine payslip/SARA letter in the STR slot
is *the wrong document*, not a forgery.

---

## 5. Structured currency states (what the verdict consumes)

`income_engine._str_currency(...)` must return a structured state, not collapse everything into
`unconfirmed`. The smarter document read already knows "this is a salary slip" — that insight must
reach the decision layer as a state, not stay as prose.

| State | Meaning | Doc status | Income-fact contribution |
|---|---|---|---|
| `current` | approved + dated current | 🟢 | proves B40 (→ Certain) |
| `unconfirmed` | recognised format, approved, no date | 🔵 | probable B40 |
| `stale` | approved, prior-year | 🟡 | needs current cycle |
| `rejected` | Ditolak | 🔴 | STR fails — fall through to salary |
| `wrong_type` | `source_type = unknown` (not an STR) | 🔴 | STR fails — fall through to salary |

`rejected` and `wrong_type` are **terminal for the STR axis** and **trigger the route fall-through**
(§6). `unconfirmed`/`stale` keep asking for a better STR while still allowing the salary route.

---

## 6. Evidence-driven verdict — never freeze on a failed STR

The income verdict is **evidence-driven, not locked to the declared route.** Today a failed STR leaves
the verdict reporting the STR problem and silent on the salary docs already on file (the #13 / SARA
cases). Required behaviour:

1. If a valid **current** STR (recipient = earner) → B40 proven → 🟢.
2. Else if STR is `rejected` / `wrong_type` / absent **and salary/benefit evidence is on file** →
   **evaluate the salary route** on that evidence (§7) and report *that* band. Do not freeze.
3. Else if STR is `unconfirmed`/`stale` (a real STR, just unpinned) → 🔵/🟡 with the §4 ask, salary
   route still available.
4. Else (no usable income evidence at all) → 🔴 Can't-verify.

---

## 7. Income computation (salary route)

This is a **separate exercise in its own right** (a fuller salary-track spec is owed); the rules below
are the ones the STR cases forced and must hold.

- **Use annualised pay including variable components (O/T), not single-month basic.** A single month
  understates or overstates; annualise from YTD. The YTD *period* (months elapsed vs employment-to-date)
  is ambiguous on a payslip → a **flagged interview item**, and itself a reason to lean Unsure when the
  figure sits near the line. (#13: basic RM3,800/mo, but YTD-annualised ≈ RM7,064/mo.)
- **A pension / benefit statement is real income.** A PERKESO survivor's pension (PENCEN PENAKAT) is
  household income for the per-capita calc — the salary-slot check must accept it, not reject it as
  "not a salary slip from an employer." (The SARA case: RM687.50/mo is the household's income.)
- **Hardship corroborators** push *toward* need, never away: utility-bill arrears (already surfaced),
  SARA recipiency, a survivor's pension. They are soft signals, not B40 proof, and never disqualify.
- **Two B40 tests** (per the cohort config): gross household income ≤ `income_ceiling` (RM5,860) is the
  **primary** test; per-capita ≤ `per_capita_ceiling` (RM1,584) is a **safety net** above it.

### 7.1 The headroom rule (household corroboration)

The per-capita safety net divides by household size. **It is only trustworthy when household size is
corroborated.** But "uncorroborated → Unsure" is too blunt — the band depends on **how much an unknown
member could move the needle**:

> Compute the **headroom** = (binding ceiling for the declared household) − (known income). Ask: *what
> would each unaccounted member need to earn to breach it?* Grade the confidence by how plausible that
> is.

- **Large headroom** (the unknown would need an implausibly high wage to breach) → the gap can't
  realistically change the answer → **🔵 highly probable B40, confirm at interview.**
- **Thin headroom** (the unknown needs only a modest, plausible wage to breach), especially with the
  known income already near the line → **🟡 Unsure.**

Worked, same rule, opposite outcomes:

| | Known income | Declared size | Headroom (per-capita) | Unknown member must earn | Band |
|---|---|---|---|---|---|
| **#13** | ~RM7,064/mo | 5 | RM7,920 − 7,064 = **RM856** | ~RM856/mo (trivially plausible) + own income already at line | 🟡 **Unsure** |
| **SARA case** | RM687.50/mo | 6 | RM9,504 − 687.50 = **RM8,816** | ~RM8,816/mo (implausible for a B40 sibling) | 🔵 **Highly probable** |

(The gross primary test gives the same verdicts — for the SARA case the unknown would still need
~RM5,172/mo to breach the RM5,860 gross line; implausible.)

This is also where the parked **structured family roster** pays off — it corroborates household size
directly, shrinking the unknown.

---

## 8. Income (B40) overall verdict band

Combining the STR axis and the salary route:

| Band | Condition |
|---|---|
| 🟢 **Certain** | valid current STR (recipient = earner); OR salary clearly under the line with household corroborated |
| 🔵 **Probable** | recognised-but-unconfirmed STR (no date); OR salary under the line with large headroom despite an uncorroborated member |
| 🟡 **Unsure** | stale STR; OR salary near the line; OR per-capita passes only via an uncorroborated household with thin headroom; recipient ≠ earner |
| 🔴 **Can't-verify** | rejected STR with no other evidence; OR no usable income evidence; OR income clearly over the line with no mitigation |

"Blue needs a green" still holds (a tile reaches 🔵 only on ≥1 verified value; soft signals don't
qualify it) — see `verdict-confidence-bands.md`.

---

## 9. Worked examples (regression anchors → TD-151 corpus)

- **#112** — dashboard, "Status Permohonan STR" → `status` read as `"STR"` (label leak) → false
  `unconfirmed` → 🔵. **Fix:** read the value, not the label → 🟢/🔵 correctly.
- **#13** — salary slip in the STR slot → `wrong_type` → STR 🔴 ("not an STR"); fall through to salary;
  annualised ~RM7,064/mo, declared 5 (4 identified), thin headroom → **income 🟡 Unsure**.
- **SARA case** — SARA letter + PERKESO pension in the STR slot → `wrong_type` → STR 🔴; fall through;
  RM687.50/mo income, declared 6 (5 identified), large headroom → **income 🔵 highly probable**.

---

## 10. Implementation checklist (for the alignment; each is TD-151-adjacent)

1. **Format gate first.** `source_type = unknown` → 🔴 "Not a valid STR" at the document level; never
   `unconfirmed`/🔵.
2. **`_str_currency` returns a structured state** (`current`/`unconfirmed`/`stale`/`rejected`/`wrong_type`),
   and the verdict engine maps each to its band + its §4 copy. `wrong_type`/`rejected` trigger the
   route fall-through (§6).
3. **Extraction fixes:** read `status` as the value after the label (kill the `"STR"` leak); classify
   dashboard vs semakan by §1 signatures; read the date ONLY from a `letter` date or a Semakan
   `Maklumat Pembayaran` payment date — never the FAQ-nav "2026" chrome.
4. **Drop the "may not be genuine" caveat for wrong-type** (genuine doc, wrong slot ≠ forgery).
5. **Income engine:** evidence-driven route fall-through; accept pension/benefit as income; annualise
   incl. O/T; the **headroom-graded** household-corroboration rule.
6. **Capture-date as a one-directional fraud flag only** (filename date; never grants currency, only
   flags a stale/implausible screenshot for review). EXIF skipped (screenshots/WhatsApp strip it).

## 11. Out of scope (separate work)

- The full **salary-track spec** (income sources, per-member aggregation, sibling-income handling).
- Real disbursement / money (TD-075).
- Re-extraction of existing live STR docs to the new model — must run on the **live service** (cockpit
  Re-run), NEVER from a local checkout (see `memory/halatuju_never_reextract_locally.md`).
