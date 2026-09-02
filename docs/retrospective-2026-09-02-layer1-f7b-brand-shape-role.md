# Layer 1 F7b — the shape role, and the last gate exemption closes

**2026-09-02. web + api. No migration.** Branch `feat/layer1-f7b-brand-shape-role`.
jest 1597 → **1603**; pytest 5765 → **5772**; tsc **24** (baseline); lint **0**; i18n **4640 × 3**;
build clean. Four guards bite-checked. Reviewed in a browser in both modes.

---

## What shipped

`--brand-shape`: `brand-500` in light, `brand-600` in dark. Applied to every dot, progress bar,
toggle track, spinner, selected-pill border and — by far the most of them — **the focus ring on
every form control**. 204 utilities.

They were all spelled `brand-500`, the IDENTITY stop, which is byte-identical across modes **by
owner ruling** and therefore cannot move. So a tenant whose brand is dark got a dark shape on a dark
card: **10 of 18** realistic colours measured under 3.0, worst **1.42**.

The ruling is untouched. `--brand-500` does not move; the ROLE does — exactly as `--brand-fill`
does, and the test says so in one line: `navy['light']['brand-500'] == navy['dark']['brand-500']`.

`brand-600` in dark is the *smallest* move that clears it, and it only clears it because F7a's
retune made that stop genuinely pale. All 18 pass, worst **4.82**.

---

## ▶ THE RESULT THAT MAKES IT A FIX RATHER THAN A LOOSENED BAR

F7a exempted this pair with a named test because gating it would have refused ten tenants for a
defect of ours. F7b introduced the role and **deleted `DARK_EXEMPT`** — every pair is now checked in
every mode.

**The measured spread did not move by one colour.** The same 11 pass and the same 7 refuse, for the
same reasons as before. If the role had been the wrong answer, closing the exemption would have
shown up here as colours sliding into REFUSES.

That is now its own test rather than something I checked once by eye:
`test_gating_shapes_in_dark_added_NO_new_refusals`. **Whenever you remove a guard's exemption, pin
that the population it was protecting did not move.**

---

## ▶ A SECOND DEFECT, LIVE IN LIGHT MODE TODAY, THAT THE GATE COULD NEVER HAVE CAUGHT

Classifying the 204 call sites by what they DO — rather than assuming they were all shapes — found
that **31 of them were TEXT**: `text-primary-500` on numbers, emphasis and link hovers.

The platform's own colour measures **3.98** at `-500` against white. Below AA. In **eleven** places
at `text-sm` or smaller. **That is live in production right now, in light mode.**

The gate was not wrong and was never going to catch it: it had exactly one pair reading `-500`, and
that pair was correctly scoped as a non-text shape at 3.0. A token checked at one bar is invisible
to a defect of the other kind on the same token.

Brand text is `-600` now — the stop both link pairs already used, which passes in light (5.24) and
dark (4.55). Six of the eighteen test colours were affected; none of them gained a new refusal,
because the ones that fail `-600` (lime, amber) were already refused.

**The habit: when a token is checked at one bar, enumerate its uses and ask whether any of them are
the other kind.**

---

## ▶ THE BITE-CHECK FOUND A MISSING GUARD, AND THE SILENCE WAS THE FINDING

Following a comment led to `onboarding/grades`, where two-tone stream icons stroke themselves with
`rgb(var(--brand-500))` as an **SVG prop** — F3's hiding place, invisible to every class scan. Moved
to the role.

Then the bite-check reverted it, and **nothing failed.** The class scans read class names; F3's SVG
guard reads raw HEX in props; a `var()` reference to a token is neither.

The guard that closed it states the durable property rather than the instance: **`--brand-500` is
byte-identical across modes by ruling, so anything that must stay visible in both cannot read it
directly — a component reading it is always a bug.** The roles exist precisely so nobody has to.

**When an injected fault produces silence, do not move on because the code is now correct. Ask which
test should have failed, and write it.**

---

## ▶ THE CODEMOD REWROTE HISTORY, IN PROSE

The `sed` ran over every file containing `primary-500`, comments included. Three notes describing
what a class *used to be* started claiming the old value was the new token name — including
*"`ActionCentre`'s identical bar was already `bg-brand-shape`"*, which was never true of any moment
in this codebase's history.

Nothing failed. The code was right and the explanation had quietly become false, which is the shape
that survives sprints. **After any bulk rename, grep the new token in comment context and read every
hit for tense — a past-tense sentence containing the new name is always wrong.**

---

## ▶ ONE MEMBER OF THE SET DELIBERATELY DID NOT MOVE

`FundingBar` was the one brand bar already on `-600` rather than `-500`. It did not need the role:
`-600` is pale in dark after F7a, so that bar is visible there, and switching it would have
**lightened a progress bar in light mode** for no reason a person could see the point of.

The pull to make the set uniform is strong, and following it would have shipped a visible change
nobody asked for. The decision is written at that line, because otherwise the next reader finishes
the job.

---

## ▶ ONE TABLE OF BRAND ROLES, NOT TWO

`FILL_ROLE` became `BRAND_ROLE` and gained `shape`. Two tables describing the brand's roles is the
F4 role-palette shape waiting to happen, and this project has now hit that shape five times
(`roleBadge`, institution type, STPM subjects, matric tracks, and the fill role's three copies).

Three files still describe it — `globals.css`, `branding.ts`, `contrast.py` — and the guard on each
side now checks four roles instead of three.

---

## For F7c

Build the large `AdminApplicationDetail` sandbox fixture so the officer cockpit can be seen in a
browser. It is the one repainted surface never reviewed, and the sandbox forbids a hand-written
approximation.

## For F7d (the flip)

**There is still no switch a person can click.** The flag gates only the before-paint script. Owner
ruling (2026-09-02): **device-local, no account storage** — mount it where `LanguageSelector` is,
plus the admin and sponsor shells.

Also settles **TD-223** (links are `info` on some surfaces and `brand` on others; A2's gate says
brand) and the **eight category swatches seen together** on `/sandbox/course-guide`.

**Every contrast pair the product renders is now gated in both modes, with no exemptions.**
