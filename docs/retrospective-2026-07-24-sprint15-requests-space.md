# Retrospective — Sprint 15: Requests space v1 (2026-07-24)

Brief: `docs/plans/2026-07-24-sprint15-requests-space-brief.md`. Executor: Opus 4.8. Ships **dark**
behind `REQUESTS_ENABLED`; the coordinator applies migration 0111 migrate-first and flips the flag
after prod smoke + owner copy review.

## What shipped

An org-section **Requests** area: an org_admin submits a bug report or feature request; an AI
reviewer classifies (bug vs feature per the adjudication rule), estimates the work in **hours**, and
may ask clarifying questions that flow to the requestee **directly**; the owner triages
(authoritative — may reclassify) and sends an **owner-gated** hours quote (`≈N hours, includes M%
margin`); the requestee **accepts / defers / modifies / withdraws**. No money in v1 (no hourly rate
exists yet).

Five commits, one per phase, every commit green:

| Phase | Commit | What |
|---|---|---|
| 1 Backend core | `a8bbefc6` | `OrgRequest` model + migration 0111, `org_requests.py` service, transition matrix, `run_ai_review` + `_parse_draft` |
| 2 Endpoints | `f9b8e71c` | `_OrgRequestsBase` + 14 views, two allowlist serializers + exact-key snapshot, urls, org fence |
| 3 Emails + AI | `86fb570c` | five best-effort emails, post-commit wiring, 503 mapping |
| 4 Frontend | `acff196e` | requestStatus lib + guard, api client, two pages, hub card + badge, i18n ×3 |
| 5 Dark-ship + docs | (this) | dark-by-default proof, CHANGELOG, retro |

## Key decisions honoured

- **AI draft never leaks to the org.** Two SEPARATE serializers (no shared role-conditional field);
  the org one is a plain allowlist `Serializer` with zero model passthrough; an exact-key-set
  snapshot test is the tripwire — the single worst failure (the AI's hours estimate reaching the org
  before the owner approves a quote) fails loudly.
- **One AI seam.** All AI through `contracts._gemini_generate` (mocked in every test, never a live
  call). Auto-run is best-effort post-commit, capped at `ai_run_count ≤ 3`, and never fails the user
  action. Garbage output is stored raw in `ai_draft_note`, never a 500.
- **Dark by default.** `REQUESTS_ENABLED` unset → every route 404s (proved with a no-override test)
  and the hub card is hidden by the same count-probe 404 (no client env var).
- **Org fence CI-enforced.** All 14 view classes classified in `FENCED_OR_EXEMPT`; `OrgRequest`
  added to WATCHED; `# org-fence` pragmas on every raw query. Role denials tested as REAL 403s
  (admin/reviewer/qc/partner/finance) and cross-org as 404 (no existence leak).

## Deviations

- **Baseline test counts.** The brief cited pytest 4363 / jest 688; the repo HEAD was already ahead
  (the concurrent "nudge" work landed migration 0110 + ~17 pytest since the brief was written), so
  the real pre-change baseline was pytest **4380**. The invariant held: 0 failures, 0 skips,
  pre-existing suites unmodified. Final: pytest **4445**, jest **712** (711 pass + the 1 known
  pre-existing `scholarship.test.ts` localStorage fail under local Node 26, held constant).
- **Emails referenced from Phase 2, defined in Phase 3.** The Phase 2 views call the (best-effort,
  try/except-wrapped) email functions before Phase 3 defines them — green because the calls are
  swallowed. Landed the definitions in Phase 3 as the brief sequenced.

## Coordinator hand-off (migrate-first, then flag flip)

**Migration 0111 — `CreateModel OrgRequest`, table `org_requests`.** Apply migrate-first via Supabase
MCP in one transaction: table DDL + `ENABLE ROW LEVEL SECURITY` + deny-by-default policies + the
TD-058 contenttypes workaround; record the `django_migrations` row; Security Advisor → 0. Then single
push. The exact DDL the coordinator must apply is in the executor report. After prod smoke (web 200,
gated 401, requests routes 404 while dark), the owner reviews the rate-card copy + the ms/ta
first-drafts, then flip `REQUESTS_ENABLED=1` via `--update-env-vars` (not a deploy).

## Carry

- **ms/ta first-drafts** for the whole `admin.requests.*` namespace await owner review (the owner is
  a Tamil localisation expert). 84 leaves × 3 locales, parity-checked.
- Record the `deferred` status addition + the hours-quote decision in `docs/decisions.md` at close
  (a coordinator step per the brief).
