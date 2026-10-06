# Retrospective — v2.20.0 "Cikgu Gopal" document-help coach (2026-05-31)

## What shipped

A warm, proactive helper ("Cikgu Gopal") on the /application **Documents** tab. When a student's
upload comes back with a soft mismatch, a soft-blue note appears beneath the existing amber/grey chip,
explaining *why* the document needs what it needs and encouraging a re-upload — in the student's
language. Proactive-only (no chat box), student-facing, never blocks.

- **Backend:** `help_engine.py` (`PROGRAMME_BRIEFING` + `VERDICT_GUIDANCE` + `_build_help_prompt` +
  `verdict_for_document` + `generate_document_help`), `DocumentHelpView`
  (`GET …/documents/<pk>/help/`, own-doc scoped, hourly per-application cache cap). Reuses
  `profile_engine._call_gemini_text`. **No migration** (reads existing verdict columns).
- **Frontend:** pure `lib/documentHelp.ts` (`shouldShowCoach`/`fallbackKeyFor`), `getDocumentHelp` in
  `api.ts`, `DocumentHelpCoach.tsx`, wired beneath every non-good chip in `ScholarshipDocuments.tsx`.
- **i18n:** `scholarship.docs.help.coachLabel` + `fallback.{7 verdicts}` × en/ms/ta (parity 1559;
  Tamil first-draft, queued for refine).
- **Tests:** +18 backend (1373→1391), +8 jest (163→171), `next build` clean. All Gemini mocked.

## Key decisions

1. **The engine is structurally firewalled, not prompt-trusted.** `generate_document_help` takes only
   `doc_type`, `verdict`, `first_name`, `target_language` — no application/profile/session object. A
   signature test asserts this. The student's own profile (name/NRIC for the verdict) is read by a
   *separate* `verdict_for_document`, never by the phrasing engine. This is a stronger guarantee than
   "the system prompt tells it not to leak."
2. **The coach only phrases; it never decides a verdict** (reuses the deterministic matchers / Vision
   OCR). Mirrors the v2.17.0 "Gemini extracts, matchers decide" decision — a misread degrades to a
   soft, correctable nudge.
3. **Hybrid AI + i18n fallback.** AI message when available; pre-written i18n copy (keyed by verdict)
   when off/throttled/errored. Guarantees a kind message even with zero Gemini, and keeps the cost on
   the free tier (fires only on mismatch, hourly-capped). Network-error (no verdict) → a `generic`
   warm note rather than guessing the wrong specific reason.
4. **Trigger model re-derived, not copied.** Like doc-assist (and unlike the admin gap-spotter), this
   is student-facing and fires at the mismatch moment — applying the v2.17.0 lesson explicitly.

## What went well

- TDD throughout: red → green on both backend files; the guardrail/firewall tests were written
  *with* the engine, not bolted on.
- Lessons paid off pre-emptively: node-env Jest (pure logic, no render), single mockable seam (0
  billable CI calls), pure prompt-builder tested directly, `build` captured to a file not piped to
  grep.
- Stitch one-screen sign-off before any TSX (mandatory rule honoured); render matched first try on
  `GEMINI_3_FLASH`.

## What went wrong / lessons

- **A parallel Claude instance was doing the v2.19.0 sprint-close on the same working tree.** This
  instance mis-read v2.19.0's uncommitted docs as "abandoned leftovers" and committed them
  (`ce4f4b6`), colliding with the other instance's close. Resolved by the other instance
  (`git reset --soft` + one consolidated commit `59910e9`). **Lesson (reinforces L37): never run two
  instances against one working tree — use `git worktree` per instance.** No code was ever at risk
  (the feature was already committed); only the paperwork collided.
- **Missed a 5th `SingleDocCard` call site** (the minor-only guardianship card) when threading the new
  `token`/`lang` props — `next build` caught it (the node-env type-check is the safety net, exactly as
  the NRIC-gate lesson predicts). One extra build cycle.
- **Inline `python -c` mangled long Tamil** (a stray `\u0index` from corrupted text). Switched to a
  throwaway script file (deleted after) with `PYTHONIOENCODING=utf-8` — the L99 hygiene rule. Wrote
  JSON back with `newline='\r\n'` to preserve CRLF so the i18n diff was +12/−1 per file, not a full
  reformat.

## Deferred / follow-ups

- **Tamil copy is first-draft** — append to the existing Tamil refine queue (follow `tamil-style-guide.md`).
- **Live click-through verify** still pending on the real test account (Elanjelian / app 16): upload a
  mismatching doc, confirm the coach appears and reads warmly, try to trick it ("write my story",
  "what's my score?") and confirm it deflects, and confirm a green upload stays silent. Test-green is
  not ship-confidence for a stateful UI (Phase-C lesson).
- **Deploy is gated on the user** (push → Cloud Run deploy; no migration needed this time).
