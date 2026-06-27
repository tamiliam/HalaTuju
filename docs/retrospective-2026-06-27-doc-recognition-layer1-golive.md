# Retrospective — Layer-1 document-recognition model: go-live (2026-06-27)

Branch `feature/doc-eval-harness` merged to `main` (`4cb26111`) → deployed. The owner-gated Layer-1
doc-recognition work is now LIVE (`DOC_GENUINENESS_CHECK_ENABLED` already on in prod). `MODEL_VERSION = 1.0`.

## What Was Built
The complete **deterministic document-recognition (genuineness) model** — a probabilistic SIGNATURE
scorer (auditable, identical every run; the reviewer stays the authority):
- **results_slip + certificate**, **birth_certificate** (text-only), **epf** (+ wrong-type backstop),
  **offer_letter** families (stpm / matriculation / polytechnic / pismp / **ua_offer** — one generic
  family for the 20 fixed public universities — all identity-anchor gated), and **STR** (MOF letter /
  MySTR dashboard / Semakan Status, identity gated; SALINAN + SARA correctly excluded).
- Wired live via `assess()` + `vision.run_field_extraction_for_document`; canonical `genuine / suspect /
  not_<type>` enum; **`MODEL_VERSION` stamped on every result** and persisted in `vision_fields.authenticity`.
- Riding alongside (same thread): IC-anchored offer-NRIC matching, EPF salary reverse-engineering,
  the SPM-slip 2-column bounce-to-Gemini, the hand-written salary ringgit\|sen decimal read, and the
  Asasi-at-Politeknik pathway classification.
- **Validated on the local corpus AND held-out unseen production docs for every model.**

## What Went Well
- **Held-out validation earned its keep repeatedly.** Running each model against unseen prod docs (not
  just the calibration corpus) caught gaps the corpus never showed — and at go-live the final held-out
  sweep (90 unseen docs across 5 models) had **zero false rejections** of genuine in-scope documents.
- **The signature-scorer architecture generalised cleanly** — deterministic, per-type families with an
  identity-anchor gate, now versioned so future tweaks are comparable and traceable.
- **Frequent `main` re-merges** kept a long-lived branch's conflicts small and mechanical.

## What Went Wrong
1. **A false wrong-person flag (#36) shipped into a held-out run.**
   *What:* an offer letter's NRIC, read by image-Gemini, was compared by exact-equality to the IC and a
   dropped digit read as a different person. *Why:* the design assumed the offer NRIC was as reliable as
   the OCR'd IC — it isn't (non-deterministic multimodal read). *Fix:* anchor identity on the reliably-read
   IC; treat the offer NRIC as soft with a bounded edit-distance tolerance + a regression test. Lesson
   logged: never exact-compare an OCR'd identifier.
2. **A single fragile anchor failed cropped STR Semakan screenshots (#50, #17).**
   *What:* genuine approved Semakan pages cropped above the "Semakan Status" title scored `unrecognised`.
   *Why:* the form had ONE identity anchor (the page title), which a common crop removes. *Fix:* added two
   more anchors (`Status Permohonan Semasa`, `Status Pedalaman`) — body fields that survive crop AND the
   desktop label-wrap; regression tests. Lesson: anchor on durable body fields, not just titles.
3. **Phantom visual weights dragged genuine BCs to `suspect` (3/13 unseen).**
   *What:* the BC scorer (text-only in prod) weighted the Jata Negara crest + barcode in its total —
   signals it can never credit — so genuine plain BCs lost score and zero fakes were caught. *Why:* visual
   signatures were left in a text-only-scored list. *Fix:* dropped them (kept as a comment for a future
   visual-read escalation); held-out re-run 13/13 genuine. Lesson: don't weight a signal you don't read.
4. **A mis-transcribed signature string never matched (`Sumbangan Asas Rumah`).**
   *What:* the STR Semakan carried a spec term coded verbatim that the real document spells `Rahmah`
   (SARA) — so it matched nothing and quietly capped Semakan scores. *Why:* the owner-supplied string was
   coded without validating against the actual OCR. *Fix:* corrected to `Rahmah`; lesson: validate every
   signature string against real OCR text before locking it in.

## Design Decisions (see docs/decisions.md)
Generic `ua_offer` family + anchor gate; offer identity anchored on the IC; EPF salary reverse-engineered;
STR three-form scorer; **UPU/MOHE semakan stays `suspect` (official offer letters only)**; **`MODEL_VERSION`
on every result**; BC scored text-only (visuals dropped).

## Numbers
- **1610 scholarship pytest green**; held-out: 90 unseen prod docs across 5 models, **0 false rejections**.
- `MODEL_VERSION = 1.0`. No migrations added by this work (all on prod via prior `main` merges).
- Merged `4cb26111` → `main` (fast-forward); deployed.

## Open / Next
- **a27** (corpus BC cropped above its header) scores `not_birth_certificate` — a narrow pre-existing
  header-crop edge; the 13 unseen BCs all pass. Owner to decide: leave / soften to `suspect` / log TD.
- Deferred **Layer-2** cross-doc matching (poly/PISMP pathway via `courses.pismp_taxonomy`).
- A future UPU-semakan offer form only if the owner later accepts it as sufficient proof (calibrate on >1).
