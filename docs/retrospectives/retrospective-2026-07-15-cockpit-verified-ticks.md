# Retrospective — Cockpit verified-value ticks (2026-07-15)

Owner ask: a small, non-obtrusive FB/X-style "verified" badge beside a field on the officer
cockpit whose value has been corroborated by an uploaded, machine-read document — Name, IC, School,
SPM Grades, Chosen Programme, Address, Parent Name, Household Income, STR, Reporting Date. Built in
three rounds (initial, #137 review, #132 fix), all display-only + additive.

## What Was Built

- **`lib/fieldVerification.ts`** (`fieldVerifications(app)`) + **`components/VerifiedTick.tsx`** — a
  pure frontend projection of the SAME document-matching the Documents drawer chips already compute
  (reuses `officerCockpit.documentFacts`), so a tick can never disagree with a chip. A field ticks
  ONLY on the engine's strongest clean-match (`verified`) state; partial/mismatch/no-doc → no tick
  (absence = "not corroborated"; the drawer's red chips still own mismatches). Ticks: Name/NRIC←IC,
  School←school-leaving cert, SPM Grades←results slip, Chosen Programme←offer pathway, Reporting
  Date←offer reporting date, Address←utility bill, Parent name←parent IC, STR←STR (approved AND
  current). Hover tooltip names the source.
- **Household income + size ticks = backend document-vs-stated reconciliation** (round 2, off #137).
  New `income_engine.household_income_reconciliation` (Σ each earner's documented income vs the
  stated figure, within ±10%/RM300 → `matches`) + `household_size_accounted` (itemised roster ==
  stated size AND no unknown-status member → `accounted`; `overcount` when roster > stated), exposed
  as `household_check` on `AdminApplicationDetailSerializer`. **Non-mutating** (owner decision): a
  mismatch shows an amber note beside the value ("Documents show RM7,875" / "Roster counts N people")
  — the reviewer reconciles; we never overwrite the student's declared value.
- **JKM field → Per capita income** (JKM is always "No") = household income ÷ size.
- **Reporting-date tick relaxed** (round 2): ticks when a genuine offer carries a reporting date
  (was wrongly gated on the rare `reporting_official` validated-summons bonus, hiding #137's tick).
- **Grades-tick fixes** (round 3, off #132): the tick renders AFTER the subject chips (a `trailing`
  slot on `<Grades>`), and only for SPM students — see What Went Wrong.

## What Went Well

- Reusing `documentFacts` meant zero new matching logic on the frontend and guaranteed the tick and
  the drawer chip agree by construction.
- Grounding each round against the real record via read-only Supabase MCP (#137 income/offer, #132
  slip) turned "is this a bug?" into a precise diagnosis before touching code.
- The FE-light vs backend split held: per-document facts stayed on the FE, the aggregate income/size
  reconciliation went to the engine (where the earner-sum + SGD/EPF normalisation already lives).

## What Went Wrong

1. **A `git commit --amend` folded two new lines into a concurrent session's tip commit.**
   *Symptom:* after committing the initial ticks, `--amend --no-edit` rewrote a different session's
   "docs" commit (which had advanced `main` between my commands), creating an ahead/behind divergence.
   *Root cause:* amended without re-checking `git log`/reflog on a repo that other sessions push to
   continuously. *Fix:* recovered via `reset --hard origin/main` (my commit was already an ancestor),
   re-committed clean; lesson added — never `--amend` on this shared repo without re-reading the log.

2. **The first household-income tick was semantically wrong** — it ticked whenever *any* amount was
   read off a payslip/EPF, ignoring whether it matched the stated household income. *Symptom:* #137
   (documented RM7,874.73 vs stated RM7,000, +12.5%) would have ticked. *Root cause:* treated
   "a document exists" as "the value is verified" for an aggregate field the FE can't actually
   reconcile. *Fix:* moved income/size to a backend reconciliation (`household_check`) that compares
   the documented total to the stated figure within tolerance; the FE ticks off `matches`.

3. **The grades tick was misattributed on STPM applicants** (#132). *Symptom:* an STPM student's
   headline STPM grades carried a tick they hadn't earned. *Root cause:* `academic_engine.
   student_slip_check`/`compare_academics` ALWAYS compare the results slip against the SPM
   `profile.grades`, never `stpm_grades`; #132 had uploaded an SPM slip that legitimately matched its
   SPM grades, and that SPM match was shown as a tick on the STPM grades (the STPM display). *Fix:*
   the grades tick now shows only for SPM students, whose displayed grades are exactly what
   `academic_check` verifies. Latent (flagged, not fixed): an STPM student who uploads an actual STPM
   slip yields a VACUOUS `results='match'` (STPM subjects skipped as untyped) that would also mislead
   the officer Documents "Results" chip/verdict — harden `student_slip_check` if it surfaces.

## Design Decisions

- **Ticks computed on the FE, reusing `documentFacts`** (not a new server-authoritative map) — see
  decisions.md. Aggregate income/size went to the backend precisely because the FE can't re-derive
  the earner-sum.
- **Non-mutating on a mismatch** — flag the documented/roster figure for the reviewer, never
  overwrite the student's declared value (the officer-is-the-authority model used everywhere else).

## Numbers

- +9 backend pytest (`test_household_check.py`) + 13 jest (`fieldVerification.test.ts`); combined
  suite recorded at sprint-close (see MEMORY.md registry). No migration.
- 4 deploys across the three rounds (r1 web-only; r2 web+api; r3 web-only) + the earlier bundled
  header-label/university-picker small change (web-only). Each round build-verified green on Cloud
  Build; local `next build` "Compiled successfully" (the type-check-worker OOM after pytest is the
  documented 8 GB-box memory issue, not code — full `tsc` clean).
