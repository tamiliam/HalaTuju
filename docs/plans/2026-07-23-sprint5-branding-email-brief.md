# Sprint 5 — Per-org branding & email sender identity, BACKEND (implementation brief)

**Date:** 2026-07-23 · **Author:** architect session (owner pulled the S5–S6 split-gate option 2026-07-23) · **Executor:** Opus 4.8 agent
**Roadmap:** `docs/plans/2026-07-14-platform-roadmap-draft.md` Phase 2, Sprint 5.
**Gate note:** Phase 2's rule-stability clock runs to ≈21 Aug, but S5–S6 are branding-only and the owner's on-record split option covers them. S7–S9 remain gated — do NOT touch engine rules, thresholds, or document/route config in this sprint.

---

## 0. Read before you start

1. Follow `Settings/_workflows/sprint-start.md` pre-flight: `git status` + `git log origin/main..HEAD` — start on a clean, fully pushed tree or STOP and report. (Architect verified clean at 2026-07-23; re-verify.)
2. Read `halatuju_api/CLAUDE.md` and `docs/build-for-tenancy-conventions.md`. Every rule binds.
3. **NO migrations this sprint.** The 19 tenant columns landed in platform Sprint 1 (`courses/0061` + seed `scholarship/0098`); this sprint READS them. If you believe you need DDL, stop and report.
4. **Push = deploy** (Cloud Build). ONE push at the very end, after Phase 5 verification. Verify builds by SHORT_SHA (`gcloud builds list --project gen-lang-client-0871147736 --account tamiliam@gmail.com`).
5. **Backend only.** No frontend, no i18n JSON, no legal pages — that is Sprint 6. `halatuju-web/` must have zero diffs.
6. Multi-line source edits go through the editor tools (Write/Edit) or a scratch script file — NEVER a bash heredoc (`lessons.md`, cost Sprint 14 two cycles).
7. Line numbers in this brief were spot-verified 2026-07-23 but WILL drift — find constructs by name. A brief fact that contradicts the code: the code wins; document the deviation (CHANGELOG + retro), per `lessons.md`.

### Verified facts (2026-07-23, architect)

- `PartnerOrganisation` (`apps/courses/models.py` ~:397-455) carries: `programme_name_{en,ms,ta}`, `logo_url`, `brand_colour`, `persona_name_{en,ms,ta}`, `team_signoff_{en,ms,ta}`, `email_from`, `email_reply_to`, `email_support`, `frontend_url`, module flags. Convention: `'' = use platform default`.
- BrightPath (org #1, code `brightpath`) is seeded with **today's live constants verbatim** (`scholarship/migrations/0098_seed_brightpath_organisation.py`) — `team_signoff_en='The BrightPath Bursary Team'`, `email_from='info@halatuju.xyz'`, `email_reply_to='help@halatuju.xyz'`, `email_support='help@halatuju.xyz'`, `frontend_url='https://halatuju.xyz'`, persona `'Cikgu Gopal'` ×3. **`team_signoff_ms`/`_ta` were NOT seeded (default `''`)** — today's emails use the English sign-off in all languages, so the fallback chain must preserve that.
- `emails.py` is 3375 lines, ~45 `send_*` functions. **125 occurrences of "BrightPath"** (mostly inline body/subject literals + the sign-off "The BrightPath Bursary Team" inlined at ~10 sites + a `_bold_team` HTML helper). The roadmap's `_REVIEWER_SIGNOFF` constant NO LONGER EXISTS — do not hunt for it.
- Topical aliases at `emails.py:16-20`: `INTERVIEW_REPLY_TO`/`INTERVIEW_FROM_EMAIL` = `interview@halatuju.xyz`, `SPONSOR_REPLY_TO` = `sponsor@halatuju.xyz`.
- `FRONTEND_URL` is read via `getattr(settings, 'FRONTEND_URL', 'https://halatuju.xyz')` at ~15 sites in `emails.py`.
- `programme_name` is **already data-driven** — every caller passes `application.cohort.name` (verified in `services.py`). It is NOT a target of this sprint; leave that plumbing alone.
- Persona "Cikgu Gopal" as a rendered string lives in **`help_engine.py`** (the coach prompt) and **`emails.py`** (reminder emails name the coach). Hits in `pathway_engine.py`, `income_engine.py`, `resolution.py`, `views.py` are comments/docstrings — NOT extraction targets. FE fallback strings are Sprint 6.

### Owner-settled decisions (binding)

| # | Decision |
|---|---|
| D1 | **One read seam.** A new `apps/scholarship/branding.py` module is the ONLY place org branding columns are read for rendering. No per-site column lookups. |
| D2 | **BrightPath output is byte-identical.** Proven by golden snapshot tests captured BEFORE the refactor (Phase 1) and kept green through it, unmodified. |
| D3 | **Fallback chain:** requested-language column → `_en` column → platform default (today's constant). `''` is always "fall through". A missing/None org falls through entirely to platform defaults, so best-effort emails never raise. |
| D4 | **Topical aliases (`interview@`, `sponsor@`) are platform-domain features.** They apply when the org's sender identity is on the platform domain (BrightPath today → byte-identical). An org with its OWN `email_from` domain gets its `email_from`/`email_reply_to` for all mail — no per-topic aliases until a tenant asks. Encode this in the seam, comment the rule. |
| D5 | **Platform/ops emails stay platform-branded** (vision outage alert, contact-submission admin email, sponsor-interest admin email, partner welcome). They are not tenant mail. List them explicitly in the guard's allowlist with a comment. |
| D6 | **Grep-guard is AST-based and self-checking.** It scans string constants (not comments/docstrings) in `emails.py` + `help_engine.py` for `BrightPath` / `Cikgu Gopal` / `halatuju.xyz`, allowing only the designated platform-defaults block in `branding.py`. It must also assert a MINIMUM count of scanned `send_*` functions (derived by `inspect`, never a hand list — `lessons.md`: a test that enumerates the thing it guards must derive the list). |

---

## Phase 1 — Golden snapshots FIRST (own commit)

Before touching any production line: a new `apps/scholarship/tests/test_email_branding.py` that renders a representative matrix of the CURRENT emails and pins their full output (subject + text body + HTML where produced):

- Every student-facing `send_*` in `emails.py` that takes `lang`, rendered in en/ms/ta.
- The award-offer, sign-invitation, reminder (all 4 stages + closure), decline (each category), countersign/witness/executed set, sponsor notify (realtime + digest), reviewer/QC set.
- Use `django.core.mail.outbox`; assert exact `subject`, `body`, `from_email`, `reply_to`, and the HTML alternative payload.
- These tests must pass against the UNTOUCHED code. Commit them alone: `test(emails): golden snapshots before per-org branding extraction`.

Phase 2 may not modify this file except to ADD the org-2 cases (Phase 4). If a snapshot must change, stop — the refactor broke byte-identity.

## Phase 2 — The seam + emails extraction (one commit)

1. **`apps/scholarship/branding.py`** — small, pure, lazy (no DB at import):
   - A `PLATFORM` defaults block holding today's constants verbatim (sign-off, aliases, sender identities, persona, frontend URL) — the ONE sanctioned home for these literals (guard allowlist).
   - `class Branding` (or namedtuple) with lang-aware accessors: `team_signoff(lang)`, `persona_name(lang)`, `email_from`, `email_reply_to`, `email_support`, `interview_from`, `interview_reply_to`, `sponsor_reply_to` (D4 rule), `frontend_url`.
   - Resolvers: `for_organisation(org_or_none)` and `for_application(app)` (via `app.cohort.owning_organisation`, tolerant of missing links). Both never raise.
2. **`emails.py` extraction:**
   - Every send function that renders tenant mail resolves a `Branding` — preferred: callers that hold the application pass it (add an optional `branding=None`/`org=None` kwarg, defaulting to platform → byte-identical for untouched callers); update the call sites in `services.py` etc. that have the application in hand.
   - Replace: inlined "The BrightPath Bursary Team" sign-offs (+ `_bold_team`), inline "BrightPath" body/subject literals, the module alias constants at their use sites, the ~15 `FRONTEND_URL` getattr sites → `branding.frontend_url` (settings fallback stays inside `branding.py`).
   - D5 platform/ops emails: leave content, but route their literals through the `PLATFORM` block so the guard passes.
3. **Suite must stay green with the Phase-1 goldens UNMODIFIED.** Existing email tests pass unmodified too — if one hardcodes a wrong assumption, stop and report rather than editing it silently.

## Phase 3 — Persona seam in `help_engine.py` (same or separate commit)

- The coach prompt takes the persona name from `branding.persona_name(lang)` (resolved from the application the view already holds). Fallback = platform default `'Cikgu Gopal'`.
- Reminder emails that name the coach use the same accessor.
- Comments/docstrings mentioning Cikgu Gopal stay as-is.

## Phase 4 — Fixture org #2 proof + the guard (one commit)

1. **Org-2 rendering tests** (extend `test_email_branding.py`): a fixture org (`code='inspire'`, its own programme name/sign-off/persona/`email_from='hello@inspire.example'`/`frontend_url`) — assert its name/sign-off/sender/persona/URL appear and NO "BrightPath"/"halatuju.xyz"/"Cikgu Gopal" appears anywhere in the rendered output (subject, bodies, from, reply-to). This is the leak test the roadmap demands.
2. **AST grep-guard** per D6, in its own test module. Sanity checks: minimum `send_*` function count (via `inspect.getmembers`), minimum string-constant count scanned — fail loudly, never skip.

## Phase 5 — Verify, close, single deploy

1. Full backend suite (`python -m pytest` — currently 4346; expect growth, ZERO failures/skips) + `makemigrations --check` clean (no model changes expected at all).
2. Confirm `halatuju-web/` has no diffs; no migration files created.
3. Close-out per `Settings/_workflows/sprint-close.md`: CHANGELOG under "Sprint 5 — Per-org branding & email (backend)"; retrospective `docs/retrospective-2026-07-23-sprint5-branding-email.md`; decisions (D4 alias rule at minimum) + lessons if earned; update `halatuju_api/CLAUDE.md` Next Sprint; run `python Settings/_tools/wat_lint.py`; delete scratch files.
4. **ONE push.** Verify both Cloud Build triggers by SHORT_SHA; smoke: a gated endpoint 401-not-500, web 200. (API-only change; the web rebuild is incidental.)

---

## Risks / edge cases

1. `emails.py` renders at request time from cron and best-effort paths — the seam must NEVER raise on a missing org/cohort link (fall through to platform defaults, D3).
2. Bilingual (`_send_bilingual`) and `english_only` paths: the sign-off appears in both EN and BM blocks — snapshot both.
3. `_bold_team` bolds the team name in HTML by matching the literal — after extraction it must match the branding value, not a constant.
4. `reply_to`/`from_email` flow through `_send_html`/`_send` kwargs — make sure the seam's values reach the actual `EmailMessage`, and the goldens assert `from_email`/`reply_to` (not just bodies) so a silent sender regression is impossible.
5. Do NOT rename or re-word any email copy "while you're in there" — extraction only. Byte-identity is the contract.
6. The 125-literal inventory must come from UNFILTERED grep with counts (`lessons.md`: never conclude from a truncated search). Track them off; the org-2 leak test + AST guard are the completeness proof.
