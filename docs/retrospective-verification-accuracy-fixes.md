# Retrospective — Verification accuracy fixes (live-testing pass)

**Date:** 2026-06-11 · **Branch:** `fix/verification-accuracy` (5 commits → main) · **Migration:** none

## What Was Built

Five upstream gaps the owner surfaced while reviewing real applicants — investigated against the live code + prod data,
then fixed. One coherent deliverable: make the Check-1 matchers + income/STR coaching match what students actually upload.

1. **#4 — Optional wrong-person income doc no longer hard-blocks.** `services.document_red_blockers` only raises
   `income_document_mismatch` for a **compulsory** salary-route slip (a selected member); an optional/extraneous proof
   (STR route, EPF, a non-selected member) doesn't gate. Gopal's `income_proof_person_mismatch` copy is now earner-aware
   (names the STR recipient via the firewall-safe `context` seam; "optional on STR — upload nothing if she has none";
   advises removal) instead of a hardcoded "father's payslip" example.
2. **#2 — Transliteration-tolerant relationship matching.** New `vision.relationship_name_match` (fold w↔v, doubled
   letters, trailing-h + a 1-char OCR slip on longer tokens). `income_engine` aliases it for all name comparisons (every
   one is the same person across two documents); identity keeps the exact `name_match`. Strictly more lenient.
3. **#3 — Utility address tolerates a missing postcode.** `vision.address_present` falls back to a strong distinctive
   street-token overlap (+ city) when the postcode isn't in the doc; new `_address_tokens` keeps numbers, drops generic
   road words. Street threaded through the bill match + field-extraction paths.
4. **#1 — Reactive roster→income prefill.** A `useEffect` re-seeds `income_working_members` / `income_earner` from
   `earningMembers(app)` whenever the roster changes, until the student explicitly touches the selection.
5. **#5 — Approved STR is current without a year.** `_str_currency`: approval word alone → current (the MySTR status
   pages omit the year; "Semasa" = current); a year only catches a stale prior-year STR; SALINAN still unconfirmed. STR
   extraction gains a closed-set `source_type` + Tarikh-Kredit year reading. Gopal + i18n copy simplified.

## What Went Well

- **Prod data drove every fix, not synthetic samples.** Swetha's two real bills (#3), the 6 real STR screens viewed via
  signed URLs (#5 — confirmed the year is genuinely absent, not an OCR miss), and the 16-earner differential audit (#2)
  meant each change was validated against reality before any code (applying L86/L92 up front).
- **Scoping kept blast radius small.** #2 was scoped to a NEW tolerant matcher aliased into `income_engine` only, so the
  golden identity path was provably untouched — the audit only had to prove "no new false-merges", not "no regression".
- **Clean separation → 5 reviewable commits, one push, no migration.** All changes were matcher logic / Gopal copy /
  Gemini-prompt-schema-in-JSON.

## What Went Wrong

- **The #4 gate had a second hidden path I almost missed.** Symptom: my first instinct was to relax only the
  `salary_slip`/`epf` branch of `document_red_blockers`. Root cause: the `parent_ic` branch *also* rolls up a
  proof-coherence check (`proof_name_status`) that could independently block. What saved it: reading
  `_cluster_proof_identity` confirmed it uses the **STR** (not the optional slip) on the STR route, so the parent_ic
  branch doesn't false-block. Prevention (already a lesson, re-applied): when relaxing a gate, enumerate **every** code
  path that can emit the same blocker code before declaring the fix complete — don't stop at the first branch.
- **An existing test encoded the very behaviour being fixed.** `test_approved_but_no_year_is_unconfirmed` asserted the
  old over-strict #5 rule. Caught immediately (it's a direct unit test), updated to `_is_current` with a comment
  explaining the real-world reason. No system change needed beyond the discipline of reading the test the change breaks.

## Design Decisions

See `docs/decisions.md`: (1) relationship-tolerant matcher as a separate, strictly-more-lenient function aliased into
income_engine (never loosen identity); (2) accept an approved STR without a year as current (real MySTR pages omit it) —
refines, does not reverse, the SALINAN-not-proof rule; (3) don't hard-block an optional mismatched income doc.

## Numbers

- 1007 scholarship pytest (+~25) · 1063 courses/reports pytest (golden masters SPM 5319 / STPM 2026 intact)
- 282 jest (+6) · i18n parity 2474 × en/ms/ta (edits only, no new keys) · `next build` clean · no migration
- Differential audit (#2): 0 false merges across 16 distinct prod earner names
