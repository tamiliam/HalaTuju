# Retrospective — Sprint 15: Requests space v1 (2026-07-24)

Brief: `docs/plans/2026-07-24-sprint15-requests-space-brief.md`. Executor: Opus 4.8. **Status:
SHIPPED + DEPLOYED + LIVE 2026-07-24** — migrations 0111+0112 applied migrate-first, both Cloud
Builds SUCCESS, `REQUESTS_ENABLED=1` flipped after owner review of the rate-card copy + a UI mock.

## The plan pivot — static rate card → AI-reviewer flow

The roadmap (`docs/plans/2026-07-14-platform-roadmap-draft.md`, Phase 5 / Sprint 15) originally
scoped a **published rate card**: bugs free, features priced in RINGGIT off a fixed table, with
"triage v1 = owner-run with an AI-drafted evaluation … price from the rate card". At the brief
stage the owner locked a different design before a line of code was written: no rate card exists
yet (there is no hourly rate to price against), so v1 quotes in **hours only**
(`≈N hours, includes M% margin`) — the rate card becomes real data later, once enough quoted work
exists to derive one. The AI's role also widened: rather than only drafting a priced verdict for
the owner to approve, it may ask the requestee **clarifying questions directly** (no owner gate on
the *questions* — only the eventual *quote* stays owner-gated). This is a genuine pivot, not an
implementation detail: it changes what "priced" means in v1 (hours, not money) and who the AI talks
to (the requestee, not only the owner). The roadmap's `submitted → triaged → quoted → approved →
scheduled → done/declined` flow also gained an 8th status, `deferred`, so a requestee can park a
quote without either accepting it or forcing a decline/re-submit cycle.

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
| 5 Dark-ship + docs | `ed3efeec` | dark-by-default proof, CHANGELOG, retro |
| 6 Increment (same day, owner-approved) | `d8e34931` | migration 0112 — optional component/urgency/steps-to-reproduce scoping fields, both serializers extended, org-payload snapshot widened 16→19 |

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

## What Went Well

- **The org-fence discipline held under a same-day increment.** Adding three optional fields
  (component/urgency/steps) touched both serializers, and the exact-key-set snapshot test caught
  the exact thing it exists to catch — it forced a deliberate, visible 16→19 key-count update
  rather than letting the org payload silently widen.
- **Dark-by-default meant the increment was risk-free to ship same-day.** Because
  `REQUESTS_ENABLED` was still off when migration 0112 was authored, the owner could approve an
  extra field set without touching the flag-flip decision at all — the two decisions (build vs.
  reveal) stayed cleanly separated.
- **The concurrent income-route session never collided.** Both sessions worked the same repo
  the same day; explicit-path staging and a pull-before-push discipline meant Sprint 15's five
  core commits, the increment, and the unrelated income-route fix (`1c515954`) landed as three
  clean, independently-reviewable diffs with no merge conflict.

## What Went Wrong

1. **The flag was briefly ON before the owner had seen a UI mock.**
   - *What happened:* `REQUESTS_ENABLED` was flipped to `1` for approximately two minutes before
     the owner's request to review the UI visually arrived mid-turn; the coordinator caught this
     and flipped it back off immediately.
   - *Why it happened:* the flip-on ask was sequenced by "is prod smoke clean?" rather than "has
     the owner seen what this looks like?" — for an owner-facing feature, code-level readiness and
     owner-readiness are different gates, and only the first was checked before asking.
   - *What prevents recurrence:* for any owner-facing feature, present the UI artifact (a Stitch
     screen or a claude.ai mock) BEFORE the first flag-on ask, not concurrently with it. No
     workflow file has an obvious single home for this rule yet (it sits across
     `sprint-close.md`/`sprint-start.md`/deployment discipline) — recorded here and in the
     CLAUDE.md Next Sprint carry rather than invented a new doc section for one instance; worth
     folding into a workflow if it recurs.

2. **The executor found another session's uncommitted files in the shared tree, twice.**
   - *What happened:* mid-sprint, the executor's `git status` surfaced files it had not touched,
     left uncommitted by the concurrent income-route session.
   - *Why it happened:* two sessions working the same repo without worktree isolation will
     routinely see each other's in-flight state — this is expected, not a fault.
   - *What prevents recurrence:* nothing new — the executor correctly staged only its own files by
     explicit path (never `git add -A`), which is exactly the discipline
     `parallel-work-isolation.md` already prescribes. No new lesson needed; this is the guidance
     working as intended, noted here only because it happened twice in one sprint.

3. **The brief's cited pytest baseline (4363) was stale within hours of being written.**
   - *What happened:* by the time Phase 1 landed, the real HEAD baseline was already 4380 — the
     concurrent session's migration 0110 + ~17 tests had landed between the brief being written and
     execution starting.
   - *Why it happened:* two sessions committing to the same `main` the same day means any baseline
     captured at brief-writing time is a snapshot, not a contract.
   - *What prevents recurrence:* nothing new — the "code wins over the brief's stated baseline"
     rule already governs this (the invariant checked was 0 failures / 0 skips / pre-existing
     suites unmodified, not a specific starting number), and it worked exactly as intended here.

## Design Decisions

- **Hours-only quotes, no RM figure, in v1.** See "The plan pivot" above — no hourly rate exists
  yet, so pricing would be fabricated. Logged in `docs/decisions.md`.
- **The 8th status, `deferred`.** The roadmap's 7-status flow had no way to park a quote without
  either accepting or declining it; `deferred` sits between `quoted` and `approved`, re-quotable.
  Logged in `docs/decisions.md`.
- **AI clarifying questions flow directly to the requestee; only the quote is owner-gated.** A
  narrower reading of the roadmap's "AI verdict is always a draft" rule — the roadmap's intent was
  to protect the PRICE from reaching an org unapproved, not to gate every AI utterance. Logged in
  `docs/decisions.md`.
- **Component/urgency/steps-to-reproduce as optional Bugzilla-inspired scoping fields** (same-day
  increment, owner request) — all blank-default, never a 400 on omission, so the core flow is
  unaffected for a requester who skips them. Logged in `docs/decisions.md`.
- **Screenshots/attachments deliberately deferred** (TD-172) rather than bolted onto the existing
  applicant-document vault, which is shaped for a different (signed-URL, per-applicant) access
  pattern than a general org-fenced attachment store would need.
- **Quote email to the submitting `org_admin` only**, not the whole org — mirrors the "who acted"
  precedent used elsewhere (e.g. payments sign-off notifications) rather than a broadcast.
- **Withdraw allowed until quoted** (submitted/triaged/quoted, and declinable from deferred) — a
  requestee can always change their mind before the owner has invested triage+quote effort into a
  request; withdrawing after a quote exists routes through decline instead, which requires a
  reason.

## Numbers

- **Commits:** 6 (5 core phases + 1 same-day increment), all green.
- **Migrations:** exactly 2 — `scholarship/0111` (model) + `scholarship/0112` (additive scoping
  fields) — both applied migrate-first to prod, no courses migration.
- **Tests:** pytest 4363 → **4458** (net +95, includes the concurrent session's income-route
  tests); jest 688 → **712** (711 pass + 1 known pre-existing local-Node-26 failure, TD-171).
- **Endpoints:** 16, all org-fenced/classified in `test_org_fence.py`; `OrgRequest` added to
  WATCHED.
- **Serializer surface:** org-visible payload 16 → 19 keys (increment), owner payload unchanged in
  shape (all model fields); zero `ai_*`/`triage_*` leakage in either, pinned by an exact-key-set
  snapshot test.
- **Emails:** 5, all best-effort and seam-compliant (zero brand literals).
- **i18n:** `admin.requests.*`, 102 leaves × 3 locales (en/ms/ta), parity-tested.
- **Cloud Builds:** 2 SUCCESS (`ed3efee`, `d8e3493`), Security Advisor → 0 errors on both
  migrations.
- **Flag state:** `REQUESTS_ENABLED=1`, live, verified via `gcloud run services describe`.

## Deploy (completed)

**Migrations 0111 (`CreateModel OrgRequest`) + 0112 (additive scoping fields), table `org_requests`.**
Applied migrate-first via Supabase MCP in one transaction each: table DDL + `ENABLE ROW LEVEL
SECURITY` + deny-by-default policies + the TD-058 contenttypes workaround; `django_migrations` rows
recorded; Security Advisor → 0 errors on both. Single push for the core five phases, a second push
for the increment; both Cloud Builds SUCCESS. Prod smoke passed (web 200, gated 401, requests
routes 404 while dark). The owner then reviewed the rate-card copy + a UI mock (claude.ai artifact)
and approved; `REQUESTS_ENABLED=1` flipped via `--update-env-vars` (not a deploy); re-smoke
confirmed endpoints role-gated and the Administration hub card visible for org_admin/super.

## Carry

- **ms/ta review of `admin.requests.*` is optional, not outstanding.** The first-drafts (102
  leaves × 3 locales) were reviewed by the owner against the rate-card extract as part of the
  pre-flip copy approval; a deeper Tamil-localisation pass remains available if the owner wants
  one, but nothing is blocked on it.
- **Owner rollout:** brief BrightPath org admins on the new Requests space + rate card; monitor the
  first real requests as they arrive.
- **TD-172** (screenshots/attachments, deferred pending org-fenced file storage design) is the one
  open follow-up from this sprint.
