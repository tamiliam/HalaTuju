# S19 Retrospective — Minor consent v2 + /application UX iteration round (2026-05-29)

## What Was Built

Composite sprint after S18 ship. Six commits, one headline (minor consent v2)
plus four copy/UX iterations the user drove through live, plus a follow-up
policy change on parent_ic.

1. **Minor consent v2** (`7a9e8cb`) — typed parent NRIC field with masked
   `XXXXXX-XX-XXXX` input; structured 7-option relationship dropdown
   (father/mother/legal_guardian/grandparent/brother/sister/relative); consent
   text body interpolates `{student_name}` / `{student_nric}` / pronouns
   derived from the student's NRIC last digit (new `gender_from_nric`
   helper); **hard-gate** name+NRIC match against `parent_ic` Vision OCR
   (was a soft anomaly flag in S17 — now a 400 block); FE pre-checks live
   and disables the toggle on mismatch. Migration `scholarship/0021`
   (additive ADD COLUMN + choices-only AlterField). `CONSENT_VERSION` bump
   `2026-draft-2` → `2026-draft-3`.
2. **Layout iteration** (`abdfab5`) — simpler parent-voice body in B40
   language (two short paragraphs); student-directed info-box at top
   ("As you are under 18 years of age, please ask your parent or legal
   guardian to read the following section…"); removed redundant
   guardianNotice; moved `needParentIc` warning up; DRAFT label removed.
3. **InfoBox component** (`cf9b1d4`) — `components/InfoBox.tsx` locks the
   4-colour convention (green=success, blue=info, amber=warning,
   red=block); applied across all `/application` boxes. Adult subtitle
   dropped. Consent body renders `**bold**` markers for student name /
   NRIC / programme name via a 5-line `renderRich` helper.
4. **Box-ify all tab intros** (`d6c0505`) — every step opens with one
   instruction-led blue InfoBox where applicable (Story langNote, Funding
   intro merged from two paragraphs, Documents step4Body rewritten as
   instruction). step6Body intro on Consent removed. minorInfoNotice
   trimmed.
5. **parent_ic universal compulsory** (`35d61b3`) — admin cross-check of
   STR/EPF needs the parent's IC even for adult applicants.
   `documents_done` now requires all three; `guardian_docs_done`
   simplified.

## Numbers

- 6 commits (~1300 lines added / ~250 removed across the run).
- Backend tests: **1236 / 1236 pass** (+12 from 1224 at S17 close).
- Frontend jest: **154 / 154 pass** (documentsComplete suite rewritten
  in-place to drop the isMinor flag tests; net key count unchanged).
- i18n parity: **1369 × en/ms/ta** (12 new keys, several edits).
- 1 migration: `scholarship/0021` applied via Supabase MCP.
- 6 deploys (one per commit) — all small.

## What Went Well

- **The iteration loop with the user converged fast.** Five FE/UX
  iterations in one session (S19 main → layout → InfoBox → box-ify
  → parent_ic universal), each kicking off from a screenshot or a
  short text note. Each round shipped clean, no rework.
- **The "Pre-existing consents = 0" sanity check saved a lot of
  worry.** Before bumping `CONSENT_VERSION` `2026-draft-2` →
  `2026-draft-3` I queried prod and confirmed zero existing consents —
  bump was purely forward-looking, no real users needed to re-attest.
  Will continue running this check before every CONSENT_VERSION change.
- **InfoBox extraction was the right call.** The user named the
  convention explicitly ("if so, let's be consistent across the forms"),
  and pulling the 4 kinds into one component is now both an enforcement
  mechanism and a documentation artefact. Next sprint can drop the
  inline class strings entirely if anything else needs to consistent.
- **`parent_ic` policy change landed cleanly on real-data realisation.**
  My first reaction was "this is retroactive, 12 applications will go
  incomplete." User pushed back: "have anyone reached the application
  stage yet?" Verifying showed all 12 are pre-decision-reveal —
  forward-looking, not retroactive. I'd jumped to a wrong worry; the
  user's question prevented me from over-flagging it.

## What Went Wrong

1. **My initial framing of the "retroactive impact" of parent_ic was
   wrong** — I conflated `status='submitted'` with "at /application
   Step 4." Status `submitted` means scored-but-pre-reveal; the
   applicant sees the "received" card, not the Documents tab. Only
   `shortlisted` applicants see /application Step 4.
   - **Root cause:** I'd forgotten the status flow distinction. The
     decision-reveal at +48h flips `submitted` → `shortlisted` (or
     rejected), and only then does the Step-4 tabbed UI render.
   - **System change:** when scoping any change that touches the
     /application flow, explicitly check the status distribution by
     `status` (not just `submitted_at IS NOT NULL`) to figure out who
     actually sees the affected UI. User caught this in one question
     before I shipped a wrong narrative. Worth burning into muscle
     memory for the next change.
2. **Tamil-pending queue is now 10 batches deep** (was 9 at S17
   close, +1 minor delta for S19's added keys).
   - **Root cause:** unchanged — no batching gate; every sprint that
     touches UI strings adds Tamil first-drafts.
   - **System change:** unchanged — flag at sprint close. The user is
     about to take the consent text to lawyers; the Tamil refine
     would benefit from happening BEFORE that meeting since the consent
     text IS the legal artefact being evaluated. Will surface that
     timing point if helpful.
3. **One Next.js build failed mid-sprint** (S19 main commit, second
   pass) due to `Set<>` downlevel-iteration on this project's tsconfig
   target. Caught + fixed in the same push (used `Array.from(set).every`
   instead of `for…of set`). Cost was one extra build cycle.
   - **System change:** when writing fresh utility helpers in `.tsx`,
     prefer `Array.from(set).every` / `.some` over `for…of set` for
     iteration. Tsconfig target is downlevel for this project.

## Design Decisions

See `docs/decisions.md` (new entries: hard-gate vs soft-flag for
parent_ic identity mismatch; InfoBox component as the convention
enforcement mechanism; parent_ic as universal compulsory).

## Standing items carried

- **Tamil-pending queue: 10 batches / ~125+ strings.** Especially
  worth a refine session before the lawyer meeting — consent text is
  the legal artefact being reviewed.
- **TD-061**: drop 4 dead cols (`family_income`, `siblings`, `phone`,
  `siblings_studying`) under expand-contract.
- **TD-062**: orphan Storage blobs cleanup script (low priority).
- **Deferred S13 polish**: MyKad header-phrase blocklist.
- **Recommended next sprint**: Phase C of post-shortlist vision
  (admin role categories + InterviewSession + capture UI) — still the
  unlock for Phase D Gemini v2 refine.
- **Working model for lawyer review**: the minor consent flow is
  ready for legal sign-off. Once they advise, expect text/policy
  tweaks; the structural model (parent_ic + typed name/NRIC + hard
  gate + structured relationship) is in place.

## Lessons

See `docs/lessons.md` (new entry: check status distribution before
scoping any /application Step-4 UI change; `submitted` ≠ at-Step-4).
