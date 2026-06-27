# Retrospective — Offer-validity submission gate + cockpit genuineness consistency

**Date:** 2026-06-27
**Branch:** `feature/doc-eval-harness` → `main`
**Commits:** `c935dad` (gate) → `1cff7f9` (doc-drawer) → `ff2af26` (#30) → `c48ffbd` (SPM year)
**Migrations:** none. **Deploys:** 4 (api+web as touched; all SUCCESS). **Flag:** rides the already-ON `DOC_GENUINENESS_CHECK_ENABLED`.

## What Was Built
1. **Offer-validity submission gate.** Owner policy: HalaTuju can only support a student on a genuine **OFFICIAL public** offer. A conditional offer, a private/IPTS offer, or a non-official notification (UM *Pemakluman Kemasukan* / UPU *Semakan Kemasukan*) is judged not-genuine by the offer-letter signature scorer and:
   - **blocks submission** for a not-yet-submitted student (`consent_blockers` → `offer_not_official`, en/ms/ta), so they can upload the official letter; and
   - is **grandfathered** for an already-submitted student — the check lives in `consent_blockers`, NOT `application_completeness`, so `revert_if_profile_incomplete` can never roll the status back; only the pathway BADGE recomputes to `review`.
   - The pathway **verdict** now gates on `pathway_engine.offer_official_status` (`review` + `offer_not_official` for a non-genuine offer). The offer **holistic image fallback was dropped** so a private/IPTS letter stays not-genuine instead of being quietly rescued.
   - The offer-line signature now requires the real header `TAWARAN KEMASUKAN` (a pemakluman that merely *mentions* "surat tawaran rasmi akan menyusul" no longer matches). `MODEL_VERSION` → `1.1`.
2. **Cockpit Documents-drawer genuineness consistency.** `get_authenticity` was excluding `offer_letter`, so the FE never received offer genuineness and the chip coloured itself from `pathway_check` alone — a non-genuine offer showed a green "Verified" pill + green "Pathway". Now the serializer exposes offer authenticity, and a non-genuine offer forces **Pathway → red** + a red **"Official"** fact → the chip rolls up to amber "Check", never green (matching the verdict tile).
3. **#30 pathway false-clash fix.** A genuine matriculation offer was flagged a MISMATCH because the offer's programme line read as the issuer wrapper "PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN" — `kementerian`/`pendidikan` clashed with the declared stream `sains`, though the college matched (both → `selangor`). Added ministry/issuer boilerplate to the non-distinguishing token set; a real wrong stream/place still clashes (guarded by tests).
4. **SPM exam year on the results-slip chip.** Already extracted (`academic_check.exam_year`); now shown as a muted data point after Results.

## What Went Well
- **Held-out re-score guided the gate, not guesswork.** Re-scoring all 65 offers with the new model up front (read-only, free Cloud Vision OCR) gave an exact who's-affected list (9/65) and separated confident `suspect` cases from low-confidence `unrecognised` false-positive risks — so the owner could decide per-case instead of trusting a blanket flag.
- **Status invariant held by construction + test.** Putting the gate in `consent_blockers` (not `application_completeness`) means a submitted student's status is structurally safe; a test pins that offer-validity is absent from `application_completeness`.
- **Owner caught the UI desync I missed.** The verdict tile was correct on ship; the owner spotted that the drawer chip still showed green — a real two-surface inconsistency, fixed same session.

## What Went Wrong
1. **The doc-drawer chip silently contradicted the verdict tile.**
   - *Symptom:* a non-genuine offer (#31) showed a green "Verified" pill + green "Pathway" in the Documents drawer while the verdict tile correctly said "not official".
   - *Root cause:* I wired the new genuineness signal into the verdict path but not into the *display* path — and the serializer's `get_authenticity` had an explicit doc-type allow-list that omitted `offer_letter`, so the FE chip could never see it and fell back to the lenient `pathway_check`.
   - *Fix / prevention:* added the lesson "when a verdict gains a new signal, every surface that shows the doc must consume the SAME signal; a serializer allow-list is a silent desync point — grep every consumer + the per-type gates." Added 3 jest cases pinning the offer chip's colour to genuineness.
2. **The pathway matcher false-clashed on ministry boilerplate (#30).**
   - *Symptom:* a genuine matriculation offer at the declared college was flagged a pathway mismatch.
   - *Root cause:* the lenient token matcher's stoplist covered institution-type words but not ISSUER/ministry boilerplate, so "KEMENTERIAN PENDIDIKAN" in the OCR'd programme line counted as a distinguishing token and clashed with the declared stream.
   - *Fix / prevention:* added ministry/issuer words to the stoplist + a regression test; lesson logged ("a lenient matcher must drop issuer/administrative boilerplate, validated against real document wording").
3. **Build-watcher polled a mistyped SHA.** I truncated `1cff7f98` to `1cff7f8` (correct short SHA is `1cff7f9`), so the watcher found no builds and timed out. No impact (confirmed the deploy directly), but a reminder to derive the short SHA, not hand-truncate.

## Design Decisions
- **Genuineness signature is the single gate signal** (no bespoke conditional-offer text detector) — see `docs/decisions.md` "Offer-validity submission gate". A conditional/non-official offer doesn't score genuine; the only miss is an unmapped public IPTA, which is reviewer-backstopped.
- **Wrong-PUBLIC-university stays a SOFT confirm, not a hard gate** (UPU routinely re-places students; the course tree can be wrong) — deferred as **TD-145**.

## Numbers
- **Tests:** 2821 api pytest passed (was 2809; +12: gate, offer-official, #30, drawer-adjacent) + ~374 jest (+3 officerCockpit cases; jest validated in the web Cloud Build, not runnable locally — deps incomplete).
- **i18n:** `offer_not_official` (blocker + action-centre + officer copy) and `fact.official` + `examYear` added across en/ms/ta.
- **Held-out:** 9/65 offers re-score as not-official (5 `suspect`: #31/#75/#56/#43/#12; 4 low-confidence `unrecognised`: #16/#64/#84/#86 — eyeball before trusting).
- **Deploys:** 4, all SUCCESS, no migration.
