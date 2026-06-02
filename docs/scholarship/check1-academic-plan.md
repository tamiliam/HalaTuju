# Check 1 — Academic (results slip) hardening (sprint plan)

**Status:** ✅ BUILT (2026-06-03, branch `check1/academic`) — gates green
(541 scholarship pytest · 231 jest · i18n 1811 · `next build` clean). **NOT deployed
yet** (no migration; deploy = merge → `main`, user-gated). Mirrors the IC Check-1; the
second of the four facts. Part of TD-081 (residual after Identity).

> **Principle:** the student must get **good feedback on every document they upload** —
> and it must be **clinical** (like the IC's three-line read), not one vague chip.

The results slip answers *"what did they score?"* It carries Name · IC · Subjects ·
Grades · School · Exam year. We check **three** things — **Name · Subjects · Results** —
and surface the **exam year** as a soft data point (user 2026-06-03: "exam year might be
useful"). We do **not** check school.

---

## The issue list (from the user's live test)

The user uploaded *another* student's clear slip (Yeswindran's) onto Elanjelian's
application. Findings:

1. **BUG — "Entered 0 of 9 subjects." (the headline)** Gemini glued the SPM grade-**band**
   words onto the subject name — an SPM row prints the grade twice, as a word-band AND a
   letter: `MATEMATIK … CEMERLANG TINGGI … A`. So `subject` came through as
   `"MATEMATIK CEMERLANG TINGGI"`, which doesn't equal `"Matematik"` → every subject read
   as *missing*. **Fix:** `academic_engine._split_band` strips a trailing band phrase
   (`cemerlang|kepujian|lulus|gagal` + optional `tinggi|tertinggi|atas`) before matching,
   and keeps a band→letter map as a fallback when the OCR'd letter is unread. Plus a
   prompt hint telling Gemini to put only the subject name in `subject`. Read-time fix →
   **existing prod slips are corrected without re-OCR**. (Won't touch a real subject like
   "Bahasa Arab Tinggi" — no band word precedes "Tinggi".)
2. **Verbose, generic Gopal.** Replaced with **specific** advice per failure (below).
3. **No clinical 3-check.** Added `ResultsSlipChecklist` (Name/Subjects/Results + exam
   year), mirroring the IC `ICChecklist`.

## The three checks + Gopal's specific advice (source-of-truth: the slip)

| Check | Status from | Gopal on mismatch |
|-------|-------------|-------------------|
| **Name** | doc-assist candidate-name vs profile | *wrong file* — "this looks like someone else's slip; upload **your own**." (no profile link) |
| **Subjects** | every slip subject is entered (`compare_academics`) | "add the missing subject(s) on your **Profile**" → `/profile` link |
| **Results** | typed grades vs slip grades | "the slip is the official record — update the grade on your **Profile** to match it (or re-upload if blurry)" → `/profile` link |

Precedence (most important first): name → subjects → results. The user chose **slip wins →
fix profile** for grade disagreements (2026-06-03).

## Where it lives
- **Backend:** `academic_engine.py` (`_split_band`, `_BAND_TO_GRADE`, band strip in
  `read_slip`, new `student_slip_check` = the single source for the FE checklist AND the
  Gopal verdict — they can't disagree); `help_engine.py` (3 new verdict codes
  `slip_name_mismatch`/`slip_subjects_missing`/`slip_grade_mismatch` + fix hints + a
  results_slip branch in `verdict_for_document`); `serializers.py` (`academic_check`
  field, null for non-slips); `vision.py` (`_DOC_HINTS['results_slip']` prompt nudge).
- **Frontend:** `ScholarshipDocuments.tsx` (`ResultsSlipChecklist`); `DocumentHelpCoach.tsx`
  (`/profile` link for grade/subject mismatch, none for the wrong-file name mismatch);
  `documentHelp.ts` (new codes + `shouldShowCoach` on academic mismatch + `helpSignal`
  folds the 3-check so Gopal re-fires when the student edits their profile);
  `lib/api.ts` (`AcademicCheck` type); i18n `slipCheck.*` + 3 fallbacks + `editProfileResults`.
- The **officer verdict** (`verdict_engine._verdict_academic`) is fixed for free — it uses
  the same `read_slip`/`compare_academics`, so the band-strip removes the "0 of 9" there too.

## Constraints
- No migration (extraction/serializer/copy only). British English; i18n parity en/ms/ta
  (Tamil first-draft). One deploy.
- The slip also carries the **IC number** (`NO. PENGENALAN DIRI`) — a possible future
  *strengthening* of the identity check (IC is unique where names can coincide), but out
  of scope here per "we don't have to check everything."

## Carried forward
- Live billable smoke of the new prompt on a fresh slip upload (user-run).
- Check-1 for the remaining facts: **Income** (payslip/EPF/STR) and **Pathway** (offer letter).
