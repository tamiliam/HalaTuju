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
  `flex flex-wrap`, as the Home top bar does (`src/app/page.tsx`, pinned by
  `src/lib/__tests__/navLayout.test.ts`).

### 2. Text fields are 16 px or more on phones
- **Why:** iPhone Safari zooms the whole page when you tap a field under 16 px, and it stays zoomed.
- **Checked by:** static guard (unprefixed `text-sm` / `text-xs` / `text-[<16px]` on an input, select
  or textarea) and mobile-check (the computed font size, which also catches inherited sizes).
- **Copy this:** the `.input` class in `src/app/globals.css` (16 px). Smaller text is allowed from
  tablet up: `text-base md:text-sm`.

### 3. Tap targets are at least 44 × 44 px
- **Why:** a thumb is not a mouse pointer; small targets cause mis-taps, worst for buttons side by side.
- **Checked by:** mobile-check (every link, button, select, summary, and the label of every
  checkbox/radio). Inline text links inside a sentence are excepted.
- **Copy this:** `h-11` buttons (`src/components/bursary/BursaryLetters.tsx`). Make the hit area big
  with padding — the look can stay small. (A pseudo-element hit area is invisible to the check, so use padding.)

### 4. No hover-only information or actions
- **Why:** a phone has no hover. A tooltip or a hover-revealed button simply does not exist there.
- **Checked by:** static guard (`title=` as the only explanation on an icon-only button or link) and review.
- **Copy this:** visible text, or a tap `InfoTip` (`src/components/InfoTip.tsx` — its tap behaviour
  is fixed in M1). Never `title=` alone.

### 5. One shared Sheet for every overlay
- **Why:** each hand-rolled overlay re-decides height, scrolling and the close button, and several
  decided wrong — buttons hidden behind the iPhone keyboard.
- **Checked by:** static guard (`fixed inset-0` outside the shared Sheet).
- **Copy this:** until the shared `Sheet` lands in M1, the scrolling modal in
  `src/components/admin/IntakeYearTab.tsx`. The Sheet will be: a bottom sheet on phones, centred on
  desktop, `max-h-[90dvh]`, inner scroll, 44 px close, safe-area padding.

### 6. Safe areas and dvh
- **Why:** `100vh` on iPhone is taller than the visible screen while the address bar shows; fixed
  bars sit under the home indicator unless they pad for it.
- **Checked by:** static guard (`vh` heights, `h-screen`; `min-h-screen` on its own floor) and review.
  The root layout sets `viewportFit: 'cover'` so `env(safe-area-inset-*)` works (also guarded).
- **Copy this:** `dvh` units (`max-h-[90dvh]`, `min-h-dvh`); sticky bars add
  `pb-[env(safe-area-inset-bottom)]`. Sticky bar pattern: `src/components/admin/SaveBar.tsx`.

### 7. Tables become cards on phones
- **Why:** a seven-column table dragged sideways is the wrong shape for the screen people check things on.
- **Checked by:** static guard (`src/lib/__tests__/pageWidth.test.ts` — every admin list has phone
  cards or a written exemption) and mobile-check (overflow).
- **Copy this:** `hidden md:block` table + `md:hidden` cards (`src/app/admin/students/page.tsx`), or
  `TableFrame` (`src/components/admin/TableFrame.tsx`) for genuinely wide data.

### 8. The right keyboard for every field
- **Why:** a number pad for a postcode, the one-time-code row for an OTP — fewer mistakes, faster.
- **Checked by:** review.
- **Copy this:** `inputMode="numeric"` / `"decimal"` (`src/components/admin/InvoicePaymentPanel.tsx`);
  `type="tel"`, `type="email"`, `autoComplete="one-time-code"`, `autoComplete="postal-code"`.

### 9. Files: camera-friendly pickers, PDFs full-screen
- **Why:** some phones will not open the picker for a `hidden` input; a PDF in an iframe shows only
  page one on iPhone, with no zoom.
- **Checked by:** static guard (`type="file"` inputs hidden with `hidden`) and review (PDF iframes).
- **Copy this:** `src/components/ScholarshipDocuments/cards.tsx` — `sr-only` input, big button,
  `accept="image/*,application/pdf"`. PDFs open full-screen or in a new tab on phones.

### 10. Long forms keep their progress
- **Why:** iOS kills a background tab while a student checks WhatsApp or the camera; everything typed is lost.
- **Checked by:** review (the apply draft is decided in M4).
- **Copy this:** keep the main action reachable with a sticky bottom bar
  (`src/components/admin/SaveBar.tsx`); save a draft as the student goes.

### 11. One-thumb navigation
- **Why:** every shell needs a phone navigation that fits — in Tamil, at 360 px.
- **Checked by:** mobile-check (Tamil at 360) and review.
- **Copy this:** the admin drawer (`src/components/admin/AppShell.tsx`) or bottom tabs
  (`src/app/scholarship/apply/page.tsx`).

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

## Tamil type

Tamil will use **Mukta Malar** (owner, 2026-10-31), adopted in **M1** from SJKT Connect:
`C:\Users\tamil\Python\Production\SJKTConnect\frontend\lib\fonts.ts` loads a Tamil-only subset
(`frontend/app/fonts/mukta-malar/MuktaMalar-Tamil-{400,600,700}.woff2`) with `next/font/local`, a
Tamil-only `unicode-range`, `preload: false` and no fallback faces — so it sits first in the body
stack yet never touches English, and only Tamil pages download it. Today every phone draws Tamil in
its own system font, so widths differ by device; Tamil widths are re-measured after M1.

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
