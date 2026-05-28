# S13 — Vision OCR for MyKad (post-launch, soft assist)

**Status:** ✅ **DONE — shipped 2026-05-28 (v2.5.0; web `…00221-qzp`, api `…00182-q84`).** Migration `0016` applied migrate-first via Supabase MCP; Cloud Vision API enabled on `gen-lang-client-0871147736`; runtime SA had `roles/editor`. End-to-end verified with a real MyKad upload — 3 billable Vision calls total all-sprint (free tier). Retrospective: [retrospective-s13-vision-ocr.md](../retrospective-s13-vision-ocr.md). Tiny deferred polish: `_extract_name` should blocklist MyKad header phrases — verdict already correct, only the displayed raw name is misattributed on back-only uploads.

---

**Original plan below** (preserved for context).
**Sized:** one sprint, ~10–12 files, additive migration (4 columns on `ApplicantDocument`).
**Risk posture:** soft signal only — **never a hard block**. The admin verify-&-accept stays the real identity gate (S11a, lock the NRIC). Vision exists to **reduce friction**, not to replace human judgement.

---

## Goal (one paragraph)

When a student uploads their **MyKad as the `ic` document** at Step 4, automatically run Google Cloud Vision OCR on the image to read the **NRIC** and the **name on the card**. Compare against `profile.nric` and `profile.name`. Show the student an inline, friendly **"matches your details ✓"** or **"hmm, your NRIC says X — please re-check"** prompt at upload time. Surface the same result to the admin as a small **badge inside the verify-&-accept card** ("Vision ✓ NRIC match · ⚠ name partial match"). Use the MyKad-read name to upgrade the v2.3.0 typed-name **declaration signature** from a self-consistency nudge to a real MyKad-anchored check (still soft — a warning, never a block).

---

## What's IN (locked scope)

1. **Backend `vision.py` module** mirroring the `profile_engine.py` pattern — Google Cloud Vision `DOCUMENT_TEXT_DETECTION` call, NRIC + name extraction via regex/heuristics, mocked in tests, degrades gracefully to `{'error': ...}` when unavailable or quota-exhausted.
2. **Auto-trigger on IC `record-document`** — when an applicant uploads `doc_type='ic'`, the record endpoint runs Vision **synchronously**, stores the result on the new `ApplicantDocument` fields, and returns it in the response so the frontend can show feedback inline.
3. **Re-run from admin** — small "Re-run Vision" link in the admin verify card, in case the photo was bad and the student replaced it.
4. **`ApplicantDocument` gets 4 additive fields:**
   - `vision_nric` (CharField, blank) — the NRIC string Vision read off the card
   - `vision_name` (CharField, blank) — the name string Vision read
   - `vision_run_at` (DateTimeField, null) — when Vision was last called
   - `vision_error` (CharField, blank) — empty on success, short message on failure
5. **Match helpers** in `vision.py` (pure functions, fully unit-testable):
   - `nric_match(extracted, profile_nric)` — exact-only (canonicalise hyphens/spaces).
   - `name_match(extracted, profile_name)` — soft fuzzy: case-insensitive, strips `bin`/`binti`/`a/l`/`a/p`, token-set comparison. Returns one of `'match' | 'partial' | 'mismatch'`.
6. **Student-side feedback** in `ScholarshipDocuments`: after the IC card upload, render a one-line chip below the file row showing the verdict (with the "soft, please double-check" wording — never alarm).
7. **Admin-side badge** in `/admin/scholarship/[id]` verify-&-accept card: a compact row "Vision says: NRIC ✓ · Name ⚠ (partial)" with the raw extracted values visible on hover/expand, plus the **Re-run** action.
8. **Declaration upgrade:** the v2.3.0 typed-name signature now compares against `vision_name` (if present) **in addition to** the About-Me name — still soft (a warning toast that the typed name doesn't match the IC), never blocks submission. The existing `declaration_name`/`declared_at` audit record is unchanged.
9. **i18n ×3** (en/ms/ta) for the new student chip, admin badge labels, declaration-mismatch toast, and "Re-run Vision" action.
10. **Tests:** pure-function tests for `nric_match`/`name_match`; mocked-Vision tests for the auto-trigger endpoint (success, transient error, NRIC mismatch, name partial); admin-page re-run.

## What's OUT (anti-scope)

- **Vision as a hard gate.** No code path blocks submission, shortlisting, acceptance, or any state transition on a Vision result. The admin checklist is the gate.
- **Other docs.** Vision runs **only on `ic`**. Results slip / utility bills / income proof are out of scope for OCR (different formats, lower value per pixel).
- **Full identity verification (face/photo match, JPN lookup, liveness).** Not in S13.
- **Async/background processing.** Synchronous call at IC record. Avoids job-queue plumbing for a feature whose per-call latency (~1–2 s) is acceptable inside a single upload.
- **Storing the full Vision API response.** We persist the extracted strings + a short error message — not the raw blob (cost + PII).

---

## Design decisions to confirm BEFORE the build

1. **Cost cap + sign-off.** Google Cloud Vision `DOCUMENT_TEXT_DETECTION` pricing (as of last check): **first 1,000 units/month FREE**, then **$1.50 per 1,000 units** (1 unit = 1 image). For a B40 cohort of ~500 applicants × ~2 retries each ≈ 1,000 calls/month → likely **under USD $1/month** in steady state. **Ask:** OK to enable the Vision API on the existing HalaTuju GCP project (`gen-lang-client-0871147736`) under the **existing RM10 budget alert** + a hard per-day cap of e.g. 200 calls? I'll surface the price once before any real call.
2. **Privacy phrasing.** The current sponsor-share consent (`share_with_sponsors`) doesn't explicitly mention "we may run automated OCR on your MyKad to help us verify identity." Two options: **(a)** add a one-line clarifying note inline at the IC upload card ("We'll check the IC photo against your details automatically to help you spot typos — your photo is not stored at Google."); **(b)** bump the consent version with a small wording change. Option (a) is enough legally (it's a transient processing step on data already collected), but I'd lean **(a) AND** a sentence added to the existing consent text for honesty.
3. **Name-match strictness.** MyKad names often carry `bin`/`binti`/`a/l`/`a/p`/`@`-aliases that the profile name might not. I propose **token-set comparison after stripping those tokens, case- and space-normalised** — returns one of `match`/`partial`/`mismatch`. Partial = "every token in the profile name appears in the IC name, or vice versa, after normalisation." Mismatch = anything else. Want me to start there and adjust on real data?
4. **Failure mode UX.** If Vision returns garbage/error (bad photo, network), what does the student see? My proposal: a neutral "We couldn't read the photo automatically — that's fine, the team will check it manually." No alarm, no block.

---

## Backend plan

- **New module** `halatuju_api/apps/scholarship/vision.py`:
  - `extract_mykad(image_bytes_or_storage_path)` → `{'nric': str, 'name': str, 'model_used': 'cloud-vision', 'error': None}`
  - Pure helpers: `nric_match(a, b) -> bool`, `name_match(a, b) -> 'match'|'partial'|'mismatch'`, `_canonical_nric`, `_canonical_name`.
- **Migration** `scholarship 0016_applicantdocument_vision_fields.py` — additive (`ADD COLUMN ×4` with defaults). **Migrate-first via Supabase MCP** (lesson: deploy-first for destructive; migrate-first for additive). 0 IC docs in prod today → migration trivial.
- **`views.DocumentListCreateView` POST**: after `ApplicantDocument.objects.create(...)`, if `doc_type=='ic'`, call `vision.extract_mykad` synchronously, store extracted fields + run_at + error. Returns the new fields in the response so the frontend can show feedback inline. Don't fail the request if Vision errors — store `vision_error` and continue.
- **New admin endpoint** `POST /admin/scholarship/applications/<pk>/documents/<id>/re-run-vision/` — re-runs Vision on an existing IC; PartnerAdmin only.
- **Serializer**: expose `vision_nric`, `vision_name`, `vision_run_at`, `vision_error` (read-only) on `ApplicantDocument`.
- **Tests**: pure-function tests for the matchers; mocked-Vision tests for record-document auto-run; admin re-run endpoint.

## Frontend plan

- **`ScholarshipDocuments`**: when the IC card's existing row carries `vision_*` fields, render a chip below it — green tick + "matches your details" or amber + "we read 'X' on your IC — please double-check your NRIC". Plus the privacy one-liner (decision #2).
- **`admin/scholarship/[id]`**: inside the verify-&-accept card, a small section "Vision OCR" with two pills (NRIC ✓/⚠ · Name ✓/⚠/✕), the raw extracted strings, and a **Re-run** button.
- **Declaration step**: if `vision_name` exists, compare the typed declaration name against it too; warning toast on mismatch (still non-blocking).
- **i18n keys** ×3 for: the inline chip variants (`match`/`partial`/`mismatch`/`unavailable`), the privacy note, the admin badge labels, the re-run action, the declaration mismatch toast.
- **Types**: `api.ts ApplicantDocument` + `admin-api.ts` parallel shape — **both** (lesson from TD-059).

## Stitch first (MANDATORY)

Two prototypes before any TSX:
1. **Student inline-feedback** — the IC card with the new chip below the uploaded file row, all four states (match, partial, mismatch, "couldn't read").
2. **Admin verify-card badge** — the verify-&-accept card with the new Vision row + Re-run button.

Use `GEMINI_3_FLASH`, tight prompts (lesson: dense screens time out).

## Gates

- **Local**: backend `pytest` (full suite, serial), `next build`, **explicit exit-code check** (lesson — don't pipe to grep). i18n parity.
- **No paid Vision calls during dev/test** — Vision is fully mocked. If the orchestrator needs a real call, **ask first** (CLAUDE.md rule).
- **Migrate-first** on prod via Supabase MCP (additive ADD COLUMN ×4).
- **Deploy-once budget.** Aim for 1 push.
- **Post-deploy sanity:** admin-triggered live Vision call on one test IC upload **once you greenlight a billable run.**

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Cost overrun | Low | RM10 budget alert; per-day cap; free tier covers expected volume |
| Garbage OCR on poor photos blocks the student | Low | Non-blocking by design; neutral "we couldn't read it" message |
| Student panics at "mismatch" warning | Med | Soft wording, never red; explicit "the team will check this manually" |
| API key leak | Low | Server-side only; Cloud Run secret env var, never committed |
| MyKad image leaves Malaysia (data residency) | Med | Google Vision processes in their region; flag this in the privacy note; if it's a hard line, defer S13 |

## Sequence (single sprint)

1. **Stitch** the two screens; get visual sign-off.
2. Enable Vision API on the GCP project; generate + store the key in Cloud Run env var.
3. Migration `0016` migrate-first (additive).
4. Backend: `vision.py`, hook into record-document, admin re-run endpoint, tests.
5. Frontend: types, ScholarshipDocuments chip, admin badge, declaration upgrade, i18n.
6. Gates (local), push, verify deploys.
7. **One** real Vision call (admin-triggered, with your OK) on a test IC to confirm end-to-end.
8. Sprint-close.

---

## What you need to do before "sprint start"

- **Confirm cost path** (decision #1) — happy to proceed under the existing RM10 budget alert + a daily call cap?
- **Confirm the four design calls above** (#1 cost, #2 privacy phrasing, #3 name-match strictness, #4 failure UX).
- (Optional) data-residency check — comfortable with MyKad images going to Google Vision?

When you're ready, just say "sprint start" and we begin with the Stitch prototype.
