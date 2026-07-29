# Configuration layers — Layer 0, then Layer 1

**Approved by the owner 2026-07-28.** Route in: `Settings/_workflows/implementation-planning.md`.
This file is the durable home; the working plan file under `.claude/plans/` is deleted at sprint close.

---

## Why this exists

Suresh (BrightPath's `org_admin`) wants his own UI/UX team to shape how things are organised across
the student application, the console and the sponsor portal. The owner's governing concern is not
the design — it is durability:

> *"Suresh's team may have the enthusiasm today, but this may not last. And we don't want to end up
> with a broken system."*

That rules out the obvious answers. Repo access makes an external team a third party to a system
processing applicants' personal data — the same category as the DPA already blocking tenant #2 —
and anything they hand-build rots when they lose interest. The durable answer is **configuration**:
an organisation changes what it needs through controls we built and tested, so the capability
survives whoever holds the job.

### The owner's three layers

| | Covers | Decision |
|---|---|---|
| **Layer 0** | What a programme ASKS FOR — documents, questions, requirements | **Build first** |
| **Layer 1** | Colours, text, background, light/dark — "a click of one or a few buttons" | **Build second** |
| **Layer 2** | Moving elements around | **NOT built** — *"I do not want to build Layer 2 stuff."* |

### Owner decisions taken during planning (do not re-litigate)

1. **Sandbox now, no repo access.** Suresh's team gets a fake-data surface, not the codebase.
2. **Layer 0 is CATALOGUE-ONLY.** Organisations tick from a set we build and translate. They never
   author free text. New catalogue items remain our work.
3. **Layer 0 DOES cover the student application** — an organisation configures what its programme
   *asks a student for*, but never how the journey is laid out. One journey, different contents.
4. **Build order: Layer 0 first.**
5. **Layer 2 descoped**, and nothing may prepare for it (see the constraint below).

### Twelve sprints, but only five are new

Sprints 6–12 are the **themes arc already owed** since 2026-07-28 (`2026-07-27-nav-ia-roadmap.md`
§"Theming is NOT part of this roadmap"). Suresh's request adds Sprints 1–5. Phase 2 is approved
separately, after Layer 0 lands. Nothing in Phase 1 depends on Phase 2.

---

## Layer 2 — not built, but deliberately NOT closed off

**Owner, 2026-07-28:** *"While I do not want to build layer 2, I want to have some option to do it.
I do not want to completely close that option."*

That is a real distinction and it changes what we owe. There are two different things:

| | Where it lives | Verdict |
|---|---|---|
| **Keeping the option open** | In this document, and in the SHAPE of the code | **Yes — do this** |
| **Leaving a placeholder** | In the code, as a stub, column, flag or format | **No — see below** |

**What would genuinely CLOSE the option**, and is therefore forbidden even though Layer 2 is not
being built:
- A page written as one undivided blob, so no part of it has a name or a boundary.
- A section that reaches into shared mutable state rather than taking what it needs as arguments —
  it then cannot be rendered anywhere else.
- A section whose correctness depends on another having rendered first.
- Styling that assumes a fixed position ("this card is always second, so it needs no top margin").

**What keeps it open, and costs nothing** because each is better code on its own terms:
- Every section a named component that takes explicit inputs.
- No positional styling assumptions.
- No order-dependent side effects between sections.

Each page touched during the Phase 2 repaint should be *left* in that state. Not as groundwork —
as ordinary quality, which happens to mean that if Layer 2 is ever approved it starts from a
tractable position rather than a rewrite.

**Revisit if:** the owner approves Layer 2, at which point this section becomes its brief.

## ⚠ Standing constraint — the option stays in the DOCUMENT, never as a stub in the code

`docs/lessons.md`: *"A placeholder for future work encodes an assumption about that work — if the
assumption is not yours to make, do not leave the placeholder."* Written after a reserved `theme`
key was deleted from `src/lib/uiPrefs.ts` for silently asserting that a theme is a device preference.

**No sprint here may add** a layout registry, a layout document format, a `layout`/`order`/`position`
column, a `sort_order` field justified only by future re-ordering, a disabled "arrange" control, or
a comment reserving a seam.

**The only permitted forward-compatibility** is extracting a page section into a named component
**where that is justified on its own merits** (a 1,899-line file is unreadable; a section needs its
own test) **and only on a page the sprint is already touching**. If the sole argument is "this helps
later", don't.

**Why the option lives here and not in the code.** A stub encodes a guess about *how* Layer 2 would
work — that order is a stored integer, that it belongs to a programme rather than a person, that
hiding and reordering are the same feature. A later sprint finds the stub, reads it as settled, and
builds on a guess nobody made deliberately. That already happened once on this project: a reserved
`theme` key in `uiPrefs.ts` silently asserted that a theme is a device preference, which was
precisely the open question. A sentence in a roadmap can be re-read and changed; a column in a
schema acquires callers.

A later sprint reading this file must treat the section above as an intention to preserve
FLEXIBILITY, never as a design for Layer 2 and never as permission to start it.

### The POSITIVE half of the same constraint — how the option is actually kept open

Owner, 2026-07-29: *"I am NOT narrowing the scope. Maintain the planned scope, including optionality
for Layer 2 in future."*

Banning stubs is only half the instruction, and on its own it reads as "do nothing", which is the
wrong lesson. **Layer 2 stays possible through decisions that are already correct for Layer 1** —
none of which is a placeholder, and every one of which is justified on its own merits today:

| Decision | Why it is right for Layer 1 | Why it happens to keep Layer 2 open |
|---|---|---|
| `data-theme` + CSS variables, never Tailwind's `dark:` | a tenant tint cannot be expressed as a compiled class pair | a theme stays DATA; a third theme, or a per-section override, is a new variable set, not a new build |
| Semantic tokens (`--surface-*`, `--text-*`, tone families) | an organisation tints meaning-free ground, not meaning | a moved section carries its own tones with it and cannot land somewhere it reads wrong |
| Page sections as NAMED components taking props | a 1,899-line file is unreadable and untestable | a thing with a name and a boundary is a thing that could later be ordered; inline markup is not |
| Section visibility COMPUTED from configuration at render | Layer 0 already collapses a section whose documents are all off | order and visibility stay derived, so neither has to be un-stored later |

**The distinction that matters:** do not RESERVE anything, and do not FORECLOSE anything. A reserved
`layout` column is a guess about Layer 2. A 500-line inline JSX blob with no component boundaries
forecloses it — not because it lacks a stub, but because there is nothing there to move. Neither is
acceptable; the middle is simply writing Layer 1 well.

**Do not read this table as a Layer 2 design.** It is a list of Layer-1 decisions with a favourable
side effect. If a future sprint finds itself arguing for something on this table *because of the
right-hand column*, the argument has already gone wrong.


## ⚠ Migration numbers are NOT reserved here

The roadmap originally pencilled `0134` for Sprint 2. By the time it was approved, another agent had
shipped `0134_sponsor_terms.py`. **Re-derive the number at sprint start, never from this file.**
TD numbers collided twice on 2026-07-28 for the same reason; this is the third instance.

---

# Phase 0 — the sandbox

## Sprint 1 — A fake-data sandbox Suresh's team can open in a browser

**Goal.** A hosted URL rendering the real components against synthetic data — no repo access, no
login, no real personal data, and unable to render in production.

**Scope.** New `halatuju-web/src/app/sandbox/**`, `halatuju-web/src/sandbox/**` (typed fixtures,
`stubFetch.ts`, `providers.tsx`, `__tests__/sandbox-safety.test.ts`).

**Design calls.**
- **Route outside `/admin`.** The route-drift test in `src/lib/__tests__/navigation.test.ts` fails
  the build for any unregistered `/admin/<x>` page, and a registry entry means a visible menu row in
  production. `/sandbox` needs neither, and is the honest shape: the sandbox is not part of the console.
- **Build-time env guard**, not a runtime check — `NEXT_PUBLIC_SANDBOX` unset ⇒ `notFound()`,
  mirroring `NEXT_PUBLIC_ORG_CODE` in `src/lib/branding-context.tsx`.
- **Do not export** the ~25 in-file components in `src/components/ScholarshipDocuments.tsx`. Mount
  default exports; stub the providers and `window.fetch`. Precedent: the ~90-line throwaway stub page
  from nav/IA N2 that mounted real console components with a stubbed identity (`docs/lessons.md` —
  *"build the smallest thing that RENDERS the work"*).
- **Anti-drift is the compiler.** Fixtures are TypeScript typed against the real interfaces
  (`ScholarshipApplication`, `ApplicantDocument` in `src/lib/api.ts`; `AdminScholarshipDetail` in
  `src/lib/admin-api.ts`). A JSON fixture rots silently; a typed one cannot. Plus an import guard —
  **the sandbox may contain mounts, never markup.**
- A safety test scans fixtures for NRIC-shaped strings and live-roster names, in the posture of
  `src/lib/__tests__/brand-guard.test.ts`.

**Does NOT.** No editing (Sprint 5). No Storybook. No second copy of any screen. No auth.

**Acceptance.** `next build` clean with the var unset **and** `/sandbox` absent from the output;
safety + import-guard tests pass; owner opens the URL and sees the apply form, Documents tab, Action
Centre, cockpit and a sponsor card.

**Complexity: medium** (~16 files).

---

# Phase 1 — Layer 0 (what a programme asks for)

## Sprint 2 — The catalogue and the read seam, provably inert

**Goal.** A catalogue, a per-programme selection table, and one function every gate will later ask —
with **zero behaviour change**, proven by the existing suite passing unmodified.

**Scope.** `apps/scholarship/models.py` (two models + migration — **re-derive the number**), new
`apps/scholarship/requirements.py` (the seam), a seed command, `src/messages/{en,ms,ta}.json`.

**Model.**
- `ApplicationItem` — the catalogue, our content, never org-authored: `kind` (`document`|`question`),
  `code`, `label_key`, `is_core`, `default_on`, `is_active`.
- `ProgrammeApplicationItem` — the selection: `programme`, `item`, `state` (`off`|`optional`|`required`),
  unique on (programme, item).

**Verified constraint.** For `kind='document'`, `code` **must** be a value in
`ApplicantDocument.DOC_TYPES` (`models.py:1040`) — a closed list of 19 types, each with recognition
logic, a versioned model and verification behaviour attached. **The catalogue names an existing type;
it never invents one.** This is what makes "catalogue, not form builder" real rather than a slogan.

**Hold the income boundary.** `services.income_doc_blockers` (`services.py:2094`) is a route engine —
STR route vs salary route, per-member evidence — not a list. **One** catalogue item, `income_proof`,
on or off. Decomposing that tree breaks "engine logic stays programme-agnostic" and is precisely
where BrightPath gets broken.

**Acceptance.** Existing `pytest` suite passes **unmodified** — that, not the new tests, is the
evidence. A test asserts `requirements.required_documents()` for BrightPath equals the literals still
present in `services.py` (they stay this sprint so the seam can be diffed against them). RLS enabled
on new tables; migrate-first via Supabase MCP; `check-i18n.js` clean.

**Complexity: medium** (~14 files).

## Sprint 3 — Documents: the catalogue governs, everywhere it matters

**Goal.** A document switched off is not asked for, not gated on, not chased, and reads red nowhere —
with BrightPath byte-identical.

**Scope.** `services.py` (`application_completeness` 1851, `consent_blockers` ~2210, `_offer_blocks`
2180, `document_red_blockers` 2270), `verdict_engine.py` (`build_verdict` 1145), `resolution.py`
(`sync_resolution_items` 122), `check2_queries.py`, the serializers; front end
`src/lib/scholarship.ts`, `src/components/ScholarshipDocuments.tsx`, `ActionCentre.tsx`,
`src/app/admin/scholarship/[id]/page.tsx`.

**Two calls decide whether this works.**
1. **The front end reads the resolved set from the payload, never mirrors the rule.** Precedent:
   `finance_check_required` on the payments payload. This also closes an existing drift —
   `COMPULSORY_DOC_TYPES` (`src/lib/scholarship.ts:1096`) is `['ic','results_slip']` while the backend
   gates on more. **The two sides already disagree; Layer 0 collapses them into one source.**
2. **A fact with no required evidence is OMITTED from `build_verdict`** — not green (which asserts we
   verified something) and not red (which asserts a gap that isn't one). Highest-risk change in the
   roadmap; check `officerCockpit.factTileTone` and `verdict_narrative._fact_band` first.

**Risk + mitigation.** A switched-off document could leave a stale ticket open, or move a submitted
student's gate. `sync_resolution_items` already auto-resolves system items — assert it. And **snapshot
the resolved set at submit** (the shape exists in `services.build_intake_snapshot`) so a tick today
never re-gates yesterday's applicant.

**Acceptance.** Existing suite unmodified for BrightPath. A second seeded programme with the offer
letter off proves: no blocker, no Pathway fact, no ticket, no Check-2 request, no card.

**Complexity: high** (~30 files). Do not add the admin screen to it.

### ✅ Sprint 3a SHIPPED 2026-07-29 (`92784b20`, live `halatuju-api-00901-485`) — backend half only

Gates, blockers, income switch and verdict facts read the seam. 5022 pytest, no existing test edited.
Production catalogue **seeded** (8 documents / 10 questions, 0 programme overrides). Retro
`docs/retrospective-2026-07-29-layer0-documents-gate.md`.

**⚠ FOUR RULES FROM 3a's NEAR-MISS — BINDING ON 3b AND EVERY LATER SPRINT.** An application WITH a
programme against an EMPTY catalogue resolved to "requires nothing", which would have let all 60
students inside the submission gate submit with no documents. **The full suite passed throughout**,
because no fixture seeds the catalogue, so every test took the fallback branch and none took the new one.
1. An empty config source means **"not configured"**, never "requires nothing" — fall back to the OLD
   behaviour, per kind.
2. Write at least one test from **production's shape**, not from what the code is meant to do.
3. **Disable a new guard and watch the tests fail** before trusting it.
4. When a sprint consumes what an earlier sprint **deferred**, that deferral is in this change's blast
   radius.

### ✅ Sprint 3b SHIPPED 2026-07-29 — the front end reads the payload. **SPRINT 3 IS NOW COMPLETE.**

`requirements.documents.{required,optional}` on the student payload; `documentRequirement()` /
`asksForDocument()` are the only readers; `COMPULSORY_DOC_TYPES`, `OTHER_OPTIONAL_DOC_TYPES` and
`documentsComplete()` deleted. **NO migration.** 5077 pytest · 1137 jest · both configurations reviewed
in a browser before merge. Retro `docs/retrospective-2026-07-29-layer0-documents-frontend.md`;
decisions ×3; lessons ×3.

**What scoping found that this section did not predict:** the rule existed in FOUR places, not two, and
the two named constants were nearly dead — consumed only to build the `DocType` union, with
`documentsComplete()` having no caller outside its own test. What actually governed what a student saw
was the JSX, four hand-written sections each asserting its own `required: true`.

**⚠ A FIFTH RULE, and it generalises rule 4 above.** `school_leaving_cert` had been rendered by the
Documents tab for months while missing from the catalogue, from `OTHER_OPTIONAL_DOC_TYPES`, and from
the `DocType` union (it compiled because the card helper takes a bare `string`). Harmless while nothing
read those lists to decide what to DRAW — and a silent withdrawal of a live document the moment the
catalogue started governing the render.
5. **When a sprint changes what a list is USED for, everything that list ever omitted is in the blast
   radius. A list nobody reads is never wrong.** Before wiring a source of truth into a new consumer,
   diff it against the thing it now claims to govern.

**Two boundaries this sprint set, which Sprint 4 must not blur:**
- **A missing `requirements` block degrades to `'optional'`** — every card renders, nothing marked
  compulsory. Not `'off'` (blanks the page) and not a front-end copy of the platform defaults (the
  mirror we just deleted). The front end displays; the server gates. Same shape for questions.
- **`DOC_TYPES` stays a static literal.** What a programme ASKS FOR is configuration; what a document
  type IS is not. Sprint 4's question codes are the same: an organisation ticks "ask about
  aspirations", it never authors a question.

**Production at close:** 9 document items · **0 programme overrides** · 143/143 applications carry a
programme · 41 inside the submission gate. With no overrides every application resolves to the
defaults, so the deploy is a no-op for BrightPath bar the offer letter and income section gaining the
compulsory marker they always deserved.

**Carried into Sprint 4:** the `requirements` block currently carries `documents` only, pinned by a
test — adding `questions` is a deliberate edit to `test_the_payload_carries_only_the_documents_block_for_now`.
**TD-197** (the catalogue's `apply.*` label keys have no messages behind them) belongs to Sprint 5, not 4.

## Sprint 4 — Questions: the catalogue governs the student application

**Goal.** A programme configures which questions it asks. One journey for every tenant, different contents.

**Scope.** `services.py` completeness parts (`details_done` 1877, `_family_done` 1941, funding 1886),
the serializers, `FundingNeed.categories` (`models.py:1002`); `src/app/scholarship/apply/page.tsx`,
`src/lib/scholarship.ts` (`ApplyFormState`, `buildApplicationPayload`), `ScholarshipReview.tsx`, the
message catalogues.

**The line that holds.** `TAB_ORDER` and `NEXT_STEP_ORDER` are **not** configurable. A section whose
questions are all off collapses out at render time — computed, never stored, never orderable. A stored
step list is Layer 2 in disguise.

**Also holds.** Free text is never org-authored. An organisation ticks "ask about aspirations"; the
wording is ours, in three languages, parity-enforced by `scripts/check-i18n.js`.

**Does NOT.** No org-authored text. No new question types. No conditional branching (a rules engine,
and not what was asked for).

**Acceptance.** Existing suite unmodified. A test programme with two questions off renders without
them, completes, and the generated sponsor profile doesn't mention them — audit
`profile_engine._build_prompt` for "absent means absent, not zero" (the `_gated_str` pattern).

**Complexity: medium-high** (~26 files).

## Sprint 5 — The screen Suresh's team actually touches

**Goal.** An `org_admin` ticks what their programme asks for, sees it in the sandbox, and cannot break
anything.

**Prerequisites.** Sprints 3 and 4 — a switch that governs nothing is a lie. **Stitch prototype
approved before any page code** (house rule).

**Scope.** New `src/app/admin/programme/page.tsx` (the `programme` nav scope already exists), a
`NAV_GROUPS` entry in `src/lib/navigation.ts` (or the route-drift test fails), one `_AdminBase`
subclass in `views_admin.py`, and **a `FENCED_OR_EXEMPT` entry in
`apps/scholarship/tests/test_org_fence.py` or CI fails by design.**

**Design calls.** Gate to `org_admin` + `super`. **Three states — Off / Optional / Required** — a binary
tick cannot express the optional documents that already exist. Core items render **locked with the
reason**, not hidden ("Identity card — always required" is information; a missing row is a mystery).
Every change writes an `AUDIT` line. A live-applicant warning before saving. "Ask for a document we
don't have" links to the existing Requests space (`OrgRequest`) — don't invent a second mechanism.

**Risk + mitigation.** The catalogue must never be mistaken for a fence. State it in the module
docstring as `src/lib/navigation.ts` already does; the org fence (`_org_scoped`/`_org_allows`,
cross-org ⇒ 404) is untouched. The 2026-07-15 surface-partition lesson applies verbatim.

**Acceptance.** Cross-org write returns 404 not 403. Owner ticks the water bill to Required, sees it
appear in the sandbox, unticks it, sees it go.

**Complexity: medium** (~18 files).

---

# Phase 2 — Layer 1 (themes) — APPROVE SEPARATELY

Not approved yet. Summarised so the shape is on record.

| # | Goal | Notes | Complexity |
|---|---|---|---|
| 6 | **Semantic token vocabulary** | Derived by auditing the literals FIRST, not invented. Ground (`--surface-*`, `--text-*`, `--border-*`), tone (`positive/info/caution/critical/neutral` — the convention `components/InfoBox.tsx` already enforces, given names), and a separate `--scale-*` family for the ordinal grade badges. **`data-theme` + variables, never Tailwind's `dark:`** (which hard-codes a two-theme world and doubles every class in 114 files). **`--brand-*` is tenant identity — a theme must never write it**; add a test. | medium (~20) |
| 7 | **Sponsor portal repaint** | 12 files, 204 chromatic literals. Smallest surface, worst ratio — **1** use of `primary-N` against 90 `blue-N`. Falsifies the vocabulary cheaply. Named hazards: the `DOT`/`tone` class-string Records at `src/app/sponsor/(portal)/page.tsx` ~225–286 and the raw-hex `conic-gradient` donut at line 32. | medium |
| 8 | **Student surfaces repaint** | Highest traffic; the surface an organisation's brand is judged on. | medium-high |
| 9 | **Shared components repaint** | 67 files, 561 literals. **Split into two passes at measurement** — do not force one 67-file sprint. | high |
| 10 | **Admin console** minus the cockpit | 49 `primary-N` against 200 `blue-N`. | medium-high |
| 11 | **The cockpit** | `src/app/admin/scholarship/[id]/page.tsx`, 510 literals — the worst file in the repo, and the one place section extraction is justified on readability alone. | high |
| 12 | **The theme switch and the flip** | Blocked on the ownership question below. | medium |

Each repaint sprint lowers a `palette-guard.test.ts` ceiling that may only fall, and **ends with a
browser pass in both themes on the sandbox** — a passing test is not the evidence here (see the
lesson about bulk edits matching but not reading correctly).

**Measured input:** 1,858 chromatic palette literals across 114 files (4,860 including neutrals; 112
raw hex in 20 files) against 624 uses of the themed `primary-N`. Dark-mode readiness is zero — no
`darkMode` key, no `dark:` variants, no `prefers-color-scheme`, no `data-theme`.

---

# Verification (all sprints)

- `pytest` (scholarship + courses), `jest`, `tsc --noEmit`, `node scripts/check-i18n.js`, `next build`.
- Migrations applied **migrate-first via Supabase MCP**, then `makemigrations --check`.
- **The byte-identity claim for Layer 0 is the existing suite passing UNMODIFIED** — a new test cannot
  make it. Golden snapshots captured before the refactor, as the July branding extraction did.
- `test_org_fence.py` classifies every new `_AdminBase` subclass or CI fails.
- **TD-194** — local console review is still impossible (no local API, no localhost CORS). A second
  reason Sprint 1 comes first.

---

# Open — owner's to answer, not the agent's to default

**~~Blocks Sprint 1's DEPLOY~~ — ANSWERED 2026-07-28: Google-account allowlist.**
Access is Identity-Aware Proxy, which Cloud Run now supports **directly** (`gcloud beta run
services update --iap`) — no external load balancer, so no ~RM80/month for one. Designers sign in
with their own Google account; no account is created in HalaTuju, and the sandbox holds no real
data either way. The image is the same `halatuju-web/Dockerfile` built with
`--build-arg SANDBOX=1 --build-arg API_URL=https://api.invalid`; both arguments default to the
production values so an ordinary build is unchanged.
**✅ DEPLOYED AND WORKING 2026-07-28.** `https://halatuju-sandbox-l6l7b6xaia-as.a.run.app/sandbox`
— IAP redirects to Google sign-in; only allowlisted addresses get through.

| | |
|---|---|
| Service | `halatuju-sandbox`, `asia-southeast1`, revision `00001-gc9` |
| URL | `https://halatuju-sandbox-l6l7b6xaia-as.a.run.app` |
| Build | `halatuju-web/cloudbuild.sandbox.yaml`, run by hand — **deliberately no trigger** (an automatic rebuild would move the ground under a review in progress) |
| Access | `--no-allow-unauthenticated` + IAP enabled; `roles/run.invoker` granted to `tamiliam@gmail.com` and the IAP service agent |
| OAuth | **Custom OAuth client `HalaTuju Sandbox IAP`** — NOT the live `HalaTuju Web` client |
| Allowed | `tamiliam@gmail.com` only |

**⚠ THE TRAP, WRITTEN DOWN BECAUSE IT COSTS AN HOUR TO REDISCOVER.** Enabling IAP on Cloud Run
leaves it on **Google-managed OAuth**, which is the default and is described in the console as
*"recommended for simplicity"*. On a project with **no organisation** — which HalaTuju is, see
`memory/halatuju_org_status.md` — Google cannot self-provision the client, and every request
returns a bare `502` whose body is the only clue:

> `x-goog-iap-generated-response: true`
> `Empty Google Account OAuth client ID(s)/secret(s).`

The container is healthy throughout; the failure is entirely in front of it. The console's own
small print names the condition — Google-managed is *"best suited for apps for users within your
organisation"* — but it is selected by default and nothing warns you.

**The fix is the second radio button: Custom OAuth** (*"external users … allowlisting"*), with your
own client. Two dead ends on the way, both worth skipping:
- `gcloud iap oauth-brands create` → *"Project must belong to an organization."* Those OAuth Admin
  APIs were shut down in March 2026 anyway.
- `gcloud beta run services update` has **no flag** to attach a client. This step is console-only.

**Recipe, ~5 minutes, one time per project:**
1. Google Auth Platform → Clients → **Create client**, type *Web application*. Do **not** edit the
   existing `HalaTuju Web` client — it is the live Google sign-in for students and admins.
2. Create it with **no** redirect URI, then reopen it and add
   `https://iap.googleapis.com/v1/oauth/clientIds/<CLIENT_ID>:handleRedirect` — the URI must contain
   the client's own ID, so it cannot be filled in before the client exists.
3. Security → Identity-Aware Proxy → the service → **Custom OAuth** → paste ID + secret → Save.

**⚠ SECOND TRAP, immediately after the first: signing IN and being LET in are different checks.**
With the OAuth client attached, Google authenticated the owner correctly and IAP then refused him —
*"You don't have access"*, naming his own address. `roles/run.invoker` is not the permission IAP
asks about; it wants **`roles/iap.httpsResourceAccessor`**. And that role **cannot be bound to the
Cloud Run service** (`gcloud run services add-iam-policy-binding` → *"Role
roles/iap.httpsResourceAccessor is not supported for this resource"*), so it goes on the
**project**.

**Consequence to remember:** a project-level grant covers **every IAP-protected resource in the
project**. Today only `halatuju-sandbox` has IAP enabled, so the two are equivalent — but the
moment IAP is switched on for `halatuju-web` or `halatuju-api`, everyone on this list reaches those
too. **Before enabling IAP on any other service, re-read this list.**

**Adding a designer** is then two commands, no console:
```
gcloud run services add-iam-policy-binding halatuju-sandbox --region=asia-southeast1 \
  --member=user:<email> --role=roles/run.invoker \
  --project=gen-lang-client-0871147736 --account=tamiliam@gmail.com

gcloud projects add-iam-policy-binding gen-lang-client-0871147736 \
  --member=user:<email> --role=roles/iap.httpsResourceAccessor --condition=None \
  --account=tamiliam@gmail.com
```
Removing someone is the same pair with `remove-iam-policy-binding`, and takes effect within about a
minute (IAP caches briefly).

**Owner intent recorded for later, NOT built:** *"Later we may create a surface for the super to
add/remove emails from an allow-list."* That is an intention in this document, deliberately not a
stub in the code — same rule as Layer 2 above. Until then, adding a designer is one `gcloud run
services add-iam-policy-binding … --member=user:<email> --role=roles/run.invoker`.

**Blocks Sprint 2:**
2. **Which items are CORE**, never switchable off? Assumption absent an answer: identity card, results
   slip, consent, and the family/income block. A policy floor, not an engineering one.
3. **`Programme` or `ScholarshipCohort`?** Convention says new tunables go on the cohort. Recommend
   `Programme` — a document set is the gift's identity, and a cohort home means re-ticking the same
   list every intake, which is the rot this work exists to prevent.

**Blocks Sprint 3:**
4. **Do configuration changes apply to applications already in flight?** Recommend **no** — snapshot
   at submit, so a tick today never re-gates yesterday's student. Costs one column.

**Blocks Phase 2 only — the owner's answers, 2026-07-29:**

> *"1) We — i.e. the platform — has two default themes, light and dark. 2) Organisations can have
> their own themes, palettes, and should be able to customise their surfaces however they want.
> Layer 0 and Layer 1 that we have planned. 3) I am NOT narrowing the scope."*

**⚠ A MISREADING TO NOT REPEAT.** An earlier remark — *"for now, I am only thinking of light and
dark"* — was recorded here as "light and dark ONLY, no organisation-authored themes", and the arc was
written down as smaller because of it. That was wrong in the way that matters: it read a statement
about **what the PLATFORM ships** as a **ceiling on what a TENANT may have**. Light and dark are our
two defaults. They are the floor an organisation starts from, not the limit it is held to. When an
answer could be about the platform or about a tenant, it is about whichever one the sentence names —
ask rather than infer, because the two produce different roadmaps.

5. **✅ ANSWERED — an `org_admin` determines their organisation's colours.** This is a deliberate
   REVERSAL of a recorded decision and must not be quietly reversed back by a later reader: the
   platform PRD says the per-org configuration surface is a closed list of seven branding rows, all
   **superadmin**-editable. Colour control moves to the tenant.
   **▶ ONE GUARD STILL NEEDS THE OWNER'S RULING, because "however they want" and this guard pull in
   opposite directions.** Recommendation: an organisation owns `--brand-*` and the ground it sits on;
   the SEMANTIC tone families (`positive` / `critical` / `caution` / `info`) stay ours. Those carry
   MEANING rather than identity — green error text is not a taste to have, and `components/InfoBox.tsx`
   already enforces that convention across the product. This is the one place I would hold a line
   inside "customise however they want", and it is the owner's call to overrule.
6. **✅ ANSWERED — the MODE is personal, with an AUTO that follows the time of day.** Owner,
   2026-07-29: *"Dark or light is a personal choice. And there are those like light at day time and
   dark in the evenings, auto set. Which is how I see it."*
   So the split is clean and each half has one owner: **the ORGANISATION owns the colours, the
   PERSON owns the mode.** An `org_admin` never sets what mode a reviewer sits in. Three states —
   **Light · Dark · Auto**, and Auto is the default.
   **▶ RECOMMENDATION FOR "AUTO", because it has two possible meanings and they are not equivalent.**
   Auto should mean **follow the device**, i.e. the `prefers-color-scheme` media query — NOT a
   time-of-day switch we implement ourselves. Both macOS and Windows already offer a scheduled
   light/dark that flips at the user's local sunset, so following the device inherits a schedule that
   is already location-aware and already the person's own choice. Writing our own means picking a
   cutover hour and a timezone, getting it wrong for anyone travelling or on a night shift, and
   fighting the setting their machine is already applying. One media query versus a scheduler we own
   and support forever.
   **⚠ AND ONE CONSTRAINT THIS PUTS ON THE TOKEN WORK, which is easy to miss until it bites.** If the
   mode can flip at sunset, it can flip **mid-session** — while a student is halfway through the
   Documents tab, or a reviewer is part-way through a verdict. **The repaint must therefore be pure
   CSS: a variable set swapping under the same DOM, never a re-render, a re-mount or a re-fetch.**
   Anyone who loses a half-filled form to a sunset will not report it as a theming bug. This is a
   testable acceptance criterion for the Phase 2 sprints, not a nicety.
   **▶ SMALLER CALL, recommendation only:** an EXPLICIT Light or Dark should be stored against the
   PERSON (so it follows them between machines — someone who needs dark needs it on every machine),
   while Auto needs no storage at all because the device answers. Note `src/lib/uiPrefs.ts` is
   currently device-local, so this is the first preference that would want an account home; decide it
   when sprint 12 is planned, not before.
7. **✅ ANSWERED — organisations MAY author their own themes and palettes. This is the opposite of
   what was briefly recorded here on 2026-07-29 and it makes the arc BIGGER, not smaller.**
   The platform ships light and dark as defaults; a tenant may customise its surfaces.
   **⚠ WHAT THAT MEANS FOR THE PLAN, stated plainly rather than absorbed quietly.** Sprints 6–12 as
   written are the FOUNDATION only — a semantic token vocabulary and the repaint of every surface
   onto it (measured: **1,858 chromatic colour literals across 114 files** against 624 `primary-N`;
   the sponsor portal at **1** `primary-N` versus 90 `blue-N`; zero dark-mode readiness anywhere),
   plus the switch. **The authoring surface an `org_admin` actually touches is NOT in those seven
   sprints** — this file's own question 7 flagged it as "its own arc": a colour picker, a contrast
   checker (a tenant WILL choose an unreadable pair, and it must be refused before it ships, not
   after a student cannot read the page), a live preview, and a place to store a theme.
   **The foundation is not optional and cannot be skipped to reach the authoring** — an editor over
   1,858 hard-coded literals changes nothing on screen. **▶ Re-plan Phase 2 at the full scope: the
   foundation arc, then the authoring arc, presented together with an honest sprint count.**

---

## Phase 2 status, in one line

**NOT approved, and now known to be UNDER-PLANNED.** The seven sprints in this file cover the
repaint; org-authored themes need their own arc on top. Nothing here should be started until Phase 2
is re-planned at full scope and approved on that basis.
