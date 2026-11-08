# Request #66 — IIUM / UIAM English offer letters read as "not an offer letter" (bug, 2026-11-08)

Executor: Opus agent. Branch `req66` (from origin/main 6c58efae). Approved analysis 158 (3.0 h, bug, no
charge), scheduled 2026-11-08. **Main is under audit: commit and push to `req66` only. Never push or
merge main, never deploy, no production writes, no paid AI calls / re-reads.**

## Verified cause (analysis 158)

- App 523 (org 11, shortlisted). Live offer doc 5105: an AI read of a 5-page text-layer PDF; stored
  authenticity `not_offer_letter`, MODEL_VERSION 1.25.0, reason "1/10 polytechnic signatures present
  (p=0.06)". The private-arm veto did NOT fire.
- `genuineness/offer_signatures.py`: `_UA_NAMES` holds IIUM only as "UNIVERSITI ISLAM ANTARABANGSA
  MALAYSIA"; every `UA_OFFER_SIGNATURES` line is Malay-only ("TAWARAN KEMASUKAN", "PEJABAT PENDAFTAR",
  "TARIKH PENDAFTARAN" …). IIUM writes in English: issuer "Academic Management and Admission Division
  (AMAD), International Islamic University Malaysia", "Offer of Admission".
- So `ua_offer` scores 0; `score_signatures` picks the polytechnic family (`results_doc.py` ~332), < 0.35 →
  `not_offer_letter` (~444); `offer_issuers.unfingerprinted_offer` keeps it (~146-157);
  `verdict_ladder.py` ~175-185 → `offer_not_official` ("a private college or university (IPTS) … can't be
  accepted").
- Rulings: docs/decisions.md ~11911 (one `ua_offer` family keyed off `_UA_NAMES` covers all 20 public
  universities), ~18568 (IIUM = UNIV-006, an IPTA), ~11975 (pathway gate), ~280-284 (subsidy test). The
  fee table (tuition RM510/semester) is a public subsidised fee.
- Live impact: 523 only.

## What to build

1. `offer_signatures.py`: recognise IIUM's English name ("INTERNATIONAL ISLAMIC UNIVERSITY MALAYSIA",
   and IIUM / UIAM if safe as whole tokens) and the standard ENGLISH UA offer wording — at least the offer
   line ("OFFER OF ADMISSION" — check it cannot match a non-offer such as an admission NOTIFICATION /
   conditional / pre-offer; mirror the Malay rules' care about "Pemakluman Kemasukan" and "surat
   tawaran"), the AMAD / admission-office line, English registration-date and programme lines. Smallest
   set that makes a genuine English IIUM letter score genuine, with justification of each weight.
2. **Never weaken the private blocks.** `offer_rulings.py` (S6 BLOCK / LIFT closed lists),
   `offer_reading.py`, `_private_arm_offer` and every reader of `_UA_NAMES` must keep refusing: IIUM's own
   fee-paying arms if any (e.g. a "Centre for Foundation Studies" is IIUM's public foundation — check
   decisions.md for how Asasi/foundation and CFS are treated; a continuing-education / professional
   arm, "Sdn Bhd", SPACE, SATU). Add tests that a private English-language letter that merely MENTIONS
   IIUM (or "International Islamic") still does not read genuine.
3. TD-145 university comparison (the offer's institution vs the catalogue's UNIV-006 "Universiti Islam
   Antarabangsa Malaysia"): make sure the English name compares as a MATCH, not "unknown"; fix if not.
4. Bump the genuineness `MODEL_VERSION` (1.26.0) with a history line; `VERDICT_ENGINE_VERSION` only if the
   verdict rules change (they should not). docs/decisions.md entry, CHANGELOG.
5. Fixtures: SYNTHETIC text only (no real student data). To learn the exact English wording you may look
   at doc 5105's stored fields read-only (Supabase pbrrlyoyyiftckqvzvvo, SELECT only; no names/ICs in
   output, files or commits). If you need the letter's actual layout, view it only in a short-lived way
   and delete any downloaded copy; never commit it.
6. After deploy (not yours): doc 5105 needs one cockpit Re-run (paid, owner's yes) — note it in the report.

## Gates

Targeted tests while building; then full API suite `-n auto`, `manage.py check`, `makemigrations --check`
(heavy runs through `python /Users/elanjelian/Python/Settings/_tools/test_queue.py -- …`, no `|` in args).
Web untouched unless a string changes (then `npm run gates`). Also run any offer-recognition eval that
runs on stored/synthetic text with NO paid calls (check `apps/scholarship/eval/`), and report its before/
after on the existing corpus if it needs no network. Commit type `fix:`.
