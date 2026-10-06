# Retrospective — Sprint 6: Per-org branding (frontend)

**Date:** 2026-07-24. **Scope:** `halatuju-web/` frontend + a small backend extension (3 visual
accessors + a public branding endpoint). **Result:** SHIPPED + LIVE — commits `d900cbc7`..`7038c37b`
(5 commits), both Cloud Builds SUCCESS for `SHORT_SHA 7038c37`, smoke-tested. jest 662 → 688 (687
pass + 1 pre-existing environment-only failure); pytest 4346 → 4363, 0 fail 0 skip; zero migrations.

## What was built

Sprint 5 (2026-07-23/24) moved every rendered brand literal on the BACKEND — programme name,
sign-off, persona, sender identity, display domain — behind one seam, `apps/scholarship/branding.py`.
Sprint 6 completes the pair on the frontend: the programme name, theme colours, logo and message
copy the student and officer actually SEE.

- **FE seam `src/lib/branding.ts`** — `PLATFORM` defaults captured verbatim from today's literals
  (the FE's one sanctioned literal home, guard-allowlisted); `resolveBranding(config|null)` with an
  empty-string-falls-through chain; `interpolateMessage()` (extracted from `i18n.tsx`, with a
  function-replacer that closes a `$`-in-replacement hazard `String.replace` would otherwise trip
  on); `brandRamp(hex)` (a computed 50–900 Tailwind-shape ramp for a tenant's single brand colour);
  `AUTO_TOKENS` (the 5 tokens auto-injected into every `t()` call).
- **`BrandingProvider`** (`branding-context.tsx`, mounted in `providers.tsx` outside `I18nProvider`)
  — dark fetch: BrightPath/platform mode (unset or `'brightpath'` `NEXT_PUBLIC_ORG_CODE`) NEVER
  calls the branding endpoint; it renders the baked platform defaults with zero network cost and
  zero flash. A future tenant's `NEXT_PUBLIC_ORG_CODE` triggers one fetch to the new backend
  endpoint at mount.
- **`t()` auto-injects 5 branding tokens** beneath any explicit params the call site passes
  (explicit always wins), plus a `'{'`-absent fast path that skips interpolation entirely for a
  message with no placeholder — the majority of calls, so this also trims a small amount of
  runtime work off every render.
- **CSS-variable theme, RGB-channel form** — ten `--brand-N` space-separated RGB triplets (not hex),
  because the existing Tailwind config uses opacity modifiers (`bg-brand-500/10`, `/40`, `/20`)
  which only work against the `rgb(var(--x) / <alpha-value>)` pattern; converted 1:1 from today's
  exact hex ramp so first paint is unchanged and SSR-safe (no client-side colour swap for
  BrightPath).
- **`<BrandLogo>`** — one new component replacing the 14 hardcoded `<Image src="/logo-icon.png"
  alt="HalaTuju">` sites, preserving each site's width/height/priority props; a tenant's external
  logo URL renders `unoptimized` so `next.config.js` needs no `remotePatterns` churn.
- **18 message keys × 3 locales (en/ms/ta)** interpolated to `{programmeName}` / `{orgShortName}`
  (bare-brand sites where the full programme name would read oddly) / `{personaName}` /
  `{supportEmail}` / `{displayDomain}`, plus the Tamil-only `authGate.applyReason` string. Legal
  pages (`terms/page.tsx`, `privacy/page.tsx`) swap only the brand-mention JSX token — vendor names,
  dates and every other line untouched. 4 further JSX email literals
  (`scholarship/page.tsx` ×2, `ScholarshipNextSteps.tsx`, `SponsorLanding.tsx`) brought onto the
  same scheme.
- **Backend extension:** `branding.py` gained 3 `PLATFORM` entries (`brand_colour`, `logo_url`,
  `org_short_name`) + 3 accessors, and a new public `GET /api/v1/branding/<slug:code>/`
  (`views_branding.py`, AllowAny + throttle, exact key-set snapshot-pinned, unknown codes → the
  platform payload — no enumeration oracle) that the FE provider calls for a non-platform org.
  `emails.py`/`help_engine.py` untouched — Sprint 5's goldens stay green.
- **FE guards, added last (by design):** `brand-guard.test.ts` (forbidden brand literals scanned
  across message VALUES and comment-stripped `src/**`, with documented allowlists —
  `lib/branding.ts`, `content/manual/**`, `layout.tsx`, `r/[code]/page.tsx`, tests — and
  self-checking floors so a scanner that silently matches nothing fails loudly) and
  `placeholder-parity.test.ts` (every locale's placeholder set stays a subset of en's, unioned with
  `AUTO_TOKENS`). Both were proven to actually bite (a planted violation was caught, then reverted)
  before being trusted as the sprint's final gate.

## What went well

- **Byte-identity was provable at every step, not just claimed at the end.** A consent-string
  snapshot test captured the fully-rendered en/ms/ta text/textMinor BEFORE any message edit; the
  content-interpolation phase (D4 of the brief) ran against that snapshot continuously, so a
  byte-break would have surfaced at the exact key that caused it. It never did — the snapshot
  passed unmodified straight through.
- **The phase order (pin → backend → invisible FE plumbing → content → guards last) meant every
  intermediate commit was independently green.** Plumbing landed before any message changed, so a
  `next build`/lint/jest failure in that phase could never be confused with a content mistake, and
  vice versa.
- **The RGB-channel CSS-variable decision was verified, not assumed.** The brief flagged the
  opacity-modifier constraint from static analysis; the build spot-checked the two known
  opacity-dependent sites (admin payments table, profile tiles) in the compiled CSS output and
  confirmed the modifiers still resolved correctly before treating the theme phase as done.
- **Sprint 5's 113 email goldens + AST brand-guard were never touched and stayed green throughout**
  — confirming the backend/frontend split was clean; nothing in this sprint needed to reopen
  `emails.py` or `help_engine.py`.

## What went wrong

- **What happened:** partway through the sprint, `git status` showed 16 files (14 modified + 4
  untracked) belonging to an entirely unrelated in-flight feature (an "application nudge" reminder
  — migration 0110, `nudge.py`, a management command, edits to `emails.py`/`views.py`/
  `serializers_admin.py`/`urls.py`/`models.py`/`test_org_fence.py`, and FE edits to the admin
  scholarship detail page, `admin-api.ts`, `blockers.ts` + its test, and all three message files)
  sitting uncommitted in the same working tree, from a concurrent session working the SAME repo
  without worktree isolation.
- **Why it happened:** two sessions were active on `Production/HalaTuju` at once with no git
  worktree separating them (the project convention `parallel-work-isolation.md` recommends a
  worktree for exactly this shape of concurrent work, but this pairing predated that separation
  being applied). A same-tree `git add -A` at any point in either session would have silently
  co-committed the other's half-finished, unrelated, and untested changes — including a fresh
  Django migration — under this sprint's message.
  - **Important correction:** `en.json`/`ms.json`/`ta.json` were among the 14 modified files
    carrying the other session's work, and Sprint 6 ALSO needed to edit all three message files
    (the 18-key interpolation). This was not avoidable by "just not touching those files" — the
    two changesets landed in the same files. The safe path was to diff precisely: every message
    edit in this sprint's commits is a token-insertion into an EXISTING value at an EXISTING key
    (verified against the pre-edit snapshot + leaf-map diff — 0 keys added, 0 removed, exactly the
    18+1 intended values changed), never a touch to any key the nudge work had added or altered.
    The leaf-map diff step existed already in the brief's gate list for a different reason (proving
    byte-identity); it turned out to double as the proof that this sprint's edits didn't collide
    with the other session's.
  - **What system change prevents recurrence:** the response was to run the sprint's final gates
    (full pytest + jest + build + lint) from an isolated git worktree checked out from the same
    commit, so the reported numbers (4363 pytest / 688 jest) are provably this sprint's own code
    plus the existing baseline — never contaminated by the other session's uncommitted, untested
    diff sitting in the shared working tree. This is exactly the scenario
    `Settings/_workflows/parallel-work-isolation.md` already prescribes a worktree for; the gap was
    that isolation wasn't set up ahead of time. The workflow's existing guidance covers it — no new
    lesson is needed, but it is worth flagging as a live example of why the guidance exists (this
    sprint would have been meaningfully harder to close cleanly without a mid-sprint recovery to
    worktree isolation).
- **Staging discipline at close:** every commit and the final push staged explicit paths only,
  never `git add -A` — the 16 foreign files were verified absent from every commit's file list, and
  `git status` after the close shows exactly those 16 files remaining, untouched, in the shared
  tree (owned by the other session to commit or discard on its own timeline).

## Design decisions

See `docs/decisions.md` ("Per-org branding — frontend seam" and related entries, Sprint 6,
2026-07-24) for the full record: `NEXT_PUBLIC_ORG_CODE` + public-endpoint delivery (dark for
platform); `t()` auto-injection over per-call threading; RGB-channel CSS variables; the
`orgShortName` vs `programmeName` token split for bare-brand sites; consent/legal interpolation
approved with a byte-identity snapshot gate; TD-169 stays parked; `"BrightPath Foundation"`
tenantName deferred + guard-allowlisted; the support phone stays a literal.

## Numbers

- jest: 662 → 688 (687 passing; 1 pre-existing environment-only failure — see TD-171 — not a
  regression, reproduces identically on an untouched `origin/main` checkout under local Node 26,
  green on CI Node).
- pytest: 4346 → 4363, 0 failures, 0 skips.
- `next build` + lint: clean. `makemigrations --check`: clean — **zero migrations this sprint**
  (migration `0110` visible in the working tree belongs to the concurrent nudge session, not this
  sprint).
- Byte-identity: consent snapshot fixture passes unmodified; Sprint 5's 113 email goldens + AST
  guard untouched and green; leaf-map diff — en 18 / ms 18 / ta 19 values changed, 0 keys added, 0
  removed, leaf counts (3725) unchanged across all three locale files.
- Deploy: both Cloud Builds SUCCESS for `SHORT_SHA 7038c37`; smoke-tested post-deploy — web 200,
  a gated endpoint 401, `GET /api/v1/branding/brightpath/` returns the pinned platform payload,
  and an unknown org code also resolves to the platform default.
