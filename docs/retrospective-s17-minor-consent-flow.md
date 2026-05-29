# S17 Retrospective — Minor consent flow (2026-05-29)

## What Was Built

Single push (`84462c2`) — full working model for legal review.

**Why this sprint existed:** Pre-S17, the minor branch showed the same
"I consent…" student-voice paragraph, with the only minor-specific
change being a toggle-label swap and two free-text fields (guardian
name + relationship). Lawyer review needed something defensible end
to end.

**What S17 delivered:**

1. **Re-voiced consent text** for minors (full parent-voice
   `scholarship.consent.textMinor` i18n block): *"I am the parent or
   legal guardian of the named applicant, who is under 18 years of
   age. On their behalf, I consent to… I confirm that I have legal
   authority to give this consent for the applicant."*
2. **Structured `guardian_relationship` dropdown** with 6 codes
   (father, mother, legal_guardian, grandparent, older_sibling,
   other_relative). "Other" intentionally excluded per user — if no
   fit, the right path is `legal_guardian` + letter. Backend rejects
   any non-listed value (`ConsentCreateSerializer` validator → 400).
3. **`parent_ic` document compulsory for minors** — new doc type;
   auto-Vision-OCR'd on upload (reuses S13's pipeline + matchers).
   Backend blocks consent POST with 400 `parent_ic_required` if
   missing.
4. **`guardianship_letter` document compulsory for non-parent
   guardians** — pragmatic acceptance per user: court-issued
   guardianship order OR parent's written authorisation letter (both
   accepted; lawyer can advise once the working model is in front of
   them). Backend blocks consent POST with 400
   `guardianship_letter_required` when `needs_guardianship_letter(rel)`
   is true and the doc isn't uploaded.
5. **`application_completeness` gains `guardian_docs_done`** — adult
   trivially true; minor requires `parent_ic`, and if the active
   consent's relationship is non-parent also `guardianship_letter`.
   `complete` is now 7-part.
6. **2 new anomaly rules** (extending S16's Phase A engine):
   - `parent_ic_name_mismatch` — Vision-OCR name on parent_ic vs the
     typed guardian name on the consent.
   - `parent_ic_underage` — Vision-OCR NRIC on parent_ic indicates
     the guardian is themselves a minor (cannot legally consent).
7. **`CONSENT_VERSION` bumped** `2026-draft-1 → 2026-draft-2`. Zero
   existing consents on prod, so no real users need re-attestation.
8. **Migration `scholarship/0020`** — choices-only, no DDL, applied
   directly via Supabase MCP (TD-058 workaround).
9. **Admin verify-&-accept card** — new "Parent/guardian IC (Vision
   OCR)" row when present, surfacing extracted NRIC + name + address
   + Re-run link.

## Numbers

- 17 files changed (+689 / -47).
- Backend tests: **1224 / 1224 pass** (+13 from 1211 at S16 close).
  Composition: 4 TestGuardianDocsDone (adult / minor needs IC /
  non-parent needs letter / father OK without letter); 4 new
  TestConsentApi tests (parent_ic_required, guardianship_letter_
  required, non-parent OK with letter, invalid relationship rejected)
  + 3 minor relationship test updates; 4 anomaly tests for the 2
  new rules.
- Frontend jest: **112 / 112 pass** (+2: documentsComplete minor
  signature; DOC_TYPES count bump 11 → 13).
- i18n parity: **1356 × en/ms/ta** (+20 keys).
- Next build: EXIT=0.
- 1 deploy.

## What Went Well

- **User-driven calibration round trimmed the scope cleanly.** My
  first draft taxonomy had 3 wrongly-framed rules (STR/JKM as student
  actions, when both are family-applied) — corrected in one round
  with the user before any code. Same as S16. Confirms the pattern:
  for any sprint where the *content* of the rules is the actual
  product call, ship the rule table for sign-off (markdown, numbered
  cells) before touching code. Saves the re-write.
- **The "lawyer-needs-to-see" framing was a useful design lens.**
  Bundling all 4 items into one push (rather than splitting voice +
  dropdown from IC + letter) meant the lawyer can review the whole
  flow in one sitting. The alternative — splitting into S17a small
  + S17b big — would have left them with two incomplete artefacts
  to evaluate over two visits.
- **Pragmatic acceptance (parent's letter OR court order) is the
  right call for B40 reality.** Strict "court order only" would
  exclude legitimate applicants from single-parent / separated /
  parents-working-abroad households. The user named this trade-off
  cleanly when I asked.
- **Backend enforcement + frontend warnings stack cleanly.** The
  consent POST returns specific error codes (`parent_ic_required`,
  `guardianship_letter_required`) that the FE can route from; the FE
  also pre-checks and shows warnings before the click, so the bad
  path is rare. Defence-in-depth, not just one or the other.
- **Choices-only migration via MCP is now muscle memory.** No DDL,
  no `manage.py migrate` against prod, just one INSERT into
  `django_migrations`. Same path as the S15 `0019` choices change.
- **Zero pre-existing consents made the CONSENT_VERSION bump
  free.** I checked at sprint close and confirmed; no migration of
  active consents needed, no banner for re-attestation, no edge case
  to defend. Lucky timing — but worth the 30-second check.

## What Went Wrong

1. **Documents-tab UX choice is a known soft spot.**
   - **Symptom:** the relationship dropdown (which determines whether
     `guardianship_letter` is required) lives on the *Consent* step
     (5), but the upload widget lives on the *Documents* step (4).
     A student who picks "grandparent" at consent and only then sees
     the letter requirement has to navigate back to step 4, upload,
     then return to step 5. One back-and-forth round trip.
   - **Root cause:** I considered an inline upload widget on the
     consent step but rejected it to avoid duplicating the
     SingleDocCard UI. Cleaner code, slightly worse UX.
   - **System change:** acceptable for the lawyer demo (lawyer
     reviews the legal flow, not the UI navigation friction).
     Revisit if real-use feedback shows students repeatedly hit
     this round trip. Could mitigate cheaply by showing
     `guardianship_letter` as Required (not Optional) on Documents
     for all minors, with helper text *"skip if a parent is signing"*
     — currently it's Optional which is slightly understating its
     importance for non-parent guardians.
2. **Tamil queue is now 9 batches / ~110+ strings.**
   - **Symptom:** Every sprint that touches UI adds Tamil first-
     drafts. S15 close flagged 7, S16 close flagged 8, now 9.
   - **Root cause:** unchanged — no batching gate.
   - **System change:** unchanged — I keep flagging at sprint close;
     the user will refine when they want. Today's batch is
     substantive consent text + relationship labels — worth a real
     refine pass given the lawyers are about to read it.

## Design Decisions

See `docs/decisions.md` (new entries: pragmatic letter acceptance;
view-time enforcement vs completeness-only; no "Other" in the
relationship dropdown).

## Standing items carried

- **Tamil-pending queue: 9 batches / ~110+ strings.** Particularly
  worth a refine session before lawyer review, since the consent
  text is the artefact being legally evaluated. Offer to lay
  English+Tamil side-by-side on demand.
- **TD-061**: drop 4 dead cols (`family_income`, `siblings`,
  `phone`, `siblings_studying`) under expand-contract.
- **TD-062**: orphan Storage blobs cleanup script (low priority).
- **Deferred S13 polish**: MyKad header-phrase blocklist.
- **Phase C** (admin role categories + InterviewSession model +
  capture UI) is still the recommended next big sprint. Phase B
  (Gemini gap-spotting + 3 deferred deterministic rules) lower
  priority.

## Lessons

No new cross-cutting lessons. The user-calibration-before-code
pattern from S16 applied again successfully (and is worth keeping
explicit in `lessons.md` if it isn't already).
