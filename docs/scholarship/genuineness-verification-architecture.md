# Document Genuineness & Verification Architecture

Status: **design spec** (2026-06-16). Captures the model agreed in the genuineness-signatures
work. Some of it is built (the slip/cert signature scorer, on `feature/doc-eval-harness`), some is
target. "Current state vs target" at the end says which is which.

Governing principle (unchanged from the verification-assurance roadmap): **SOFT throughout — the
reviewer is the authority.** Nothing here hard-blocks a submission except a true positive
contradiction; the threat model is casual / wrong-document / incomplete uploads, not forgers.

---

## 1. The two layers (with a dependency)

Verification of an applicant document splits into two layers, and **Layer 2 depends on Layer 1**:

- **Layer 1 — per document (self-contained).** Decided from the document alone:
  - **Issue 1 — Genuine?** Is this a real, official document of the expected type?
  - **Issue 2 — Read correctly?** Were the document's required fields (and optional ones) extracted?
- **Layer 2 — cross document (relational).** Decided by comparing documents to each other / to the
  declared data:
  - **Issue 3** — relationship link (e.g. a parent IC's name vs the father named in the student's IC).
  - **Issue 4** — STR route: the earner IC's name + IC No. vs the STR (and optional salary/EPF).
  - **Issue 5** — salary route: the earner IC's name + IC No. vs the salary slip (and optional EPF).
  - **Issue 6** — name vs the optional utility bill.

**The dependency rule:** a Layer-2 check is only meaningful when **every document it compares has
cleared Layer 1**. Matching a parent IC against an STR whose own genuineness is unknown and whose
recipient name we may have mis-read is comparing against noise. Therefore:

> If a related document is ungenuine, unreadable, or not-yet-extracted, the Layer-2 result is
> **indeterminate** (soft / "can't tell yet") — **never** a confident `mismatch`, and never a block.

A Layer-2 `mismatch` is only asserted as a real flag when it is a **positive contradiction between
two documents that have both cleared Layer 1** (e.g. the earner's *own*, genuine, cleanly-read IC
names a different person than the genuine, cleanly-read STR it is paired with).

---

## 2. Issue 1 — Genuineness: one outcome, per-doc derivation

**Unified outcome enum for every document type:**

| Outcome | Meaning | Verdict effect |
|---|---|---|
| `genuine` | a real official document of the expected type, showing its verifiable anchors | no cap |
| `suspect` | the right *kind* of document but not confidently genuine — fabricated/typed, OR **incomplete** (cropped, anchors missing), OR low-confidence | soft cap + officer flag + Gopal re-upload nudge |
| `not_<type>` | not this kind of document at all (wrong document) — `not_ic` / `not_str` / `not_results` / … | soft cap + officer flag + Gopal "upload the right document" nudge |

The **derivation differs by document** (this is expected — only the *outcome shape* is shared):

- **IC / STR / birth cert / EPF** — a holistic multimodal read returns the outcome directly
  (`genuine` / `suspect` / `not_<type>`), reporting its markers as evidence.
- **results slip / certificate** — a **probability** over a per-type SIGNATURE list decides it:
  most signatures are fixed printed strings matched **deterministically in the OCR text** (auditable,
  no AI), plus two visual signatures (QR, Jata Negara crest) from one focused multimodal read.
  Bands: **`genuine` ≥ 0.70 · `suspect` 0.35–0.70 and < 0.35 · `not_results`** when the text matches
  neither the slip nor the certificate signature list (no type fit). Calibrated on a 48-doc corpus
  (46 genuine 0.56–0.80, 1 typed fake 0.04).

(Target tidy-up: move the IC/STR/BC/EPF onto the same probability-over-markers style so all types
score identically. Not required for correctness; consistency only.)

### The verifiable-anchors standard (why cropped = `suspect`)
A document must **show its verifiable anchors** to be `genuine`. We would not accept an IC with the
face or chip cut off; the same standard applies to a slip missing its QR / serial / Director's
signature — those *are* the anchors, and without them the document cannot be verified. A cropped or
partial upload is therefore `suspect` (not a penalty — an honest "we need the complete copy"), which
triggers the Gopal re-upload nudge below. The honest student fixes it in one re-upload (the full
document then scores `genuine`); a fabrication can't satisfy it and escalates to the officer.

### `suspect` → Gopal re-upload, driven by `missing[]`
The signature scorer returns `missing[]` (which anchors are absent), so the student nudge is
**specific**, not generic:
- missing QR + signature + disclaimer → *"We can't see the QR code or the official signature at the
  bottom — please upload the **full** slip, including the lower part."*
- matches almost nothing / typed → *"This looks like a typed copy — please upload a clear photo or
  scan of the **official** document."*

---

## 3. Issue 2 — Field extraction: the per-type field contract

Each document type has a defined field set. **Required** fields must be read for Layer-2 to run on
that document; **optional** fields are corroboration. (✱ = printed on the document but **not yet
extracted** — a known gap.)

| Doc type | Required | Optional |
|---|---|---|
| **ic / parent_ic** | name, IC number | address |
| **results_slip** | candidate_name, subjects+grades (`results[]:{subject,grade,band}`) | **IC number ✱**, **Angka Giliran ✱**, exam/year, school ✱ |
| **str** | recipient_name, recipient_nric, status, year | amount, source_type |
| **salary_slip** | name, nric, gross/net income, period | employer |
| **epf** | name, nric, avg/monthly contribution, contribution_status | employer, balance, statement_date, address, year |
| **water_bill / electricity_bill** | name, address, amount | unpaid_balance, billing_period |
| **offer_letter** | candidate_name, candidate_nric, programme, institution, issuer | offer_date, intake, address |
| **birth_certificate** | child + mother + father (name + NRIC each) | bc_number |
| **guardianship_letter** | guardian_name, guardian_nric, ward_name | doc_kind |

**Highest-value extraction gap:** the results slip prints **No. Pengenalan Diri (IC number)** and
**Angka Giliran**, but we extract neither — so the slip is matched on **name only**. Capturing the
slip's IC number gives a hard identity anchor (*slip NRIC == student IC NRIC*) independent of name
OCR/spelling; the Angka Giliran is a second unique anchor. Both are already in the genuineness
signature list (we confirm they're *present*) but their *values* are unread.

---

## 4. Layer 2 — relationship & matching (issues 3–6)

Runs only on Layer-1-cleared documents (per §1). Policy:

- **Issue 3 (relationship link)** — e.g. parent IC name vs the father in the student's IC patronymic,
  or the mother via the birth certificate. This is **commonly but not 100%** true (adoption, name
  variation, OCR/romanisation). So a link *gap* is **soft** ("confirm at interview"), never a block.
- **Issues 4/5 (proof match)** — cross-check **only the earner's own IC** (the IC tagged to the
  declared earner) against that route's required proof (STR / salary), plus optional EPF. A
  **non-earner** parent's IC has no proof to match → not flagged. A *match* is strong corroboration
  and **outweighs** an issue-3 relationship gap.
- **Issue 6 (utility)** — name vs the optional utility bill; soft officer signal only.
- **The one hard signal:** the **earner's own**, genuine, cleanly-read IC whose **name *and* IC
  number both contradict** its genuine, cleanly-read proof — that is the real "the proof isn't theirs"
  case and may flag firmly. Everything else in Layer 2 is soft.

---

## 5. Current state vs target

**Built (on `feature/doc-eval-harness`, not deployed):**
- The slip/cert **signature scorer** (`genuineness/results_doc.py`) — probability + bands + `missing[]`.
- It is **wired live for `results_slip`** (replaces the holistic read there) and its `suspect` rides
  the soft cap + officer flag.
- All genuineness checks consolidated in the `genuineness/` package (`assess()` entry point).

**Target (not yet built):**
- **Unified outcome enum** `genuine`/`suspect`/`not_<type>` across *all* doc types (today: IC →
  `…/not_an_ic`; STR/BC/EPF → `…/wrong_type`; slip → `…/suspect`). Touches the cap trigger set,
  the officer-flag check, the serializer, and FE i18n — mechanical, cross-cutting, test-guarded.
- **Layer-1 gating of Layer-2** (the dependency rule in §1) — make every cross-doc match return
  *indeterminate* when a related doc hasn't cleared Layer 1.
- **Parent-IC matching fix** (TD-119, the first Layer-2 piece): issue-3 link gaps → soft;
  issues-4/5 cross-check the earner's IC only; proof-match outweighs a relationship gap.
- **Slip extraction additions:** capture the IC number + Angka Giliran (§3 gap).
- **Genuineness coverage backfill:** most existing docs were uploaded before the genuineness layer
  (e.g. only 9 of 44 corpus parent ICs have a result). Re-running genuineness on the backlog is the
  TD-116/117-class billable question — orthogonal to the matching logic.
- **`gvs.moe.gov.my/qr/<hash>` live QR verification** — a possible future *hard* genuineness check
  (the slip QR resolves to a real government record); today we only check the QR is *present*.

## 6. Implementation sequence
1. Land the **parent-IC matching fix** (TD-119) against this model — the first Layer-2 piece.
2. Normalise the **outcome enum** across all doc types (its own cross-cutting change).
3. Add the **slip IC-number / Angka Giliran** extraction (hard identity anchors).
4. Implement the **Layer-1 gating** of Layer-2 generally; extend the matching fixes to the other
   doc types (BC, EPF, STR, offer letter — the rest of the 13 corpus flags).
5. (Later, owner-gated) genuineness backfill + QR live-verification.
