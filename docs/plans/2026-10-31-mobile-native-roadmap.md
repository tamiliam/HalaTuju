# HalaTuju Mobile-Native — Plan

## Context
Students use HalaTuju on phones almost all the time. Today it "works most of the time" on an iPhone, but it is not app-quality. The owner's rule: **if we show it on a phone, it must be perfect; if the work is desktop-only, do not offer it on a phone — or reorganise it for the phone.** Owner answers (2026-10-31):
- Desktop-only screens get a friendly **"works best on a computer"** panel on phones.
- The perfect-on-phone standard covers **students, sponsors, reviewers and org admins**.

The outcome: every screen is measured at iPhone width in all three languages, every screen is fixed or gated, and a written **Mobile Standard** plus automatic checks stop new work from slipping back.

## What the investigation found (evidence)
Measured live on halatuju.xyz at 390 px (Playwright), plus 3 code audits of all 93 pages.

**Confirmed live**
- `/` and `/login` in **Tamil are 458 px wide on a 375 px screen** → the page scrolls sideways (TD-311, still open).
- `/contact` has 4 fields at 14 px; home has 2 selects at 14 px → **iPhone zooms the page on tap**.
- Home header spends ~160 px on raw "Auto / English" dropdowns; it differs from the header on other pages.
- Footer and header links are 18–20 px tall (target is 44 px).

**Cross-cutting (whole product)**
- No `viewport` export, no `viewport-fit=cover`, no safe-area padding, no `dvh`, no web-app manifest / home-screen icon (`src/app/layout.tsx`).
- `globals.css:515-519` sets no input font size → ~45 student fields and many reviewer fields use `text-sm` (14 px) → iOS zoom on every tap. `.input` (`globals.css:555`) is already 16 px — the good pattern.
- `InfoTip.tsx:18-23`: on iPhone a tap fires mouseenter then click → the help bubble opens and shuts at once. Fixed 256 px wide, can run off-screen.
- 18 hand-rolled `fixed inset-0` overlays in 13 files; several have no max-height or scroll → buttons hidden behind the iPhone keyboard (e.g. `TypedConfirmDialog.tsx:33`, `award/page.tsx:645`, `admin/payments/page.tsx:373`). No shared Modal/Sheet component.
- `Toggle.tsx`: 24 px tall tap target. `Toast.tsx`: up to 384 px wide, wider than the phone.
- Hover-dependent UI: save button label flips on touch (`CourseDetailShared.tsx:63-74`); `title=` used as the only explanation in 127 places (e.g. `VerifiedTick.tsx:11`).
- Hidden file inputs (`ActionCentre.tsx:363`, `PostAwardTasks.tsx:139`) — some phones will not open the picker. `cards.tsx:61-77` already uses the safe `sr-only` pattern.
- Missing phone keyboards: OTP has no `inputMode="numeric"` / `autoComplete="one-time-code"` (`AuthGateModal.tsx:421`, `profile/page.tsx:833`); postcode, CoQ, household size lack `inputMode`.
- Tamil is 1.23× longer than English on average, 1.8× at the 90th percentile — short labels blow up most.

**Students**
- Mobile menu has no max height and lists Profile/Saved twice (`AppHeader.tsx:272-341`).
- Onboarding header (logo + "Langkah 2 daripada 3" + bars) ~380 px vs 327 px available (`ProgressStepper.tsx:15`).
- STPM grade row collapses when the "not counted" tag shows (`stpm-grades/page.tsx:171, 234-293`).
- Search: the filter block fills the first screen; filter dropdowns open off-screen (`FilterPill.tsx:71`).
- Course page: a 600 px scroll box inside the page traps the thumb (`course/[id]/page.tsx:435`).
- Saved: **course compare is switched off on phones** (`saved/page.tsx:326, 402`); status pills do not wrap in Tamil (`:360`).
- Scholarship apply: **5 tabs, nothing saved until submit** (`apply/page.tsx:691`) — if iOS kills the tab while the student checks WhatsApp or the camera, everything is lost. Bottom tab bar 6 × 56 px with 10 px labels, no safe-area padding (`:713`).
- Documents: main actions (Choose / Replace / Remove) are ~20 px text links (`ScholarshipDocuments/cards.tsx:119-126`).

**Sponsors**
- **Portal top bar does not fit a phone** — logo + 3 tabs + theme select + logout on one `h-14` row, ~470–530 px needed vs 343 px (`sponsor/(portal)/layout.tsx:169-197`). It is the sponsor's only navigation.
- Terms wizard squeezed to ~220 px by nested padding (`layout.tsx:218` + `SponsorTermsWizard.tsx:123`). 9 px labels on My Giving (`page.tsx:269`).

**Reviewers / org admins**
- Admin top bar overflows (`Topbar.tsx:81-205`); it is not sticky.
- **PDFs shown in an iframe** (`DocViewer.tsx:53`) → on iPhone usually only page 1, no zoom.
- Review screen: decision panel lands at the very bottom on phones (`scholarship/[id]/view.tsx:962`); Prev/Next ~24 px (`CockpitHeader.tsx:53`); list cards only tappable on the name.
- Three-across money figures overflow (`ScholarMoney.tsx:46`); unframed table (`PartnerEmailsCard.tsx:180`); menus clamp only on the left (`Menu.tsx:153`).

**What already works (reuse it)**
`.input` (16 px) · `TableFrame.tsx` + `hidden md:block` / `md:hidden` card pairs (14 places) · admin mobile drawer (`AppShell.tsx:375-397`) · sticky bottom bar `SaveBar.tsx:49` · scrolling modal `IntakeYearTab.tsx:466` · `Menu.tsx` viewport measuring · Home bar wrap pinned by `navLayout.test.ts` · side-rail→bottom-tabs in `scholarship/apply/page.tsx:637-729` · `pageWidth.test.ts` static guard · sandbox harness `src/app/sandbox/[surface]` + `src/sandbox/surfaces.tsx`.

## The Mobile Standard (new doc: `docs/mobile-standard.md`)
Target devices: **360, 375, 390, 430 px wide**, iOS Safari first, all three languages. Rules:
1. **No sideways scroll, ever.** `scrollWidth ≤ clientWidth` on every page, every language. Long words/IDs get `break-words` / `truncate`.
2. **Text fields ≥ 16 px on phones** (no iOS zoom). `md:text-sm` allowed from tablet up.
3. **Tap targets ≥ 44 × 44 px** for every control (padding or hit-area, the look can stay smaller). Inline text links in paragraphs excepted.
4. **No hover-only information or actions.** Explanations are visible text or a tap `InfoTip`. Never `title=` alone.
5. **One shared `Sheet` / `Modal`.** Bottom sheet on phones, centred on desktop; `max-h-[90dvh]`, inner scroll, 44 px close, safe-area padding. No hand-rolled `fixed inset-0`.
6. **Safe areas + dvh.** Sticky/fixed bars pad with `env(safe-area-inset-*)`; use `dvh`, never `vh`, for heights.
7. **Tables → cards on phones** (`hidden md:block` table + `md:hidden` cards), or `TableFrame` scroll for genuinely wide data.
8. **Right keyboard for every field.** `type`/`inputMode`/`autoComplete` (tel, email, numeric, decimal, one-time-code, postal-code).
9. **Files:** `accept="image/*,application/pdf"`, `sr-only` input never `hidden`, big button, camera-friendly. PDFs open full-screen / new tab on phones, never an iframe.
10. **Long forms keep their progress** (survive an iOS tab kill) and keep the main action reachable (sticky bottom bar).
11. **One-thumb navigation:** each shell has a phone nav that fits in Tamil at 360 px (drawer or bottom tabs).
12. **Body text ≥ 12 px on phones;** 9–11 px only for badges.
13. **Desktop-only screens** use the shared `DesktopOnly` panel below `md`, with a read-only summary where useful. A screen is desktop-only only if listed in the ledger with a reason.
14. **Design at 390 px first.** New pages/redesigns: Stitch screen at phone width first (existing workspace rule), then desktop.

**Enforcement (so it cannot be skipped)**
- **Static guards in `npm run gates`** (Jest, runs in the Cloud Build deploy gate, using `src/test/sourceGuard.ts`): input font floor, no `hidden` file inputs, no new `fixed inset-0` outside `Sheet`, no `vh` heights, no `title=` on icon-only controls, every route listed in the mobile ledger. Existing violations become a **floor count that may only go down** (same ratchet as `code-standards.json`), reaching zero by the last sprint.
- **Real-browser check `npm run mobile-check`** (new; `@playwright/test` as a dev dependency, run locally — not inside Cloud Build, to save build minutes): visits every public page and every sandbox surface at 360 and 390 px in en/ms/ta. Fails on sideways scroll, inputs < 16 px, primary tap targets < 44 px. Saves screenshots for the owner.
- **Mobile ledger** `docs/mobile-ledger.md`: every route, its class (Must / Can / Desktop-only), and last measured status.
- **Workflow gates:** add one line each to `Settings/_workflows/sprint-close.md` and `small-change-lane.md`: "UI touched → `npm run mobile-check` green + ledger updated". (Workspace workflow edit — covered by approving this plan.)

## Roadmap (9 sprints, web only unless noted)
Each sprint: tests + `mobile-check` green, owner sees phone screenshots, **owner's yes before push** (a push deploys), ≤ 2 deploys per sprint. Sprints touching consent/money/identity (M4) get the adversarial review before push.

**M0 — Standard, harness, baseline** (low–medium)
`docs/mobile-standard.md`, `docs/mobile-ledger.md`, `scripts/mobile-check` + Playwright config, sandbox surfaces for the logged-in Must screens (dashboard, profile, apply, documents, award, sponsor portal, review cockpit), static guards with today's floor counts, workflow lines. `layout.tsx`: `viewport` export (`viewportFit: 'cover'`, `themeColor`), web-app manifest + apple-touch-icon (installs as a home-screen app; no offline mode). Done when: baseline report lists every route × width × language.

**M1 — Global foundations** (medium; fixes the most screens per line changed)
Found in M0: the favicon `src/app/icon.png` is 5.7 MB (2048 px, with an image-generator watermark) — every phone downloads it; replace it with a small cropped icon like the M0 home-screen icons.
**Tamil font = Mukta Malar** (owner, 2026-10-31: "use the font we use in SJKT Connect"): copy SJKTConnect's Tamil-only subset (`frontend/app/fonts/mukta-malar/MuktaMalar-Tamil-{400,600,700}.woff2`, loaded via `localFont` in `frontend/lib/fonts.ts`, `--font-tamil` first in the body stack with a Tamil-only unicode-range) — so Tamil looks the same on every phone and is compact in small print; extend `fontSources.test.ts`; re-measure Tamil widths. 16 px input rule in `globals.css`; `InfoTip` tap fix + edge clamp; new shared `Sheet` and migrate all 18 overlays; `Toggle` 44 px hit area; `Toast` phone width; `Menu.tsx` / `FilterPill` right clamp; sticky-hover save button; `hidden`→`sr-only` file inputs; keyboard/autocomplete sweep; `VerifiedTick` visible text; TD-311 Tamil hero. Done when: input and overlay floors reach 0.

**M2 — Student shell + onboarding** (medium; Stitch first for the header)
One student header on all pages (Home included; theme/language move into the menu); menu height cap + scroll + no duplicates; onboarding header fit; STPM/SPM grade rows restack; stream buttons; 44 px remove buttons.

**M3 — Student discovery** (medium; Stitch first for filters + compare)
Search filters in a bottom sheet ("Filters · 3"); course page without inner scroll traps; saved-course compare on phones (card-swipe compare); status pills wrap; course card save target; report page width.

**M4 — Scholarship apply, documents, award** (high; consent/PII → adversarial review)
Apply form keeps a draft through an iOS tab kill (owner decision below); bottom tab bar fits + safe area; document cards get full-size action buttons; income wizard text sizes; award: contract readable at phone width, guardian form in `Sheet`, PIN keyboard.

**M5 — Sponsor portal** (medium; Stitch first)
New phone nav (bottom tabs: My Giving / Students / Account); terms wizard full width; 9 px labels; filters; login card padding.

**M6 — Admin shell + reviewer cockpit** (high; Stitch first)
Topbar phone version (sticky; search/theme/help into a menu; breadcrumb truncates); review cockpit on phones: sticky decision bar (SaveBar pattern), 44 px Prev/Next, whole-card tap, sort on phone lists; documents in a full-screen viewer — images inline, PDFs rendered as page images or opened in a new tab.

**M7 — Admin "Can" screens + desktop-only gate** (medium)
Cards for scholars/sponsors/payments detail tables; `ScholarMoney` stacks; `PartnerEmailsCard` framed; new `DesktopOnly` panel on billing-rates, billing, course-data, contracts, sponsors/terms/[id], partner template editor.

**M8 — Close-out** (low)
Full re-measure (all routes × 360/390 × 3 languages); decide manifest `display: 'standalone'` only once every screen has its own way back and sign-in links are proven inside the installed app (M0 ships `'browser'`); owner real-iPhone walkthrough with a short checklist, all floors at 0, ledger 100 % green, retrospective, memory + `projects.json` updated.

## Owner decisions still open (asked at the sprint that needs them)
- **TD-311 (M1):** shrink the Home heading on phones for all languages (recommended) or Tamil only.
- **Apply draft (M4):** keep the draft in the browser tab only, cleared on submit/sign-out (recommended — simple, IC stays on that tab) or save drafts on the server (survives a phone change, but a new data model).
- **Stitch looks (M2, M3, M5, M6):** approve phone screens before code.

## Files (representative)
- New: `halatuju-web/src/components/Sheet.tsx`, `DesktopOnly.tsx`, `scripts/mobile-check.*`, `playwright.config.ts`, `src/lib/__tests__/mobileStandard.test.ts`, `public/manifest.webmanifest`, `docs/mobile-standard.md`, `docs/mobile-ledger.md`, `docs/plans/2026-10-31-mobile-native-roadmap.md`.
- Change: `src/app/layout.tsx`, `src/app/globals.css`, `InfoTip.tsx`, `Toggle.tsx`, `Toast.tsx`, `AppHeader.tsx`, `ProgressStepper.tsx`, `admin/Topbar.tsx`, `admin/Menu.tsx`, `DocViewer.tsx`, `sponsor/(portal)/layout.tsx`, `scholarship/apply/page.tsx`, `ScholarshipDocuments/cards.tsx`, `scholarship/[id]/view.tsx`, `src/sandbox/surfaces.tsx`; workspace `Settings/_workflows/sprint-close.md`, `small-change-lane.md`.

## Verification
- `npm run gates` (typecheck, lint, i18n, Jest incl. new static guards) green in every sprint.
- `npm run mobile-check`: 0 sideways scroll, 0 inputs < 16 px, 0 small primary targets, at 360/390 × en/ms/ta, on public pages + sandbox surfaces.
- Owner screenshots per sprint; live check on halatuju.xyz after each deploy with the same probe (`scrollWidth ≤ clientWidth`).
- M8: owner walks the student, sponsor and reviewer journeys on a real iPhone using the checklist.

## First steps after approval
1. Save this roadmap to `docs/plans/2026-10-31-mobile-native-roadmap.md`; update `halatuju.md` NEXT pointer.
2. Start M0 via `Settings/_workflows/sprint-start.md`.
3. Delete the investigation screenshots in `C:\Users\tamil\Python\.playwright-mcp\` (gitignored scratch).
