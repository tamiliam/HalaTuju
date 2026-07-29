# Layer 1 — themes: light, dark, and a tenant's own colours

**Status: PROPOSED, not approved.** Supersedes the seven-sprint sketch in
`docs/plans/2026-07-28-configuration-layers-roadmap.md` §Phase 2, which covered the repaint only and
omitted the screen an `org_admin` actually touches.

**The owner's answers, 2026-07-29, all four now settled:**

| | |
|---|---|
| Platform ships | light and dark as **defaults** |
| An organisation may | author its own themes and palettes, and customise its surfaces |
| Colours belong to | the **organisation** (`org_admin`) — a deliberate reversal of the PRD's superadmin-only branding rows |
| Light/dark belongs to | the **person**, with **Auto** following the time of day |
| Semantic tones (pass / check / blocked) | stay **ours** — owner ruling, 2026-07-29 |
| Layer 2 | still not built; the option stays open, and the [standing constraint](2026-07-28-configuration-layers-roadmap.md) applies verbatim |

---

## What is actually there — measured 2026-07-29, not remembered

Counted across `halatuju-web/src/**`, excluding tests.

| Surface | Chromatic | Brand (`primary-N`) | Ground (neutral + white/black) | Files |
|---|---:|---:|---:|---:|
| Admin console | 480 | 43 | 665 | 34 |
| Public course guide | 379 | 200 | 719 | 36 |
| Shared components | 328 | 134 | 553 | 52 |
| Sponsor portal | 307 | **1** | 371 | 21 |
| Officer cockpit (ONE file) | 235 | 31 | 275 | 1 |
| Student surfaces | 234 | 204 | 636 | 16 |
| **Total** | **1,963** | **613** | **3,705** | **160** |

### Three findings that shape everything below

**1. The mechanism is already proven in production — this is an extension, not an invention.**
`tailwind.config.ts` maps `primary-50…900` to `rgb(var(--brand-N) / <alpha-value>)`; `globals.css`
defines the channels; `branding-context` overrides them at runtime for a tenant. **613 utilities are
already tenant-brandable and already mode-agnostic.** No new approach is needed — the same trick has
to reach the ground and the tones. There is also **no `dark:` usage anywhere in the product**, so
there is nothing to unpick.

**2. The chromatic half is largely MECHANICAL. The ground half is JUDGEMENT — and it is nearly twice
the size.**
1,834 of the 1,963 chromatic utilities (**93%**) belong to just four tone families, and they are
almost perfectly balanced — info 546, critical 455, positive 439, caution 394. Twelve
(property, shade) pairs cover **88%** of them:

```
text-{tone}-600  289    bg-{tone}-50   287    text-{tone}-700 281    bg-{tone}-100  163
border-{tone}-200 132   bg-{tone}-600  110    text-{tone}-800 103    text-{tone}-500 70
bg-{tone}-700     68    bg-{tone}-500   49    border-{tone}-500 42   ring-{tone}-500 38
```

That is a convention applied by hand ~1,800 times, and `components/InfoBox.tsx` already names it in
so many words — success / info / warning / block, locked to `bg-50 / border-200 / text-800`. **So the
token vocabulary is an EXTRACTION of something the codebase already believes, not a design exercise**,
and a codemod with a dozen rules does most of the work.

The **3,705 ground utilities** are the opposite. `bg-white` is a card, a page, a modal, an input, a
sticky header and a table row, and each becomes a different surface token. There is no codemod for
that, and it is the half that decides whether dark mode looks designed or merely inverted.

**3. Tenant colour and dark mode are two separable projects that share one mechanism.**
Setting a tenant's brand colour works *today*, wherever `primary-N` is used. Dark mode needs the
repaint. They are sequenced together below because they share the token layer — but if the plan ever
has to be cut, that is the seam it cuts along. **⚠ Note the unevenness before promising anything:**
`primary-N` is concentrated in student surfaces (204) and the public guide (200); the **sponsor
portal uses it once** and the admin console 43 times. A tenant who set a colour today would see the
student journey change and almost nothing else.

---

## The shape of the plan

**Ten sprints in two arcs.** The switch ships **dark in F1 and flips at the very end**, which is what
makes the repaint order a question of risk rather than of user-visible breakage — no one can reach a
half-repainted dark mode.

### Arc F — the foundation (dark mode, and surfaces ready to be tinted)

#### F1 — The vocabulary, the switch, and one surface proven end to end
**Goal.** A person can pick Light / Dark / Auto, and the sponsor portal is completely correct in both.
Everything else is untouched and unaffected.

**Why the switch is FIRST and not last.** The superseded plan built the switch in sprint 12. That
means repainting six surfaces before anything can prove the vocabulary survives a mode flip — and a
token set that is wrong in dark is discovered after 1,900 edits rather than after 300. The switch is
the falsifier; it belongs at the front, on the smallest surface.

**Scope.** `globals.css` (light + dark token sets), `tailwind.config.ts`, a `data-theme` root
attribute, `src/lib/uiPrefs.ts` (Light/Dark/Auto), a theme switcher, the tone codemod as a reusable
script, and the **sponsor portal repaint** (21 files — smallest surface, worst ratio at 307 chromatic
against 1 brand use, and the one place the vocabulary cannot hide behind existing brand awareness).

**Design calls.**
- **`data-theme` + CSS variables, never Tailwind's `dark:`.** `dark:` doubles every class across 160
  files, hard-codes a two-theme world, and cannot express a tenant tint — which is the whole point.
- **Auto = follow the device (`prefers-color-scheme`), NOT a clock we own.** macOS and Windows both
  already flip at the user's local sunset; following the device inherits a schedule that is already
  location-aware and already theirs. Our own would need a cutover hour and a timezone, and would be
  wrong for anyone travelling or on a night shift.
- **A theme may never write `--brand-*`, and a tenant may never write the semantic tones.** Owner
  ruling. Enforced by a test in the posture of `brand-guard.test.ts`, not by a comment.
- **Ships behind a flag.** The switcher is unreachable until F7.

**Acceptance.** The sponsor portal is correct in both modes, reviewed in a browser on the sandbox.
**A mid-session flip loses no state** — a half-filled form survives the sunset, because the repaint is
a variable swap under the same DOM and never a re-render. A test asserts the brand and tone guards.

**Complexity: high** (~30 files). It is the only sprint here that is hard for a reason other than volume.

#### F2a / F2b — Shared components
**Goal.** The 52 components everything else mounts, split into two reviewable halves (student-journey
components first, the rest second).
**Scope.** `src/components/**` excluding `admin/` and `sponsors/` (repainted in F4 and F1).
**Acceptance.** Both modes correct on the sandbox; the tone codemod's output reviewed by hand, not
trusted — 88% mechanical means 12% wrong. *medium ×2 (~26 files each).*

#### F3 — Student surfaces
**Scope.** 16 files, 234 chromatic and 636 ground; `ScholarshipDocuments.tsx` alone carries 126.
**Acceptance.** The apply flow and Documents tab in both modes, on the sandbox, which already mounts
them. *medium-high.*

#### F4 — Admin console (excluding the cockpit)
**Scope.** 34 files, the largest chromatic count on the list. *high.*

#### F5 — The officer cockpit
**Scope.** ONE file: `src/app/admin/scholarship/[id]/page.tsx`, 235 chromatic and 275 ground.
**This is the one place section extraction is justified on readability alone** — and only as far as
the repaint already reaches. Never as Layer-2 groundwork. *high.*

#### F6 — Public course guide
**Scope.** 36 files, plus the ~78 colour literals returned as class strings from `lib/` —
`courseBadges.ts` (32), `applicationStatus.ts` (22), `requestStatus.ts` (14), `paymentStatus.ts` (6).
**⚠ Colour that is not in any JSX.** A codemod over `.tsx` misses them entirely, and they are exactly
the status tones the vocabulary should own. Last because it is the shared base product rather than a
tenant surface — but it must ship before the flip, or a person in dark mode clicks a course and gets
a white page. *medium-high.*

#### F7 — The flip
Lower a `palette-guard` ceiling that may only fall, remove the flag, and review every surface in both
modes. *low, but it is the sprint that must not be skipped.*

### Arc A — the authoring (what an `org_admin` actually touches)

**Not in the superseded plan at all.** This is the arc that question 7 flagged as "its own arc" and
which the owner has now confirmed is in scope.

#### A1 — A theme belongs to an organisation
**Goal.** An organisation's colours are stored, served and applied.
**Scope.** One model (or an extension of the existing branding rows), the public branding endpoint,
`branding-context`. `brandRamp()` already derives ten shades from one hex, so the derivation exists.
**Acceptance.** Two organisations, two colours, no leakage; the fence unchanged. *medium.*

#### A2 — The colour picker, and the contrast gate
**Goal.** An `org_admin` picks a colour, sees it immediately, and **cannot ship an unreadable one**.

**⚠ THE STAGING DECISION, AND THE ONE THING THAT MAKES IT SAFE.** The owner's intent (2026-07-29) is
a **full token set** eventually; the near-term build is a **single-colour picker**, expanded "when
there is a real ask". That is the right call — but only if the small version does not foreclose the
large one, and there is an obvious way to build it that does:

> **Store the TOKEN SET from day one. The picker is a UI that WRITES it.**
> A picker that stores `brand_hex` and derives the ramp at serve time is smaller by one table column
> and makes the full palette a migration — two storage shapes, a backfill, and every reader taught
> both. A picker that derives ten shades in the editor and saves them AS TOKENS makes the full
> palette a **second editor over the same storage**: new screen, no migration, no second reader.

**And it is the right design on its own merits, which is why it is not a placeholder.** A tenant
approved *those* colours and they passed *that* contrast check. If the resolved values were derived
per request, improving `brandRamp()` would silently restyle every tenant's product without anyone
asking — the same reasoning behind snapshotting an application at submit and freezing a published
terms version. Storing what was approved is correct here regardless of what comes next.

**The contrast gate follows the same rule:** check **token PAIRS**, not "is this hex safe". A checker
written against a hex has to be rewritten when tokens arrive; one written against the pairs actually
rendered simply gets more pairs. Deterministic relative-luminance maths, tested, **blocking at save —
it refuses, it does not warn.** A tenant will pick a colour that renders 4:1 against white; a warning
is dismissed and a student cannot read the page.

**Prerequisite.** Stitch prototype approved before any page code (house rule).

**Also settled.**
- **The preview surface already exists.** The design sandbox mounts real components against fixtures,
  so a tenant previews their colour on genuine screens without touching live data.
- **A tenant tints the brand and the ground; the tones stay ours.** Owner ruling, enforced in A1's
  serializer as well as in the UI — a UI-only guard is not a guard.

**Complexity: medium-high.**

#### A3 — Draft, preview, publish, revert
**Goal.** Changing a colour is not a live experiment on applicants.
**Scope.** Draft → sandbox preview → publish, mirroring the sponsor-terms shape already in the
codebase; an `AUDIT` line per publish; one-click revert. *medium.*

#### A4 — The full palette — DEFERRED, WITH A WRITTEN TRIGGER
**Not scheduled.** The owner's stated intent, held until there is a real ask.

**⚠ THE TRIGGER, written down because this project has watched an unwritten one fail to fire.** The
nav/IA N3a trigger had *already fired* before anyone noticed, because "when there is a second
organisation" lived in prose nobody re-read. So, explicitly — build A4 when **any one** of these is
true:

1. A tenant asks for a colour the ramp cannot produce (a distinct accent, a different surface tint).
2. A tenant's brand cannot pass the contrast gate as a single hex, and the honest fix is per-token
   control rather than telling them to pick a different brand colour.
3. A second tenant onboards with a designer who asks what they can change, and the answer "one
   colour" ends the conversation badly.

**What A4 is NOT allowed to be, in the meantime:** a `tokens` column that nothing writes, a disabled
"advanced" tab, or a reserved key. The forward-compatibility is entirely in A2's storage shape, which
is justified above on its own merits. See the standing constraint in the Layer 0 roadmap.

---

## Sequence, and the one thing to decide

**Recommended: F1 → F2a → F2b → F3 → F4 → F5 → A1 → A2 → A3 → F6 → F7.**

Every surface Suresh named — student application, administration pages, sponsor pages — is repainted
before the editor appears, so the first colour he sets lands coherently across all three. The public
course guide follows, then the flip.

**The alternative, and why I do not recommend it:** running arc A straight after F1 gets Suresh a
colour editor five sprints sooner. But `primary-N` is unevenly distributed — his colour would
transform the student journey, barely touch the admin console and do nothing at all to the sponsor
portal. A tenant's first experience of the feature would be "it half works", which generates more
support than it saves time.

**If the ten sprints need cutting, cut along finding 3**: arc F alone gives every person light and
dark. Arc A alone gives a tenant colour where `primary-N` already reaches. They are separable.

---

## Verification, per sprint

- `jest`, `tsc --noEmit`, `next build`, `node scripts/check-i18n.js`.
- **A `palette-guard` ceiling that may only fall** — each repaint sprint lowers the count of raw
  colour literals on its surface and can never raise it.
- **Both modes reviewed in a BROWSER on the sandbox.** A passing test is not the evidence here, and
  this arc is the reason the sandbox was built.
- **The mid-session flip test, every sprint**: change mode with a form half-filled; nothing is lost.
- **The two guards, every sprint**: a theme cannot write `--brand-*`; a tenant cannot write a tone.

## Open, and not mine to default

1. **✅ ANSWERED 2026-07-29 — a full token set eventually, a single-colour picker now.** Owner:
   *"I meant full set of tokens. But can we start with picker and move to the full set? … we build
   picker; stabilise it, and move to the full palette when there is a real ask."* Reflected in A2
   (which stores tokens from the first day so the expansion is a screen, not a migration) and A4
   (deferred, with a written trigger).
2. **✅ ANSWERED 2026-07-29 — the account.** Owner: *"Light/dark choice would be under the personal
   account settings/profile."* So it is a PERSON's setting stored against their account, and it
   follows them between machines — which is the outcome that matters for anyone who needs dark for
   accessibility rather than taste.
   **⚠ THREE THINGS THIS PULLS IN THAT ARE EASY TO COST AT ZERO. Size F1 with them, not without.**
   - **There are FOUR account surfaces, not one**, because there are four kinds of person:
     `/settings` and `/profile` (student), `/admin/profile` (every console role),
     `/sponsor/(portal)/account` (sponsor). The control has to appear on each, and the value has to
     persist against three different identity models — `StudentProfile`, `PartnerAdmin`, `Sponsor`.
     A single shared control component, three small write paths.
   - **Account-stored means a FLASH OF THE WRONG THEME unless it is handled deliberately.** The value
     arrives with the session, which is after first paint, so a dark user would see a white page and
     then watch it turn — on every navigation. The fix is standard and must be in the sprint from the
     start rather than patched later: **the account is the source of truth, mirrored to
     device-local storage for an instant first paint**; read local synchronously before paint,
     reconcile with the account when the session resolves. Getting this wrong is not subtle — it is
     visible on every page load, and it is the single most likely thing to be discovered late.
   - **An anonymous visitor has no account.** The public course guide is browsable logged-out, so
     there the answer is Auto (the device) with any explicit toggle held device-local until they sign
     in, at which point their account value wins. State it, or the first person to notice will report
     it as a bug.
3. **✅ ANSWERED 2026-07-29 — ONE SCREEN, TWO TABS.** Owner. Layer 0's configuration screen (what a
   programme asks for) and Layer 1's colour picker are the same person doing two related jobs, so
   they share one route with two tabs rather than two menu entries.
   **⚠ THIS CREATES A DEPENDENCY THAT DID NOT EXIST BEFORE, and it points BACKWARDS.** Layer 0
   Sprint 5 is not built yet. Whichever of the two is built first **owns the tabbed shell** — a route,
   a `NAV_GROUPS` entry, the role gate (`org_admin` + `super`), and the org fence entry in
   `test_org_fence.py` — and the second one adds a tab to it. Build either as a single-purpose page
   and the other arrives as a retro-fit.
   **▶ Recommend Layer 0 Sprint 5 goes first** and lands the shell, because its tab is the one that
   completes work already shipped: sprints 2, 3a and 3b are all plumbing, and **until that screen
   exists an `org_admin` cannot actually change anything.** Three sprints of Layer 0 have shipped and
   Suresh still has no control to touch. Not a blocker for F1 — nothing in F1 touches that route —
   but it is the sequencing question worth putting to the owner before A2 is scheduled.

