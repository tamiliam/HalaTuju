# Sprint 6 — Per-org branding (frontend): Implementation Plan

## Context

HalaTuju is becoming a multi-tenant platform. Sprint 5 (shipped 2026-07-24, `e188ad42`) de-hard-coded programme branding on the **backend** (emails + coach persona) through one seam, `apps/scholarship/branding.py`, proven byte-identical by 113 golden snapshots. Sprint 6 is the frontend counterpart: de-hard-code the programme name, brand colour, and logo in `halatuju-web/` so a future tenant org can run with its own identity — while BrightPath (the only live tenant) renders **identically to today**. Roadmap: `docs/plans/2026-07-14-platform-roadmap-draft.md` Sprint 6 (pointers verified stale; facts below re-verified 2026-07-24).

**Owner decisions (locked):** consent + legal text interpolated (BrightPath render byte-identical, snapshot-proven; owner reviews final wording pre-deploy) · TD-169 parked · ta `authGate.applyReason` interpolated (rendered Tamil unchanged) · "BrightPath Foundation" tenantName deferred + guard-allowlisted · support phone stays literal · no Stitch prototype (zero visual change) · **no migrations**.

## Verified facts (exploration 2026-07-24)

- "BrightPath" in messages: en 13 / ms 13 / ta 14 values. Consent keys `scholarship.consent.text`/`textMinor` (en:1614-1615) embed `**BrightPath Bursary Programme**`; `t()` interpolates **before** `ScholarshipConsent.tsx`'s `renderRich()` splits `**bold**` — so `**{programmeName} Programme**` renders byte-identically (verified).
- i18n is a custom flat `{var}` engine — `src/lib/i18n.tsx` `t()` (26 lines, verified): nested lookup, `value.replace(regex, v)` per param (has a latent `$`-pattern hazard), key-path fallback. No ICU (guard-tested). Zero collisions: `programmeName`/`personaName`/`orgShortName`/`supportEmail`/`displayDomain` appear in **no** message value today (verified).
- Theme: hardcoded hex ramp `tailwind.config.ts:11-27` (`primary.500 = '#137fec'`); **opacity modifiers in use** (`/40`, `/20`) → CSS vars MUST be RGB-channel form. No colour CSS vars exist; no dark mode; no stray `#137fec` in src.
- Logo: `/logo-icon.png` via `next/image` in **14 sites**, all `alt="HalaTuju"`. No `images` config in next.config.js.
- Backend: `branding.py` has no `logo_url`/`brand_colour`/short-name accessors; no branding endpoint; no anonymous org resolution. Public precedent: `SponsorPoolCountView` (AllowAny + throttle). `brand_colour` seeded `'#137fec'`; `logo_url` seeded `''`.
- Extra rendered literals beyond messages: mailtos in `scholarship/page.tsx:208,227` (`info@halatuju.xyz`), `ScholarshipNextSteps.tsx:95` (`help@`), `SponsorLanding.tsx:149` (`sponsor@`); legal pages `terms/page.tsx:52,55` + `privacy/page.tsx:21,29,42` (hardcoded English JSX).
- Test conventions: pure lib + node-env jest (`blockers.ts` pattern); per-namespace parity + source-scanning key guards; **no** FE brand guard and **no** placeholder-parity test (gaps this sprint closes). Gates: `next build` (tsc strict), `next lint`, jest 662; backend pytest 4350.
- lessons.md bindings: en.json has duplicate blocks — edit by exact key path only; guards must derive the set they scan.

## Design

**D1 — Delivery: `NEXT_PUBLIC_ORG_CODE` env + public branding endpoint, dark for BrightPath.**
Env unset or `'brightpath'` ⇒ platform mode: FE renders baked platform defaults, **never fetches** (zero change, zero flash for BrightPath). New `GET /api/v1/branding/<slug:code>/` (AllowAny + throttle, in `apps/scholarship/views_branding.py`, registered beside `sponsor/pool/count/`): resolves via `branding.for_organisation(...)`, total/never-raises, unknown code → platform payload. Payload (exact key-set snapshot-pinned): `programme_name{en,ms,ta}`, `persona_name{...}`, `org_short_name`, `brand_colour`, `logo_url`, `email_support`, `sponsor_email`, `frontend_domain`. Backend seam gains 3 PLATFORM entries (`brand_colour '#137fec'`, `logo_url ''`, `org_short_name 'BrightPath'`) + 3 total accessors. `emails.py`/`help_engine.py` untouched (Sprint 5 goldens stay green).

**D2 — FE seam: pure `src/lib/branding.ts` + provider; branding tokens auto-injected into `t()`.**
`branding.ts`: `PLATFORM` (today's literals verbatim — the FE's one sanctioned literal home, guard-allowlisted), `resolveBranding(config|null)` with `''`-falls-through fallback, `interpolateMessage()` (extracted from i18n.tsx, function-replacer closes the `$` hazard, re-imported by `t()`), `brandRamp(hex)` (computed 50–900 ramp — tenant-only; BrightPath uses the verbatim literal ramp), `AUTO_TOKENS`. `branding-context.tsx`: `BrandingProvider` (initial = platform; dark fetch per D1) mounted in `providers.tsx` **outside** `I18nProvider`. `t()` merges the five branding params beneath explicit call-site params (explicit wins) + a `'{'`-absent fast path.
*Why auto-injection:* ~18 keys / ~15 call sites; per-call threading = 15 chances to render a literal `{programmeName}` to a student; auto-injection is one audited change and makes tenancy Rule 2 free for all future strings.

**D3 — Theme: RGB-channel CSS vars, full ramp.**
`tailwind.config.ts` `primary.50–900` → `'rgb(var(--brand-N) / <alpha-value>)'`; `globals.css` `:root` gets ten `--brand-N` space-separated RGB triplets converted from today's exact hexes (static CSS ⇒ correct at first paint, SSR-safe). Tenant override via `documentElement.style` only when colour differs — never fires for BrightPath. `success`/`warning`/`error` stay literal.

**D4 — Logo: one `<BrandLogo>` component** replacing all 14 `<Image src="/logo-icon.png" alt="HalaTuju">` sites, preserving each site's width/height/priority. `src`/`alt` from branding (platform = today's values). External tenant URLs render with `unoptimized` (no `remotePatterns` churn, no raw `<img>`, platform asset keeps optimisation). `layout.tsx` metadata = platform identity, untouched.

**D5 — Consent + legal:** consent values get the token inside each locale's own phrasing (en `**{programmeName} Programme**`, ms `**Program {programmeName}**`, ta placed where "BrightPath Bursary" sits). Byte-identity pinned by a snapshot test captured **before** any message edit. Legal pages: `useBranding()` + replace only the brand token in JSX (`{b.programmeName.en}` — English-only prose); everything else (HalaTuju mentions, vendors, dates) untouched.

### Scope table

**De-hard-code now (BrightPath output byte-identical):** 18 message keys ×3 locales — `footer.b40Heading`, `scholarship.nav`, `consent.text`/`textMinor`, `landing.about.body`, `admin.scholarship.title`, `admin.payments.subtitle`, `recordVerdict.reasonPlaceholder`, `sponsorLanding.faq.a6`, `sponsorPortal.trust.whoWeAre.body` → `{programmeName}`; `sponsorPool.verifiedByBrightPath`, `sponsorPortal.students.balanceLabel` → `{orgShortName}` (bare-brand sites — programmeName would change output); `docs.help.coachLabel`, `actionCentre.coach` → `{personaName}`; `nextSteps.techSupport` → `{supportEmail}` (phone stays); 3 × `actionCentre.item.*.desc` → `{displayDomain}`; ta-only `authGate.applyReason` → `{programmeName}`. Plus: theme ramp (D3), logo ×14 (D4), legal pages ×5 lines (D5), 4 JSX mailto/email literals (`scholarship/page.tsx` ×2, `ScholarshipNextSteps.tsx`, `SponsorLanding.tsx`).

**Defer as tenant content (guard-allowlisted, documented):** `admin.administration.tenantName` ("BrightPath Foundation"), support phone, SMC/CUMIG coalition prose, `src/content/manual/**`.

**Platform identity — keep:** `layout.tsx` metadata + `r/[code]` OG url, all "HalaTuju" mentions, vendor names, comments/docstrings.

## Phases (each commit green; ONE push at the very end)

1. **Pin the present** — `src/lib/branding.ts` + `branding.test.ts` + `branding-consent-snapshot.test.ts` (pinned fully-rendered consent strings from CURRENT messages, en/ms/ta × text/textMinor, via `interpolateMessage`). No app-code change. *Gate:* full jest.
2. **Backend** — seam accessors + `views_branding.py` + route + `test_branding.py` extension + `test_branding_endpoint.py` (anonymous 200; brightpath/unknown/garbage codes → exact platform payload; fixture org-2 → own columns; exact key-set snapshot; no student data). *Gate:* full pytest 0 fail 0 skip (113 goldens + AST guard unmodified), `makemigrations --check` clean.
3. **FE plumbing (invisible)** — provider + mount, `t()` auto-inject + `interpolateMessage` adoption + fast path, tailwind/globals CSS vars, `BrandLogo` + 14 swaps, 4 JSX email swaps, `next.config.js` env exposure. Messages untouched. *Gate:* build + lint + jest; consent snapshot green; spot-check the `/40`,`/20` opacity sites (admin payments table, profile tiles).
4. **Content interpolation** — the 18+1 message-key edits (exact key paths — en.json duplicate-block hazard) + legal pages. *Gate:* consent snapshot proves byte-identity ×3; scripted leaf-map diff shows exactly the intended paths changed; parity counts unchanged.
5. **Guards last** — `brand-guard.test.ts` (forbidden `BrightPath`/`Cikgu Gopal`/`halatuju.xyz` over all message values + comment-stripped `src/**` with documented allowlists: `lib/branding.ts`, `content/manual/**`, `layout.tsx`, `r/[code]/page.tsx`, tests; self-checking floors ≈4000 keys) + `placeholder-parity.test.ts` (every locale's placeholders ⊆ en's ∪ `AUTO_TOKENS`). Prove the guard bites (plant + revert). *Gate:* full jest.

**Final:** full jest + pytest + `next build` + lint → single push (BOTH Cloud Build triggers fire — expected; no migrate-first, `NEXT_PUBLIC_ORG_CODE` deliberately unset on Cloud Run). Post-deploy smoke: homepage/consent/footer identical; `GET /api/v1/branding/brightpath/` returns platform payload; builds verified by SHORT_SHA. Then sprint close per `Settings/_workflows/sprint-close.md`.

## Key files

Backend: `apps/scholarship/branding.py`, `views_branding.py` (new), `urls.py`, `tests/test_branding.py` + `tests/test_branding_endpoint.py` (new).
Frontend: `src/lib/branding.ts` + `branding-context.tsx` (new), `src/lib/i18n.tsx`, `src/app/providers.tsx`, `tailwind.config.ts`, `src/app/globals.css`, `src/components/BrandLogo.tsx` (new) + 14 logo sites, `src/messages/{en,ms,ta}.json`, `terms/page.tsx`, `privacy/page.tsx`, `scholarship/page.tsx`, `ScholarshipNextSteps.tsx`, `SponsorLanding.tsx`, `next.config.js`, 4 new test files.

## Risks

- **Duplicate en.json blocks** → exact-key-path edits + leaf-map diff verification (lessons.md binding).
- **Opacity-modifier breakage** → RGB-channel var form mandated; spot-check the two known sites.
- **Auto-inject side effects** → verified zero token collisions today; parity test pins it permanently.
- **`$` in replacements** → function replacer + regression test.
- **Missed literal ships to a tenant** → brand guard lands last, derived scan set, self-checking floors.
- **Public endpoint surface** → throttled, serves 8 brand strings only, exact key-set pinned, unknown codes → platform (no enumeration oracle).

## Owner gates before deploy

1. Review the final `{programmeName}`-templated consent/legal wording (standing decision — snapshot guarantees BrightPath render unchanged).
2. Tamil values remain first-drafts only where new (none expected — all edits are in-place token swaps).

## Execution

Executor: Opus 4.8 agent (as Sprint 5), commits locally per phase, never pushes; coordinator verifies, pushes once, confirms both builds by SHORT_SHA, smokes, closes the sprint, updates memory.
