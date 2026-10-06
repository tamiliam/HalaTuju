# Retrospective — v2.17.0: Gemini doc-assist + interview gap-spotter (+ consent-gating, supporting-doc OCR)

**Date:** 2026-05-31
**Version:** 2.17.0
**Migrations:** `scholarship/0025` (supporting-doc OCR fields), `0026` (doc-assist `vision_fields`), `0027` (gap-spotter `interview_gaps`) — all additive, all applied migrate-first via Supabase MCP.

This was a long, composite post-shortlist session. The headline is the **two Gemini features** that complete the three-engine gap model, but the same session also hardened consent, added supporting-doc OCR, fixed a latent admin-email bug, and shipped a batch of /application polish.

## What Was Built

**The three-engine gap model is now complete** (deterministic anomaly rules + Vision OCR + Gemini):

1. **Consent is a properly-gated final step.** `consent_blockers(application)` returns *every* unmet precondition at once (completeness + missing docs + student-IC identity: NRIC exact-match, name not-disjoint, `ic_unreadable` vs `ic_service_down`). `ConsentView` GET returns the blocker list; POST hard-blocks `consent_not_ready`. The FE checklist disables the button until the list is empty. Reuses the IC Vision OCR fields cached at upload — no repeat OCR.

2. **Soft OCR name/address checks on supporting docs** (`scholarship/0025`). Full-text Vision read + tolerant presence check (student *or* parent/guardian name; bills also home address). Soft — never blocks. Student chip + admin badges.

3. **Doc-assist — Gemini extracts, deterministic decides, the *student* self-corrects** (`0026`, `vision_fields`). On upload of a weak-OCR supporting doc, Gemini extracts structured fields from the OCR text; the existing deterministic matchers compute a soft verdict (so the verdict can't be a hallucination); the **student** sees a specific nudge ("the name doesn't match you or your parent/guardian", "this address doesn't match your home", "this doesn't look like a salary slip") and fixes it at upload — no admin↔student round-trip. Guardrails: 8 MB/file, 40-doc/application, hourly AI throttle (skips only the billable call), cost knob `DOC_ASSIST_ONLY_WHEN_UNCERTAIN`.

4. **Interview gap-spotter (Phase B)** (`0027`, `interview_gaps`). Admin-on-demand: one Gemini call reads the typed narrative → 3–6 `{code, question, why}` gaps rendered beside the deterministic flags and capturable as interview findings (combined list keyed by `code`). New `gap_engine.py` reuses `profile_engine` helpers + the shared `vision._call_gemini_json` seam. Reviewer-gated; **no Gemini in any GET**.

Plus: internal cron endpoint (`X-Cron-Secret`) + the `ADMIN_NOTIFY_EMAIL` latent-bug fix; Vision-outage daily alert; MyKad header-phrase blocklist in `_extract_name`; guardianship letter made optional (removed a hard block); Step-4 live-refresh + un-confirm-on-incomplete; /apply W.P. state prefixes; a Step-4 polish batch.

## What Went Well

- **The "Gemini extracts, deterministic decides" split held up across both features.** Neither feature lets the model emit a verdict — the model only *extracts*; the trustworthy matchers decide. This made every test trivially mockable (`@patch` the one `_call_gemini_json` seam) and means a Gemini misread degrades to a soft nudge, never a false block.
- **One shared Gemini seam.** Both engines + the structured-JSON variant route through `vision._call_gemini_json`, so the whole AI surface is mocked by patching a single function. Zero billable calls in CI; 24 new mock tests pass in 7s.
- **Migrate-first discipline was clean.** Three additive migrations (`0025`/`0026`/`0027`) all applied via Supabase MCP *before* the push; columns + `django_migrations` rows verified each time. No deploy-time migrate surprises.
- **Two separate ship cycles, not a batch.** Doc-assist and gap-spotter shipped as independent commits with independent migrations, per the approved plan — so a problem in one wouldn't strand the other.

## What Went Wrong

1. **I designed doc-assist with the wrong trigger model and the user had to reject the plan.**
   - *Symptom:* my first plan made doc-assist admin-on-demand (run Gemini over a doc when an admin asks), mirroring the gap-spotter.
   - *Root cause:* I copied the gap-spotter's *trigger model* because the two features share the same *plumbing* (Gemini + structured JSON + a deterministic decider), without checking that they serve a different *user* at a different *moment*. Gap-spotter helps the **admin** prep an interview; doc-assist should help the **student** fix a bad upload *at upload time* — an admin-on-demand trigger would re-introduce exactly the admin↔student round-trip the feature exists to remove.
   - *Fix:* when two features share a technical pattern, explicitly state *who* acts and *when* for each before reusing the trigger. Added to lessons.md.

2. **A mid-session crash (thinking-block API error) left edits half-applied; I had to re-derive state from disk.**
   - *Symptom:* an instance crashed with the i18n edits written to disk but the `page.tsx` wiring unfinished, and a same-sprint uncommitted change surfaced only on resume.
   - *Root cause:* a very long single session with many uncommitted edits across files — no checkpoint between logically complete sub-steps, so a crash left an ambiguous on-disk state.
   - *Fix:* commit at each logically complete sub-step (the plan's "two separate ship cycles" is the right granularity) rather than accumulating a large uncommitted working set. The doc-assist→gap-spotter split already followed this; apply it within features too.

3. **Backticks in a `git commit -m` message executed as shell (`app: command not found`).**
   - *Symptom:* a cosmetic shell error during commit; the commit still succeeded.
   - *Root cause:* backticks inside a double-quoted `-m` string are command substitution in bash/PowerShell — a known repo gotcha that I hit again because the habit isn't yet automatic.
   - *Fix:* never put backticks in commit messages; this sprint's gap-spotter commit deliberately used plain quotes. (Already a known gotcha — repeating it confirms it belongs in muscle memory, not just docs.)

## Design Decisions

Logged in `docs/decisions.md`:
- **Doc-assist is automatic-on-upload + student-facing** (not admin-on-demand) — the value is student self-correction at the moment of upload.
- **A gap carries its own dynamic text; only `code` is stable** — unlike anomalies (`{code, params}` resolved from i18n), a gap's question is Gemini-written, so it ships its text and is never i18n'd; the stable `code` lets an interview finding-verdict attach.
- **Throttle the AI, never block the upload** — guardrails cap cost (size/count/hourly) by skipping the billable Gemini call, never by rejecting a student's upload; a genuine student near a deadline is never locked out.
- **Gemini extracts, deterministic matchers decide** (shared safety) — the model never emits a verdict, so a misread is a soft nudge, not a false block.

## Numbers

- **Backend:** 1340 pytest passed, 0 failures (was ~1276 pre-session; +~64 across consent-gating, supporting-doc OCR, MyKad blocklist, doc-assist (+16), gap-spotter (+8), live-refresh/un-confirm).
- **Frontend:** 163 jest passed; `next build` clean; `tsc` clean on touched pages.
- **Golden masters:** SPM 5319, STPM 2026 — unchanged.
- **i18n parity:** 1533 × en/ms/ta (Tamil first-draft for the new keys; refine queue ~12 batches).
- **Migrations:** `scholarship/0025`, `0026`, `0027` — additive, migrate-first.
- **Commits this session:** ~13 (1 per logical change), 2 of them the headline Gemini features.
- **Billable AI in CI:** 0 (every Gemini/Vision call mocked).

## Carried Forward

- **User live-verify** the two Gemini features on the Elanjelian app (app 16) — both shipped test-green but were not click-tested.
- **Phase D** (Gemini refines profile with interview findings) — next Gemini slice; consumer gated on Phase E.
- **Tamil refine** (~12 batches incl. consent + Phase B/doc-assist strings) — the consent text gates the lawyer meeting.
- **Remove the TEMP tech-support box** once testing concludes (TD-066).
