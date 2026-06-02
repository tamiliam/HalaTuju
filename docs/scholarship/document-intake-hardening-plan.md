# Document-Intake Hardening — Implementation Plan

**Status:** draft for approval (2026-06-02). A short, standalone sprint that slots
**before** Verification-Verdict S4 (the student Action Centre), because intake
correctness underpins the whole student-facing queue. Resolves the live bug
**TD-080** and lifts a hidden ceiling on the verdict's signal quality.

> Accept **image + PDF** for every document, OCR both reliably, and reject
> everything else. Stop sending PDFs to the wrong API; stop losing income/academic
> signal on the very documents (EPF, payslips, slips) that are usually PDFs.

---

## 1. Why now

1. **Live bug (TD-080).** A PDF/video IC returns Vision "Bad image data", which we
   mislabel as `ic_service_down` ("try again later") — a permanent dead-end at
   consent. 5 real applicants stranded.
2. **Hidden signal loss.** Our OCR (`vision.extract_text`) sends inline bytes to
   Vision `document_text_detection`, which only decodes raster images. So **any
   PDF supporting doc silently yields no text** → S2 grade extraction and
   doc-assist field extraction get nothing → Academic stuck at `grades_unverified`,
   Income evidence weakened. EPF/payslips/offer letters are *usually* PDFs, so a
   large slice of signal is being dropped today.
3. **Meets students where they are.** Scan-to-PDF apps and native PDF downloads
   (KWSP/employer/university) are normal. Forcing photo-only adds friction and
   *loses* quality for digital docs.

## 2. Strategy (the core design)

Make the two OCR entry points **content-type aware**, with a cheap, graceful path:

```
get text from a document:
  if PDF:
     text = PDF text layer (all pages)          # digital PDF → FREE, perfect fidelity
     if text is substantial: use it             # no Vision call
     else: rasterise page 1 → image bytes → Vision   # scanned PDF → 1 Vision unit
  else (image):
     image bytes → Vision                        # unchanged path
```

- **IC (`extract_mykad`)**: a MyKad is always a scan/photo (never a text PDF), so
  a PDF IC → rasterise page 1 → the **existing** Vision + NRIC/name/address
  parsers. The image path is byte-for-byte unchanged (a clear JPG IC behaves
  exactly as today).
- **Supporting docs (`extract_text`)**: text-layer-first (free) for digital PDFs;
  rasterise-fallback for scanned PDFs. Feeds S2 grade extraction + doc-assist
  unchanged downstream.
- **Format allowlist**: accept `image/*` + `application/pdf` only; **reject
  everything else** (videos, etc.) at upload — backend validation + an FE `accept`
  hint. (Today there is *no* format check — that's how a `.mp4` got in. This sprint
  makes us **stricter** while accepting the formats people actually use.)
- **TD-080 fix #1 folded in**: re-map decode-type Vision errors ("Bad image data",
  "could not fetch image", read-nothing) → `ic_unreadable` ("re-upload a clearer
  photo/scan of your IC"), reserving `ic_service_down` for genuine outages
  (`detect_vision_outage` already distinguishes). This makes the Identity verdict +
  the S3 `ic_unreadable` resolution ticket fire correctly even for the residual
  truly-corrupt case.
- **Graceful degradation**: if the PDF library isn't importable, a PDF is treated
  as unreadable — i.e. today's behaviour, no regression.

## 3. Library choice (a real decision — see Open Questions)

Two paths; both server-side, no system binaries:

- **(A) PyMuPDF (`fitz`)** — one pip dep, does text-extract *and* rasterise. Simplest.
  **Licence: AGPL-3.0** (or paid commercial). For a networked service, AGPL's
  network-use clause is a consideration for an NGO.
- **(B) `pypdfium2` (Apache/BSD, PDFium) for rasterise + `pypdf` (BSD) for text** —
  two permissive deps, no copyleft. Slightly more glue.

**Recommendation: (B)** — permissive licences, no AGPL question, both are small
wheels. (A) only if AGPL is explicitly fine.

## 4. Scope (~10 files, mostly backend; no migration)

- `requirements.txt` — add the PDF lib(s) **in the same diff** as the import (lesson #78).
- `apps/scholarship/vision.py` — content-type-aware `extract_text` + `extract_mykad`;
  a small `pdf_text()` / `pdf_first_page_image()` helper (guarded import); thread
  `content_type` through `ocr_document` / `run_vision_for_document` / `_fetch_image_bytes`.
- `apps/scholarship/services.py` — `_ic_identity_blockers` error re-map (TD-080 #1).
- `apps/scholarship/serializers.py` or `views.py` — format allowlist on upload
  (`content_type` ∈ image/* ∪ application/pdf; else 400 with a clear code).
- `halatuju-web/src/components/ScholarshipDocuments.tsx` — `accept="image/*,.pdf"` +
  a one-line helper note; reject message i18n (en/ms/ta).
- Tests: `test_pdf_intake.py` — text-layer PDF (no Vision), scanned PDF (rasterise →
  Vision seam), IC PDF → parsed NRIC/name, allowlist rejection, the error re-map.
- `CHANGELOG.md`, this plan.

**No migration** — `ApplicantDocument.content_type` already exists.

## 5. Cost & safety

- **Cost neutral-to-cheaper:** digital PDFs cost **$0** (text layer, no Vision);
  scanned PDFs + images cost **1 Vision unit** (unchanged). Rasterise **page 1 only**
  to bound multi-page PDFs.
- **Mock the Vision seam** in tests (`vision._call_*` / `document_text_detection`) —
  no billable calls in CI (lesson #101). PDF text extraction is pure (tested with a
  tiny generated PDF).
- **Real-doc smoke (user-run, billable, before trusting):** validate rasterise+OCR
  against a *real* scanned-IC PDF — one of the 5 stuck students' files, or a sample
  (lessons #86, #79). Ship the code with graceful degradation first; flip/verify the
  billable rasterise path as an explicit step.
- **No regression guarantee:** the image path is unchanged; a clear JPG IC and a
  JPG slip OCR exactly as before.

## 6. Lessons applied

- **#78** — requirements bump in the same diff as the new `import`.
- **#79** — ship behind graceful degradation; verify the billable rasterise path as
  a separate real-doc step.
- **#86** — validate the rasterise+OCR heuristic on a *real* PDF before trusting,
  not just synthetic fixtures.
- **#101** — feed the existing Vision seam; mock it in CI.

## 7. How it fits the roadmap

Upstream of the verdict — **no `verdict_engine` / `resolution` change needed.** Once
OCR works on PDFs, the signals improve automatically: PDF results slip → grades read
→ Academic can verify; PDF IC → NRIC/name read → Identity verified; PDF EPF → fields
read → Income evidence stronger. Then **S4** (student Action Centre) lands on a clean
intake. TD-080 fix #1 is folded in here.

## 8. Decisions (settled 2026-06-02)

1. **PDF library / licence** — ✅ **(B) permissive: `pypdfium2` (rasterise) + `pypdf`
   (text layer)**, plus `Pillow` to encode the rasterised page. No AGPL.
2. **Multi-page scanned PDFs** — ✅ **rasterise page 1 only** (1 Vision unit; key data
   is on page 1). Digital text-layer PDFs still read all pages, free.
3. **Deploy** — ✅ **standalone deploy to `main`** (branch `fix/document-intake-pdf`
   off `main`), independent of the held verdict branch, because TD-080 is live.

## 9. Status — BUILT (branch `fix/document-intake-pdf`, 2026-06-02)
Content-type-aware `extract_text`/`extract_mykad` via a shared `_vision_document_text`
seam (text-layer-first, rasterise-fallback); `_is_pdf`/`_pdf_text_layer`/
`_pdf_first_page_png` helpers (graceful if libs absent); TD-080 re-map in
`_ic_identity_blockers` + the outage detector; upload format allowlist (`views._is_allowed_upload`)
+ FE `accept` + client pre-check + `unsupportedFormat` i18n. **No migration.** 15 new tests
(`test_pdf_intake.py`, real-PDF lib checks + seam-mocked dispatch); scholarship suite 425
green; `next build` clean; i18n parity 1663. **Deferred:** the billable real-scanned-IC-PDF
Vision smoke (user-run, before/after deploy, per lessons #86/#79).
