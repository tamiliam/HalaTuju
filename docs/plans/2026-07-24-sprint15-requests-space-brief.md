# Sprint 15 — Requests space v1: Implementation Plan

## Context

Sprint 7 is gated (rule-stability clock, ≈21 Aug); the owner triggered **Sprint 15 — Requests space v1** (Phase 5, owner-go, the only ungated roadmap sprint). Goal: an org-section "Requests" area that turns the feature-ask firehose into managed, priced work — bug/feature forms, an AI reviewer, a status flow, and quotes the org can act on. Planning by Fable; implementation by an Opus 4.8 executor.

**Owner decisions (locked 2026-07-24):**
- **AI-reviewer flow** (supersedes the static-panel v1): the AI assigned to each request (a) classifies bug vs feature per the adjudication rule, (b) estimates work in **hours**, (c) may ask the requestee **clarifying questions** — questions flow to the requestee **directly** (no owner gate); the **quote remains owner-gated** (AI output is a draft until the owner sends the quote).
- **Quotes are denominated in hours only** ("≈N hours, includes M% margin") — no money in v1 (no hourly rate exists yet; that becomes the rate card later). Preset margin ~50%, owner-adjustable per quote.
- Requestee responses to a quote: **accept / reject / defer / modify** — defer parks the quote in a `deferred` state (acceptable later, re-quotable); modify lets the requestee amend the request and returns it to triage.
- Quote email → **submitting org_admin only**. Withdraw allowed **until quoted** (submitted/triaged/quoted; also declinable from deferred). Ships **dark** behind `REQUESTS_ENABLED`; flip after prod smoke + owner review of rate-card copy and ms/ta first-drafts.
- Adjudication rule (published verbatim): *behaviour contradicting the role matrix / manual = bug (free); working-as-documented-but-wanted-different = feature (priced)*.

## Verified facts (three exploration agents, 2026-07-24)

- **Greenfield**: no Request/RateCard/Quote model, endpoint, or UI exists; no prices exist anywhere. Roadmap budget: 1 migration, Medium.
- **Backend conventions**: org-scoped FK to `courses.PartnerOrganisation` (PROTECT); plain tuple `STATUS_CHOICES`; transitions in a service module (`payments.py` shape: domain-error class with string codes, `save(update_fields)`); admin endpoints subclass `_AdminBase` with `_org_scoped`/`_org_allows` (cross-org → 404); **every new `_AdminBase` subclass must be classified in `test_org_fence.py FENCED_OR_EXEMPT`** (CI-enforced) and the new model added to its `WATCHED` tuple; lean `{count}` badge endpoint precedent (`AdminSponsorPendingCountView`); emails thread `branding=None → b = branding or _P`, zero brand literals (AST guard); owner-notify precedent `send_sponsor_interest_admin_email` → `settings.ADMIN_NOTIFY_EMAIL`; **AI must use a sanctioned seam** — `contracts._gemini_generate(prompt, model)` (raises `ContractsError` codes, mocked in tests); flags = `os.environ.get(...) in ('1','true','yes')` default OFF, gated views 404 (`pool_not_available` precedent); leak-sensitive payloads = plain Serializer allowlists + exact-key-set snapshot tests; **deploy = migrate-FIRST via Supabase MCP** (Cloud Build never migrates) with RLS + policies same-transaction + TD-058 contenttypes workaround + Security Advisor to 0. Latest migration: scholarship 0110 → this sprint creates **0111 only**.
- **FE conventions**: Administration hub `IconCard` grid (Sponsors card = template; badge from lean count endpoint, hidden on 404 — that's also how the FE ships dark, no client env var); sponsors page = CRUD list template (status filter, busyId lock, optimistic row replace); `admin-api.ts` contracts block = client template (`adminFetch`/`adminMutate`, typed interfaces); status family = new pure `src/lib/requestStatus.ts` mirroring `applicationStatus.ts` (statuses tuple + complete-literal tone map + label-key fn) with its own guard test (label parity ×3, tone coverage, BANNED-local-map regex); role payload via `useAdminAuth()`; "FE reads the payload, never the rule" view-model helpers; new i18n namespace `admin.requests` needs its own parity/resolution guard; all copy passes Sprint 6 brand-guard + placeholder-parity ({programmeName} auto-injected; no brand literals); forms = controlled components, no library. jest 688 (+1 known pre-existing local Node-26 failure), pytest 4363.
- **Sprint 14 lessons**: test denials as real 403s; derive test enumerations from source; ships-dark = pre-existing suites pass UNMODIFIED; endpoints live under `admin/scholarship/` (codebase reality beats brief wording).

## Design

### Model — `OrgRequest` in `apps/scholarship` (migration **0111**, the only one)

Named `OrgRequest` (grep-unambiguous vs HTTP Request); table `org_requests`; service module **`org_requests.py`** (NOT `requests.py` — name collision with the HTTP library in live imports).

```
KIND_CHOICES   = [('bug','Bug report'), ('feature','Feature request')]
LANE_CHOICES   = [('small_change','Small change'), ('sprint','Sprint')]
STATUS_CHOICES = [('submitted',…), ('triaged',…), ('quoted',…), ('approved',…),
                  ('deferred',…), ('scheduled',…), ('done',…), ('declined',…)]
                  # roadmap's 7 + 'deferred' (owner decision 2026-07-24)

organisation FK courses.PartnerOrganisation PROTECT related_name='org_requests'
submitted_by FK courses.PartnerAdmin PROTECT related_name='submitted_org_requests'
kind / title(200) / description(Text) / status(default 'submitted')

# Clarification thread (AI ↔ requestee, flows free; owner CC'd by email)
clarifications JSONField(default=list)   # [{question, asked_at, answer|null, answered_at|null}]
ai_run_count   PositiveSmallIntegerField(default=0)   # auto-run cap = 3

# AI draft — NEVER in the org-facing payload
ai_draft_kind/'' ai_draft_lane/'' ai_draft_hours Decimal(6,1) null
ai_draft_note(Text,'') ai_draft_model(50,'') ai_draft_at(null)

# Owner triage (authoritative; may reclassify kind per the adjudication rule)
triaged_kind/'' lane/'' triage_note(Text,'') triaged_at(null)

# Owner quote (hours only, v1)
quote_hours Decimal(6,1) null; quote_margin_pct PositiveSmallIntegerField null
quote_note(Text,'') quoted_at(null)

approved_at(null) scheduled_for(Date null)
decline_reason(Text,'') declined_by_role(20,'')     # 'super'|'org_admin' (withdraw audit)
created_at/updated_at; Meta db_table='org_requests', ordering=('-created_at',); __str__
```

Settings: `REQUESTS_ENABLED` (default OFF), `REQUESTS_TRIAGE_MODEL` (default `gemini-2.5-pro`), `REQUESTS_QUOTE_MARGIN_PCT` (default `50`).

### AI reviewer — `org_requests.run_ai_review(req)` via `contracts._gemini_generate`

Prompt = kind/title/description + answered clarifications + adjudication rule + lane definitions → strict JSON `{classification, lane, estimated_hours|null, clarifying_questions[0-3], rationale}`. Defensive parse (strip fences, clamp enums, Decimal try/except; garbage → raw text into `ai_draft_note`, never a 500). Runs **automatically, best-effort** after create and after each clarification answer (synchronous post-commit, try/except — never fails the user action; capped by `ai_run_count ≤ 3`), plus a super-only manual re-run endpoint. New questions from the AI are appended to `clarifications` and emailed to the submitter directly (owner decision: questions flow free); the hours estimate stays in `ai_draft_*` — **owner-gated**. `ContractsError` → mapped codes (`triage_ai_unconfigured`/`triage_ai_unavailable`); manual triage always works.

### Transition / actor matrix (enforced in `org_requests.py`; views re-gate)

| Action | From → To | Actor |
|---|---|---|
| create | — → submitted | org_admin (own org); super (+organisation_id). Owner emailed; AI auto-runs |
| answer (clarification) | no transition (submitted/triaged) | submitting org's org_admin. AI auto-re-runs; owner emailed |
| ai rerun | no transition (submitted/triaged) | super |
| triage | submitted → triaged | super (sets triaged_kind + lane; may override AI) |
| quote | triaged → quoted | super; feature only (`bug_is_free`); hours>0; margin defaults from settings; email submitter |
| schedule | triaged → scheduled | super; bug only (free lane skips quote) |
| accept (approve) | quoted/deferred → approved | submitting org's org_admin; super (recorded). Owner emailed |
| defer | quoted → deferred | org_admin (own org) |
| re-quote | deferred → quoted | super |
| modify | quoted/deferred → submitted | org_admin (own org): amends description (old text appended to clarifications as history); AI re-runs |
| schedule | approved → scheduled | super (optional date) |
| done | scheduled → done | super. Terminal |
| decline / withdraw | submitted/triaged/quoted/deferred → declined | super (reason required); org_admin own org (withdraw, reason optional). `declined_by_role` recorded. Terminal |

Error codes: `wrong_role, bad_transition, bug_is_free, bad_hours, reason_required, triage_ai_unconfigured, triage_ai_unavailable, bad_kind, bad_lane, ai_limit_reached, not_answerable`.

### Endpoints (scholarship `urls.py`, `admin/scholarship/requests/`; ALL flag-gated 404-first via `_OrgRequestsBase(_AdminBase)`)

| Path | Method | Roles (others → real 403) | Fence class |
|---|---|---|---|
| `requests/` | GET | org_admin (fenced), super | FENCED (`_org_scoped(field='organisation_id')`) |
| `requests/` | POST | org_admin, super(+org id) | FENCED (org forced to caller's) |
| `requests/count/` | GET | org_admin, super | FENCED (super: global `submitted`; org_admin: own `quoted`+unanswered questions) |
| `requests/<pk>/` | GET | org_admin (own, else 404), super | FENCED |
| `<pk>/answer/`, `<pk>/approve/`, `<pk>/defer/`, `<pk>/modify/`, `<pk>/decline/` | POST | org_admin (own, else 404); super also on approve/decline | FENCED |
| `<pk>/triage/`, `<pk>/quote/`, `<pk>/requote/`, `<pk>/schedule/`, `<pk>/done/`, `<pk>/ai-rerun/` | POST | super | EXEMPT-super-only (documented) |

All new view classes classified in `FENCED_OR_EXEMPT`; `OrgRequest.objects` added to `WATCHED` with `# org-fence:` pragmas.

**Serializers** (plain allowlists, `serializers_admin.py`): `OrgRequestOrgSerializer` — id, kind, title, description, status, clarifications, quote_hours, quote_margin_pct, quote_note, quoted_at, approved_at, scheduled_for, decline_reason, created/updated, submitted_by_name. **No `ai_*`, no `triage_note`** — exact-key-set snapshot test (the single worst failure would be the AI draft leaking to orgs). `OrgRequestOwnerSerializer` — all fields + org id/name.

**Emails** (emails.py, branding-seam, English, best-effort): submit→owner; AI questions→submitter; answer→owner; quote→submitter (submitting org_admin only); accept→owner.

### Frontend

- `src/lib/requestStatus.ts` (8-status tuple, tone map, label keys, `requestActionsFor(role, status, triagedKind, hasUnansweredQuestions)`) + guard test (label parity ×3, tone coverage, BANNED-local-map regex over the new pages).
- `admin-api.ts` requests block (typed Summary/Detail, list/get/create + verb actions + `getOrgRequestCount`).
- `src/app/admin/requests/page.tsx`: rate-card panel (i18n: bugs FREE; adjudication rule; "features are estimated in hours by an AI reviewer and quoted with the owner's approval — quotes state hours incl. margin"), submit form (kind select per contact-form pattern), list (status filter, badges).
- `src/app/admin/requests/[id]/page.tsx`: detail + clarification thread (Q&A list; answer box for the submitting org's admin); org actions accept/defer/modify/withdraw; super controls triage/quote(hours+margin prefilled from settings)/requote/schedule/done/decline/AI-rerun. All action visibility from `requestActionsFor` (keep-in-step comment → `org_requests.py`).
- Administration hub card (🎫, ORGANISATION section, manage branch only — admin/finance get 403 server-side and no card), badge from count endpoint, card hidden when the probe 404s (dark-ship, no client flag).
- i18n `admin.requests.*` en/ms/ta (British English; ms/ta first-drafts for owner review) + `admin-requests-i18n.test.ts` parity/resolution guard. All copy clears brand-guard + placeholder-parity.

### Phases (one commit each, every commit green: pytest/jest/build/lint; executor NEVER pushes)

1. **Backend core**: settings flags; `OrgRequest` model + migration 0111 (verify exactly one new file, no courses migration); `org_requests.py` (transitions map, all actions, `run_ai_review` + `_parse_draft`); `test_org_requests.py` — matrix derived from the TRANSITIONS source, terminal refusals, bug_is_free, withdraw/defer/modify paths, ai cap, parse fuzz (good/fenced/garbage/bad-enum JSON), seam mocked + ContractsError mapping.
2. **Endpoints**: `_OrgRequestsBase` + views; two allowlist serializers + exact-key snapshot (no `ai_*` leak); urls; org-fence classification + WATCHED + pragmas; tests — two-org isolation, cross-org 404s, real 403s for admin/reviewer/qc/partner/finance on list+detail+one write, `@override_settings(REQUESTS_ENABLED=False)` → 404 on every route.
3. **Emails + AI wiring**: five send functions (seam-compliant, zero literals — AST guard stays green); post-commit wiring (create/answer/quote/accept); auto-run + cap behaviour; 503 mapping when AI unconfigured.
4. **Frontend**: requestStatus lib + guard, api client, two pages, hub card + badge, i18n ×3 + namespace guard. Gates incl. brand-guard + placeholder-parity.
5. **Dark-ship proof + docs**: flag-off = zero behavioural diff (pre-existing suites pass UNMODIFIED; FE card hidden; direct nav graceful); CHANGELOG; retro notes for close.

### Verification & deploy (coordinator, after owner sees the report)

1. Executor report verified (counts, snapshots, fence suite, guards).
2. **Migrate-first**: apply 0111 via Supabase MCP — same transaction: table DDL + `ENABLE ROW LEVEL SECURITY` + deny-by-default policies + TD-058 contenttypes workaround; `django_migrations` INSERT; Security Advisor → 0 errors.
3. Single push → both Cloud Builds by SHORT_SHA; smoke (web 200, gated 401, requests endpoints 404 while dark).
4. Owner reviews rate-card copy + ms/ta drafts → flip `REQUESTS_ENABLED=1` via `--update-env-vars` (not a deploy); re-smoke (endpoints now role-gated; card appears for org_admin/super).
5. Sprint close per workflow + memory update. Record the 'deferred' status addition + hours-quote decision in decisions.md.

### Risks

- **AI draft leaking to orgs** → separate allowlist serializers + exact-key snapshot; org/owner payloads never share a serializer.
- **AI cost runaway** → auto-run capped at 3 per request; owner-triggered re-runs beyond that; Gemini failure never blocks manual flow.
- **Fence regression** → CI-enforced classification + WATCHED; two-org behavioural tests.
- **Migration budget** → single 0111; `makemigrations --check` clean after.
- **Sync AI on submit adds latency** → best-effort post-commit with try/except; form success never depends on it.
- **Quote/answer races** → linear status flow + `bad_transition` guards; optimistic row replace surfaces refreshed truth.

### Execution

Executor: **Opus 4.8** agent (per owner), commits locally per phase, never pushes. Coordinator (Fable): verify → migrate-first → single push → smoke → owner copy review → flag flip → sprint close (Sonnet, per pattern) → memory.
