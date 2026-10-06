# Retrospective — SARA≠STR fix + cockpit document UX + HEIC + extraction audit

**Date:** 2026-06-11 · **Branch:** `fix/sara-not-str` (4 commits → main) · **Migration:** none

Follow-up batch after the verification-accuracy pass, driven by the owner reviewing real applicants.

## What Was Built

1. **#5b — SARA is not STR (correctness fix).** A standalone SARA (Sumbangan Asas Rahmah) document — e.g. app #63's
   Perdana Menteri "terpilih untuk terus menerima bantuan SARA" letter — was auto-passing as a current STR because
   `_str_currency` trusted an AI-inferred status word. Now the Gemini-classified `source_type` GATES the verdict: a
   positively-classified `unknown` source → `unconfirmed` whatever status was read; SARA's "Layak" removed from the STR
   approval words; the extraction prompt classifies a SARA-only letter as `unknown` without inferring approval. Blank/
   legacy `source_type` still falls through (existing approvals not retro-broken).
2. **Cockpit Documents drawer polish.** Per-doc-type tinted icons; standard labels ("STR proof" / "Mother's IC") with
   the filename muted in brackets; the label is the view-link (redundant corner "View" dropped).
3. **In-cockpit document viewer.** Click a doc → opens embedded (img / iframe) beside the verdict — standardises on
   "view, never download", fixing the inconsistent open-vs-download behaviour (browser + content-type dependent).
4. **HEIC → JPEG server-side conversion.** iPhone HEIC (no browser render, no Vision OCR) converts to JPEG on upload +
   a command for the existing files.

## What Went Well

- **Real files settled every design question.** The SARA letter (#63), the 6 STR screens, Swetha's bills, and — for the
  extraction audit — live samples of every doc type were pulled and read, not guessed. The audit's conclusion (most
  "AI-captured" docs are actually fixed-format/standardised-issuer and many are digital PDFs with clean text layers) is
  grounded in the actual uploads.
- **The viewer + HEIC together fully resolved the "sometimes downloads" report** rather than papering over it.

## What Went Wrong

- **The SARA gap was a latent consequence of trusting an AI-inferred field in a deterministic rule.** Symptom: a SARA
  letter read "current STR". Root cause: `_str_currency` is deterministic and correct, but its *input* (`status`) was a
  Gemini inference of non-STR wording. The fix made the *classification bucket* the gate. **System lesson (logged):**
  when a deterministic verdict consumes an AI-extracted field, the field's *provenance/type* must be gated too, not just
  its value — which is exactly what the next sprint (deterministic label-anchored capture) addresses structurally.

## Design Decisions

See `docs/decisions.md`: SARA≠STR (source_type gates the STR verdict). The in-cockpit viewer ("view, never download")
and server-side HEIC conversion are straightforward UX/robustness choices.

## Audit finding → next sprint

A full document capture/verification audit (two read-only explorers + real-file sampling) found that **only the IC and
SPM results-slip are captured deterministically; STR, EPF, offer, BC, salary, utilities rely on Gemini for the field
read** with a deterministic *verdict* on top. But the owner's hypothesis — confirmed against real files — is that the
standardised-issuer docs (TNB elec, KWSP EPF, JPN birth cert, government offers, the MySTR STR pages) are **fixed-format
and label-anchorable**, and many are **digital PDFs with clean text layers** (already extracted, then needlessly handed
to Gemini). **Next sprint:** a shared `parse_by_labels` deterministic capture layer (text-layer/OCR → fixed labels),
Gemini fallback for the unstandardised tail — ranked STR → TNB → KWSP → JPN BC → govt-offer identity. This also kills the
SARA inference deterministically and catches mis-slotted uploads for free.

## Numbers

- 1015 scholarship + 1063 courses/reports pytest · 290 jest · i18n parity 2486×3 · `next build` clean · no migration.
- New dependency: `pillow-heif` (self-contained manylinux wheel).

## Post-deploy follow-ups (this batch)

- Re-classify app #63's STR record (its extraction predates `source_type` — `source_type='unknown'` so it reads
  `unconfirmed`).
- Run `python manage.py convert_heic_documents --apply` for the existing HEIC files.
- Watch the first Cloud Build for the `pillow-heif` install (new dependency).
