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

⚠ **THE FORMAT HAS CHANGED SINCE JULY — DO NOT PARSE TO THE JULY SHAPE.** Read off the real
`2026-08-30` report on 2026-09-09 (screenshot of row 1 + rows 2–7). It is now a **Google Sheet**,
not XLSX, with **eleven** columns:

| # | Header | Example | Note |
|---|---|---|---|
| A | `transaction_date` | `30 Aug 2026` | **DATE ONLY — the time of day is gone.** July had `12 Jul 2026, 20:37:59`. |
| B | `wallet_id` | `8000400176805` | 13 digits — the SAME shape as our stored `vircle_id`. This is the join. |
| C | `transaction_id` | `1026083032545` | The idempotency key. Appears to encode the date; do not rely on that. |
| D | `Wallet User` | `THAVASRI A/P …` | **The ACCOUNT HOLDER — not necessarily the student.** See below. |
| E | `Child User` | `null` | New since July. See below. |
| F | `Merchant Name` | `99 Speedmart` | July called this `Receiver`. |
| G | `duitnow_type` | `STATIC_MERCHANT` / `DYNAMIC_MERCHANT` | The only trustworthy person-vs-shop signal. |
| H | `Entry Type` | `CREDIT` | ⚠ Reads `CREDIT` on a **Spend** — it is the counterparty's view. Do not gate on it. |
| I | `TX Type` | `Spend` | Gate on this. |
| J | `amount` | `2`, `12.4` | **A NUMBER now, not the string `"RM25.50"`.** July's currency-string parser is wrong. |
| K | `Status` | `00` | `00` = success. Gate on this. |

July's `Sender` column is gone. Anchor the parser on the header row **by NAME, not position**, and
fail loudly listing unexpected headers.

⚠⚠ **TRAP 1 — `Wallet User` IS NOT ALWAYS THE STUDENT, AND `Child User` IS WHY THE COLUMN EXISTS.**
Vircle will not let someone **born after 2008** hold their own account: a parent registers and the
student is added as a **child** on it (this is already a live, named case — `STATUS_PARENT_ACCOUNT`
in `sheets.py`, and the award email carries a selective guardian paragraph gated on
`vircle.can_register`). On such a wallet the parent is `Wallet User` and the student is `Child User`.
**A join that reads `Wallet User` as the spender will attribute a parent's own shopping to a
student, and there is nothing on the row that would look wrong.** Join on `wallet_id`, and treat a
populated `Child User` as the spender. ✅ **Superseded by §0b: it is populated on 28 of 1,368 real
rows** — a live case, not a hypothetical.

⚠⚠ **TRAP 2 — A SHOP'S NAME IS OFTEN A PERSON'S NAME.** In the six sample rows, `AZMI BIN BAKA…`
and `MUHAMMAD N…` sit beside `99 Speedmart` — and both carry `duitnow_type = STATIC_MERCHANT`. They
are hawker stalls and sundry shops registered to an individual, which is ordinary in Malaysia.
Two consequences, and both are load-bearing:
  * **`transfer` ("Sent to a person") MUST be derived from `duitnow_type`, NEVER from the name
    looking like a person.** Name-shape matching would file half the student's meals as money sent
    to a friend — the single most damaging thing this card could get wrong. ✅ **Superseded by §0b:
    the full vocabulary is now measured and the person value is
    `STATIC_CUSTOMER_QR_CODE_DUITNOW_P2P`** — no longer a guess.
  * **It confirms the owner's privacy ruling was the right one.** "RM3 at Azmi bin Bakar" repeated
    daily locates a named individual's stall next to a campus. Merchant names must never reach a
    sponsor.

⚠ **TRAP 3 — EXPECT "NOT YET SORTED" TO DOMINATE AT FIRST.** Of the six sampled merchants, two are
recognisable chains and four are not. Real amounts are small (RM2–RM12), so this is daily food from
independent traders. **Curate the map from the ACTUAL distinct merchant list before the card goes
live**, or the donut ships as one enormous grey slice — technically honest and useless to a sponsor.

---

## 0b. ⚠ MEASURED ON THE WHOLE CORPUS, 2026-09-10 — read this before designing the sorter

The owner downloaded all eight reports (`Downloads/spending/`, XLSX exports of the Sheets). Analysed
read-only in the scratchpad; **the raw files hold student names and wallet ids and must never enter
the repo.** 1,554 raw rows → **1,368 unique** → **1,366 `SPEND`**, **RM10,650.22** over 5 Jul–30 Aug.

⚠⚠ **CORRECTED 2026-09-10 — AN EARLIER DRAFT OF THIS LINE SAID RM10,029.03, AND IT WAS WRONG BY
RM621 (5.8%) IN EXACTLY THE WAY THIS DOCUMENT WARNS ABOUT.** The first probe summed only the values
openpyxl already handed back as numbers, so the **88 rows whose amount is the STRING `"RM26.90"`**
were silently skipped — the same defect flagged two paragraphs below as *"handle both or 88 real
payments vanish"*. Writing the warning is not the same as obeying it. The true figures, with every
amount parsed as a `Decimal`: **1,366 SPEND rows = RM10,650.22**; all 1,368 rows = RM10,662.72 (the
two `RECEIVED` rows are RM12.50). **A sum that silently skips what it cannot parse reports a smaller
number that looks entirely plausible** — count the skips and print them, or the total is a guess.

**⚠ THE HEADER LAYOUT CHANGED TWICE IN EIGHT WEEKS. THREE VARIANTS EXIST:**

    A  transaction_date, wallet_id, BrightPath name, transaction_id, Sender, Receiver, …
    B  transaction_date, wallet_id, transaction_id, Wallet User, Child User, Receiver, …
    C  transaction_date, wallet_id, transaction_id, Wallet User, Child User, Merchant Name, …

The merchant column is **`Receiver` OR `Merchant Name`**; the student column is **`BrightPath name`
OR `Wallet User`+`Child User`**. `Sender` existed then vanished. **Resolve every column by trying a
list of known names, and fail loudly on an unknown header** — a positional parser would already have
broken twice, and a parser written to any single variant breaks on the archive.

**⚠ `amount` IS SOMETIMES A NUMBER AND SOMETIMES THE STRING `"RM26.90"`** — 1,280 numeric, 88 string,
*within the same corpus*. Handle both or 88 real payments vanish.

**⚠ 186 TRANSACTION IDS APPEAR IN MORE THAN ONE FILE — AND THE PATTERN IS NOT WHAT JULY PREDICTED.**
July expected a rolling overlap on every export. The measured truth is narrower and more useful:
**exactly one pair of files overlaps** — `2026-08-02` re-includes 186 of `2026-07-26`'s 196 rows.
Six of the eight files contribute nothing but new rows:

    2026-07-05   25 rows,  25 new,   0 repeat
    2026-07-12   63 rows,  63 new,   0 repeat
    2026-07-26  196 rows, 196 new,   0 repeat
    2026-08-02  326 rows, 140 new, 186 repeat   ← the only one
    2026-08-09  377 rows, 377 new,   0 repeat
    2026-08-16  299 rows, 299 new,   0 repeat
    2026-08-23  169 rows, 169 new,   0 repeat
    2026-08-30   99 rows,  99 new,   0 repeat

So this reads as a **one-off human export slip** (a date range started a week early), not a standing
property of the feed. **The guard is still mandatory** — it happened once in eight weeks, it will
happen again, and nothing in the file announces it. Without dedup the corpus total is 14% too high.

✅ **All 186 repeated pairs are byte-identical on date, wallet, merchant and amount — ZERO disagree.**
So dedup is safe as "first copy wins"; there is no reconciliation problem to solve. ⚠ Do not read
that as a guarantee: if a future repeat ever DISAGREES, that is a corrected figure and must be
reported, never silently dropped. Count and log the disagreements.

**✅ `duitnow_type`'S FULL VOCABULARY IS NOW KNOWN — the person-QR value exists:**

    STATIC_MERCHANT_QR_CODE_DUITNOW      1152
    DYNAMIC_MERCHANT_QR_CODE_DUITNOW      214
    STATIC_CUSTOMER_QR_CODE_DUITNOW_P2P     2   ← person-to-person

⚠ **Both P2P rows are `DEBIT` / `RECEIVED`, i.e. money coming IN, not sent out.** So in two months
**no student sent money to a person.** Keep the `transfer` category — it must exist the day one does
— but expect it empty, and do not let an empty slice read as a missing feature.

**✅ THE PARENT-WALLET CASE IS REAL AND PRESENT: `Child User` is populated on 28 of 1,368 rows.**
Not the untested edge §0 assumed. A join that reads `Wallet User` as the spender is wrong on those
rows today.

**✅ THE 2026-07-19 "MISSING WEEK" IS NOT MISSING — the owner spotted it, 2026-09-10.** The 26 July
report covers **FOURTEEN days**, not seven. Coverage is unbroken:

    2026-07-05    1 Jul → 5 Jul     5d   (first report, partial)
    2026-07-12    6 Jul → 12 Jul    7d
    2026-07-26   13 Jul → 26 Jul   14d   ← holds the "missing" 19 Jul week
    2026-08-02   27 Jul → 2 Aug     7d
    2026-08-09    3 Aug → 9 Aug     7d
    2026-08-16   10 Aug → 16 Aug    7d
    2026-08-23   17 Aug → 23 Aug    7d
    2026-08-30   24 Aug → 30 Aug    7d

**1 July → 30 August with no gap and no overlap** (once the 2 Aug duplicates are removed).

⚠⚠ **THEREFORE THE FILENAME DATE IS NOT THE COVERAGE WINDOW, AND NOTHING MAY TREAT IT AS ONE.** A
missing FILE is not a missing WEEK. Derive coverage from the `transaction_date` values inside, never
from the filename or the file count — a "one file per week" reader would have reported a gap that
does not exist, and would miss a real one the day two weeks land in one file again.

**⚠ AND THERE ARE TWO DATE FORMATS, not one.** The early files carry a TIME:

    2026-07-05 / 2026-07-12    "5 Jul 2026, 15:14:59"   ← with time of day
    2026-07-26 onwards         "26 Jul 2026"            ← date only

Brief §0 says the time "is gone" — true of new reports, **false of the archive**. Parse both, and
**discard the time** rather than storing it: it is not needed, and a sponsor must never see it.

**Amounts are small: median RM5.00, p75 RM6.90, p90 RM12.50, max RM300.00.** This is daily food.

**290 distinct merchants. The top 100 cover 82% of rows** — so the map is a few hundred names, not
thousands, and it grows slowly.

**Keyword rules alone reach 59% of rows** (prototype measured over the corpus):

    local (person-name)  21.6% | food 17.4% | study 11.0% | groceries 4.9%
    transport 2.4% | online 1.9% | health 0.1% | UNPLACED 40.7%

⚠ **AND THE UNPLACED 41% IS ONE SHAPE: A GENERIC MALAYSIAN BUSINESS SUFFIX.** `BACHOK MAJU
ENTERPRISE`, `IZAN MEGA ENTERPRISE`, `EZASNY GLOBAL TRADING`, `SZA G RESOURCES`, `DVENDS TECH SDN
BHD`. `ENTERPRISE`/`TRADING`/`RESOURCES`/`SDN BHD` say *"a registered business"* and nothing about
what it sells. **Only 91 distinct names** sit in that bucket — small enough to settle in one pass.

**⚠ THEIR AVERAGE SPEND IS THE SIGNAL THE NAME WITHHOLDS.** BACHOK MAJU RM4.00 over 46 visits, IZAN
MEGA RM4.47 over 43, D ANZ RM3.76 over 29, ATLAS VENDING RM2.16. Repeated RM2–RM6 on a campus is a
food stall or a vending machine. **This is why the owner's "name AND value" instinct is right** — but
it is an INFERENCE, so it must land in a category that is honest about being one (see §4c).

**Two real co-op signals worth keeping as rules:** `KOPERASI`/`KOOP` + a campus name is the campus
shop (150 rows), and `KTMB` is the national railway (transport, median RM10.00).

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

## 4c. ✅ HOW A SHOP GETS A CATEGORY — owner ruled option B, 2026-09-10

> *"Let's go with food. And add a clarification note somewhere on assumptions we have made."*

**A four-rung ladder. Each rung only sees what the rung above could not place.**

**1 — `duitnow_type`, not the name.** `STATIC_CUSTOMER_QR_CODE_DUITNOW_P2P` → `transfer`.
⚠ **NEVER decide this from the name looking like a person** — see §0 Trap 2.

**2 — Keyword rules on the merchant name.** Free, instant, readable in a diff, and it is CODE not a
guess. Reaches **100 of 290 merchants**. The two non-obvious ones worth keeping: `KOPERASI`/`KOOP`
+ a campus name is the campus shop (`study`), and `KTMB` is the national railway (`transport`).

**3 — THE SPEND-PATTERN INFERENCE (this is option B).** For a merchant whose name says nothing —
`BACHOK MAJU ENTERPRISE`, `SYAHIR AZHAR` — read the money instead:

    a merchant with >= 3 visits AND a median <= RM8.00   →  food
    ...but ONLY the rows of that merchant at or under RM20.00

**Measured on the corpus: 62 merchants, 681 rows (49.9%), RM2,974 (27.9%).**

⚠⚠ **THE PER-ROW CEILING IS NOT TIDINESS — IT CAUGHT TWO REAL CASES.** A merchant-level verdict
would have swept every row along with it. `AL HUDHA ENTERPRISE` is RM7.20 nine times **and once
RM200**. `TEGUH ENIGMA (MATRIK 1)` is RM0.80 five times **and RM119.50 across two**. A median hides
an outlier by design. Without the ceiling, **RM320 of large one-off purchases would have been filed
as campus meals** and nobody would ever have found out. **Classify the TRANSACTION, not the shop.**

**4 — `unsorted`.** Everything left: **129 merchants, 170 rows (12.4%), RM3,088 (29.0%)**. Note it
is only 12% of ROWS but 29% of MONEY — the leftovers are the big, rare, genuinely-unknown purchases
(`GLASSEYE EYEWEAR TRADING` RM130, `IBIBO (REDBUS)` RM80.44, a RM50 temple donation, a RM99 apparel
shop). **This is the bucket Gemini works on**, and its being money-heavy is the argument for doing
so: a quarter of the picture is sitting in it.

**⚠ Gemini's job is rung 4 ONLY, and it is small.** It never sees rungs 1–3, never sees an amount it
could be swayed by, and never sees a student. It is handed a **list of merchant name strings** and
must answer with one of the ten codes or `unsorted`. Anything outside the vocabulary is discarded.
A name once answered is **stored**, so the same shop is never asked about twice — which is why the
cost falls to near zero after the first run and stays there.

**⚠ `local` IS NOT A CATEGORY.** An earlier draft proposed "Small local shops" for personal-name
traders. Option B dissolves it: `SYAHIR AZHAR` (40 × RM2.00) and `FAIZUL BIN HAT` (16 × RM4.00) are
food by rung 3. The list stays at ten.

**Every merchant carries HOW it was decided** — `rule` / `inferred` / `ai` / `owner`. Without that
column the card cannot tell a fact from an estimate, and §4d below becomes unwriteable.
**An `owner` verdict is never overwritten by any rung.**

---

## 4d. ✅ THE ASSUMPTIONS NOTE — owner asked for it, 2026-09-10

**Rung 3 is an inference and the card must say so.** A sponsor reading "Food RM3,000" is entitled to
know that part of it was deduced from the size of the payments, not read off a receipt.

**On the sponsor card**, under the donut, plain and short — not buried in a tooltip:

> **How we work this out.** Vircle tells us the shop's name and the amount. It never tells us what
> was bought. Where the shop's name says what it sells, we use that. Where it does not — and a
> student visits often for small amounts — we have counted it as food. That is our best estimate,
> not the shop's own description. Anything we cannot place is shown as **Not yet sorted**.

⚠ **THREE THINGS THAT NOTE MUST NEVER DO:** name a shop (that is the whole privacy ruling); state
the RM8/RM20/3-visit thresholds (a number in prose rots the day it is tuned — say "small amounts");
or apologise. It is a statement of method, not a disclaimer.

**In the officer view**, the fuller version: the same text plus the live thresholds, the count of
merchants at each rung, and a list of everything the AI decided this week so a wrong call can be
corrected. **Correcting one is a one-click `owner` verdict, which then outranks every rung.**

**i18n:** en/ms/ta, under `sponsorPortal.myStudents.detail.spending.*`. ms/ta will be first drafts.

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
