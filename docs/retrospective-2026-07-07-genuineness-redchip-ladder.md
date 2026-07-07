# Retrospective — Genuineness score-band + red-chip ladder (2026-07-07)

**Sprint:** replace the shipped V1 genuineness ladder (which *stepped* each card's bespoke content
band) with the owner-locked EXPLICIT model. Backend only, **no migration**. `MODEL_VERSION` 1.3.0 →
1.4.0. Re-banding owner-audited + signed off before deploy.

## The model (Identity / Academic / Pathway — Income keeps its own STR-precedence model)

```
band_index = max(base_index, genuineness_step + red_chip_count),   floored at Fail
_BAND_LADDER = (verified=Certain, review=Probable, recommend=Unsure, gap=Fail)
```
- **genuineness_step** — by SCORE, uniform for every signature-scored doc (offers INCLUDED):
  genuine (p≥0.70) → 0, suspect (0.35–0.70) → 1, fake (p<0.35) → 2.
- **red_chip_count** — one −1 per RED content variable: Identity Name·NRIC; Academic Name·Subjects·
  Results; Pathway Name·IC·Pathway. RED = the value MISMATCHES (an unread/pending value is grey, not
  a chip — carried by the base band's under-claim so `max` keeps it at Probable, never Certain).
- **base_index** — the `_verdict_*` band, now carrying ONLY the missing→gap / unread→review
  under-claims; content mismatches are no longer baked in (they are chips).

Worked, owner-verified: **#12** offer p=0.30 → fake(2) + Name+IC+Pathway(3) = 5 → 🔴 Fail;
**#31** pemakluman p=0.40 → suspect(1) + Pathway(1), Name+IC green = 2 → 🟡 Unsure.

## What changed in code

1. **`genuineness/results_doc.py`** — dropped `offer_letter` from `_IDENTITY` so an offer is scored
   purely by `band_for` (like slip/BC/EPF). A recognised-issuer offer below the suspect floor now
   reads `not_offer_letter` (fake) instead of being floored at `suspect` — the #12 mechanism. STR
   keeps its anchor (the SALINAN/SARA gate). `MODEL_VERSION` 1.3.0 → 1.4.0. `vision.py` + `genuineness/
   __init__.py` offer comments updated (the `unrecognised`→`suspect` store conversion is now legacy-only).
2. **`verdict_engine.py`** — replaced `_apply_pathway_ladder` + `_step_band` + `_LADDER_CARDS` with:
   `_LADDER_DOCS`, per-card `_identity/_academic/_pathway_red_chips`, `_add_genuineness_caveat`, and a
   rewritten `_apply_genuineness_ladder` (the `max(base, step+chips)` rebuild). `_verdict_academic` no
   longer hard-gaps a name mismatch (it's a Name chip → −1). `_verdict_pathway` no longer early-returns
   on identity mismatch — it evaluates Name, IC and Pathway independently so all three chips can stack.

## The submission gate is UNCHANGED

`offer_official_status` already collapsed suspect + unrecognised → `not_genuine`; `not_offer_letter`
maps there too. So `consent_blockers`'s `offer_not_official` fires exactly as before. Only the
*verdict band* + the *award CONFIDENT_DISQUALIFIER* (`offer_not_official` now fires at step 2 = fake)
are affected. `results_slip_name_mismatch` stays a submission blocker via `application_completeness`
(a separate gate) even though the verdict softened — verified before shipping.

## Re-banding audit (whole live cohort: 96 active + 23 awarded)

- **Identity: 0 band changes** — no live IC scores suspect/fake; the one NRIC mismatch (app 94) is
  1 chip = Probable under both models.
- **Academic: 0 band changes** — no live slip has a name mismatch; slip genuineness never had an
  anchor so its step is identical.
- **Pathway on deploy: 1 change** — app **48** (an OCR name-split artefact, "LAKSMITHA A/P" →
  "LAKSMITHAA/P") Unsure → Probable. The softening working, not a regression. Zero regressions.
- **Pathway on re-run (MODEL_VERSION 1.4.0, owner-supervised per app):** 7 offers currently score
  <0.35 (64/113/109/86/93/136/52) and are candidates to drop Probable → Unsure — but their scores are
  STALE (mv 1.1–1.3.0) and several are asasi/UA offers mis-scored against the polytechnic family
  ("not one of the standard issuers", p=0.056). The old anchor was MASKING this coverage gap. Re-running
  re-scores each fresh, so a genuine UA offer may recover. Owner signed off to deploy and re-run per-app.

## Same-day correction — the missing-IC chip (owner flagged #64)

The first cut of `_pathway_red_chips` counted only a `== 'mismatch'` — but the locked spec says
"missing-required on an offer = red", and the cockpit's own `officerCockpit.factStatus` already reds
BOTH `'mismatch'` AND `'unreadable'` (an empty candidate field on an extracted offer). So a missing
candidate IC showed a RED chip on the cockpit but was NOT counted in the band — #64 (missing IC +
pathway clash + suspect) sat at Unsure when it should be Fail. Fix: `_pathway_red_chips` now counts
the offer Name/IC red on `{mismatch, unreadable}` (`_OFFER_CHIP_RED`), matching the visible chips.
Owner confirmed "full red chip, always". Re-banding of the 9 live offers with a missing candidate IC
(all stricter): 4 Certain→Probable (clean genuine offers whose NRIC OCR missed), 4 Probable→Unsure
(incl. the no-identity notice), **#64 Unsure→Fail**. 2135 pytest.

**Lesson (added):** a backend band that COUNTS "red chips" must count the SAME set the FE paints red —
here `factStatus` reds `unreadable`, not just `mismatch`. When the display and the tally are computed
in two places, pin the tally to the display's exact predicate (mismatch OR unreadable), or the tile
silently disagrees with the chips the reviewer is looking at. (This is the "reconcile every surface"
lesson biting within the same feature — verdict band vs the doc chips.)

## Lessons

- **An identity anchor that floors a score can MASK a signature-coverage gap.** Removing the offer
  anchor didn't create the 7 thin offers — it revealed that the offer signature families under-cover
  asasi/UA offers (they were scoring 0.056 against the polytechnic family and being floppy-floored to
  "suspect"). A "floor at suspect" rule hides exactly the docs the fingerprint fails on. → follow-up:
  POSITIVE asasi/UA offer fingerprints (already on the roadmap).
- **A `MODEL_VERSION`-gated re-score change lands in TWO waves, not one.** Deploy day is safe (stored
  statuses read identically); the band move only materialises on re-run. Separating "what changes on
  deploy" from "what changes on re-run" in the audit made the sign-off honest and the deploy low-risk.
- **Reconcile the gate + the verdict when softening a hard-stop.** Softening academic name-mismatch
  from Fail → Probable in the verdict is safe ONLY because the submission blocker is a separate gate
  (`application_completeness`); confirmed by grep before shipping, not assumed.

## Tests

2133 scholarship pytest green (124 verdict). Updated: `test_verdict_engine` (red-chip ladder + #12/#31
worked examples), `test_doc_signatures` (offer by-score, no anchor), `test_signature_genuineness_wiring`,
`test_award_rule` (`_add_not_genuine_offer` → `not_offer_letter`).

## Follow-ups

- Owner re-runs all offers on the cockpit (MODEL_VERSION 1.4.0 re-score) — per-app, results reviewed live.
- POSITIVE signature fingerprints for asasi/UA offers (the masked coverage gap) — roadmap item.
