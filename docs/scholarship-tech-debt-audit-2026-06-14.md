# Scholarship Programme — Technical-Debt Audit (2026-06-14)

**Method:** multi-agent audit, 8 dimensions (structure, duplication, dead code, error handling,
security/PII, tests, web/React, performance). Every finding was then handed to an independent
sceptic agent that re-opened the cited file and tried to refute it. Only findings that survived
verification appear below.

**Headline:** the codebase is **healthy, not rotting** — ~1,214 tests, 2 TODO markers, logic
already split into engines. **0 critical** issues. The debt is **structural + a few real bugs**,
concentrated where the Check-2/Check-3 cockpit churned through 8 rapid review rounds (r4–r8).

| | Count |
|---|---|
| Raw findings | 33 |
| **Confirmed** | **29** |
| Rejected by verification | 4 |
| Critical / High / Medium / Low | 0 / 4 / 12 / 13 |

---

## Fix-order (severity × effort — quick wins first)

### 🔴 Do first — real bug, cheap to fix
1. **Document re-upload can permanently destroy a student's file** *(high, small)* —
   [views.py:504-514](../halatuju_api/apps/scholarship/views.py#L504-L514). On every re-upload the
   code deletes the old Supabase blob **and** the DB row *before* creating the replacement, with no
   transaction. If the create fails, the student's income slip / IC / STR proof is gone from both
   storage and DB with no replacement — irrecoverable PII loss on a live B40 programme.
   **Fix:** create-first, then sweep the stale blob only after success; wrap DB writes in
   `transaction.atomic`. (`_is_single_instance` now hardcodes `True`, so this path runs on *every*
   re-upload of any doc type — not an edge case.)

### 🔴 High value on the hottest admin screen — medium effort
2. **Applicant-detail GET fires 20–30 duplicate document/consent queries (N+1)** *(high, medium)* —
   [serializers_admin.py:286-358](../halatuju_api/apps/scholarship/serializers_admin.py#L286-L358),
   queryset at [views_admin.py:63](../halatuju_api/apps/scholarship/views_admin.py#L63). ~10
   method-fields each re-query the same documents table with no prefetch. Most-opened admin screen,
   1000+ applicants. **Fix:** `prefetch_related('documents','consents','resolution_items',
   'interview_sessions','referees')` + make the engines iterate the prefetched `.all()` in Python.
3. **The same GET also performs DB *writes* and re-runs the verdict engine 2–3×** *(high, medium)* —
   [serializers_admin.py:330-347](../halatuju_api/apps/scholarship/serializers_admin.py#L330-L347).
   `get_resolution_items` calls `sync_resolution_items` + `sync_check2_queries`, which `create()`
   rows and re-run `build_verdict`. A read endpoint that mutates breaks read-replica routing and is
   non-idempotent. **Fix:** move the syncs to the write paths (upload / answer / verdict) or an
   explicit refresh POST; compute `build_verdict` once per request.

### 🟠 Big structural smell — large effort, plan as its own work
4. **Cockpit detail page is a 1,775-line single component** *(high/medium, large)* —
   [admin/scholarship/[id]/page.tsx](../halatuju-web/src/app/admin/scholarship/[id]/page.tsx).
   One function: 24 `useState`, ~20 async handlers, ~1,280 lines of inline JSX with business-rule
   IIFEs. All 8 review rounds landed here. **Fix:** extract panels (VerdictTiles, DocumentsDrawer,
   DecisionPanel, InterviewStage, OutstandingPanel) into co-located components; lift the derived
   gates (`queryingLocked`/`decisionReady`/`approveReady`/`clearAccept`) into the *already-existing*
   `lib/officerCockpit.ts` and unit-test them. (Flagged by two dimensions — structure rated high,
   web rated medium; same file.)

---

## Medium (12)

**Structure**
- `services.py` is a 1,541-line module spanning 6+ responsibilities (49 top-level functions);
  it's the most-imported module in the app — a churn/merge-conflict magnet.
  [services.py](../halatuju_api/apps/scholarship/services.py). *Fix:* split into
  `blockers.py`/`reminders.py`/`assignment.py`/`consent_utils.py`/`decision.py`, keep a thin
  re-export shim. *(large)*
- Engine modules import each other's underscore-private helpers (6 sites: `income_engine.py:32`,
  `verdict_engine.py:42`, `submission_review.py:34`, `resolution.py:213`, `offer_pathway.py:24`,
  `anomaly_engine.py:29`). The privacy convention is false — renaming a `_helper` silently breaks a
  sibling. *Fix:* promote shared helpers to public names or move to a shared util module. *(small)*

**Duplication**
- Income-requirement rules are mirrored verbatim in Python (`income_engine.py`) **and** TypeScript
  (`incomeWizard.ts`) — "keep in lockstep" by comment only. The two patronymic regexes *already*
  differ. *Fix:* drive the wizard from the API's already-returned `requirements`, or add a
  cross-language contract test. *(medium)*
- Identical name/NRIC cross-check block inlined 3× in `income_engine.py` (259-264, 356-361,
  445-450) despite `_name_bucket`/`_nric_bucket` helpers existing. *Fix:* call the helpers. *(trivial)*
- `mother_relationship` and `father_via_bc` are line-for-line identical except the BC field
  ([income_engine.py:72-107](../halatuju_api/apps/scholarship/income_engine.py#L72-L107)). *Fix:*
  one `_bc_link()` helper. *(trivial)*

**Security / PII**
- Admin/super privilege is granted on an **unverified JWT email claim** — no `email_verified`
  check ([courses/views_admin.py:56-65](../halatuju_api/apps/courses/views_admin.py#L56-L65) +
  `middleware/supabase_auth.py`). Supabase's default email-confirmation mitigates it, but there's
  zero backend defence-in-depth. *Fix:* require a verified-email claim before linking an admin row;
  add a regression test. *(small)*

**Tests**
- Student-side querying-lock (`querying_closed` 400) has no test — only the two officer paths are
  covered ([views.py:705-707](../halatuju_api/apps/scholarship/views.py#L705-L707)). *(trivial)*
- `_maybe_autofinalise` error/exception-swallow paths untested — the "never break interview submit"
  guarantee is unverified ([services.py:911-932](../halatuju_api/apps/scholarship/services.py#L911-L932)). *(trivial)*

**Web**
- Single shared `busy`/`error` string couples ~20 unrelated cockpit actions — one in-flight call
  freezes the whole screen, and errors render under the wrong panel. *Fix:* `useReducer` keyed by
  action, or a `useAsyncAction` hook per handler. *(medium)*
- ~20 near-identical async handlers (`doGenerate`…`doReRunVision`) — ~250 lines of boilerplate with
  an existing error-handling inconsistency. *Fix:* a `runAction()` helper. *(small)*
- Apply form builds all 5 step-UIs as one eager 446-line `sections` object every render
  ([apply/page.tsx:427-872](../halatuju-web/src/app/scholarship/apply/page.tsx#L427-L872)). *Fix:*
  extract per-step components, render only the active tab. *(medium)*

---

## Low (13) — tidy-ups / preventative

**Structure**
- `AdminRecordVerdictView.post` (881-945) inlines profile-finalise orchestration that belongs in a
  service — a *third* copy of the finalise gate (alongside `AdminFinaliseProfileView` and
  `services._maybe_autofinalise`). *Fix:* `services.record_verdict()` + one shared finalise helper.

**Duplication**
- Own-application lookup + 404 idiom re-inlined 5× in `views.py` despite two base helpers existing
  (note the two helpers differ in `select_related`, so unify carefully).
- Reviewer-gate auth prologue repeated in ~23 admin handlers (`get_admin` 30×). A future write
  endpoint that forgets the role check would silently under-protect PII (latent foot-gun;
  `AdminRunVisionView:341` already skips it). *Fix:* a `@require_reviewer` decorator.

**Dead code** *(all trivial deletes)*
- `send_fail_email` superseded by `send_decline_email` ([emails.py:509](../halatuju_api/apps/scholarship/emails.py#L509)); zero call sites.
- Unused imports `Consent`/`Donation`/`CONSENT_VERSION` in `sponsorship.py:19-20`.
- Unused import `is_minor` in `anomaly_engine.py:28`.

**Error handling** *(both trivial — wrap in `transaction.atomic`)*
- Verify-&-accept writes `profile.nric_verified` + application status in two unwrapped saves
  ([views_admin.py:247-254](../halatuju_api/apps/scholarship/views_admin.py#L247-L254)) — partly
  protected by an idempotent retry guard + a DB unique constraint.
- Record-verdict + finalise mutate two models in one request without a transaction (re-runnable).

**Security**
- JWT verifier accepts HS256 *and* JWKS (ES256/RS256) with the alg taken from the token header.
  **Not currently exploitable** (separate key material per branch), but worth hardening: pin a
  fixed asymmetric allowlist and sunset HS256 after ES256 rollout.

**Tests**
- Interview-agenda composition asserted only as "key exists" — seed a known anomaly and assert the
  code appears. (Note: the agenda has no carry-over logic, contrary to the original finding.)

**Web**
- `exhaustive-deps` suppressed on the cockpit load effect (`t` omitted) — harmless today, hides a
  future stale-closure risk.

**Performance**
- Utility-bill checks re-query bills + parent ICs in nested loops on the detail GET (bounded by
  small per-applicant doc counts; folds into the prefetch fix above). *Note: it does NOT re-OCR —
  it reads the persisted `vision_fields` column.*
- Admin sponsor / sponsorship list endpoints are unpaginated, unlike the other list views in the
  same file. Low-cardinality tables, but inconsistent + non-deterministic order. *Fix:* apply
  `FlexiblePageNumberPagination`.

---

## Rejected by verification (recorded so we don't re-flag them)
1. **"Pervasive deferred imports mask a circular dependency"** — false: the import graph is a clean
   DAG (`vision` is a leaf), no cycle exists; the deferred imports could be promoted today.
2. **"Officer-code counter can collide after delete"** — unreachable: no hard-delete path for
   officer items exists, and `code` is never a lookup key (everything keys on `pk`).
3. **"Auto-accept gate logic duplicated in the click handler"** — false: `clearAccept` and
   `decisionReady` are *different* predicates; the real award is backend-gated anyway.
4. **"List endpoint recomputes merit score per row via a heavy engine call"** — over-stated: the
   "engine" is microsecond dict arithmetic on a paginated page; no N+1 (profile is `select_related`).

---

## Suggested grouping into work
- **Small-change / hotfix:** #1 upload data-loss bug (PII safety — should not wait).
- **One focused sprint — "cockpit hot-path + safety":** #2 + #3 (N+1 + GET-writes) + the two
  trivial `transaction.atomic` wraps + the email-verified auth gate + the two missing tests.
- **One refactor sprint — "cockpit decomposition":** #4 (1,775-line page) + shared `busy`/`error` +
  `runAction` helper + lift gates into `officerCockpit.ts`. Largest, but highest future-velocity payoff.
- **Trivial cleanup batch (small-change lane):** the 3 dead-code deletes + 2 duplication helpers +
  unused-import trims — ~1 hour, knocks out 5 low findings.
- **Backend de-duplication sprint (optional):** split `services.py`, promote private helpers,
  `@require_reviewer` decorator, income-rule single-source-of-truth.
