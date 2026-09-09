# Reporting student spending to sponsors — the brief

Written 2026-09-09, immediately before a context compaction, from a screenshot the next session will
not have. **Nothing has been built or investigated beyond what is written here.** This is a starting
point, not a plan — the plan needs `implementation-planning.md` after the owner answers §4.

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
- **⚠ THE FOLDER NAMING IN SETTINGS DOES NOT MATCH THE SCREENSHOT.** `base.py` has
  `VIRCLE_PAYMENTS_FOLDER = '01 BrightPath/03 Vircle/01 Payment'` and
  `VIRCLE_GUIDE_FOLDER = '03 Vircle/05 Student Guide'`; the screenshot's breadcrumb says
  **"03 Payments, Vircle"**. Either the tree was renamed or these are different roots. **Resolve by
  the folder ID, not by a path string**, and check whether the existing two settings still point at
  anything real — a silently-wrong folder path is how the guide fetch would fall back to its bundled
  copy without saying so.
- The service account and its Drive scope are live and proven (payments CSV filing, guide fetch,
  relay sheet). **Whether it can see THIS folder is untested** — that is task zero.

---

## 4. ⚠ THE OWNER MUST RULE ON THIS BEFORE ANY CODE — it is not an engineering choice

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
