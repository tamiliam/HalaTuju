# Reporting student spending to sponsors — the brief

Written 2026-09-09, immediately before a context compaction, from a screenshot the next session will
not have. **Nothing has been built or investigated beyond what is written here.** This is a starting
point, not a plan — the plan needs `implementation-planning.md` after the owner answers §4.

---

## 0. ⚠⚠ READ `docs/plans/2026-07-18-bursary-spend-reporting-brief.md` FIRST

**A full implementation brief for this exact feature already exists, written 2026-07-18 from REAL
Vircle exports.** This document was written without knowing that. It carries the thing §5 below asks
for — **the verified column shape** — plus models, an ingest command, tests and sizing (~18–24
files). **Nothing was built** (`BursarySpendTxn` / `MerchantCategory` / `ingest_bursary_spending`
appear in no source file, only in that brief).

What it recorded, from the real files:

    transaction_date ("12 Jul 2026, 20:37:59") · wallet_id · student full name ·
    transaction_id (UNIQUE — the idempotency key) · Sender · Receiver (merchant, OR an
    individual person for DuitNow person QR) · duitnow_type · Entry Type · TX Type ·
    amount ("RM25.50" as a STRING) · Status ('00' = success)

⚠ **Two things it says that must survive into any plan:** the weekly exports **OVERLAP**, so
`transaction_id` uniqueness is the only thing stopping double-counting; and the student's **NAME in
the export is used ONLY to cross-check the wallet mapping and is NEVER STORED** — the join is
`wallet_id → application`, which the payments run CSV already pairs.

⚠ **BUT VERIFY THE FORMAT AGAIN BEFORE PARSING.** July says **transaction-level XLSX** in a folder
called `03 Vircle/02 Student Spending`; the September screenshot shows **Google Sheets** in
`03 Payments, Vircle/06 Student Spending`. The tree was renamed (see §3) and the file type may have
changed with it. Anchor the parser on the header row **by NAME, not position**, and fail loudly
listing unexpected headers.

---

## 1. The ask, verbatim

> *"I want you to look at reporting student usage of funds to sponsors. The spending reports are
> saved in the drive."*

So: a sponsor who funds a student should be able to see **what their money was spent on**.

---

## 2. Where the data is — CAPTURED FROM A SCREENSHOT, verify before trusting

Google Drive, breadcrumb **`… › 03 Payments, Vircle › 06 Student Spending`**.

**Folder id `1a19kBPPUsHVLEBF9iOooVHtcIjWzJcNV`** (read off the browser URL — this is the one detail
that cannot be re-derived from the repo, which is why it is written down first).

Eight Google **Sheets**, owned by the owner, named to one pattern:

    YYYY-MM-DD BrightPath Bursary_Bursary Usage Report_Table

| Report date | Size |
|---|---|
| 2026-08-30 | 4 KB |
| 2026-08-23 | 5 KB |
| 2026-08-16 | 8 KB |
| 2026-08-09 | 9 KB |
| 2026-08-02 | 7 KB |
| 2026-07-26 | 5 KB |
| 2026-07-12 | 3 KB |
| 2026-07-05 | 1 KB |

**Weekly, dated on a Sunday, 5 July → 30 August.** ⚠ **2026-07-19 IS MISSING** — either a week with
no spending, a week nobody exported, or a naming variant. Do not build a "one file per week" reader
that treats a gap as an error until that is understood. The files are tiny (1–9 KB), so this is a
handful of rows each, not a ledger.

Everything above is from an image. **Re-list the folder before relying on any of it.**

---

## 3. What already exists — the encouraging part

- **⚠ THE SPONSOR-FACING SLOT IS ALREADY BUILT AND WAITING.**
  `halatuju-web/src/app/sponsor/(portal)/my-students/[id]/page.tsx` renders a dashed placeholder
  card whose own comment reads *"Reserved for the Vircle spending panel (a later sprint)"*, with
  i18n keys `sponsorPortal.myStudents.detail.spending` / `.spendingSoon` already in en/ms/ta. This
  feature fills that card. **Start there** — the page, its fence and its anonymity rules exist.
- **Reading a Google Sheet is already a solved problem in this codebase.**
  `apps/scholarship/sheets.py` carries `read_sheet_values(spreadsheet_id, cell_range)` — the one
  inbound sheet READ, built for the Vircle activation relay — plus `_find_folder_path(drive, path)`,
  `_find_folder`, and the shared `_services()` credentials. No new integration is needed, only a new
  caller.
- **✅ THE FOLDER-NAMING WORRY IS CLOSED — production was already right.** `base.py`'s DEFAULTS are
  stale (`'03 Vircle/…'`), but **every one of them is env-overridden on the live service**, read from
  `gcloud run services describe halatuju-api` on 2026-09-09:

      MEET_ORGANISER_EMAIL      = admin@halatuju.xyz
      VIRCLE_DRIVE_FOLDER       = 01 BrightPath/03 Payments, Vircle
      VIRCLE_ACTIVATION_FOLDER  = 01 BrightPath/03 Payments, Vircle/01 Activation
      VIRCLE_PAYMENTS_FOLDER    = 01 BrightPath/03 Payments, Vircle/04 Payment Execution Docs for Vircle
      VIRCLE_GUIDE_FOLDER       = 01 BrightPath/03 Payments, Vircle/05 Student Guide

  So the tree WAS renamed and the env vars followed it. Nothing is silently falling back. **Read a
  folder path from the running service, never from a settings default** — the stale defaults would
  have sent this sprint hunting a bug that does not exist. The new setting follows the same shape:
  `VIRCLE_SPENDING_FOLDER = '01 BrightPath/03 Payments, Vircle/06 Student Spending'`.
- **✅ ACCESS IS SETTLED IN PRINCIPLE.** The SA impersonates **admin@halatuju.xyz**, who is the
  **owner** of `06 Student Spending` (the screenshot's "me"). `fetch_drive_pdf` already walks this
  exact tree with the full `drive` scope and is proven live against `05 Student Guide` next door.
  ⚠ `drive.readonly` is NOT in this SA's delegation allowlist — requesting it fails
  `unauthorized_client`; the granted `drive` scope is the one that works.
- **⚠ THE CLAUDE DRIVE CONNECTOR CANNOT SEE ANY OF THIS, and that is not a fault.** It is signed in
  as `tamiliam@gmail.com`; the folder lives in `admin@halatuju.xyz`'s Drive. Four searches returned
  empty. Do not read that as "the folder is missing" — check WHICH identity is asking.

---

## 4. ✅ THE OWNER HAS RULED (2026-09-09) — shape 1, categories and totals only

> *"We won't share where they shopped. We'll categorise the expenses into, say, 10 categories.
> There should also be payment given. So the sponsor knows how much has been released and how much
> spent and for what category."*

**Merchant names, dates and times NEVER reach a sponsor.** That is inside the live consent
(`CONSENT_VERSION 2026-draft-6`: sponsors receive an anonymised summary; documents are never
shared), so **no consent-version bump is needed**. Anything wider later IS a consent change.

**The four numbers, in this order:**

    RM2,000 promised · RM1,400 released so far · RM1,120 spent · RM280 left in their wallet

`promised` = `award_amount`; `released` = `payments.paid_to_date(application)` (SUM of **released**
`Disbursement` rows — our own record, the authoritative one); `spent` and `left` come from Vircle.

⚠ **"SPENT" CAN EXCEED "RELEASED", AND THAT IS NOT A BUG.** The Vircle wallet is the student's own;
a parent may top it up. We cannot tell our ringgit from theirs. The copy must never imply the
student overspent our money — and the arithmetic must not go negative on screen.

**The ten categories** (owner, 2026-09-09) — the fixed sponsor-safe vocabulary:

`food` Food & drink · `groceries` Groceries · `transport` Transport · `study` Books & study supplies ·
`phone` Phone & internet · `hostel` Hostel & bills · `health` Health & pharmacy ·
`clothing` Clothing & shoes · `transfer` **Sent to a person** · `unsorted` **Not yet sorted**

⚠ **THE LAST TWO ARE THE HONEST ONES AND MUST NOT BE QUIETLY DROPPED.** `transfer` is the
DuitNow-person-QR case — the one line a steward most needs to see — and it is assigned
automatically, never by merchant name. `unsorted` is every shop not yet in the map; showing it is
what stops the other nine reading as complete when they are not.

**Time window (owner): ALL TIME, refreshed weekly.** No month picker in v1 — the reports arrive
weekly, so the card simply restates the whole picture each week. One "as at DD/MM/YYYY" stamp.

**Chart (owner): DONUT + RANKED LIST.** Top 6 categories as slices, everything else folded into one
`Other` slice; beside it the full ranked list with ringgit amounts, which is what people actually
read. ⚠ **The released-vs-spent line is NOT the donut** — it is one horizontal bar (a fuel gauge).
Two questions, two shapes; do not merge them.

**Per student, not programme-aggregate** — the reserved card is on `my-students/[id]`.

---

## 4b. The superseded question, kept for the reasoning

**How much of a student's spending may a sponsor see?**

The whole sponsor surface is built on anonymity: a sponsor never learns a student's name, school,
NRIC, phone or address, and every sponsor-facing serializer is an **allowlist** with a leak test
behind it (`pool.py`, `SponsorPoolCardSerializer`, `GraduationRelaySerializer`). Spending is the
most intimate data we would ever have shown them — a line-item feed says where somebody shops, when
they eat, and how much they have left.

Three shapes, roughly, from least to most revealing:

1. **Categories and totals only** — "RM180 on food, RM60 on transport, RM40 on books this month".
   Anonymous, hard to misuse, and probably answers the sponsor's real question ("is it being used
   for what I gave it for?").
2. **Category + weekly trend**, no merchants, no timestamps.
3. **Line items** — merchant, date, amount. Most transparent, and the one that turns a bursary into
   surveillance of a named-to-nobody-but-still-real teenager.

**My starting recommendation is (1)**, with the reasoning that the sponsor's question is about
STEWARDSHIP, not about the student's day. But it is the owner's call, it is a consent question as
much as a design one, and the students agreed to something specific at consent
(`CONSENT_VERSION`, currently `2026-draft-6`, whose text says sponsors receive an **anonymised
summary** and that **documents are NEVER shared**). **Read the live consent wording before
proposing anything wider than a summary** — if what the owner wants exceeds what students agreed to,
the change is a consent-version bump, not a feature.

Second question, smaller: **is this per-student, or the programme in aggregate?** The reserved card
is on ONE student's page, which implies per-student.

---

## 5. Open questions for the investigation (not for the owner)

- What columns do these sheets actually have? Is a student identifiable in them, and by what key
  (eWallet id? name? `vircle_id`?). The join back to `ScholarshipApplication` is the crux.
- Who produces them, and how — a Vircle export the owner downloads by hand, or something scheduled?
  That decides whether the product reads Drive on a cron or the owner uploads.
- Do they cover all 47 funded students or only some?
- Does the money in them reconcile with `Disbursement` / `PaymentRun` totals we already hold?

---

## 6. Rails that apply whatever the shape

- **This is a SPRINT, not the small-change lane** — it is a new feature surface, it touches money
  and it touches what a third party may see about a minor. `implementation-planning.md` first.
- **The sponsor serializer is an ALLOWLIST and must stay one.** A new model field is invisible to
  sponsors until deliberately added, and that is the property that has kept this surface safe.
- **Stitch-first**: the spending card is a new component on an existing page — get the visual
  approved before writing the page code.
- **Push = deploy, owner-gated.**
- ⚠ **Do not put spending data in the pool/discovery card.** A person browsing students they have
  not funded must never see it; the reserved card is on `my-students/[id]`, behind "you fund this
  student", and that fence is the whole design.
