# Retrospective — Action Centre: mount + smart documents + answer nudge

**Date:** 2026-06-09 → 2026-06-10
**Branch:** `feature/action-centre-mount` (7 commits, linear on `main`) → merged + deployed at close.
**Gates:** 989 scholarship + (courses/reports unchanged) pytest · 276 jest · `next build` clean · i18n parity 2474 · **no migration**.
**Plan:** `docs/scholarship/action-centre-gopal-plan.md` (Phases 1–2, decisions D1–D3).

## What Was Built

The post-submission student surface, end to end. A submitted student (`profile_complete` / `interviewing` /
`interviewed`) previously hit a dead-end "received" card — exactly when queries/document-requests are raised.

1. **Mount (`37ce7e1`).** `/scholarship/application` renders the **Action Centre only** for the post-submit statuses
   (`ActionCentre formLocked`). The 5-step form is **locked forever** (the student consented + submitted final values);
   nothing pending → a calm "you're all set, we'll be in touch" card. A `confirm` ticket becomes a typed reply (no form
   to jump back to).
2. **Phase 1 — smart documents (`111f8b5`).** Uploading a requested document runs **that document's specific scan**
   (`resolution.doc_match_verdict`, which mirrors the consent-gate per-doc red/unreadable classification): **match →
   ticks Done, Gopal silent; mismatch/unreadable → keeps the task open + contextual `DocumentHelpCoach`** (the same
   coach as the Documents tab). `resolve_doc_items_for_upload` wired into `recordDocument` (returns `match_verdict`).
   This **fixed a real bug**: a reviewer/AI *document request* (`officer` resolution item) never cleared on upload —
   only verdict (`system`) items did. The static Gopal footer was removed (he's contextual now).
3. **Live-testing polish (`ff440e7`, `3db4ce6`).** (a) The student queue shows **only deliberately-raised items**
   (officer + AI clarify), **never `source='system'` verdict gaps** — killing a duplicate where a mismatched upload
   spawned a "system" ticket beside the reviewer task + Gopal. (b) Resolved tasks **stay as green "Done" cards** (check
   + strikethrough + DONE badge) instead of vanishing.
4. **Phase 2 — answer nudge (`1e58702`).** `help_engine.judge_answer_relevance` (one Gemini JSON call, firewalled to
   the question + answer text only, defaults to ACCEPT on any error) nudges a typed answer **only when it is TOTALLY
   off-topic** (owner D2) → keeps the task open + one warm Gopal steer. Behind `CHECK2_ANSWER_RELEVANCE_ENABLED`
   (**default off** — billable). Resolve view takes the displayed `question`, returns `{resolved:false, nudge}`.

**Shipped with the email + AI-clarify queries (`CHECK2_STUDENT_QUERIES_ENABLED`) OFF and Phase 2
(`CHECK2_ANSWER_RELEVANCE_ENABLED`) OFF** — owner's call; both are one env var away from on.

## What Went Well

- **Reuse over reinvention.** Phase 1 + Phase 2 were mostly *wiring*: the per-doc `*_check` engines, `DocumentHelpCoach`
  / `CoachCard`, and the `help_engine` + `vision._call_gemini_json` seams already existed. Two enhancements, ~no new
  engine.
- **One source of truth for "is this doc a red".** `doc_match_verdict` mirrors `services.document_red_blockers` /
  `document_unreadable_blockers`, so the Action Centre and the consent gate can never disagree on a document.
- **Phased shipping with a click-through gate at each step** surfaced real UX issues that unit tests can't — the
  duplicate system-ticket and the "completed task vanishes" both came from the owner driving the live surface.
- **Firewall + flag discipline held.** The new AI call (relevance) is structurally firewalled (question+answer only)
  and flag-gated + AI-off-safe, matching the codebase's billable-AI pattern.

## What Went Wrong

1. **The local click-through took many attempts to stand up.**
   - *Symptom:* "local FE → live API" (which worked for the FE-only mount) showed *none* of Phase 1 — then a local
     backend against the live DB failed (`could not translate host name db.<ref>.supabase.co`), then uploads failed
     ("that upload didn't work").
   - *Root cause:* (a) a **FE+BE** change can't be verified by pointing a local FE at the *old* prod backend — only an
     FE-only change can; (b) Supabase's **direct DB host is IPv6-only**, unreachable from an IPv4 box; (c) the upload
     path needs the **Storage service-role key**, which I'd omitted for "isolation".
   - *Fix (lesson):* for a FE+BE feature, plan a **self-contained local stack from the start** — local backend on a
     fresh SQLite + a seeded dummy + the AI **and** Storage creds — rather than improvising "local FE → prod API".
     Added to `docs/lessons.md`.

2. **`next build` repeatedly died mid static-generation** (`Static worker exited … spawn UNKNOWN errno -4094`).
   - *Symptom:* "✓ Compiled successfully" then a worker-spawn crash; `BUILD_EXIT≠0`.
   - *Root cause:* **22 orphaned `node.exe`** workers had accumulated over a very long session and exhausted Windows'
     process spawner — not a code fault (compile/type-check passed).
   - *Fix (lesson):* on a long Windows session, **kill orphan `node.exe` before `next build`**; "Compiled successfully"
     is the code-correctness signal, a worker-spawn crash is environmental. Added to `docs/lessons.md`.

3. **The Action Centre surfaced the system's own verdict gaps to the student**, producing duplicate queries.
   - *Symptom:* a mismatched/unreadable upload spawned a `system` ticket ("Check the name on your results slip" /
     "…hard to read") *beside* the reviewer task + Gopal's coach — and bare apps showed 6 system tickets of noise.
   - *Root cause:* the original Check-2 design deliberately surfaced `source='system'` tickets to the student; live use
     showed those are the *officer's* cockpit concern, and they duplicate what a reviewer query + Gopal already cover.
   - *Fix:* `ResolutionItemListView` now excludes `source='system'` (student sees officer + AI-clarify only); a
     regression test asserts it. Decision logged.

## Design Decisions (see `docs/decisions.md`)

- Post-submit is **form-locked → Action-Centre-only** (the student can't re-edit a submitted application).
- The student queue shows **only deliberately-raised items**, never raw system verdict gaps.
- `doc_match_verdict` **mirrors the consent-gate** per-doc classification (single source of truth; only definite
  mismatch/unreadable keeps a task open — uncertain/soft/pending are accepted).
- Phase 2 relevance nudge is **flag-gated, maximally lenient (only totally off-topic), and AI-off-safe**.

## Numbers

- **7 commits.** FE: `ActionCentre.tsx`, `app/scholarship/application/page.tsx`, `api.ts`, reuse of
  `DocumentHelpCoach`, 3 i18n locales. BE: `resolution.py` (`doc_match_verdict` + `resolve_doc_items_for_upload`),
  `views.py` (record-resolve + relevance check + system-exclude), `help_engine.py` (`judge_answer_relevance`),
  `settings/base.py` (one flag).
- Tests added this arc: **+24 scholarship pytest** (17 Phase 1 + 7 Phase 2) → 989. 276 jest, parity 2474.
- **No migration.** No new model/field.
- Live-verified on a seeded local stack (mount, scan match/mismatch/unreadable, Done cards, the off-topic nudge).
