# Retrospective — v2.18.0: Phase D — Gemini v2 profile refine

**Date:** 2026-05-31
**Version:** 2.18.0
**Migration:** `scholarship/0028` (additive — `SponsorProfile.final_markdown`/`final_model_used`/`finalised_at`), applied migrate-first via Supabase MCP.

Phase D is the last open piece of the post-shortlist roadmap: a **second** Gemini pass that folds the submitted interview's findings into the draft sponsor profile, producing a refined "final" (v2) profile.

## What Was Built

- **`refine_sponsor_profile(application, draft, session, language)`** + `REFINE_PROMPT` in `profile_engine.py`. Reads the existing draft + the submitted `InterviewSession` (each finding's verdict + the interviewer's free-text rationale, the 1–5 rubric, the overall note) and writes a refined profile in the target language. Same guardrail as the draft: *use only what's given; don't invent.*
- **`_render_interview()`** — renders findings/rubric/note as plain text for the prompt. Gap-coded findings get their question for context; anomaly-coded findings rely on the interviewer's own rationale (so no backend i18n resolution of anomaly codes is needed).
- **`SponsorProfile.final_markdown` / `final_model_used` / `finalised_at`** (migration `0028`) — kept separate from the draft so both stay visible.
- **`AdminFinaliseProfileView`** (reviewer-gated): 400 `no_draft` if no draft, 400 `no_interview` if no *submitted* interview, 503 on engine error. Serializer exposes the 3 new fields read-only — no Gemini in any GET.
- **Admin UI**: "Refine with interview findings (AI)" button (disabled until a submitted interview exists) + a "Final profile (v2)" indigo panel with an AI badge + finalised timestamp. `finaliseSponsorProfile()` admin-api helper + types. i18n en/ms/ta.

## What Went Well

- **The morning's "one AI mock seam" lesson paid for itself the same day.** Extracting `_call_gemini_text` (shared by the draft + refine functions) made both prose engines mock by patching a single function, mirroring the JSON engines' `vision._call_gemini_json`. 13 new tests, zero billable calls.
- **The trigger model was right the first time** — admin-on-demand + interview-gated. Unlike v2.17.0's doc-assist (where I got the trigger wrong and the user rejected the plan), here I explicitly asked "who acts, when?" up front (the lesson from that miss), and the answer — admin, after the interview — fell straight out.
- **Cheap and contained, as the roadmap predicted.** ~12 files, additive migration, reused the existing draft plumbing; no golden-master risk, no RLS change.

## What Went Wrong

1. **My first test patched the wrong seam and would have silently failed to mock Gemini.**
   - *Symptom:* I wrote the engine test as `@patch('apps.scholarship.profile_engine.genai')`, but `refine_sponsor_profile` did a *local* `from google import genai` inside the function — so the patch on the module attribute wouldn't intercept the real import, and the test would have either hit the live SDK or mis-asserted.
   - *Root cause:* the existing `generate_sponsor_profile` imported the SDK lazily inside the function and had no mockable seam (its tests only ever exercised the no-API-key path), so there was no established patch point to copy — I reached for the nearest-looking one without checking the import was local.
   - *What prevents recurrence:* I extracted `_call_gemini_text` as the single seam and patched *that* — which both fixed the test and retired the latent "no mock point" gap in the draft path. The general rule (already in `lessons.md` from this morning): a function that calls an external SDK should expose one private seam to patch; don't patch a name that a local `import` will shadow. Reinforced, not newly added.

(No deploy/runtime issues — build was green first try after the seam fix.)

## Design Decisions

Logged in `docs/decisions.md`:
- **Final profile stored separate from the draft** (`final_markdown`, not an overwrite) — draft and v2 stay independently visible; the draft's edit/publish path is untouched.
- **Refine is gated on a *submitted* interview** — the findings must be final before they feed the v2 (a draft session's findings can still change).
- **The raw prose-model call is one shared seam** (`_call_gemini_text`) used by draft + refine — the prose analogue of `vision._call_gemini_json`.

## Numbers

- **Backend:** 1351 pytest passed (+11 net; 13 new refine tests). 0 failures.
- **Frontend:** 163 jest; `next build` clean.
- **Golden masters:** SPM 5319, STPM 2026 — unchanged.
- **i18n parity:** 1540 × en/ms/ta (Tamil first-draft).
- **Migration:** `0028` additive, migrate-first.
- **Billable AI in CI:** 0.

## Carried Forward

- **TD-067** — the final profile has no edit/publish/reader path; wire it in **Phase E** (where the sponsor becomes its consumer).
- **Live-verify** — draft a profile → submit an interview → Refine → v2 panel populates; a page load without clicking fires no Gemini.
- The three post-shortlist buckets are now functionally complete; the next *new* slice is **Phase E** (sponsor portal — the reader for this artefact).
