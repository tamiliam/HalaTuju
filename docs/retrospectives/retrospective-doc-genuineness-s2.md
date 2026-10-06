# Retrospective — Document genuineness: supporting docs + wrong-type (verification-assurance Sprint 2, 2026-06-12)

Sprint 2 of the verification-assurance roadmap. Extends the IC fingerprint (Sprint 1) to the
standardised supporting documents + adds wrong-document-type detection. BE + FE + i18n, **no
migration**, flag-gated (the flag is already ON from Sprint 1). Shipped to `main` (`4922003`).

## What Was Built
- **`vision.doc_genuineness(data, content_type, doc_type)`** — a per-type multimodal "does this
  look like a genuine official document?" read for STR / results slip / birth cert / EPF, with a
  per-type config: STR allows a genuine MySTR app screenshot; the others expect a real scan/photo.
  → `{status, doc_seen, reason}` in `vision_fields['authenticity']` (reuses the Sprint 1 shape).
  Folded into the AI read these docs already get; returns `{}` on an AI outage.
- **Verdict caps** (`verdict_engine._apply_genuineness_caps`, applied in `build_verdict`): a suspect/
  wrong-type results-slip lowers **Academic** from verified→review; STR/EPF/BC lower **Income**. A
  soft post-cap — never moves a fact to gap/fail, never upgrades, only bites when the check ran.
- **Officer flag** `document_not_genuine` (names the doc + what the AI thinks it actually is).
- **Serializer** `authenticity` extended to the supporting docs; **student amber note** on the
  supporting-doc cards (shared `GenuinenessNote`). Closed a Sprint 1 i18n gap: the `ic_low_confidence`
  verdict-item had no `admin.scholarship.verdict.item.*` copy.

## What Went Well
- **Validate-on-real-files-first paid off again — and caught two design corrections before any code:**
  (1) for STR, a MySTR app SCREENSHOT is legitimate (flagging it suspect would reject good evidence),
  so "official" is doc-type-specific; (2) the wrong-type detection is genuinely useful — it caught a
  typed-text "birth cert" AND a subtle KWSP *withdrawal* form mis-filed as a member statement.
- **Reuse compounded.** Sprint 1 built the storage shape, the serializer field, the anomaly pattern,
  the badge idiom and the flag/rollout — so Sprint 2 was mostly the engine + a uniform verdict-cap +
  one shared FE note. The "prove the pattern on one, replicate" split (IC first) worked.

## What Went Wrong
- **The roadmap's "~zero extra cost (folds into the existing AI read)" was optimistic.** Symptom: I
  expected to add a `looks_official` field to the existing extraction prompt for free. Root cause: the
  supporting docs' extraction reads OCR **text** (or is deterministic), not a multimodal **image** —
  and genuineness (is this a real document image?) needs the image. So it's actually one extra
  multimodal call per supporting doc, like the IC. Still flag-gated + bounded, but not free. Lesson:
  "fold into the existing call" only holds when the existing call already sees the same modality the
  new signal needs — check the modality, not just that a call exists.
- **A Sprint 1 gap surfaced: the `ic_low_confidence` verdict caveat had no verdict-item i18n**, so it
  would render as a raw key in the cockpit verdict detail (the anomaly i18n I added is a different
  namespace). Caught while wiring Sprint 2's verdict cap; fixed both codes. Lesson: when you add a
  code to a verdict's `unresolved`, add its `verdict.item.*` copy in the same change, not only the
  anomaly copy.

## Design Decisions
See `docs/decisions.md` — "Genuineness verdict cap is a uniform soft post-step in build_verdict (per-fact docs, never upgrade)".

## Numbers
- ~15 new tests; **1190 scholarship pytest · 303 jest · parity 2570×3 · next build clean.** No migration.
- Validation = the real-file spike (genuine vs typed vs wrong-type across all four types); the flag was
  already ON from Sprint 1, so no separate flag-flip — Sprint 2 went live on deploy.

## Deferred / Next
- **Sprint 3** (roadmap): the scorekeeper — capture the AI's per-fact suggestion when the reviewer saves
  their Pass/Fail, and compute the agreement rate (the existing 4-fact suggestion + the Decision panel +
  the parked TD-083 verdict-metrics).
- Tamil refine of the new `genuineness.note` / `document_not_genuine` / `verdict.item.*` strings.
- Salary slip + offer letter remain deliberately un-fingerprinted (too varied; name cross-checks +
  interview carry them).
