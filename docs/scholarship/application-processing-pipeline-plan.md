# Application Processing Pipeline — the 3 Checks (master plan)

**Status:** PLANNED — **not started** (except the quick wins, which ride the pending
cockpit-polish deploy). Written 2026-06-02 from a mapping workflow
(`map-application-check-pipeline`) + the owner's decisions. This is the **authoritative
pipeline** the other scholarship plans hang off.

> The hard machinery for all three checks already exists. What's missing is the
> **wiring and the gates** that make them a pipeline. We **extend** three systems we
> already built (Vision/Gemini OCR at upload · ResolutionItem tickets + Action Centre ·
> the S5 record-verdict AI-audit) — we do **not** rebuild.

---

## 0. The two submissions (settled — they do NOT collide)

| Submission | Stage | Timing |
|---|---|---|
| **`/apply`** (pre-shortlist intake) | shortlist decision | ~55 min reveal (shortlist) / +48h (decline) — **unchanged** |
| **`/application`** (post-shortlist Step-4: Story/Funding/Documents/Consent) | **Check 2** of this pipeline | **5-day** query window |

The 5-day window applies **after `/application` submit**, which only **shortlisted**
students reach — so queries are immediately actionable (no pre-shortlist visibility
problem, no new interim status). Check 1 runs continuously as the student uploads
documents on `/application`.

---

## 0b. The end-to-end flow (DEFINITIVE — user-specified 2026-06-02)

```
Apply → signed & submitted → Thank-you notice
  → (if shortlisted) email with /application link, ~55 min later
  → APPLICATION FORM (Step-4: Quiz / Story / Funding / Documents / Consent)
  → Consent → Thank-you notice
  → CHECK 2 (take stock of gaps)
       → if queries: email with link → QUERIES PAGE
            → (all queries answered) → Thank-you notice
  → if NO queries, OR all answered, OR 5 days lapse (whichever first)
       → Reviewer assigned
            → reviewer raises a query → email with link → QUERIES PAGE
                 → (answered) → Thank-you notice
            → Reviewer decision
```

### THE EITHER/OR RULE (a MUST — this is the design law)
The `/application` page shows the **application form** *or* the **queries page** —
**NEVER both together**. It is a **state machine**, not a stack:

| Page state | Condition | What renders |
|---|---|---|
| **Form** | not yet submitted (`profile_completed_at` is None) | the Step-4 tabs ONLY — **no** queries |
| **(transition)** | on Consent → submit | a **Thank-you notice**, then Check 2 runs |
| **Queries** | submitted AND open queries exist | the **queries page ONLY** — it **replaces** the form |
| **Waiting / done** | submitted AND no open queries | a **Thank-you / status notice** (awaiting reviewer) — not the form, not queries |

Queries reappear (queries page) if the **reviewer** raises one post-assignment, each
time with an **email + link**. The current bug — the Action Centre rendered *above*
the still-visible Step-4 form — violates this rule and must be replaced by the state
machine. **Emails** fire at: shortlist reveal (55 min), Check-2 queries-raised, and
reviewer-query-raised. **Thank-you notices** punctuate every submit/all-answered point.

---

## 1. The pipeline (target)

### CHECK 1 — at upload, per document (immediate, robust)
- **Known docs (IC):** Python/OCR matchers first (`vision.extract_mykad`,
  `name_match`/`nric_match`), Gemini only if needed. **Unknown/supporting docs:**
  OCR + Gemini (`vision.extract_text` + `extract_document_fields`).
- **Green box** on pass; **one yellow box per *distinct* issue** (a name problem and an
  address problem are two boxes, never merged).
- Any yellow → **Cikgu Gopal** advises — **only after an upload**, advice **sticks**
  (no re-popup on page load), **plain-friendly tone** (no "dear"), and always calls it
  the **"B40 Assistance Programme"** (never "HalaTuju Scholarship").
- The **name truncation** ("THEEPICAA AP" → full) is **already** resolved here as a soft
  "partial" (NRIC is the hard key) — **no work needed**; what looked like a repeat on the
  cockpit is the OLD anomaly box re-raising it (see the consolidation note).

#### CHECK 1 — IC per-item display (user-specified design, 2026-06-02) — REPLACES the single chip
The IC card must show **all three checked items as their own lines** — each with the
**extracted value** and a **status badge** — then **Cikgu Gopal** below for the "what to
do" detail. This replaces the current single yellow box (which (a) only showed the
failing item, never what *passed*, and (b) overlapped with Gopal). Layout:
```
Identity card (IC)            [Replace]
NRICF.pdf · 117 KB            [Remove]
• IC No:   710829-02-5709                          [Match | Partial | Mismatch]
• Name:    ELANJELIAN A/L VENUGOPAL                 [Match | Partial | Mismatch]
• Address: C65B JALAN SEJATI, …, 08000 …, KEDAH     [data point — NOT a blocker]
  ↳ CIKGU GOPAL — detailed advice (only when there is a real problem)
```
- **IC No** + **Name** are the real identity checks → real **Match / Partial / Mismatch**
  badges (NRIC is the hard key; Name "partial" = OCR truncation, a pass).
- **Address is a DATA POINT, not a blocker** (user, 2026-06-02): the **IC/MyKad address is
  often outdated** and there are **other address sources**. So **never show a hard red
  "Mismatch"** for it — show the extracted address for reference with a **neutral/soft**
  treatment (e.g. "ℹ from your IC — we also check other sources"). A difference must **not**
  fail the upload or read as an error.
- **Implication for Check 2 (flag):** the existing **"Check your home state"** query was
  generated from an address **state** mismatch — reconcile with "address is not a blocker":
  likely **demote it from a required query** to (at most) a soft confirm, or drop it. Decide
  when building Check 2.
- **Backend:** the serializer already exposes the extracted `vision_nric`/`vision_name`/
  `vision_address` + `vision_nric_verdict`/`vision_name_verdict`; **no address *verdict*
  needed** (address is informational, so just display the value — don't compute a pass/fail).
- **Scope:** IC + parent_ic only (3 fixed items). Supporting docs keep their own chip for now.
  Frontend-led; reuses existing fields. Part of the **UI-polish batch**.

### CHECK 2 — at `/application` submit (take stock of gaps)
- On submit, compute the four-fact gaps (`build_verdict`) and create **queries**
  (`sync_resolution_items`) on `/application` — each query is **upload-a-doc** or
  **explanation** (the existing ResolutionItem kinds, shown by the S4 Action Centre).
- **Email** the student that queries are waiting; give **~5 days** to respond.

### CHECK 3 — assignment gate → review + AI audit → close
- Assignable to a reviewer **only when** `open_queries == 0` **OR** `submitted_at + 5d`
  has lapsed (**whichever first**). On lapse with gaps still open → **proceed as-is**
  (gaps flagged for the reviewer), **not** auto-declined.
- The assigned reviewer reviews the student **and audits the AI** (records the four-fact
  pass/fail against the AI snapshot — `AdminRecordVerdictView`, the S5 build).
- **Close/accept is HARD-blocked** unless the AI audit was recorded
  (`verdict_decided_at IS NOT NULL`) — no override.

---

## 2. Gap analysis (what exists vs what's missing)

| Stage | Status | Detail |
|---|---|---|
| C1 upload OCR/Gemini + name-truncation resolve | ✅ exists | synchronous at upload; partial-name auto-resolved |
| C1 one box **per distinct issue** (IC) | 🟡 cheap | serializer already returns `vision_nric_verdict` AND `vision_name_verdict`; the UI (`visionChipVariant`) collapses to one — split it |
| C1 supporting-doc per-issue boxes | 🟠 build | Gemini emits one dominant `student_verdict` code; needs a **list of issues** (backend + FE) |
| C1 Gopal popup-on-load + advice sticks | 🟡 cheap | `DocumentHelpCoach` re-fetches on every verdict signal incl. load — gate on an upload event / cache by `vision_run_at` |
| C1 Gopal tone ("dear") | 🟡 cheap | from `HELP_PROMPT` in `help_engine.py` (fallback i18n copy is already fine — don't touch) |
| C1 programme-name bug | 🐞 1-line | `help_engine.py` `PROGRAMME_BRIEFING` says "HalaTuju runs a B40 … scholarship" → "The B40 Assistance Programme is …" |
| C2 queries surface (tickets + Action Centre) | ✅ exists | reuse `ResolutionItem` + `ActionCentre.tsx` |
| C2 generate queries **at submit** | ❌ build | today `sync_resolution_items` runs on doc upload/admin GET, not at submit — hook `build_verdict`+`sync` into the `/application` submit |
| C2 **email** student to respond | ❌ build | `send_request_info_email` is admin-only; add a batched `send_query_raised_email` (one email per sync) |
| C2 **5-day SLA** | ❌ build | add `query_response_sla_days` (default 5) on `ScholarshipCohort` + `response_deadline` on `ResolutionItem` (additive migration); surface on Action Centre; optional reminder scheduler |
| C3 reviewer **audits the AI** | ✅ exists | `AdminRecordVerdictView` + `audit.py` override metrics (S5) |
| C3 **assignment gate** | ❌ build | `AdminApplicationDetailView.patch` sets `assigned_to` with no checks — add `is_ready_for_assignment(app)` = `open_items empty OR submitted_at+SLA lapsed` |
| C3 **must-audit-before-close** | ❌ 1-line | `AdminVerifyAcceptView` add a `400 verdict_not_recorded` guard when `verdict_decided_at IS NULL` (HARD, no override) |

---

## 3. How it ships (extends, doesn't rebuild)

**A — Quick wins, ride the PENDING cockpit-polish deploy** (cheap, isolated, no migration):
1. Programme-name bug (`help_engine.py`) → "B40 Assistance Programme".
2. Gopal tone — soften `HELP_PROMPT`, hard rule "no pet names (dear/sayang)".
3. Gopal popup — fire/show only on an actual upload + persist the shown advice (FE).
4. IC **per-issue boxes** — render one box per failing verdict (serializer already
   returns both; FE-only).
5. **Must-audit-before-close** guard — the one-line `verdict_decided_at` precondition.
   *(C3's hard close-gate; cheap, lands now.)*
These fold in with the **layout fix (issue 1)** already on `fix/cockpit-polish`.

**B — Reviewer-role sprint** (`reviewer-role-scoped-access-plan.md`): add **Check 3's
assignment gate** here (`is_ready_for_assignment`, reusing `resolution.open_items` + the
cohort SLA field) — it belongs with reviewer/assignment logic.

**C — Check-2 submission sprint** (the one genuinely new piece): wire
`build_verdict`+`sync_resolution_items` into the `/application` submit; add the SLA field +
`response_deadline` + the batched query email (+ optional reminder job); surface the
deadline on the Action Centre. Reuses `ResolutionItem` + `ActionCentre`.

**Order:** do **C before finalising B's gate** — the gate depends on queries actually
being created at submit and on the cohort SLA field, or `open_items` is always empty and
the gate is a no-op.

**Old/new consolidation (the cockpit repetition):** mostly **resolved by getting the
pipeline right** — treat the **system-generated queries as the first-class Check-2
output** (not an admin-only manual action), and **suppress the OLD anomaly/pre-interview
display for anything the verdict already auto-resolved** (the name-truncation case). The
remaining display merge (retire the standalone pre-interview-flags box; one decision
surface) is tracked with the cockpit work.

---

## 4. Decisions (settled 2026-06-02)
1. **No collision** — the 5-day window is on `/application` (post-shortlist); the 55-min
   reveal is on `/apply` (pre-shortlist). Two different submissions.
2. **Lapse = proceed-as-is** — after the window (5 days for now), the case becomes
   assignable with gaps flagged for the reviewer; **not** auto-declined.
3. **Audit gate is HARD** — accept/close is blocked until the AI audit is recorded; no
   super-admin override.

## 5. Still open (decide at sprint-planning, not blocking the map)
- **Supporting-doc per-issue split** — worth the backend change now, or is the IC split
  enough for the next deploy? *(Lean: IC split now; supporting-doc split later.)*
- **Reminder emails** — single "queries raised" email for v1, or also "2 days left /
  window closed" (needs a scheduler job + migration)? *(Lean: single email v1.)*
- **Gopal persistence depth** — client-side "show once per upload" enough, or store the
  advice on the document row (small migration, survives devices/audit)? *(Lean: client
  v1.)*

## 6. Related plans
- `reviewer-role-scoped-access-plan.md` — hosts Check 3's gate + the restricted reviewer.
- `application-review-and-referee-plan.md` — the `/application` review page sits at the
  same submit moment Check 2 fires; referee is part of a complete application.
- `verification-verdict-plan.md` — the S1–S5 spine these checks extend (deployed).

---

## 7. UI-polish batch (QUEUED — build + deploy together, from live verification 2026-06-02)

Front-end-led fixes found while the owner verified the deployed cockpit. Build as ONE
batch (one deploy), separate from the bigger Check-2 state-machine sprint.

1. **Cockpit layout overflow (REAL BUG).** The two-column grid
   (`admin/scholarship/[id]/page.tsx:427` `lg:grid-cols-[1fr_340px]`) breaks for
   applicants with **long verdict-tile text** (Theresa, PAVALAHARASI, NESHA): the left
   column has **no `min-w-0`**, so long unbreakable content stops it shrinking and pushes
   the **Record-verdict panel off-screen**. Fine for short-text applicants (THEEPICAA).
   **Fix:** `min-w-0` on the left column (line 430) + the tile grid/tiles; wrap/clamp the
   tile subtitle text (`break-words` / line-clamp). Verify on Theresa + a long-pathway case.
2. **Record-verdict message colour.** Saving a partial verdict shows a **GREEN** box
   "Verdict saved. Generate a draft profile first before finalising." Green implies done,
   but the work is **incomplete** (not finalised). **Fix:** make this an **amber/yellow**
   "saved, not yet finalised" state; reserve green for a truly finalised verdict. (Partial
   saves stay allowed — only the signalling changes.) Owner's points 2 + 3.
3. **Re-run extraction for the RESULTS SLIP (enables the grade-OCR check).** The admin
   "Re-run Vision" is wired **only for `ic`/`parent_ic`** (`AdminRunVisionView._OCR_DOC_TYPES`),
   so there's **no way to re-run the grade extraction on a results slip** → the billable
   grade-OCR smoke (checklist #5) can't be done from the UI. **Fix:** add a results-slip
   re-extraction action (re-run `run_field_extraction_for_document` / the doc-assist grade
   read) with its own admin button. Small backend + a button.
4. **IC per-item display** (already specced in §"CHECK 1 — IC per-item display"): IC No /
   Name / Address as 3 lines with value + Match/Partial/Mismatch; **Address = soft data
   point, not a blocker**; Gopal below. Front-end-led.

**Deferred (cosmetic, owner said not now):** put the About/Academic data **above** the
Review section (owner would prefer it on top; functionality is fine, so defer).

**Separate (bigger) sprint:** the full `/application` **state machine** (form XOR queries
+ Check 2 emails + thank-you notices) per §0b — not part of this polish batch.
