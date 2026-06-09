# Plan — Action Centre: active Cikgu Gopal + scan-on-upload (post-submit resolution)

**Status:** Plan — not yet built. Author: Claude (Action Centre workstream).
**Builds on:** the *Action Centre mount* (branch `feature/action-centre-mount`, commit `74e3e4e`), which surfaces
the Action Centre to `profile_complete` / `interviewing` / `interviewed` students as their whole (form-locked) surface.
**Motivation:** live click-through (2026-06-09, app #16 ELANJELIAN) surfaced three gaps — see below.

---

## 1. Why

The mount works: a submitted student now lands on the Action Centre instead of a dead-end card, and resolves tasks in
place. But the Action Centre is still a **"dumb" queue** — it stores an uploaded file and re-fetches, nothing more.
Three concrete gaps came out of the click-through:

1. **An uploaded document doesn't clear its task.** Reviewer/AI-raised **document requests** are `source='officer'`
   resolution items. The verdict-driven `sync_resolution_items` only auto-resolves `source='system'` items, and the
   Action Centre's upload path (`ActionCard.onFile` → `signUploadDocument` + `recordDocument` → re-fetch) never
   explicitly resolves the officer item. So a student can upload exactly what was asked and the task stays **open**
   ("0 of 4 done" after a correct upload). *This is a real bug, not just a polish item.*
2. **Cikgu Gopal is a static footer.** A permanent "Hi, I'm Cikgu Gopal…" bubble sits at the bottom of the queue. He
   should be **contextual** — appearing only when a student needs steering — exactly as he already does on the
   **Documents** tab.
3. **No scan on upload.** When the student uploads a requested document, **nothing is checked**. We ask for one
   *specific* document per task, so we know precisely which verification to run; we just don't run it.

The fix is not new machinery — it's **bringing the Documents-tab intelligence into the Action Centre**. The Documents
tab already scans each document with its specific engine and shows Gopal only on a problem. We reuse that here.

## 2. Goals / Non-goals

**Goals**
- Uploading a requested document **runs that document's scan**; a **match ticks the task done**, a **mismatch keeps it
  open and shows contextual Gopal advice**.
- Remove the static Gopal footer; Gopal becomes **per-task and contextual**.
- (Phase 2) For **question** tasks, a *gentle* Gopal nudge only when the typed answer is clearly off-topic.

**Non-goals**
- No change to the *mount* itself (statuses, form-lock, the "all set" empty state — all correct).
- No turning on the email / AI clarify-query flag (`CHECK2_STUDENT_QUERIES_ENABLED` stays off).
- No new verification engines — strictly reuse the existing per-document `*_check` engines + Cikgu Gopal
  (`help_engine`).
- Not a Documents-tab rewrite; the Action Centre stays its own surface, it just borrows the same scan + coach.

## 3. Building blocks to reuse (all exist today)

| Piece | Where | Role |
|---|---|---|
| Per-document verdicts | `ApplicantDocumentSerializer` SerializerMethodFields: `bc_check`, `guardianship_check`, `str_check`, `utility_check`, `income_ic_check`, `income_proof_check`, `academic_check`, `pathway_check`, `vision_nric_verdict`, `vision_name_verdict` | the match/mismatch result for a given doc |
| Scan on upload | `DocumentListCreateView` (`recordDocument`) auto-runs Vision / doc-assist on record | already triggered by the Action Centre's existing upload |
| Cikgu Gopal (doc coach) | `help_engine.generate_document_help` + `DocumentHelpView` (`GET scholarship/documents/<pk>/help/`) | concise, firewalled, per-document advice |
| Cikgu Gopal (income cluster coach) | `IncomeClusterHelpView` (`GET scholarship/income/<member>/help/`) | one coach per income earner cluster |
| FE coach UI | `components/DocumentHelpCoach.tsx`, `components/IncomeClusterCoach.tsx`, `lib/documentHelp.ts` (`shouldShowCoach` / `fallbackKeyFor`) | render the coach + i18n fallback |
| Resolution model | `ResolutionItem` (`kind` doc/explanation/confirm/clarify; `source` system/officer/check2; `doc_type`) | the task queue |

## 4. Phase 1 — Documents: scan-on-upload → resolve-on-match → contextual Gopal

### 4.1 The flow (per document task)
```
student taps Upload on a `doc` task (doc_type = e.g. birth_certificate)
  → signUploadDocument(doc_type) + recordDocument   (existing; this already kicks off the scan)
  → re-fetch THAT document's verdict for its doc_type
       MATCH      → resolve the resolution item → task ticks done; Gopal stays silent
       MISMATCH / → keep the item open; render the SAME contextual Gopal coach inline in the card
       UNREADABLE   (DocumentHelpCoach / income cluster coach), inviting a clean re-upload
       PENDING    → "checking…" state; poll/refresh once, then treat a persistent pending as "submitted,
                    reviewer will confirm" (don't block on an OCR outage — mirror the gate's Gemini-outage rule)
```

### 4.2 doc_type → which scan decides "match"
We ask for one precise document, so the match test is deterministic per type (reuse the existing `*_check`):

| Requested `doc_type` | Engine / field | "Match" = |
|---|---|---|
| `birth_certificate` | `bc_check` | child↔mother (and father where present) relationship confirmed |
| `guardianship_letter` | `guardianship_check` | guardian↔ward confirmed |
| `parent_ic` | `income_ic_check` (member-aware) | earner IC name+NRIC read and matches the income proof |
| `salary_slip` / `epf` | `income_proof_check` | earner income proof read for the named member |
| `str` | `str_check` | STR current + recipient matches the earner |
| `results_slip` | `academic_check` | slip name matches + subjects/grades read |
| `offer_letter` | `pathway_check` | offer name/IC matches the student |
| `ic` | `vision_nric_verdict` + `vision_name_verdict` | NRIC + name match the profile |
| `water_bill` / `electricity_bill` | `utility_check` | soft — accept on upload (never a hard "fail") |

A small **`matchVerdictFor(docType, doc)`** helper (pure, FE `lib/`) reads the relevant `*_check` and returns
`match | mismatch | unreadable | pending | soft`. `soft` (utilities) resolves on upload without a hard check.

### 4.3 Resolving the task
- On `match` (or `soft`): call the existing resolve path so the officer/AI item closes. Add a thin endpoint behaviour:
  **`ResolutionItemResolveView` (or the doc-upload path) resolves a `doc` item when its `doc_type` scan matches**, via
  `resolution.resolve_item(item, doc=<uploaded>, by='student')`. This also **fixes Gap #1** (officer doc items finally
  clear on a correct upload).
- On `mismatch`/`unreadable`: leave the item **open**; the card shows the contextual coach + the Upload button again
  (re-upload until it matches — see Decision D1).

> **Why not lean on `sync_resolution_items`?** That only reconciles `source='system'` items against the verdict. Officer
> items must be resolved explicitly. Keeping the resolve in the upload path covers **both** system and officer doc tasks
> uniformly (and is idempotent — a system item the verdict also clears just no-ops).

### 4.4 Frontend changes (`ActionCentre.tsx` / `ActionCard`)
- After `recordDocument`, fetch the uploaded document's verdict (reuse the doc serializer / a focused
  `getDocument(id)` or the help endpoint) and compute `matchVerdictFor`.
- **Match** → call resolve → `onResolved()` (re-fetch; the task disappears / ticks).
- **Mismatch/unreadable** → render `DocumentHelpCoach` (or the income cluster coach for income docs) **inside the card**,
  below the Upload button. Reuse `lib/documentHelp.ts` for the AI-off fallback copy.
- **Remove** the static footer Gopal bubble at the bottom of the queue.
- Keep the existing progress bar; it now moves as tasks genuinely resolve.

### 4.5 Edge cases
- **Gemini/Vision outage** → scan returns `pending`/service-down: don't trap the student. Show "we're checking this —
  you can carry on" and let the reviewer confirm; the task may auto-resolve on the next load when the scan completes.
- **Wrong document entirely** (e.g., uploads an IC for a birth-cert task) → reads as mismatch/unreadable → Gopal names
  the expected document.
- **Multi-instance income docs** (`str`/`salary_slip`/`epf`) already replace-or-add per `(doc_type, member)` — the
  income coach is cluster-aware; reuse `IncomeClusterCoach` for those tasks.

## 5. Phase 2 — Questions: gentle Gopal relevance nudge (do AFTER Phase 1)

For `explanation` / `clarify` / (form-locked) `confirm` tasks the student types an answer.

- **Respect the student's answer.** Default: accept and resolve on Send.
- Per **D2**, Gopal nudges **only when the answer is TOTALLY off-topic** (completely unrelated to the question / a clear
  misunderstanding). Anything with *any* bearing on the question is accepted — no nudge. The bar is deliberately high so
  we never second-guess a real answer.
- Mechanism: a small **relevance check** — `help_engine` gains a `judge_answer_relevance(question, answer) →
  {on_topic: bool, nudge?: str}` (one cheap Gemini call, firewalled: it sees only the question text + the answer, never
  scores/PII — same contract as `generate_document_help`). The prompt is framed to return `on_topic=false` **only** for
  a completely unrelated answer (default to `true` when unsure). Behind a flag; **AI-off → always accept** (never block
  on the model).
- On a `false`: keep the task open + one concise Gopal steer; the student edits and resends.

*Cost:* one short Gemini call per typed answer (only on Send), gated by a flag; negligible volume, but it is a billable
call — hence Phase 2 and flag-gated.

## 6. Decisions (RESOLVED 2026-06-10 by owner)

- **D1 — Mismatch handling (Phase 1): STRICT.** A mismatched/unreadable document keeps the task **open** and requires a
  matching re-upload (mirrors the Documents tab). Utilities (`water_bill`/`electricity_bill`) stay **soft** (accept on
  upload — never a hard fail).
- **D2 — Phase 2: YES, but maximally conservative.** Build the answer nudge, and **only nudge when the answer is TOTALLY
  off-topic.** Anything with *any* bearing on the question is accepted as the student's answer (no nudge). The threshold
  is "completely unrelated / clear misunderstanding", not "could be better". Bias hard toward acceptance.
- **D3 — Pending/outage copy: OK.** Use the "we're checking this — you can carry on" treatment when the scan is
  momentarily unavailable; never make the student wait or block on an OCR/Gemini outage.

## 7. Testing
- **jest (node):** `matchVerdictFor` pure helper (every doc_type → match/mismatch/unreadable/soft); the ActionCard
  resolve-on-match vs coach-on-mismatch branch (logic-level).
- **pytest:** the resolve-on-upload path resolves a `doc` officer item when the scan matches; leaves it open on
  mismatch; idempotent; system doc items still reconcile. (Phase 2: `judge_answer_relevance` pure + firewall test +
  Gemini mocked, no live call.)
- **Live click-through (TD-070):** re-run the app #16 demo — upload a matching doc (ticks done, no Gopal), a mismatching
  doc (stays open + Gopal), clear all → "all set".

## 8. i18n
- Reuse existing `scholarship.docs.help.*` fallback copy + the Action Centre keys. New keys only for any
  Action-Centre-specific coach framing + a "checking…"/pending state, en/ms/ta (Tamil first-draft).

## 9. Risks & mitigations
- **Never trap a student on an OCR outage** → pending/service-down always lets them proceed (reviewer confirms).
- **Don't nag** → Gopal silent on match; Phase 2 biased to acceptance.
- **Firewall** → the coach + relevance judge get only doc-type/verdict/question+answer, never the application/profile/
  score object (assert in tests, as today).
- **No flag creep** → Phase 1 needs no new flag (reuses existing scan + coach); Phase 2's relevance judge is flag-gated
  and AI-off-safe.

## 10. Out of scope
- The email notification + AI clarify-query generation (still `CHECK2_STUDENT_QUERIES_ENABLED`-gated, off).
- Any change to the officer cockpit or the Documents tab itself.

## 11. Coordination note
The Action Centre mount lives on `feature/action-centre-mount` (committed). This enhancement should branch from / merge
after that. A parallel agent is doing minor work on the same tree — keep commits to explicit paths (`git add <paths>`,
never `-A`) and rebase before merging. The local click-through env is currently live (FE pointed at the prod API; app
#16 seeded with 4 demo tickets + 4 waived system tickets; prod CORS temporarily allows `localhost:3000`) — tear that
down (revert CORS, delete the dummy tickets, restore `.env.local`) when testing concludes.
