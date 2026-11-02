# The Mobile Standard

Adopted 2026-10-31 (Mobile M0). Roadmap: [plans/2026-10-31-mobile-native-roadmap.md](plans/2026-10-31-mobile-native-roadmap.md).
Live status of every screen: [mobile-ledger.md](mobile-ledger.md) (generated — do not edit).

Students use HalaTuju on their phones almost all the time. The owner's rule: **if we show it on a
phone, it must be perfect; if the work is desktop-only, do not offer it on a phone — or reorganise
it for the phone.**

## Who and what it covers

- **Target phones:** 360, 375, 390 and 430 px wide. **iPhone Safari first** (it is the strictest and
  the most used), then Android Chrome.
- **All three languages:** English, Malay and Tamil. Tamil is on average 1.23× longer than English
  and 1.8× at the long end, so a label that fits in English is not proof of anything. Check Tamil.
- **Classes** (every route has one, in `halatuju-web/src/lib/mobileClass.ts`):
  - **Must** — students, sponsors, and the everyday screens of reviewers and org admins. Every rule
    below applies in full.
  - **Can** — the rest of the admin console. No sideways scroll and no zoom; a denser layout is fine.
  - **Desktop-only** — shows the shared "works best on a computer" panel below `md`. Only screens
    listed with a written reason.

## How each rule is checked

Three kinds of check, from cheapest to most human:

- **Static guard** — Jest, in `npm run gates` and in the Cloud Build deploy gate
  (`src/lib/__tests__/mobileStandard.test.ts`). Today's offenders are a **floor that may only go
  down**; a new offender fails the build. Reads source text, so it is best effort — its limits are
  written in `src/test/mobileScan.ts`.
- **mobile-check** — `npm run mobile-check`, a real phone-sized browser on every public page and
  every sandbox surface, at 360 and 390 px, in all three languages. Fails if any page gets worse than
  `mobile-check/baseline.json`. Run locally before pushing UI work (not in Cloud Build — build minutes).
- **Review** — a person looks: the owner's phone screenshots each sprint, and the code review.

## The rules

### 1. No sideways scroll, ever
- **Why:** a page that slides left and right feels broken and hides content off the edge.
- **Checked by:** mobile-check (`scrollWidth ≤ clientWidth` on every cell; it names the widest element).
- **Copy this:** long words and IDs get `break-words` or `truncate`; rows that might not fit use
  `flex flex-wrap` (the TVET requirement rows, `src/components/RequirementsCard.tsx`). A bar that must stay ONE
  row is built from fixed, measured widths instead: the student header (`src/components/AppHeader.tsx`) is the
  logo (`shrink-0`), one action and the menu button — measured in Tamil and Malay at 360 — and a row with a
  long tag restacks below `sm` (`src/components/StpmSubjectRow.tsx`). Both pinned by
  `src/lib/__tests__/navLayout.test.ts`.

### 2. Text fields are 16 px or more on phones
- **Why:** iPhone Safari zooms the whole page when you tap a field under 16 px, and it stays zoomed.
- **Done for you (M1a):** one rule at the end of `src/app/globals.css` sets every text-entry
  input, select and textarea to 16 px below `md` AND on any touch-first screen (`pointer: coarse` —
  an iPhone held sideways is 844–932 px wide, past `md`) — outside `@layer`, with enough specificity to beat
  `text-sm`, `text-xs`, `text-[13px]` and `max-md:` sizes. It only ever raises: a field that asks for
  `text-base` or larger keeps its size. On a mouse-driven screen from `md` up every field keeps its own class size. You do
  not need to do anything — just never write `!text-sm` (an `!important` size beats the rule).
- **Checked by:** static guard (the rule exists, below `md`, outside every `@layer`; no field carries
  an `!important` small size) and mobile-check (the computed size of every visible field: 0 under 16).

### 3. Tap targets are at least 44 × 44 px
- **Why:** a thumb is not a mouse pointer; small targets cause mis-taps, worst for buttons side by side.
- **Checked by:** mobile-check (every link, button, select, summary, and the label of every
  checkbox/radio). Inline text links inside a sentence are excepted.
- **Copy this:** `h-11` buttons (`src/components/bursary/BursaryLetters.tsx`). Make the hit area big
  with padding — the look can stay small. (A pseudo-element hit area is invisible to the check, so use padding.)
  For a small control in a line of text, pad it to 44 and cancel the padding with negative margins
  so nothing around it moves: `src/components/Toggle.tsx` (44 × 44 button, 44 × 24 track inside),
  `src/components/InfoTip.tsx` (44 px around an 18 px mark). A small round face on a card: a 44 px
  button with the face inside it (`CourseCard.tsx`'s save button, Mobile M3). A list of links: each an
  `inline-flex min-h-11` row with the list's gaps dropped, and two columns on a phone so the list is no
  taller (`AppFooter.tsx`).

### 4. No hover-only information or actions
- **Why:** a phone has no hover. A tooltip or a hover-revealed button simply does not exist there.
- **Checked by:** static guard (`title=` as the only explanation on an icon-only button or link) and review.
- **Copy this:** visible text, or a tap `InfoTip` (`src/components/InfoTip.tsx`, its bubble lazily from
  `InfoTipBubble.tsx`): a tap opens it and
  it stays open until a second tap, a tap elsewhere or Escape; a mouse still opens it on hover; the
  bubble is kept on screen. `VerifiedTick` does the same for its 14 px seal (tap bubble, 44 px
  target, no hover handler). A JS hover handler listens to `pointerType === 'mouse'` only
  (a tap fires a compatibility mouseenter — `CourseDetailShared.tsx`'s save button). Never `title=` alone.

### 5. One shared Sheet for every overlay
- **Why:** each hand-rolled overlay re-decides height, scrolling and the close button, and several
  decided wrong — buttons hidden behind the iPhone keyboard.
- **The rule (enforced since M1b part 2): every overlay uses `src/components/Sheet.tsx`** — never a
  hand-written `fixed inset-0`. The 18 that existed moved onto it, except three full-screen panels
  that are not dialogs (the document viewer, the console's phone nav drawer, the Ctrl/⌘-K command
  palette), each named with its reason in the guard and made phone-correct.
- **Checked by:** static guard — a `fixed inset-0` anywhere but `Sheet.tsx` and the three named
  exemptions FAILS the build — and `Sheet.test.tsx` (focus, Tab, Escape, backdrop, `dismissible`,
  scroll lock). Sign-in, consent, award acceptance and money use `dismissible={false}`.
- **Copy this:** `<Sheet open title onClose footer={…}>body</Sheet>` — a bottom sheet on a phone (grab
  bar, 90 % of the visible height, only the body scrolls, title row and footer stay put, footer
  clears the home bar, rises above the keyboard and keeps the focused field in view), a centred
  dialog from `md`. `onSubmit` makes body + footer one form; `busy` blocks closing during an action;
  `dismissible={false}` (consent, sign-in) removes the × and makes Escape and the backdrop do
  nothing. It is portalled to `<body>`: put a menu inside it with the portalled `admin/Menu`, never
  an `absolute` dropdown (the body scrolls, and would clip it). Being portalled, it also leaves its page's
  wrapper classes behind: pass a page face such as `font-plex` with `className`. **Focus opens on the first
  field** — when that is not the main action (the sign-in gate's phone box, with phone sign-in off), pass
  `initialFocus`, or a phone's keyboard rises and pushes the real action out of view. Sandbox: `sheet-short`,
  `sheet-long-form`, `sheet-locked-confirm`.
  **Filters on a phone go in a Sheet** (Mobile M3): `src/components/search/SearchFilterSheet.tsx` — one group of
  44 px chips per facet, long facets behind "Show all (N)", focus on the first chip, a tap applies at once and the
  footer button says how many results and closes. The desktop keeps its own row; both read ONE list of facets.
  Sandbox: `search-filters`.

### 6. Safe areas and dvh
- **Why:** `100vh` on iPhone is taller than the visible screen while the address bar shows; fixed
  bars sit under the home indicator unless they pad for it.
- **Checked by:** static guard (`vh` heights, `h-screen`; `min-h-screen` on its own floor) and review.
  The root layout sets `viewportFit: 'cover'` so `env(safe-area-inset-*)` works (also guarded).
- **Copy this (ONE pattern, M1a):** a bar that touches a screen edge pads that edge with
  `max(<its own padding>, env(safe-area-inset-<edge>))` as a Tailwind arbitrary value — the bar keeps
  its look on every phone without a notch and clears the home bar on one that has it:
  `pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))]` (the apply and next-steps bottom tab bars),
  `bottom-[max(1rem,env(safe-area-inset-bottom))]` (`Toast.tsx`). A bar with no padding of its own on
  that edge just adds the inset: `pt-[env(safe-area-inset-top)]` (`AppHeader.tsx`, the sponsor portal
  header), `bottom-[env(safe-area-inset-bottom)]` (`admin/SaveBar.tsx`), the admin drawer
  (`AppShell.tsx`). The LEFT and RIGHT insets (landscape) are on `body` once, in `globals.css`.
  Heights: `dvh` units (`max-h-[90dvh]`, `min-h-dvh`), never `vh` — but a browser that does not know `dvh`
  (Safari < 15.4, Chrome < 108) drops the WHOLE declaration, so a cap a screen depends on (the Sheet's) is
  computed in pixels from `visualViewport` instead.
  **A phone's main action in a long page is a sticky bottom bar** (Mobile M3, `CourseSaveBar` in
  `src/components/CourseDetailShared.tsx`): `sticky bottom-0 md:hidden` — `sticky`, not `fixed`, so it rests
  above the footer at the end and never covers it — padded `pb-[max(0.75rem,env(safe-area-inset-bottom))]`, and it
  calls `useBottomBarInset(ref)` (`src/lib/bottomBarInset.ts`) so the toast rises above it.
  **Mark it `data-page-bar`** (Mobile M4b): the student tab bar hides while any such bar is on the page (one bottom
  bar at a time), and `mobileStandard.test.ts` fails on an unmarked bar pinned to the foot of a student screen.
  **The student tab bar** (`src/components/StudentTabBar.tsx`) is `fixed`, not sticky — it is the way around, always in
  reach — so the page is padded by its height instead (`globals.css`, "THE STUDENT TAB BAR": `4rem` + the home-bar inset,
  and `--bottom-bar` for the toast). mobile-check fails a page whose end lies under it.

### 7. Tables become cards on phones
- **Why:** a seven-column table dragged sideways is the wrong shape for the screen people check things on.
- **Checked by:** static guard (`src/lib/__tests__/pageWidth.test.ts` — every admin list has phone
  cards or a written exemption) and mobile-check (overflow).
- **Copy this:** `hidden md:block` table + `md:hidden` cards (`src/app/admin/students/page.tsx`), or
  `TableFrame` (`src/components/admin/TableFrame.tsx`) for genuinely wide data. A side-by-side COMPARISON
  on a phone: two columns, each row's label a heading line above its two values, and a chooser for the second
  column when there are more (`src/components/saved/SavedCompare.tsx`, Mobile M3; sandbox `saved-compare`).

### 8. The right keyboard for every field
- **Why:** a number pad for a postcode, the one-time-code row for an OTP — fewer mistakes, faster.
- **Checked by:** review.
- **Copy this:** `inputMode="numeric"` / `"decimal"` (`src/components/admin/InvoicePaymentPanel.tsx`);
  `type="tel"`, `type="email"`, `autoComplete="one-time-code"`, `autoComplete="postal-code"`. A phone field
  is `autoComplete="tel-national"` (our fields hold the LOCAL number; `tel` fills "+60 …", which the profile
  rejected and which cut a digit off an 011 number) or `"off"` for somebody else's number. Guarded: rule 10
  in `mobileStandard.test.ts` fails on any `autoComplete="tel"`.

### 9. Files: camera-friendly pickers, PDFs full-screen
- **Why:** some phones will not open the picker for a `hidden` input; a PDF in an iframe shows only
  page one on iPhone, with no zoom.
- **Checked by:** static guard (`type="file"` inputs hidden with `hidden`; no `capture` on any file input — it
  forces the camera and refuses the PDF she downloaded), mobile-check (since M4 it measures the LABEL that opens a
  file picker, which an `sr-only` input hid) and review (PDF iframes).
- **Copy this:** `src/components/ScholarshipDocuments/cards.tsx` — `sr-only` input, a 48 px "Take a photo or choose a
  file" button on an empty card, full-width 44 px Replace and Remove under a file, Remove ASKING in a sheet first
  (`ScholarshipDocuments/RemoveConfirm.tsx`, lazy, with the phone's own confirm as its fallback), busy per card, and
  the early size / format refusal from `src/lib/uploadCheck.ts`. A long document (the award agreement) opens in a
  tall reader sheet, not a scroll box in the page (`src/components/scholarship/AwardContract.tsx`). PDFs open
  full-screen or in a new tab on phones.

### 10. Long forms keep their progress
- **Why:** iOS kills a background tab while a student checks WhatsApp or the camera; everything typed is lost.
- **Checked by:** static guard (`mobileStandard.test.ts`, rule 10: the apply page keeps, restores and clears its
  draft; its submit sends nothing while one is in flight and Enter before the last step is Next; Back / Continue is
  a sticky bar clear of the home bar) and the draft's own tests (`applyDraft.test.ts`, `page.draft.test.tsx`).
- **Copy this (Mobile M4, owner: this tab only):** `src/lib/applyDraft.ts` — the form in the TAB's `sessionStorage`,
  never the device's: bound to the user id, the programme, a version and 24 h (anything else is deleted on read);
  NEVER the IC, a typed signature or a consent (given afresh where they are used); written 0.5 s after a change and
  at once on `visibilitychange`→hidden / `pagehide` (iOS reclaims a hidden tab and a timer may never fire); cleared
  on submit and by every sign-out path. Tell her, quietly: "Saved on this device only · nothing is sent until you
  submit" (`ApplyProgress`). A form whose answers the SERVER already keeps (the award page's quiz and parent PIN)
  reads them back instead — never a second copy on the phone. One step per screen, a step line instead of an icon
  tab bar, and the main action in a sticky bottom bar (`src/components/scholarship/ApplyStepper.tsx`; the admin
  pattern is `src/components/admin/SaveBar.tsx`).

### 11. One-thumb navigation
- **Why:** every shell needs a phone navigation that fits — in Tamil, at 360 px.
- **Checked by:** mobile-check (Tamil at 360) and review.
- **Copy this:** the student header's menu (`src/components/AppHeader.tsx` + `StudentMenus.tsx`, Mobile M2: a
  one-row bar, then every destination once in the shared `Sheet`, loaded on the first open), the admin drawer
  (`src/components/admin/AppShell.tsx`). **Students also have a bottom tab bar** (Mobile M4b,
  `src/components/StudentTabBar.tsx`, mounted only by `AppHeader`): Dashboard · Explore · Saved · BrightPath, existing
  core words and the organisation's short name, 64 px tabs whose word may wrap to a second line (Tamil at 360). Its
  rules live in CSS (`globals.css`): phones only, hidden while she types, replaced by a page's own bar (`data-page-bar`,
  rule 6), never shown by a browser without `:has()`. A focused flow that keeps the header turns it off with
  `<AppHeader tabs={false} />`. Sandbox: `tab-bar-signed-in`, `tab-bar-signed-out`. mobile-check: one bottom bar at a
  time, and nothing of the page left under the tabs.

### 12. Body text is 12 px or more on phones
- **Why:** smaller text is unreadable for many people. 9–11 px is for badges only.
- **Checked by:** review.
- **Copy this:** `text-xs` (12 px) as the smallest body size.

### 13. Desktop-only screens say so
- **Why:** half-working is worse than an honest "use a computer for this".
- **Checked by:** static guard (every route is classed in `src/lib/mobileClass.ts`, and a desktop-only
  route cannot compile without a written reason) and review.
- **Copy this:** the shared `DesktopOnly` panel (built in M7) below `md`, with a read-only summary
  where useful.

### 14. Design at 390 px first
- **Why:** a desktop design squeezed down is never as good as a phone design widened.
- **Checked by:** review (the workspace's Stitch-first rule).
- **Copy this:** new pages and redesigns get a Stitch screen at phone width first, then desktop.

### 15. One box level; sections on phones
- **Why:** owner, 2026-11-02, comparing our phone screens with the Grab app: a card inside a card inside a 24 px
  gutter leaves a 300 px column of nested borders. A phone reads best as full-width sections.
- **The rule:** page gutter 16 px on a phone (`px-4`, 24 px from `md`). AT MOST ONE box level: below `md` an outer
  card is a plain full-width SECTION — no border, no rounded corners, no padding beyond the gutter — with its
  heading, separated from the next by a thin divider; from `md` it is the card it always was. Nothing inside a
  section is boxed again: rows, answer groups and particulars are separated by dividers (`divide-y`) or spacing.
  Exceptions: genuine controls (inputs, buttons, chips) and coloured status callouts. Tighter rhythm (sections
  ~16 px apart, rows 8-12 px) — never at the cost of a 44 px target or a 16 px field.
- **Checked by:** static guard (`mobileStandard.test.ts`, rule 15: the swept screens draw no hand-written white
  card — rounded-xl or -2xl, a border and the card ground in one class string, in any order — and no bare 24 px
  `container` gutter; `PHONE_SECTION` boxes nothing below `md`) and review. Swept in Mobile M4: apply, application
  (step wizard, documents, Action Centre, post-award tasks) and award; in M4b: Dashboard, Search, the course pages
  (`/course`, `/stpm`), Profile, Saved and Settings; in M4c: the rest of the student pages — My Bursary and all its
  tabs, Home, the scholarship landing, the report, About / Contact / Privacy / Terms / Cookies / Get started, the
  pathway pages, onboarding (and the scholarship's own) and both quizzes. A string sized as a 44-48 px button (`h-11`,
  `h-12`, `min-h-11`) is a control, so the card check passes it.
- **Copy this:** `src/lib/phoneSection.ts` — `PHONE_GUTTER` on the page's `<main>`, `PHONE_SECTION` for what was
  a card, `PHONE_ROWS` for the items inside it, `PHONE_INNER_BOX` (or `md:`-prefixed box classes) for a group that
  was boxed inside a card, `PHONE_BLEED` for a sticky bar that runs edge to edge across the gutter. A test that
  found a card by its look (`.border.rounded-lg`) finds it by a hook instead (`data-doc-card`).
  M4b examples: a section whose padding sits on rows inside it gets a `md:`-only card of its own instead of
  `PHONE_SECTION` (whose `md:p-5` would double it — `RequirementsCard.tsx`'s `REQ_SECTION`); read-only particulars are
  hairline rows on a phone (`profile/page.tsx`'s `PROFILE_ROWS`); a list of boxed items becomes `PHONE_ROWS` with each
  item's box `md:`-only (the institution cards); a section's icon tile is `hidden md:flex`; its Edit is a 44 px text button.
  ⚠ **Dividers are `max-md:` only** (`max-md:divide-y max-md:divide-ground-100`), never `divide-y … md:divide-y-0`:
  Tailwind's divide selector is stronger than a child's own `md:border`, so the `md:` reset strips the borders of every
  box after the first from `md` (guarded). A section inside a parent that already spaces its children takes
  `PHONE_SECTION_NO_GAP`, so the desktop keeps its old spacing.
  ⚠ **Only rows go inside a `PHONE_ROWS` list.** The divider styles every direct child, so a button or a note placed
  in the list ("Show all", "+ Add elective") loses its own border on a phone — put it after the list (M4b, M4c reviews).
  M4c examples: what was a BORDERLESS shadow card (`rounded-2xl bg-ground-0 p-5 shadow-sm`, all of My Bursary) takes
  `PHONE_SECTION_FLAT` — the same card from `md`, no border, no margin of its own. A page that was ONE card around the
  whole text (About, the legal pages, Contact, Get started, the report, a form step) keeps no section at all on a phone:
  the box classes become `md:`-only and the text sits on the gutter. A shared component that a non-student screen also
  draws takes a `className` with its old box as the default (`sponsor/SpendingCard.tsx`). A list inside a section with
  a fixed height and its own scroll bar loses both on a phone (`/pathway/stpm`'s school list; Load more pages it).

## Tamil type

Tamil paints in **Mukta Malar** (owner, 2026-10-31; live from Mobile M1a), copied byte for byte from
SJKT Connect: `src/fonts/mukta-malar/MuktaMalar-Tamil-{400,600,700}.woff2`, declared in
`src/app/layout.tsx` with `next/font/local`, a Tamil-only `unicode-range`, `preload: false` and no
fallback faces. It sits FIRST in every stack (`font-sans`, `font-plex`, `--figures-face`, the sponsor
portal's Inter stack) yet never touches a Latin letter or a digit, and only a page that shows Tamil
downloads it (measured: an English page fetches Lexend only; a Tamil page adds the three Mukta files,
99 KB). Before M1a every phone drew Tamil in its own system font, so widths differed by device.
`fontSources.test.ts` pins the files (SHA-256) and every option.

## Running the checks

```bash
cd halatuju-web
npm run gates                       # includes the static guards
npm run mobile-check                # BEFORE A PUSH: this branch — public pages + every sandbox surface
npm run mobile-check -- --update    # after a fix: lower the baseline (never raises)
npm run mobile-ledger               # regenerate docs/mobile-ledger.md
MOBILE_PUBLIC_BASE=https://halatuju.xyz npm run mobile-check   # AFTER A DEPLOY: live public pages + local sandbox
MOBILE_BASE=https://halatuju.xyz npm run mobile-check          # AFTER A DEPLOY: live public pages only
```

**Which to use when.** The default run measures **this branch**: it starts `next dev` on port 3100
with the sandbox on, and the public pages get their data from the live API — the check fetches each
API read from production itself (no local API needed, and no CORS in the way) and hands it to the
page. So a sprint that changes a public page checks its own work before the push. The two
`halatuju.xyz` lines measure **production**, so they only tell you what is deployed: use them after a
deploy, never instead of the default run.

Screenshots of every cell land in `halatuju-web/mobile-check/output/screenshots/` (gitignored).
The check is read-only: it never signs in, never submits, and blocks anonymous sign-in so it creates
no users on the real project.
