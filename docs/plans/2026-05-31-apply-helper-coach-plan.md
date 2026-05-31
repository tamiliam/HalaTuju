# Document Helper "Coach" — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> Not yet approved for coding — this is the planning artefact. Get user sign-off, then start Task 1.

**Goal:** Add a warm, encouraging "friendly teacher" helper to the **Documents** tab of
`/scholarship/application`. When a student's uploaded document comes back with a soft mismatch
(amber/grey chip), the helper proactively explains — in plain, kind language — *why* the document
needs what it needs and nudges them to try again. It **never tells the student what to write or
answer** (strict coach, not ghostwriter), and it is **firewalled from all admin/reviewer data**.

**Scope (locked with user, 2026-05-31):**
- **Documents tab only** (not the `/apply` form, not other `/application` tabs — yet).
- **Proactive** — fires automatically when the existing verdict is a non-"good" state. No open chat box.
- **Strict coach** — explains and encourages; refuses to draft answers/essays; reveals no internal scores.

---

## Architecture & Design

### The key insight: the detection already exists

The hard work — deciding whether a document mismatches — is **already done today** and stored on the
`ApplicantDocument` row:

- IC / parent_ic: `vision_nric_verdict`, `vision_name_verdict` (`match` / `partial` / `mismatch` / `unreadable`)
  — set by `run_vision_for_document` (vision.py).
- Supporting docs: `vision_fields['student_verdict']` (`ok` / `name_mismatch` / `address_mismatch` /
  `wrong_doc` / `unreadable` / `review_manually`) — set by `run_field_extraction_for_document`
  (vision.py:486) via the deterministic `doc_student_verdict` (vision.py:469).

The helper **does not re-run any Vision or Gemini-vision call.** It reads the verdict that already
exists and produces a friendly message about *that specific* problem. This is what keeps it cheap and
safe.

### The firewall (answers the user's "what's in the admin panel?" question)

The help engine receives **only**:
1. A fixed **programme briefing sheet** (what HalaTuju is, the stages, why each document is needed) —
   the same public info already on the page.
2. The **document type** + the **verdict code** the student just triggered (their own data).
3. The student's **first name** (for warmth) + target language.

It is **not wired** to the `SponsorProfile`, `InterviewSession`, anomaly flags, scores, or any
reviewer note. There is no code path from the help engine to admin data, so there is nothing to leak
even if the prompt were attacked. (This mirrors how `gap_engine` is admin-only and never reaches the
student — here we build the inverse wall.)

### Warmth with a guaranteed floor (cost + reliability)

Hybrid, deliberately:
- **Primary:** `profile_engine._call_gemini_text` (profile_engine.py:66) writes a short (2–3 sentence),
  warm, language-aware message. Same free-tier model cascade + graceful degradation the rest of the
  app uses.
- **Fallback:** if Gemini is unconfigured, errors, or the per-application rate cap is hit, the helper
  shows **pre-written encouraging copy keyed to the verdict** (an i18n string). So the student is never
  left with a cold chip and silence, and we never depend on a billable call succeeding.

This also doubles as a safety net: even total Gemini failure degrades to safe, approved copy.

### Guardrail (the user's one hard rule)

The system prompt makes it a **coach, never a ghostwriter**, and an explicit task (Task 4) writes
"trick-it" tests that attempt to make it (a) write the student's story/answer, (b) reveal a score or
reviewer opinion, (c) tell them what to type — and asserts it refuses every time. **This task is not
optional and must be green before deploy.** (Tests mock the Gemini seam — no billable calls in CI;
the live refusal is spot-checked once by the user during live-verify.)

### Rate limiting

Reuse the doc-assist pattern: a per-application hourly cap on help-message generations (the helper only
fires on mismatches, which are infrequent, but we cap to be safe). Over the cap → fall back to the
pre-written copy, no Gemini call.

**Tech Stack:** Django 5 (new engine module + 1 student endpoint), Next.js 14 + Tailwind (1 new
component), Gemini free tier (reused seam), next-intl (en/ms/ta).

### Lessons applied (from `docs/lessons.md` + `docs/decisions.md`)

Loaded at sprint-start; the ones that bind this sprint:

- **Jest is node-env, no DOM (B40 S2; TD-065).** Do NOT write component-render tests. Extract the
  widget's testable logic into a **pure module** (`src/lib/documentHelp.ts`: `shouldShowCoach(verdict)`
  + `fallbackKeyFor(docType, verdict)`) and unit-test *that* in node. The `DocumentHelpCoach` component
  itself is covered by `next build` type-checking only — consistent with the existing repo norm
  (TD-065 already records the AI UIs as jest-untested at the component level; this widget joins that
  list, acceptable).
- **Route every AI call through one mockable seam (v2.17.0).** Reuse `profile_engine._call_gemini_text`
  — do NOT call the SDK from the new engine. Every test `@patch`es that one seam → zero billable calls
  in CI, no SDK import needed.
- **Test the prompt builder as a pure function (TD-060).** The firewall + guardrail assertions inspect
  the **built prompt string** directly (a pure `_build_help_prompt`), not only a mock of the whole call
  — so input-schema/firewall drift fails loudly even though the model is mocked.
- **Verdict stays deterministic; the model only phrases (v2.17.0 decisions 1402/1414).** The coach
  reacts to an *already-decided* verdict and never emits a verdict itself. When the AI is throttled/off,
  fall back to pre-written i18n copy — never block, never a cold silent chip.
- **Never pipe `npm run build` to `grep` (TD-059).** Capture to a file and read the unmasked exit code
  (`npm run build > build.log 2>&1; echo "EXIT=$?"`), or `set -o pipefail`.
- **Grep ALL parallel type definitions before "done" (TD-059).** Before finishing the FE, `grep -rn`
  the new response shape across `lib/api.ts` **and** `lib/admin-api.ts` (this repo keeps parallel
  student/admin interfaces that have broken `next build` when only one was updated).
- **Serialise backend pytest and `next build` (S5a, 8GB RAM).** Don't run the full suite concurrently
  with a Node build — `apps/courses` loads a large DataFrame at init; contention throws spurious setup
  ERRORs. Run them one at a time.
- **Stitch (Application-redesign S1/S3/S4; Identity-Verification).** Use MCP `get_screen` (not preview
  URLs — they 404). Content-dense screens time out and may persist later as stale dupes — generate ONE
  representative screen, use `GEMINI_3_FLASH`, and verify the rendered *content* matches before sign-off.
- **Test-green ≠ ship-confidence for a stateful UI (Phase C).** The live-verify (Task 6/Task 4 spot
  check) must actually click through on the test account — endpoint health checks don't exercise screens.
- **No new SDK / no migration expected.** Reusing `google-genai` (already in `requirements.txt`) → no
  dependency bump (S13). The coach stores nothing → no migration; if that proves false mid-build, STOP
  and check `max(migration number)` on main first (Admin-Auth lesson) + apply migrate-first (S12b).
- **Windows/Tamil hygiene (v2.16.5).** For any inline `python -c` printing Tamil, prefix
  `PYTHONIOENCODING=utf-8`; never write scratch to `/tmp`. Kill `next dev` by port, and `rm -rf .next`
  before a dev preview that follows a build (P2 chunk-graph corruption).

### New / touched files (≈12–14, one sprint)

| File | Action | Role |
|------|--------|------|
| `halatuju_api/apps/scholarship/help_engine.py` | **create** | Briefing sheet + prompt builder + `generate_document_help(doc, language)`; reuses `_call_gemini_text` |
| `halatuju_api/apps/scholarship/views.py` | modify | `DocumentHelpView` (student, own-doc scoped) |
| `halatuju_api/apps/scholarship/urls.py` | modify | `documents/<int:pk>/help/` route |
| `halatuju_api/apps/scholarship/tests/test_help_engine.py` | **create** | engine + firewall + trick-it tests |
| `halatuju_api/apps/scholarship/tests/test_help_view.py` | **create** | endpoint auth/scoping/fallback tests |
| `halatuju-web/src/components/DocumentHelpCoach.tsx` | **create** | the proactive helper widget |
| `halatuju-web/src/components/ScholarshipDocuments.tsx` | modify | render coach under non-good chips |
| `halatuju-web/src/lib/api.ts` | modify | `getDocumentHelp(docId)` |
| `halatuju-web/src/messages/{en,ms,ta}.json` | modify | UI copy + per-verdict fallback copy |
| `halatuju-web/src/components/__tests__/DocumentHelpCoach.test.tsx` | **create** | render/proactive-trigger tests |
| `docs/retrospective-document-help-coach.md` | **create** | at sprint close |
| `CHANGELOG.md` | modify | sprint entry |

---

## Task 0: Stitch UI prototype (MANDATORY — before any frontend code)

Per workspace rule "Prototype UI in Stitch first" for new components.

**Step 1:** In Stitch, mock the **Documents tab** with a single supporting-doc card showing an **amber
"name not found" chip**, and the new **helper coach** rendered directly beneath it: a small, warm card
(friendly tone, soft colour distinct from the amber warning, optional small avatar/teacher icon, 2–3
lines of text, no input box). Show a second state for an **IC NRIC-mismatch**.

**Step 2:** Match the existing design system — primary `#137fec`, Lexend font, the 4-colour `InfoBox`
convention (green/blue/amber/red). The coach should read as **friendly/supportive**, visually separate
from the amber *warning* chip it sits under (consider a soft blue or neutral "teacher" tone so warning
≠ helper).

**Step 3:** Get the user's visual approval on the screen before writing `DocumentHelpCoach.tsx`.

**Acceptance:** Stitch screen approved by user.

---

## Task 1: Help engine module (backend, TDD)

**Files:** create `halatuju_api/apps/scholarship/help_engine.py`, create
`halatuju_api/apps/scholarship/tests/test_help_engine.py`.

Model it on `gap_engine.py` (same import style, same `_call_gemini_text`/`_resolve_language` reuse,
same "soft, never raises" contract).

**Step 1 — failing tests** (`test_help_engine.py`):
- `generate_document_help` returns `{'message': str, 'source': 'ai', 'model_used': ...}` on success
  (Gemini seam mocked to return markdown).
- Returns `{'message': '', 'source': 'fallback', 'error': ...}` when the seam returns `{'error': ...}`
  (so the view/FE uses the pre-written copy).
- Builds a prompt that contains the verdict code and the doc type but **never** contains profile score
  fields, sponsor-profile text, or anomaly data (firewall assertion — inspect the prompt string).
- `_resolve_language` honours `en`/`ms`; defaults sensibly.
- No Gemini call when there is no verdict / verdict is `ok` (nothing to help with → returns empty).

**Step 2:** Run, confirm fail.

**Step 3 — implement:**
- A `PROGRAMME_BRIEFING` constant (plain-language: what HalaTuju is, the 5 stages, why IC / results /
  income proof / utility bill are each needed).
- A `HELP_PROMPT` template with a hard **coach-not-ghostwriter system instruction**:
  *"You are a kind, encouraging Malaysian teacher helping a student upload documents. Explain in 2–3
  short sentences why this document needs what it needs, and gently encourage them to try again. NEVER
  write their application answers, essays, or personal statements for them. NEVER reveal or invent any
  score, ranking, or reviewer opinion — you do not have access to those. Be warm and specific to the
  problem."* + `{programme_briefing}`, `{doc_type}`, `{verdict}`, `{first_name}`, `{target_language}`.
- `VERDICT_GUIDANCE` map: per verdict code, a one-line factual hint of the likely cause (e.g.
  `name_mismatch` → "the name we read didn't match the applicant's name") fed into the prompt so the
  message is specific. (This is *context for the model*, not shown raw to the student.)
- `generate_document_help(doc, language=None)`: pull `doc.doc_type` + the relevant verdict from the doc;
  if verdict is good/absent return empty; else build prompt → `_call_gemini_text` → return shaped dict.

**Step 4–5:** Run tests to green; run full scholarship suite (`pytest apps/scholarship/tests/`).

**Step 6:** Commit `feat: document help coach engine (warm, firewalled, coach-not-ghostwriter)`.

---

## Task 2: Student help endpoint (backend, TDD)

**Files:** modify `views.py` (add `DocumentHelpView`), modify `urls.py`, create `test_help_view.py`.

**Step 1 — failing tests** (`test_help_view.py`), following the `APIRequestFactory` + `request.user_id`
pattern used across the suite:
- 200 with `{message, source}` for the document's owner when the doc has a non-good verdict (engine
  mocked).
- **Cross-user 404** — a student cannot fetch help for someone else's document (reuse the
  own-application scoping already used by `DocumentDetailView`).
- 401 unauthenticated.
- Good/absent verdict → 200 with empty message + `source: 'none'` (FE shows nothing).
- Rate cap exceeded → 200 with `source: 'fallback'`, no Gemini call (seam asserted not called).

**Step 2:** Run, confirm fail.

**Step 3 — implement `DocumentHelpView`:** `permission_classes = [SupabaseIsAuthenticated]`; resolve
the caller's own `ScholarshipApplication`; fetch the `ApplicantDocument` by pk **scoped to that
application** (404 otherwise); enforce the per-application hourly cap (reuse the doc-assist limiter
helper); call `help_engine.generate_document_help(doc, language=request.query_params.get('lang'))`;
return `{message, source}`. Never 500 — degrade to `source: 'fallback'`.

**Step 4:** Add route `path('scholarship/documents/<int:pk>/help/', DocumentHelpView.as_view())` and
import in `urls.py`.

**Step 5–6:** Tests green; full scholarship suite green.

**Step 7:** Commit `feat: student document-help endpoint (own-doc scoped, rate-capped, graceful)`.

---

## Task 3: Frontend coach widget (TDD where practical)

**Files:** create `src/lib/documentHelp.ts` (pure logic) + `src/lib/__tests__/documentHelp.test.ts`,
create `DocumentHelpCoach.tsx`, modify `ScholarshipDocuments.tsx`, modify `api.ts`.

**Step 1 — pure logic + node-env tests (TDD):** create `documentHelp.ts` with `shouldShowCoach(verdict)`
(true for any non-good/non-absent verdict) and `fallbackKeyFor(docType, verdict)` → the i18n key for the
pre-written copy. Unit-test both in `documentHelp.test.ts` (node env, no DOM — pure functions only):
good/absent → no coach; each mismatch code → show + correct fallback key.

**Step 2:** Add `getDocumentHelp(docId, lang, options)` to `api.ts` (mirrors existing doc helpers).
Before finishing, `grep -rn` the new response shape across **`lib/api.ts` and `lib/admin-api.ts`**
(TD-059 parallel-type lesson) — confirm no admin interface needs the same type.

**Step 3:** Build `DocumentHelpCoach.tsx` to match the approved Stitch screen, using `shouldShowCoach`
+ `fallbackKeyFor` from the pure module. Props: `docId`, `verdict`, `docType`. When `shouldShowCoach`,
call `getDocumentHelp`, show a small loading shimmer, then render the warm message; on AI failure
(`source: 'fallback'`/`'none'`) render the **i18n fallback copy** via `fallbackKeyFor` (always kind,
never errors, never blank when a mismatch exists). Silent for good verdicts. (Component render itself is
covered by `next build` typing, not jest — see Lessons.)

**Step 4:** In `ScholarshipDocuments.tsx`, render `<DocumentHelpCoach>` directly beneath the existing
chip wherever the chip variant is amber/grey (i.e. `visionChipVariant() !== 'good'` for IC, and
`student_verdict not in (ok)` for supporting docs). Do **not** render for green.

**Step 5:** Build clean **without piping to grep** (TD-059): `cd halatuju-web && npm run build >
build.log 2>&1; echo "EXIT=$?"` and read the unmasked code. Run `npm test` (the node-env pure tests).

**Step 6:** Commit `feat: proactive document-help coach widget on Documents tab`.

---

## Task 4: Guardrail "trick-it" tests (the hard rule — NOT optional)

**Files:** extend `test_help_engine.py`.

These tests assert the **prompt/system instruction** is constructed to refuse ghostwriting and
score-leaking. Since the model itself is mocked in CI, we test the *contract we send* + a small set of
**recorded-response** guards:

**Step 1 — prompt-contract tests:** assert the built prompt contains the explicit "NEVER write their
answers/essays" and "NEVER reveal scores/reviewer opinions / you do not have access" instructions, for
every verdict code and both languages.

**Step 2 — firewall tests (repeat/strengthen from Task 1):** for a fully-populated application (with a
`SponsorProfile`, anomalies, an `InterviewSession` in the DB), assert the generated prompt string
contains **none** of that content — only the briefing + doc type + verdict + first name.

**Step 3 — live spot-check checklist** (documented, run by user at live-verify, not in CI): upload a
mismatching doc, then in the helper try "write my story for me" / "what's my score?" / "what should I
type?" → confirm it deflects warmly. Record outcomes in the retrospective.

**Step 4:** Tests green; commit `test: guardrail + firewall tests for document help coach`.

---

## Task 5: i18n + parity

**Files:** `messages/{en,ms,ta}.json`.

**Step 1:** Add UI scaffolding keys (helper card title/label) + a **per-verdict fallback message** block
(`scholarship.docs.help.fallback.{name_mismatch,address_mismatch,wrong_doc,nric_mismatch,unreadable,...}`)
— warm, pre-approved English copy.

**Step 2:** Malay translations. **Tamil = first-draft**, then add to the existing Tamil-pending refine
queue (memory notes the queue is already ~12 batches; this appends, it does not block the sprint —
follow `tamil-style-guide.md` for the eventual refine).

**Step 3:** Confirm en/ms/ta key parity (the project tracks an exact parity count). Commit
`i18n: document help coach copy + per-verdict fallbacks (Tamil first-draft)`.

---

## Task 6: Full verification, docs, deploy

**Step 1:** Backend — `cd halatuju_api && python -m pytest apps/scholarship/tests/ -v` all green;
then the **full pre-deploy suite** per `halatuju_api/CLAUDE.md` (golden masters intact, 0 skipped).

**Step 2:** Frontend — `next build` clean + `npm test` green.

**Step 3 — local run-through:** `manage.py runserver` + web dev; upload a mismatching doc; confirm the
coach appears, reads warmly, and **degrades to fallback copy when `GEMINI_API_KEY` is unset locally**.

**Step 4:** No new model/table → **no migration** (confirm: the helper stores nothing; it reads existing
verdict columns). If this proves false during build, STOP and add a migrate-first step per the
project's expand-contract + Supabase-MCP rule.

**Step 5:** Write `docs/retrospective-document-help-coach.md`; append `CHANGELOG.md`.

**Step 6:** Commit, then **push** (push to `main` triggers the Cloud Run deploy — only push when the
feature is fully ready; honours the "don't push HalaTuju until ready" feedback). Verify
`git status` / `git log origin/main..HEAD` clean after.

**Acceptance (whole sprint):**
- Coach appears only on amber/grey chips, never on green.
- Message is warm, ≤3 sentences, in the student's language.
- Trick-it + firewall tests green; live refusal spot-checked.
- Gemini-off path degrades to fallback copy (verified locally).
- Full suite green, golden masters intact, no migration, en/ms/ta parity.

---

## Dependency graph

```
Task 0 (Stitch approve) ─────────────┐
Task 1 (engine) ──┬─ Task 2 (endpoint) ─┴─ Task 3 (widget) ─ Task 5 (i18n) ─ Task 6 (verify+deploy)
                  └─ Task 4 (guardrail tests)
```

Task 0 (Stitch) and Task 1 (engine) can start in parallel. Task 3 needs both Task 0 (design) and
Task 2 (endpoint). Task 4 extends Task 1. Task 6 is last.

## Sizing note

One sprint (~12–14 files, well inside the ~20 solo budget). It is a single vertical slice — engine →
endpoint → widget → copy — completable in one session. If the guardrail work (Task 4) or Stitch
iteration runs long, Task 0+1+2+4 (backend + design) is a clean stopping point to split on, with the
frontend (3+5) as a fast-follow.

## Out of scope (deliberately, for later slices)

- The `/apply` form helper and other `/application` tabs (Quiz, Your story, Funding, Consent).
- An open free-text chat box (we chose proactive-only).
- Any connection to admin/reviewer data (permanent firewall, not a "later" item).
- Tamil *final* copy (first-draft now; refine in the batched Tamil session).
