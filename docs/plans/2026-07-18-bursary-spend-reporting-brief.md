# Implementation Brief — Bursary Spend Reporting (sponsor-visible)

**For:** the implementing agent (Opus 4.8), in `c:\Users\tamil\Python\Production\HalaTuju`
**Shape:** ONE sprint, one deploy. HAS MIGRATIONS (new models) → migrate-first runbook required (hand-written Postgres DDL per the house pattern; note the TD-058 contenttypes caveat for CreateModel on this prod).
**Pre-flight:** start only on a clean, fully-pushed tree (an owner-gated unpushed commit existed on this checkout 2026-07-18 — do not push someone else's gated work).

## Context — the data reality (verified from real exports 2026-07-18)

Vircle's "Bursary Usage Report" is exported by the owner (weekly cadence observed) into Drive **`03 Vircle/02 Student Spending`** — the folder is ALREADY shared with the platform's service account (the same seam the payments module uses to write `03 Vircle/01 Payment` CSVs). Format = **transaction-level XLSX**, columns:
`transaction_date` ("12 Jul 2026, 20:37:59") · `wallet_id` · student full name · `transaction_id` (unique — the natural idempotency key) · `Sender` · `Receiver` (merchant name; can be an INDIVIDUAL person for DuitNow person QR) · `duitnow_type` · `Entry Type` (CREDIT) · `TX Type` (Spend) · `amount` ("RM25.50" string) · `Status` ('00' = success; verify other codes and skip non-success).
**No categories from Vircle — merchant names only.** Join: the payments module's own run CSV already pairs `Wallet ID ↔ Student NRIC` (see `PR-*.csv` schema in `sheets.write_payment_csv`), so wallet→application resolution uses that existing knowledge; persist `vircle_wallet_id` wherever the payments module keeps it (locate it — if it lives only in the owner's sheet, add the field and seed it via a first-run mapping report the owner approves).

## Deliverables

### 1. Models (migrations — migrate-first)
- **`BursarySpendTxn`**: `application` FK (PROTECT), `txn_id` (unique), `txn_at` (datetime), `merchant` (the Receiver string), `amount` (Decimal, parsed from "RMx.xx"), `entry_type`/`status` (short codes), `category` (code, from the map below; `''` = uncategorised), `is_person_receiver` (bool), `source_file`, `imported_at`. **The student's NAME from the export is used only to cross-check the wallet mapping and is NEVER stored.**
- **`MerchantCategory`**: normalised merchant string → category code. Categories (fixed vocabulary, sponsor-safe): `food` (Food & groceries), `study` (Study & supplies), `transport`, `transfer` (person receivers, automatic), `other`. Seed the map from the merchants present in the two real exports (restaurant/cafe → food; TECHSTOP-style → study; person names → transfer); everything unmapped = uncategorised until curated.

### 2. Ingest (extend the payments seam — `sheets.py`)
- Read helpers on the existing service-account seam: list files in `03 Vircle/02 Student Spending` (`_find_folder_path` already walks such paths), download/parse XLSX (add `openpyxl` to requirements if absent).
- `ingest_bursary_spending` management command, **`--report` (default) / `--apply`**: parse all new files; resolve wallet→application; report unknown wallets, non-success statuses skipped, person-receiver transactions, per-student totals vs `payments.paid_to_date(application)` (overspend = red flag in the report); idempotent by `txn_id` (weekly exports overlap — dedup is mandatory). `--apply` writes rows. Register for weekly cron per the `CronRunView.JOBS` convention. Live-service only (the SA key lives there).

### 3. Sponsor surface (My Students detail — the panel the journey promised)
"How the bursary is being used": monthly spend bars by CATEGORY (curated map; an honest "Uncategorised" slice while the map matures), cumulative "RM used of RM paid" utilisation vs `paid_to_date`, transaction COUNT, last-updated stamp. **Sponsors NEVER see merchant names, individual transactions, timestamps, or person-receiver details** — category aggregates only (a merchant line can locate a student; "Food · RM180 in June" cannot). Allowlist serializer extension in the established explicit-field style + anonymity tests extended (merchant/txn leakage = test failure). i18n ×3 under the guarded sponsor namespaces.

### 4. Organisation oversight (cockpit, modest)
Org-admin/QC application view gains a spend tab/section: the transaction table (merchant-level — oversight is their job), person-receiver transfers flagged, unmapped merchants listed with a hint to curate the map. No new role powers.

### 5. Governance
Verify the bursary agreement's wording covers spend reporting to sponsors (it is the accountability promise; cite the clause in the retro — if absent, STOP and report to the owner before shipping the sponsor panel; the ingest + cockpit parts may still ship).

## Tests & verification
Ingest unit tests on fixtures shaped EXACTLY like the real export (columns above — build fixtures with fake names/wallets); dedup across overlapping files; amount/date parsing; wallet-resolution incl. unknown-wallet reporting; category mapping incl. person-receiver; reconciliation flag; allowlist/anonymity extensions; jest for the sponsor panel (aggregates only, no merchant strings in props); full pytest + jest + `next build`; migrate-first runbook applied and verified before push; build matched by SHORT_SHA; live smoke = run `--report` on the real folder, owner reviews, `--apply`, panel shows real aggregates for one sponsored student.

## Out of scope
Vircle API integration (none exists — "Vircle gives us nothing back"); automatic AI merchant classification (the curated map + uncategorised bucket is v1; revisit when the map's coverage plateaus); sponsor-facing transaction detail (deliberately never); payment-run changes.

## Sizing & risks
~18–24 files. Risks: (1) wallet mapping errors mis-attribute spend — first-run mapping is report-first and owner-approved, name cross-check mandatory; (2) export format drift — the parser anchors on the header row by NAME, not position, and fails loudly listing unexpected headers; (3) double-counting from overlapping weekly exports — `txn_id` uniqueness is the guard, tested; (4) privacy regression — the anonymity suite gains the merchant/transaction leakage cases as permanent tests.
