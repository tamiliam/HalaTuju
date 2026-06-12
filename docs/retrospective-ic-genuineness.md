# Retrospective — Document genuineness: IC fingerprint (verification-assurance Sprint 1, 2026-06-12)

First sprint of the verification-assurance roadmap (`docs/scholarship/verification-assurance-roadmap.md`).
A soft genuineness fingerprint on the IC. BE + FE + i18n, **no migration**, **flag-gated dark**.
Shipped to `main` (`29d5e7e`).

## Context
The owner demonstrated that a **typed-text "IC"** (a screenshot with the right name + IC number, no card)
passed identity verification with a green "Match". The match only ever meant "the document agrees with
what you typed" (self-consistency) — there was no check that the image is a genuine card. The owner set
the standard: not certainty (OCR/AI can't forgery-proof, and the population is high-performing students,
not determined fraudsters), but **"highly probable" from a few independent fingerprint checks, shown with
evidence, and scored against human review** — robust enough that reviewers/sponsors can rely on it.

## What Was Built
- **`vision.ic_genuineness()`** — one multimodal read inventories the MyKad fingerprints (header words +
  face + chip + physical-card look) → `{status, markers, reason}` (likely_genuine / low_confidence /
  not_an_ic), stored in `vision_fields['authenticity']` (no migration). Returns `{}` on an AI outage — no
  signal, because a student must not be penalised for our failure. Flag-gated `DOC_GENUINENESS_CHECK_ENABLED`.
- **Identity prediction** (`verdict_engine._verdict_identity`): a suspect card appends `ic_low_confidence`
  and caps the verdict at `review`/Unsure — never `gap`. So the AI is honestly less certain even when the
  typed name + NRIC match. Only active when the check ran (no authenticity data → unchanged).
- **Officer pre-interview flags** `ic_low_confidence` / `parent_ic_low_confidence` (anomaly_engine, en/ms/ta).
- **Serializer `authenticity` field** + **FE honest amber note** on the IC card (Stitch-approved, brief
  copy): matched name/IC stay green; the note says the image doesn't look like a real MyKad and to re-upload.

## What Went Well
- **Evidence before code.** The fingerprints were validated on our real ICs *first* (a Gemini spike): clean
  separation — 6/6 genuine cards scored all markers; the typed fake scored only the words and was flagged.
  The roadmap rested on data, and the engine prompt is exactly the one that was validated.
- **The validation surfaced the real discriminator.** The fake *did* carry "KAD PENGENALAN" (typeable), so
  a single text marker is foolable — the **physical** markers (face/chip/card-look) did the separating. That
  empirically justified the "a few independent checks together" design and shaped the honest copy.
- **No migration + dark rollout.** Storing in the existing `vision_fields` JSON avoided a migration; the flag
  ships it dark so prod is unchanged until validated live.
- **Both audiences honest with minimal surface.** The student amber note + the officer pre-interview flag,
  PLUS the Identity tile dropping to Unsure (from the verdict cap) — so the cockpit needed no per-row badge
  change; the per-row "Match" stays accurate (it *did* match the entry) while the tile + flag carry the caveat.

## What Went Wrong
- **The honest framing had to be argued for, twice.** The first instinct (a black-box "looks_official"
  boolean, default-on, audit trail) drifted toward either over-claiming or over-ceremony. Symptom: a design
  that would have been *less* defensible to a sponsor (a system that claims to verify authenticity and then
  passes a fake is worse than one that's honest about confidence). Root cause: conflating "robust" with
  "unfoolable". Fix captured as a lesson: in an assurance feature, state the threat model + standard of proof
  up front (here: casual fakes, "highly probable", human-scored) — it determines the whole design.
- **Stitch's eventual-consistency lag cost time.** The IC-card render "timed out" (normal) then didn't surface
  in `list_screens` for ~10+ min across several polls; the owner pasting the preview node-id was the fast path.
  Already in `stitch_mcp_workflow.md` — re-confirmed: don't re-trigger; ask for the node-id.

## Design Decisions
See `docs/decisions.md`:
- "Genuineness is a soft confidence that lowers the Identity prediction — never auto-fails, never blocks".
- "Genuineness stored in vision_fields JSON (no migration); the IC's one extra Gemini call is flag-gated".

## Numbers
- 12 new tests; **1179 scholarship pytest · 303 jest · parity 2565×3 · next build clean.** 12 files, no migration.

## Live validation (flag-on, prod)
Deployed dark, then flipped `DOC_GENUINENESS_CHECK_ENABLED=1` (api rev `…00363-slj`) and ran the check
on **#16's typed-fake IC** (the owner's typed-text screenshot). All three surfaces fired correctly:
- `authenticity.status = low_confidence` — only the typed word "KAD PENGENALAN" present; face, chip,
  MyKad, WARGANEGARA, physical-card-look all **false** (exactly the fingerprint of a typed fake).
- Identity verdict capped at **`review`/Unsure** with `ic_low_confidence` (name + NRIC matched, so it
  would otherwise be `verified`) — never failed.
- Officer pre-interview flag `ic_low_confidence` fired.

**Snag worth recording (a validation-method footgun, not a product bug):** running the FULL
`run_vision_for_document` locally also re-ran Cloud Vision OCR, which has no API key locally (Vision uses
ADC on Cloud Run; only `GEMINI_API_KEY` is in the env) — so it blanked the IC's name/NRIC read and set
`ic_service_down`, which short-circuits `_verdict_identity` before the genuineness cap. The genuineness call
itself (Gemini) was fine. Restored the read + re-checked to get the clean result above. **Lesson for Sprint
2's live checks: validate the genuineness call in isolation (Gemini-only), don't re-run the whole Vision
pipeline locally where Cloud Vision can't authenticate.**

## Deferred / Next
- **Sprint 2** (roadmap): fold the fingerprint into the documents that already get an AI read — SPM results
  slip, BC, EPF, STR (+ best-effort salary slip / offer letter) — plus wrong-document-type detection (the
  IC-in-STR case). Each strong doc validated on our real files first.
- **Sprint 3**: the scorekeeper (AI per-fact suggestion vs the reviewer's Pass/Fail → measured agreement).
- Tamil refine of the new `icCheck.notGenuine` + the anomaly flag strings (first-draft).
