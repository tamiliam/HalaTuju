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

#### ✅ F1 — SHIPPED 2026-07-29 (`8cf6251c` → `e9d62b8c`) — vocabulary, mechanism, sponsor portal

Retro `docs/retrospective-2026-07-29-layer1-f1-tokens.md`; decisions ×3; lessons ×4. NO migration.
1153 jest / 77 suites. **Both modes reviewed in a browser on the real page.**

**⚠ THE SWITCH A PERSON CLICKS, AND ITS ACCOUNT STORAGE, ARE SPLIT OUT — call it F1b.** Four
settings surfaces (`/profile`, `/settings`, `/admin/profile`, `/sponsor/account`) across three
identity models (`StudentProfile`, `PartnerAdmin`, `Sponsor`) plus a migration. Bolting it onto F1
made a sprint nobody could review in one sitting, and nothing needs it until F7. The mechanism,
the storage cache and the before-paint script all exist; only the control and the write path do not.

**⚠ TWO DEFECTS FOUND BY LOOKING, NEITHER FINDABLE BY A TEST I WOULD HAVE WRITTEN.** Both are
recorded in full in the retro and both generalise to every remaining repaint sprint:
1. **The codemod classifies mechanically and can be semantically wrong.** `blue → info` was right in
   every individual case and wrong about the page — the primary CTA is BRAND intent. Left as a tone
   it reversed to pale-blue-under-white in dark, **and** a tenant's colour would never have reached
   it (90 blues, 1 brand-aware colour on that surface). **Rule for F2a–F6: a filled control the user
   ACTS on carries the brand; a coloured surface that INFORMS carries the tone.** Budget review time.
2. **Colour hides where a class scan cannot see it** — the giving donut carried raw hex in an inline
   `conic-gradient`. The guard now refuses a bare hex. **F6 in particular has ~78 more of these**:
   `courseBadges.ts`, `applicationStatus.ts`, `requestStatus.ts`, `paymentStatus.ts` return Tailwind
   classes as STRINGS from TypeScript, which no `.tsx` codemod will ever touch.

**▶ CARRY INTO F2a:** a **tone-tuning pass** — reversal handles the ground well, saturated mid-stops
want an eye; best done once two or three surfaces are converted. And the sandbox now has a
**Light/Dark/Auto toggle** plus a pattern for mounting a context-driven page against fixtures
(`SponsorPortalContext` is exported for harness use) — every later repaint sprint reviews this way.

#### ✅ F2a — SHIPPED 2026-08-31 (worktree `.worktrees/layer1-f2a`)

Retro `docs/retrospective-2026-08-31-layer1-f2a-shared-components.md`; decisions ×2; lessons ×3.
NO migration. 34 files, jest **1493**. 27 components converted (386 utilities); two semantic
corrections by hand (`FundingBar` → brand, `VerifiedTick`'s `#fff` → `stroke-white`).

**▶ THE CARRIED-IN TONE-TUNING PASS FOUND SOMETHING BIGGER THAN THE TONES.** F1 carried "saturated
mid-stops want an eye" into this sprint. The tones are fine; **the GROUND was the casualty of the
reversal** — `ground-0` (the card) reversed to pure black on a `#111827` page, so every card read
as a hole. The dark ground is now written as ROLES, not a derivation, and the guard pins the
property (raised is lighter than page, in both modes) rather than the formula. See decisions.

**▶ TWO DEFECTS THAT WERE NEVER IN ANY FILE LIST.** `globals.css` is not a component and not a
surface, so no sprint owned it: `body` was `bg-white text-gray-900` (a WHITE page in dark, product
wide) and `.input` declared no background, so every text control fell back to the browser's own
white. **F3–F6 must not assume their file table is the whole surface** — the stylesheet's
`@layer base` / `@layer components`, and any control that inherits rather than declares a colour,
are part of every repaint from here on. Both are now guarded.

**▶ ONE LIGHT-MODE CHANGE, deliberate:** the page ground moves `#ffffff` → `#f9fafb`. "Pixel
identical in light" still holds for the family rename; this is a separate, documented change.

**▶ FOR F2b:** the ceiling is **659** raw colours across 25 files, `src/components/*` top level
only (`components/admin` is F4's and is deliberately NOT ratcheted — it is under active feature
work). Append F2b's files to `F2A_FILES` in `theme.test.ts` and drop the ceiling to zero.
`ScholarshipDocuments.tsx` (293 utilities) stays with **F3**.

#### ✅ F2c — SHIPPED 2026-08-31 — the category family. **F7 IS NO LONGER BLOCKED.**

Retro `docs/retrospective-2026-08-31-layer1-f2c-category-colours.md`; decision ×1; lessons ×2.
NO migration. 8 files, jest **1509**. The owner chose to build the family (2026-08-31), so F2b's
open question is closed.

`--category-1…8` in `globals.css`, wired through `tailwind.config.ts` as
`bg-category-N-surface` / `text-category-N-ink` / `bg-category-N-dot`. **Three ROLES, not stops**
(the F2a lesson, applied from the first line this time). **Dark is a role swap, not a reversal** —
the surface goes deep, the ink goes pale, because a chip must stay a chip. **The eight hues avoid
green/blue/amber/red**, which belong to the tones. Values generated from `tailwindcss/colors`.

All four category files converted; the F2b exemption block in `theme.test.ts` is replaced by a
conversion check plus a **set-level guard** (each file uses exactly as many DISTINCT swatches as
its set has members) and a **family guard** (all roles defined, all swatches distinct, ink
readable against its own surface — opposite way per mode, tone hues excluded).

**▶ TWO PRE-EXISTING BUGS FIXED, found by counting rather than reading:** `ua` and `pismp` were
both purple, and `noColorblind` and `noDisability` were both red. Two categories in each set were
already indistinguishable, before any theming work.

#### ✅ F2b — SHIPPED 2026-08-31 (worktree `.worktrees/layer1-f2b`)

Retro `docs/retrospective-2026-08-31-layer1-f2b-shared-components.md`; decision ×1; lessons ×3.
NO migration. 29 files, jest **1507**. 20 components fully converted (273 utilities) + 4 converted
in their GROUND only (81). Three more brand/tone corrections by hand (sponsor CTAs, step numbers,
form submit, selected state). **`src/components` is now done except `ScholarshipDocuments.tsx`.**

**▶ ⚠ AN OWNER DECISION IS NOW OWED, AND F7 IS BLOCKED ON IT.** Four files colour a CATEGORY, not
a state — field of study, institution type, entry condition, occupation. The vocabulary has four
tones and each asserts something, so a family rename would have put `poly`(emerald) and
`ILJTM`(green) both on `positive`, and `sains_komputer`(blue) and `sains_sosial`(sky) both on
`info`: **two pairs of distinct categories rendered identically, with nothing failing.** 48
utilities are therefore still literal and do NOT follow dark mode. See `docs/decisions.md`; the
sandbox surface **`category-colours`** shows the gap in dark. **Do not run F7 until this is
answered** — the choice is a fifth categorical token family, neutral chips, or shipping those
surfaces light.

**▶ FOR F3:** the ceiling is **287** and now names exactly one file, `ScholarshipDocuments.tsx`
(a test asserts the ceiling covers only it, so the number cannot drift into meaning something
else). F3 takes it to zero and deletes the ceiling block.

**▶ A CHECKLIST ITEM, not a discovery, from here on:** every repaint sprint greps its surface for
`bg-info-[567]00` beside `text-white` (a mis-classified CTA) and for `Record<…, colour>` lookup
tables (a category palette). Three sprints, three sets of CTA corrections.

#### F2a / F2b — Shared components
**Goal.** The 52 components everything else mounts, split into two reviewable halves (student-journey
components first, the rest second).
**Scope.** `src/components/**` excluding `admin/` and `sponsors/` (repainted in F4 and F1).
**Acceptance.** Both modes correct on the sandbox; the tone codemod's output reviewed by hand, not
trusted — 88% mechanical means 12% wrong. *medium ×2 (~26 files each).*

#### ✅ F3b — SHIPPED 2026-08-31 — the brand ramp aligned to dark. **F3's open question is CLOSED.**

Retro `docs/retrospective-2026-08-31-layer1-f3b-brand-dark.md`; decision ×1; lessons ×3. NO
migration. 4 files, jest **1518**. Owner direction the same day: *"brand colours only work in light
theme… a proper alignment is needed."*

`brandRamp()` takes a theme: in dark the tints mix toward the PAGE and the shades toward WHITE —
the ends swap — while **`--brand-500`, the tenant's colour, is byte-identical in both modes**. It
had to be DERIVED, not hand-picked: a tenant supplies one colour at runtime, so a static dark
palette would only ever have fitted BrightPath. `globals.css` gains a dark `--brand-*` block
generated by that function; `branding-context` recomputes a tenant's ramp on every mode change,
which is load-bearing because the tenant override writes INLINE styles that outrank the stylesheet.

**▶ THE RULING WAS RE-READ, NOT OVERTURNED.** `a THEME may never write the tenant brand` banned the
whole family and so banned the fix. It is replaced by four properties: `500` byte-identical across
modes (the identity — which nothing had actually checked before), the ends swapping per mode, the
dark block agreeing with `brandRamp()`, and the dark-page constant unable to drift.

#### ✅ F3 — SHIPPED 2026-08-31 (worktree `.worktrees/layer1-f3`)

Retro `docs/retrospective-2026-08-31-layer1-f3-student-surfaces.md`; lessons ×2; one OPEN question.
NO migration. 24 files, ~1205 utilities, jest **1515**.

**▶ SCOPE WAS BIGGER THAN THE TABLE SAID** — the plan's "16 files" measured 2026-07-29; the real
surface was 18 student files plus 3 app shells (`error`/`loading`/`not-found`, which carried the
same hidden page ground). Re-derive at sprint start; the table ages.

**▶ TWO MORE HIDING PLACES CLOSED.** `bg-[#f8fafc]` — an arbitrary-value CLASS setting the whole
page ground, in six files, invisible to any guard that enumerates colour names — and raw hex in SVG
`stroke`/`fill` PROPS, which were also a hardcoded blue that never followed a tenant's brand. Both
now guarded. Running list of hiding places: inline styles/gradients (F1), the stylesheet's own
layers and undeclared form controls (F2a), lookup tables of class strings (F2b), arbitrary-value
classes and SVG props (F3). **Assume there is one more.**

**▶ `graduated` resolved by WEIGHT, not a new token** — the set needed two "good" states; a fifth
tone would have lied and a category swatch would have been wrong (it is a state). `on_track` stays
tinted, `graduated` is filled.

**▶ THE `src/components` CEILING IS RETIRED** — F3 converted its last file.

**▶ ⚠ ONE OPEN QUESTION FOR F7** (see `docs/decisions.md`): `bg-primary-50`/`-100` used as a
SURFACE (101 uses, 40 files) stays near-white in dark, because `--brand-*` has no dark variant by
design. Readable, looks unfinished. Options: give the brand's PALE stops a dark treatment (needs
the owner's ruling re-read), stop using brand tints as surfaces, or ship it. **Settle before F7.**

#### F3 — Student surfaces
**Scope.** 16 files, 234 chromatic and 636 ground; `ScholarshipDocuments.tsx` alone carries 126.
**Acceptance.** The apply flow and Documents tab in both modes, on the sandbox, which already mounts
them. *medium-high.*

#### ✅ F4 — SHIPPED 2026-09-01

Retro `docs/retrospective-2026-09-01-layer1-f4-admin-console.md`; lessons ×3. NO migration.
46 files, ~1445 utilities, jest **1531**. **44 files, not the 34 the table said** — third sprint
running that the plan's file list has aged; re-derive at sprint start.

**▶ 38 FILLED CONTROLS CORRECTED TO THE BRAND across 17 files** — the largest instance of the F1
defect yet. The console's primary button is `bg-info-600 text-white`; left as a tone, a tenant's
colour would have reached almost nothing on the surface their own staff use all day.

**▶ THREE COPIES OF THE ROLE PALETTE, SILENTLY DESYNCHRONISED.** `StaffAdmin`, the reviewers list
and the Manual each declared it; the Manual's comment asked that they agree. The codemod converted
one and left another. Now one module: `src/lib/roleBadge.ts`.

**▶ FIVE MORE CATEGORY PALETTES** onto `category-N` (roles, exam type ×2, request component,
platform badge) — the `CATEGORICAL` closed list went 4 → 9 and **failed first**, which is its job.
**▶ TWO STATES BY WEIGHT, not a new hue:** `suspended` = filled `caution` against pending's tint;
`declined` = `caution-500` against `rejectedAfterReview`'s `critical-500`.

**▶ ⚠ A GUARD THAT COULD NEVER HAVE FIRED.** The filled-control check was script-generated, and the
word-boundary escape in it became a literal backspace byte — the regex compiled, matched nothing,
and passed forever. Found only by bite-checking. **Never generate a regex.**

**▶ FOR F5:** the cockpit is ceilinged at **544** in `theme.test.ts` and excluded by name.

#### F4 — Admin console (excluding the cockpit)
**Scope.** 34 files, the largest chromatic count on the list. *high.*

#### ✅ F5 — SHIPPED 2026-09-01

Retro `docs/retrospective-2026-09-01-layer1-f5-cockpit.md`; lessons x2. NO migration. 2 files,
537 utilities in ONE file, jest **1534**. The cockpit's ceiling (544) is RETIRED — it now sits
inside the console's conversion walk.

**▶ THE HUNT CAME BACK CLEAN, for the first time in six sprints.** No hex, no arbitrary-value
classes, no gradients, no inline colour styles, no entities. **Age, not size, predicts hiding
places** — the biggest file in the product was the cleanest, because it was written recently and in
one idiom.

**▶ FOUR JUDGEMENT CALLS:** two Save buttons → brand; "unrelated name" → `critical` (the generic
vision warning beside it stays `caution`, and orange used to hold them apart); the capture chip →
a CATEGORY (deterministic vs model-derived); the Check-2 briefing → INFO, not a category, because
its job is to inform and its heading already says a model wrote it. All four pinned.

**▶ SECTION EXTRACTION DECLINED.** This section allows it "on readability alone"; the repaint did
not need it, and a 3,500-line restructure is a far larger blast radius than a recolour.

**▶ ⚠ PREREQUISITE FOR F7 — THE COCKPIT HAS NEVER BEEN SEEN IN A BROWSER.** It is the one repainted
surface with no visual review: mounting it needs a large `AdminApplicationDetail` fixture, which is
a piece of work in itself, and the sandbox forbids a hand-written approximation. **F7 cannot claim
"every surface reviewed in both modes" until that fixture exists.**

#### F5 — The officer cockpit
**Scope.** ONE file: `src/app/admin/scholarship/[id]/page.tsx`, 235 chromatic and 275 ground.
**This is the one place section extraction is justified on readability alone** — and only as far as
the repaint already reaches. Never as Layer-2 groundwork. *high.*

#### ✅ F6 — SHIPPED 2026-09-02. **THE REPAINT IS COMPLETE.**

Retro `docs/retrospective-2026-09-02-layer1-f6-course-guide.md`; decisions ×2; lessons ×7. NO
migration. web only. 36 files, ~860 utilities, jest **1595**. Seven guards bite-checked.

**▶ THE COUNT WAS RIGHT AND THE TITLE WAS WRONG.** "Public course guide" was 36 files four weeks
ago and is not what those 36 files are: the guide PLUS contracts, the email editor, sources,
reviewers, the interview panel and the staff manual. F7 needs all of it, so F6 took all of it.
**Fourth sprint running that the table aged — and the first where the DESCRIPTION aged too.**

**▶ THE GUARD IS NO LONGER A LIST.** Three scans (raw colour, raw hex, arbitrary-value class) now
run over `walkFiles('src')`, so a page written next month is covered with nobody remembering to add
it. That is the property F7 actually needed; **there is no ceiling left to lower.** The per-surface
blocks stay — each carries its own sprint's reasoning and names its own surface on failure.

**▶ THE FIFTH HIDING PLACE:** two quiz pages still set their whole page ground with
`bg-[#f5f7f8]` — F3's discovery exactly, in files no sprint's list had covered. **A guard scoped to
a file list is blind by construction to whatever is not on the list.** Assume there is one more.

**▶ THE LOAD-BEARING DECISION IS A REFUSAL TO WIDEN THE FAMILY.** 17 subject codes wanted 16 hues,
and type + level sit adjacent and wanted 13; the family has 8 and they avoid green/blue/amber/red so
a category is never read as a status. Both sets went NEUTRAL — each chip already renders its own
name, and an unrecognised level had always been grey. See `docs/decisions.md`.

**▶ THREE MORE COPIES OF THE F4 ROLE-PALETTE BUG**, all found by the `Record<…, colour>` grep:
institution type (×2, plus a fourth hard-coded inline), the STPM subject vocabulary, and the matric
tracks — every pair on two pages a student moves between while comparing. Merged into
`courseBadges.ts`, `stpmSubjects.ts` and `matricTracks.ts`, numbers carried over unchanged.

**▶ TEN MORE FILLED CONTROLS ONTO THE BRAND**, including the search page's two qualification
toggles, whose SELECTED state was blue and purple — two colours in one segmented control, neither
of them the tenant's. Fifth sprint running for this defect.

#### ✅ F7a — SHIPPED 2026-09-02. **TD-222 IS CLOSED.**

Retro `docs/retrospective-2026-09-02-layer1-f7a-brand-fill-role.md`; decisions ×2; lessons ×6. NO
migration. web + api. 66 files, 142 fills. jest **1597**, pytest **5765**. Reviewed in both modes.

**▶ F7 SPLIT INTO FOUR (owner approved 2026-09-02), because measuring the blockers made it bigger
than one sprint: F7a the fill role, F7b the shape role, F7c the cockpit fixture, F7d the flip.**

**▶ THE TICKET NAMED A SYMPTOM AND THE FIX WAS TWO THINGS.** TD-222 said the dark ramp cannot carry
white button text, with correct numbers. Measuring 18 realistic tenant colours over every rendered
pair found (1) the shade end was aimed right by F3b but travelled LIGHT's distances, so `brand-600`
— the app's LINK ink — failed AA on a `#1f2937` card for **14 of 18**; and (2) a button and a link
were spelled with the same stop while wanting opposite things there. Building only what the ticket
described would have fixed the buttons and left every link unreadable, with a green suite.

**▶ FOUR NUMBERS FIXED THE FIRST HALF AND CHANGED NO CALL SITES** — dark shades `.15/.30/.45/.60` →
`.45/.60/.75/.86`. All 18 pass every text pair. Light untouched.

**▶ THE SECOND HALF IS A ROLE, and it could not have been a stop.** Walking the button down the ramp
DOES let white text read (`brand-400` = 5.82) and drops it to **2.52** against its own card, so it
stops looking like a button. `--brand-fill` / `-hover` / `-ink`, `var()` indirections so a tenant
override flows through with no change to `branding-context`. That near-miss is now the
`filled_button_visible` pair, so nobody can trade one bar for the other.

**▶ TWO COLOURS HONESTLY LOST.** `#010066` and `#111827` moved to REFUSES, failing only the dark link
pairs — they were never unreadable before because nobody could see the surface they fail on.

**▶ FOR F7b:** `ui_shape` is exempt in dark with a test that names the reason. `brand-500` is the
identity stop and cannot move, so a dark tenant colour makes a dark dot on a dark card (**10 of 18**
under 3.0). The fix is `--brand-shape` over ~50 files, almost all one repeating pattern
(`focus:ring-2 focus:ring-primary-500 focus:border-primary-500`). Then delete `DARK_EXEMPT`.

#### ✅ F7b — SHIPPED 2026-09-02. **THE GATE HAS NO EXEMPTIONS LEFT.**

Retro `docs/retrospective-2026-09-02-layer1-f7b-brand-shape-role.md`; decision ×1; lessons ×5. NO
migration. web + api. 204 utilities. jest **1603**, pytest **5772**. Reviewed in both modes.

**▶ `--brand-shape`** — `brand-500` in light, `brand-600` in dark. Dots, bars, tracks, spinners,
selected-pill borders and every focus ring. They sat on the IDENTITY stop, which cannot move between
modes by ruling, so a dark tenant colour drew an invisible mark on a dark card (10 of 18 under 3.0,
worst 1.42). All 18 pass now. **`--brand-500` does not move; the ROLE does.**

**▶ `DARK_EXEMPT` IS GONE and closing it added ZERO new refusals** — the same 11 colours pass and
the same 7 refuse, for the same reasons. That result is what makes it a fix rather than a loosened
bar, and it is now its own test.

**▶ A SECOND DEFECT, LIVE IN LIGHT MODE, THAT THE GATE COULD NOT SEE.** 31 uses spelled brand TEXT
as `text-primary-500`, where the platform's own colour measures **3.98** against white — below AA —
in eleven places at `text-sm` or smaller. Its only pair on that token was correctly scoped as a
non-text shape at 3.0, so a defect of the OTHER kind there was invisible. Found by classifying the
call sites. **When a token is checked at one bar, enumerate its uses and ask about the other kind.**

**▶ THE BITE-CHECK FOUND A MISSING GUARD.** Reverting the SVG-prop fix produced no failure at all —
class scans read class names, F3's SVG guard reads raw hex, and a `var()` reference is neither. The
new guard states the property: no component may read `var(--brand-500)` directly.

#### ✅ F7c — SHIPPED 2026-09-02. **EVERY SURFACE CAN NOW BE LOOKED AT.**

Retro `docs/retrospective-2026-09-02-layer1-f7c-cockpit-fixture.md`; decision ×1; lessons ×5. NO
migration. web only. jest **1605**. Reviewed in both modes — the first time this screen ever was.

**▶ THE FIRST MOUNT FOUND A SEVERE DEFECT, AND IT WAS NOT IN THE COCKPIT.** Every text box,
dropdown and textarea in the product measured `background: white` AND `color: white` in dark —
white text in a white box. The background came from the BROWSER (F2a fixed the `.input` class;
~300 controls do not use it) and the ink was INHERITED from `body`'s `text-ground-900`, which is
white in dark. In light the two accidents cancel exactly. **No static scan could have found it** —
one half is an absent declaration and the other is inheritance, which is the entire argument for
the sandbox existing. Fixed with one element rule in `@layer base`.

**▶ F7b MISSED THE STYLESHEET** — its codemod ran over `.ts`/`.tsx`, so `.btn-primary`,
`.btn-secondary` and `.input` still reached for `primary-500`. F2a's lesson, one sprint later.

**▶ THE PAGE HAD TO SPLIT, AND ONLY `next build` SAID SO.** Next rejects a defaulted first
parameter, any prop beyond `PageProps`, and any extra module export — so a page can neither take an
id nor export the component that does. The screen moved whole into `view.tsx`; the route is 22
lines. **The body did not change.** `tsc`, `jest` and `next lint` were green through all three.

#### ✅ F7d — SHIPPED **AND DEPLOYED** 2026-09-02. **DARK MODE IS REACHABLE. AND LIGHT IS THE BROKEN ONE.**

Retro `docs/retrospective-2026-09-02-layer1-f7d-the-flip.md`; decisions ×2; lessons ×6. NO
migration. web only. jest **1617**; i18n **4646 × 3**. **All 25 surfaces walked in both modes,
measured rather than eyeballed** (`docs/contrast-sweep.md`).

**LIVE: `halatuju-web-00817-754`** (build `f6aca5a7` SUCCESS), api unchanged at `00971-ck4`.
**F7c rode along in the same push.** All eight public routes 200; `/theme-boot.js` served and
referenced; the switch is in the served markup. **Dark is reachable in production for the first
time** — `auto` is the default and follows the device.

**▶ THE SWITCH EXISTS.** `ThemeSelector` — a `<select>` matching `LanguageSelector` class for class
— on the public header (desktop + mobile), the landing nav, settings, the admin top bar and the
sponsor shell. Plus `ThemeWatcher` in the PROVIDER STACK, not in the control, so a chromeless page
still follows the device at sunset. **`themeSwitchEnabled()` is deleted and the boot script is
unconditional.** F1b as originally scoped (four settings surfaces, three identity models, a
migration) is **SUPERSEDED** by the owner's device-local ruling, not deferred.

**▶ THE WALK INVERTED THE SPRINT'S EXPECTED QUESTION.** It was scheduled to check dark was safe.
Measured over 25 routes: **light 263 failing elements / 55 distinct; dark 54 / 11.** `ground-400`,
the muted-text token, is 2.43–2.54 on a light ground against a bar of 4.5 — the footer on every
public page, 29 cockpit field labels, every `text-xs` hint. **Light is what every visitor has looked
at since launch.** The flip does not make the product less readable; it makes an existing problem
visible. Recorded as **TD-224**; this is **F7e**.

**▶ TWO OF THE FAULTS ARE ONES THIS ARC FIXED ALREADY — FOR THE BRAND ONLY.** F7a's fill role and
F7b's move of brand text off `-500` both apply verbatim to the four TONE ramps, which reverse in
dark by the same rule and were given neither. `bg-positive-600 text-white` — the cockpit's **Accept**
button — is **1.40** in dark and **3.30** in light. Named twice, generalised zero times.

**▶ THE GATE IS BLIND TO EVERY PAIR IT DOES NOT NAME.** `contrast.py`'s seven pairs are all
brand-versus-ground, so the whole TD-224 class sits outside it while it passes correctly. Third form
of one lesson in three sprints (F7b: one bar hides the other kind; F7c: a folder-scoped guard).

**▶ ALSO FOUND:** the brand logo is drawn for a light ground and its icon half-disappears in dark
(**TD-225** — artwork, and tenants supply their own, so it is the owner's call).

#### ✅ F7e — SHIPPED **AND DEPLOYED** 2026-09-04. **TD-224 IS CLOSED. THE PRODUCT PASSES AA.**

Retro `docs/retrospective-2026-09-04-f7e-contrast.md`; decisions ×4; lessons ×8. NO migration,
NO backend — web only, 68 files. jest 1692 → **1697**; pytest **5844** (untouched); tsc **24**
(baseline); lint **0**; i18n **4745 × 3** (no new keys); build clean.

**LIVE: `halatuju-web-00824-v55`** (build `242b60fa` SUCCESS; **only the WEB trigger fired**, 0
Python files changed), api unchanged at `00975-nrj`. Eight public routes 200; no error logs; the
served stylesheets were downloaded and read back rather than assumed.

**▶ THE MEASUREMENT, same procedure and same 25 routes as F7d's walk:**

| mode | before | after |
|---|---|---|
| **light** | **263 elements / 55 distinct** | **1 / 1** |
| dark | 54 / 11 | **1 / 1** |

The survivor in each mode is the decorative `·` separator, excluded by the procedure's own rules
and **said so** in `docs/contrast-sweep.md` rather than quietly dropped.

**▶ THE TICKET'S OWNER DECISION WAS WRONG IN BOTH HALVES, AND RE-DERIVING IT SAVED ~390 EDITS.**
The scoping above offered "move `ground-400` (one edit)" or "move ~150 call sites to `ground-500`".
Measured at planning: there are **404 call sites across 102 files**, and **`ground-500` on a well
(`ground-100`) is 4.39** against a bar of 4.5 — so option two would have failed *after* all ~400
edits. A third option existed because the sites were classified before a role was chosen (F7a's
lesson): **`ground-400` was NAMED for its smaller role** — `.input` spelled
`placeholder:text-ground-400` and the dark block commented it *"placeholder text"* — while **395
of its 404 sites are muted body text.** The token became the muted-ink stop, a new
`--ground-placeholder` took the small role, and it cost **~10 edits**.

**▶ DARK FAILED TOO.** TD-224 recorded this as a light-mode problem; `ground-400` on a well in dark
measured **4.06**. Both modes moved.

**▶ F7a AND F7b'S BILL, PAID.** The four tone ramps got `--<tone>-fill` / `-fill-hover` /
`-fill-ink` — the `--brand-fill` pattern verbatim, `var()` indirections so a tenant override still
resolves — and tone INK as small **text** moved one stop darker. The cockpit's **Accept** button
was `bg-positive-600 text-white`: **3.30** light, **1.40** dark. **Shapes were deliberately left
alone** at their 3.0 bar.

**▶ THE ONE ONLY A BROWSER COULD FIND.** `CourseCard`'s merit bar holds its fill class and its
`text-white` **twenty lines apart**, so the codemod's one-line pair rule could never have matched
them. The student's score measured **1.67**. The bar and its dot are now separate classes on
purpose: a dot carries no words and keeps the plain stop.

**▶ THE GATE WAS WIDENED WHERE WIDENING IT MEANS SOMETHING.** Five guards went into
`theme.test.ts` (ink on a **well** in both modes, ramp monotonicity, "a filled control may never be
spelled as a tone stop", every fill clears both bars, placeholder separate and exempt).
**`contrast.py` was NOT widened, deliberately** — it validates a *tenant-supplied brand hex*, and
the tone/ground ramps are fixed platform tokens no tenant can set, so pairs there would re-measure
constants that can never fail. Recorded as a decision, not a gap.

**▶ TD-223 WAS DEFERRED OUT — IT IS NOW F7f.** This block previously said to fold it in because it
"touches the same call sites". Measured: **89 sites across 49 files**, small overlap, taking the
sprint from ~48 files to ~90.

#### F7f — the link colour (TD-223, low) — the last Layer 1 item

Links are spelled `info` on F1–F3 surfaces and `brand` on F4–F6 surfaces, split by which sprint
converted the file. **89 sites across 49 files.**

**Nothing is left to decide.** A2's contrast gate carries a `link_on_card` pair asserting **brand**,
and F7b re-pinned brand text at `-600`. This is unfinished conversion, not an open question.

**Only a tenant with a non-blue brand can see it** — both spellings render blue on the platform's
own colour. That is the trigger, and it is why this sat behind the contrast work rather than in
front of it.

---

#### F7d — The flip *(original scoping, kept for the record)*
Lower a `palette-guard` ceiling that may only fall, remove the flag, and review every surface in both
modes. *low, but it is the sprint that must not be skipped.*

**⚠ ~~TWO THINGS NOW BLOCK IT~~ — TD-222 IS CLOSED (F7a) AND THE COCKPIT FIXTURE IS NOW F7c.**

1. ~~**TD-222 — the dark brand ramp cannot carry white button text.**~~ **CLOSED 2026-09-02 by F7a**,
   and it was two faults rather than one: the shade end travelled light's distances (fixed by
   `_SHADE_MIX`), and a button and a link were sharing a stop while wanting opposite things (fixed
   by `FILL_ROLE`). The gate now runs in both modes. See the F7a block above.
2. **The officer cockpit has never been seen in a browser** — now scheduled as **F7c**.

**⚠ AND ONE BLOCKER THE PLAN NEVER NAMED, found at F7a's planning:**

3. **THERE IS NO SWITCH A PERSON CAN CLICK.** `NEXT_PUBLIC_THEME_SWITCH` gates only the before-paint
   script in `layout.tsx`; nothing in the product renders a control. Removing the flag today makes
   everyone follow their device with no way to override. That was **F1b**, split out of F1 with the
   note *"nothing needs it until F7"* — and that day is now. **Owner ruled 2026-09-02: device-local,
   no account storage** (language, a bigger per-person choice, is already device-local). F1b as
   originally scoped — four settings surfaces, three identity models, a migration — is SUPERSEDED,
   not deferred. **This is F7d's first task.**

**AND TWO SMALL ONES RAISED BY F6, neither blocking:**

3. **TD-223 — links are `info` on some surfaces and `brand` on others**, split by which sprint
   converted the file. A2's contrast gate has a `link_on_card` pair asserting **brand**, so the
   design of record already says which is right; making it true everywhere touches files from F1
   through F5 and is a product-wide decision, not a leftover of any one surface.
4. **The eight `category-N` swatches, seen together for the first time.** F6's sandbox surface is
   the first screen in the product's history to render all eight at once — every earlier screen
   showed one badge at a time. Measured in dark, `Politeknik rgb(19, 78, 74)` and
   `Kolej Komuniti rgb(22, 78, 99)` are distinct by value (the guard passes, correctly) and hard to
   separate by eye; `Universiti` and `PISMP` are next closest. Open `/sandbox/course-guide` in both
   modes and decide. **Changing `--category-*` moves every category set in the product**, so it is
   the owner's call, not a repaint's.

**▶ F7's SCOPE IS SMALLER THAN ITS ONE-LINE DESCRIPTION SUGGESTS.** "Lower a `palette-guard` ceiling
that may only fall" no longer applies — **F6 replaced every ceiling with a tree-wide assertion.**
What is left is: fix the dark ramp, widen A2's gate to both modes, build the cockpit fixture, remove
the flag, and do the review.

### Arc A — the authoring (what an `org_admin` actually touches)

**Not in the superseded plan at all.** This is the arc that question 7 flagged as "its own arc" and
which the owner has now confirmed is in scope.

#### ✅ A1 — SHIPPED 2026-09-01

Retro `docs/retrospective-2026-09-01-layer1-a1-tenant-theme.md`; decisions ×4; lessons ×3.
**Migration `courses/0071`, ADDITIVE, migrate-first.** 11 files. pytest **5706**, jest **1548**.
Acceptance met: two organisations, two colours, no leakage; the org fence untouched (the endpoint
is public and is not an `_AdminBase` subclass).

**▶ THE STORED VALUE IS THE TOKEN SET, NOT THE HEX** — A2's ruling, applied here because A1 is
where the storage lands. `courses.theme_tokens` is the one home for the maths and the fence;
`OrganisationTheme` holds `{"light": {...}, "dark": {...}}`; the fence runs in `save()`, so a shell
caller cannot go around it. `manage.py set_organisation_theme` is the writer, shipped in the same
sprint so nothing here is a reserved key.

**▶ THE FENCE, and what makes it survive A4.** `PLATFORM_FAMILIES` is checked BEFORE the allow-list
and its test never consults the allow-list, so widening `TENANT_FAMILIES` cannot quietly widen into
a tone. `TENANT_FAMILIES` is deliberately just `brand` — ground is the owner's eventual boundary but
has no writer yet, and this arc forbids a reserved key. **`brand-500` byte-identical across modes is
now enforced at the STORAGE fence**, not only in the deriving function.

**▶ THE FENCE RUNS THREE TIMES ON PURPOSE** — write, read, browser. A row edited around the ORM has
no writer; only the browser copy sees the bytes the page received. All three bite-checked.

**▶ BRIGHTPATH DELIBERATELY HAS NO ROW.** Its light ramp in `globals.css` is the seeded hexes, not
`brandRamp()`'s output, so a derived row would move its own colours by a channel. The command
refuses that org by name.

**▶ TWO IMPLEMENTATIONS OF ONE SUM, pinned by a shared golden** in `test_organisation_theme.py` and
`branding.test.ts`. It caught a real one immediately: Python's `round()` is banker's, JavaScript's
is not, and this colour lands on an exact `.5`.

#### ✅ A2 — SHIPPED 2026-09-01

Retro `docs/retrospective-2026-09-01-layer1-a2-colour-picker.md`; decisions ×3; lessons ×3;
**TD-222** raised. **NO migration.** api + web. pytest **5738**, jest **1573**.
Design of record: the working mock approved by the owner (Stitch failed twice and produced nothing;
same fallback as the sponsored-student page in July).

**▶ THE GATE CHECKS PAIRS AND REFUSES AT SAVE.** `courses/contrast.py`; the browser runs the same
check so the answer appears as somebody types, but the `400` is the rule. When the two disagree the
screen renders the SERVER's answer — a test pins that.

**▶ ⚠ IT REFUSED THE PLATFORM'S OWN BLUE, AND THAT WAS THE FINDING.** White on `bg-primary-500`
measures 3.98 for `#137fec`. F4 had already ruled a filled control carries `-600`; **54 of them had
never moved**, across 21 files. A2 moved them, so `-500` now carries only shapes (3:1, not 4.5).
After the move 13 of 18 realistic brand colours pass, ours among them.
`test_the_platform_colour_passes_its_own_gate` is the calibration canary.

**▶ THE TAB SHELL WAS THE RETRO-FIT open question 3 predicted.** Layer 0 Sprint 5 shipped a
single-purpose page; A2 built the shell and MOVED the config tab unchanged — its 8 rendered tests
pass untouched.

**▶ ⚠ THIS DEPLOY IS VISIBLE**, unlike every Layer 1 sprint before it: 54 filled controls go one
shade darker in light mode.

**▶ ⚠ DARK IS NOT GATED — TD-222, AND IT BLOCKS F7.** See the F7 section.

#### A2 — the reasoning, kept
**Goal.** An `org_admin` picks a colour, sees it immediately, and **cannot ship an unreadable one**.

**✅ THE STORAGE HALF OF THIS SECTION IS BUILT (A1, 2026-09-01).** `OrganisationTheme` already
stores the resolved token set, `theme_tokens.validate_tokens` already refuses a tone, and
`set_organisation_theme` already writes one from a hex. **So A2 is a SCREEN over storage that
exists** — the picker derives a preview, posts a colour, and the server freezes the set. The
paragraphs below are kept because they carry the reasoning, not because anything in them is
outstanding.

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
- **A tenant tints the brand and the ground; the tones stay ours.** Owner ruling — **✅ enforced as
  of A1**, on write, on read and in the browser, so a UI-only guard was never the plan. ⚠ Note the
  allow-list today is `brand` ALONE: ground is in the ruling but has no writer, and this arc forbids
  a reserved key. A2 does not need it; A4's trigger #1 is when it arrives.

**Complexity: medium-high.**

#### ✅ A3 — SHIPPED 2026-09-01. **ARC A IS COMPLETE.**

Retro `docs/retrospective-2026-09-01-layer1-a3-draft-publish.md`; decisions ×3; lessons ×2.
**Migration `courses/0072`** — additive PLUS one deliberate DROP of A1's `OneToOne` unique, and a
data step. pytest **5757**, jest **1583**.

**▶ ⚠ A DRAFT MUST NEVER REACH A VISITOR**, and there is exactly ONE filter —
`OrganisationTheme.active_for`, which `scholarship.branding` calls and nothing else. Breaking it
fails 13 tests. That is the sprint's whole risk, held at one line.

**▶ THE SHAPE IS `SponsorTermsVersion`'s, DELIBERATELY** — draft immutability, a publish that
archives the previous active row in ONE transaction, `allowed=False` by default so a shell caller
fails closed. Uniqueness is PARTIAL, per state: one draft and one active, unlimited archived,
because that history IS the undo.

**▶ REVERTING THE FIRST COLOUR LANDS ON THE PLATFORM STYLESHEET** — a real outcome, not an error,
which is why there is no separate "reset" verb to keep in step.

**▶ ⚠ A CORRECTION TO THIS SECTION'S OWN PLAN.** It said a tenant previews on the design SANDBOX.
The sandbox is not a reachable page — its route files are deliberately renamed (`page.sandbox.tsx`)
so they never build, and it is a local tool for the owner. The preview is the card A2 built, now
showing the draft beside a banner naming what is live.

#### A3 — the reasoning, kept
**Goal.** Changing a colour is not a live experiment on applicants.
**Scope.** Draft → preview → publish, mirroring the sponsor-terms shape already in the codebase; an
`AUDIT` line per publish; one-click revert. *medium.*

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

