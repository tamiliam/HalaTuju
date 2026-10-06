# Retrospective — S13: Vision OCR for MyKad (v2.5.0)

**Date:** 2026-05-28
**Shipped:** web `halatuju-web-00221-qzp`, api `halatuju-api-00182-q84`. Migration `scholarship 0016` applied migrate-first via Supabase MCP (additive +4 cols on `applicant_documents`). Cloud Vision API enabled on `gen-lang-client-0871147736`; verified end-to-end with a real MyKad upload by the user.

## What Was Built

The long-queued post-launch fast-follow flagged at the S12 split. When a student uploads their **IC** at Step 4 (Documents tab), Google Cloud Vision is auto-triggered server-side; the student sees an instant chip below the file row ("looks good" / "name slightly different" / "NRIC doesn't match" / "couldn't read"). The admin sees the same signal as a row inside the verify-&-accept card with raw extracted values, two coloured pills, the declaration name for cross-check, and a **Re-run Vision** link.

**Vision is a soft hint only — never a hard block.** The admin verify-&-accept (S11a) remains the real identity gate.

- **`apps/scholarship/vision.py`** — pure matchers (`nric_match` exact, `name_match` token-set after stripping `bin`/`binti`/`a/l`/`a/p`, returns `match`/`partial`/`mismatch`) + a graceful-degradation entry point (`run_vision_for_document`) that fetches the IC from Supabase Storage, calls `document_text_detection`, extracts NRIC + name, writes 4 fields on `ApplicantDocument`. Never raises.
- **Auto-trigger** on `doc_type='ic'` in `DocumentListCreateView.post`; admin re-run via `POST .../documents/<id>/re-run-vision/`.
- **Server-computed verdicts** (`vision_nric_verdict`, `vision_name_verdict`) on the serializer so the frontend doesn't reimplement matchers (S5c lesson reapplied).
- **Frontend chip** in `ScholarshipDocuments` (4 variants from the verdicts); admin verify card gets a "Vision OCR (soft signal)" row.
- **Consent text bump** with one honest sentence disclosing automated OCR; inline privacy hint inside the IC card helper too.
- **Tests:** 13 pure-matcher + 3 IC auto-trigger (incl. failure path) + 4 admin re-run = 20 new. **No paid Vision calls during build** (fully mocked).

## What Went Well

- **Cost gate respected.** Code shipped with Cloud Vision API still disabled; the graceful fallback (`vision_error="AI service not configured"` → neutral "couldn't read" chip) meant the half-state was safe and student-flow-neutral. Enabling Vision was a separate, explicit step after user confirmation. **3 billable calls total** all sprint — 1 project-level smoke (Google sample image) + 2 IC uploads by the user (free tier covers).
- **Exit-code-check caught a TS error before push.** The new admin Vision row referenced `app.declaration_name`, which wasn't declared on `AdminScholarshipDetail`. `EXIT=1` from the local build (captured separately from grep) surfaced it; the TD-059 monitoring lesson paid off this sprint.
- **End-to-end verified with real data.** User uploaded their own MyKad (front + back); Vision read `710829-02-5709` correctly from BOTH faces (Malaysian MyKad prints the NRIC on the back too), names extracted, chip rendered the correct soft "mismatch" against the test profile's synthetic NRIC. The whole pipeline — upload → auto-trigger → SA-authenticated Vision call → verdicts → chip — worked first try after API enablement.
- **Public-sample-image smoke pattern**, before asking the user to upload real data, was a cheap project-level "is the API alive at all" check — one call against `gs://cloud-samples-data/vision/text/screen.jpg` separated the "did I enable the API correctly" question from "is the runtime SA permitted" from "does the integration work."

## What Went Wrong

1. **Forgot to add `google-cloud-vision` to `requirements.txt` in the main push.**
   - *Symptom:* the api built and deployed fine (lazy import in `vision.py` catches `ImportError`), but the runtime would silently report `"AI module not installed"` until a follow-up.
   - *Root cause:* a 3rd-party dependency wasn't on my mental checklist when scoping the file list. I treated it as "code + tests + i18n" and missed the package side.
   - *System change:* added a lesson — **when adding a new external-SDK module (Cloud Vision, Gemini, Stripe, etc.), the requirements bump is part of the same diff, not a follow-up**. Catchable by a small grep at push time: `git diff --stat | grep requirements.txt` after any new `from <vendor>` import.
   - *Cost:* one extra api build (deploy #2 for S13). Within the 2-budget but avoidable.

2. **Heuristic name-extraction picks up the MyKad headers on a back-only upload.**
   - *Symptom:* When the user uploaded only the back of the MyKad first, Vision correctly read the NRIC but `_extract_name` returned `"PENDAFTARAN NEGARA"` (the standard "National Registration" label on the card).
   - *Root cause:* `_extract_name` picks the longest all-caps non-numeric line that isn't the NRIC line — perfectly fine for the front of the card, but the back has no real name, just label text.
   - *System change:* **deferred** (user chose "close as-is"). Captured as a future tiny polish: in `_extract_name`, blocklist standard MyKad header/footer phrases — `KAD PENGENALAN`, `MALAYSIA`, `IDENTITY CARD`, `PENDAFTARAN NEGARA`, `WARGANEGARA`, `LELAKI`, `PEREMPUAN`. Returns `''` if nothing else qualifies. Until then the verdict still resolves correctly to `'mismatch'` for back-only uploads (the soft signal works), so the impact is purely cosmetic on the admin's "raw extracted name" line.

## Design Decisions

- **Ship the code with the external paid API DISABLED, then flip the switch as a separate explicit step.** Lets the code/tests/migration land safely and verifiably ahead of the cost gate — the graceful fallback path is exercised in production for free, and any teething problems surface there before any billable call. Logged in `docs/decisions.md`.
- **Use the runtime Service Account's Project Editor role for Vision API access**, rather than a separate API key in an env var. The default Cloud Run compute SA already has `roles/editor` (which covers `serviceUsageConsumer` + Vision API call permission). Simpler than managing a key, and the SA is the natural identity for inter-Google-Cloud calls.
- **Server computes the match verdicts; the frontend just renders.** The matchers (`nric_match`, `name_match`) live once in `vision.py` and the serializer exposes the verdict strings. No TS port to drift (S5c lesson).

## Numbers

- Files changed: 15 (`vision.py` [new], `migration 0016` [new], `models.py`, `views.py`, `views_admin.py`, `urls.py`, `serializers.py`, `requirements.txt`, `test_vision.py` [new], `test_documents.py`, `test_admin_scholarship.py`, `api.ts`, `admin-api.ts`, `ScholarshipDocuments.tsx`, `admin/scholarship/[id]/page.tsx`, `ScholarshipConsent` via i18n, 3 message files) + CHANGELOG + Stitch screenshot.
- Backend: **1162 pytest** (+21). Frontend: `next build` **EXIT=0** (explicit exit-code check). i18n parity **1257** (+11).
- Deploys: 2 (one feature push + one follow-up for `requirements.txt`). 1 web + 2 api builds total.
- **3 billable Vision calls** end-to-end (1 smoke + 2 IC uploads), all comfortably inside the free 1,000/month tier (~$0 spend).
- Heuristic miss noted: MyKad header text can be mistaken for a name on a back-only upload — verdict still correct, only the displayed extracted name is mis-attributed. Future tiny polish, not blocking.
