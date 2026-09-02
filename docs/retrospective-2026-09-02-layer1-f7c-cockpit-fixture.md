# Layer 1 F7c — the officer cockpit can finally be mounted, and it was broken

**2026-09-02. web only. No migration.** Branch `feat/layer1-f7c-cockpit-fixture`.
jest 1603 → **1605**; tsc **24** (baseline); lint **0**; i18n **4640 × 3**; build clean.
Three guards bite-checked. **Reviewed in a browser in both modes — the first time this screen ever
has been.**

---

## The point of the sprint, and what it immediately paid for

The officer cockpit is the biggest surface in the product — 3,500 lines, 537 colour utilities — and
it was the ONE surface repainted in this arc that nobody had ever opened. F5 converted it. Every
scan the project has was green over it, through four subsequent sprints.

**The first time it was mounted, every form control on it was invisible in dark mode.**

Text boxes, dropdowns and textareas measured `background: white` **and** `color: white`. Not hard
to read — white text in a white box.

Two independent accidents, and **neither is visible in light**:

| half | cause |
|---|---|
| the **background** | came from the browser's own default — these controls are written with bare utilities (`border rounded-lg px-3 py-2`) and declare none. F2a fixed the `.input` CLASS; ~300 controls do not use it. |
| the **ink** | was INHERITED from `body`, which is `text-ground-900` — and `ground-900` in dark is **white**. |

In light the two cancel exactly: the UA white matches the page, the inherited ink is dark. Only
reversing the ground stacks them on top of each other.

**No static scan could have found this.** One half is the absence of a declaration; the other is
inheritance. That is the whole argument for the sandbox existing, and it took four sprints to
collect on it.

Fixed with an element rule in `@layer base` — one property of every control, present and future.
`base` means any utility class still wins, so a control that deliberately sets its own background
keeps it. Light is byte-identical, because the rule restates what the browser was already doing.

---

## ▶ F7b MISSED THE STYLESHEET, WHICH IS F2a's LESSON WALKED INTO AGAIN

F7b's codemod ran over `.ts`/`.tsx`. `globals.css` is neither, so `.btn-primary`, `.btn-secondary`
and `.input` still reached for `primary-500` — including a filled button that should carry the fill
role and three focus rings that should carry the shape role.

F2a wrote this down in as many words: *"`globals.css` is not a component and not a surface, so no
sprint owned it."* One sprint later, the same file, the same reason. All three are on the roles now,
and a guard asserts the stylesheet carries no `primary-500` at all.

---

## ▶ THE PAGE HAD TO SPLIT, AND ONLY `next build` SAID SO

Giving the cockpit an optional `applicationId` so the sandbox could mount it failed the build
**three times**, each on a different rule:

1. a page's default export may not have a **defaulted first parameter** (`= {}` makes the type
   `… | undefined`, which is not `PageProps`);
2. it may not accept **any prop** beyond `PageProps`;
3. its module may not have **any extra export**.

So a page can neither take an id as a prop nor export the component that does.

**`tsc --noEmit`, `jest` and `next lint` were all green through all three.** This is July's lesson
in a second form — *the deploy gate is whatever the BUILD runs* — and the resolution was the honest
one: the screen moved whole into `view.tsx`, and `page.tsx` is 22 lines that hand it no id so it
falls back to `useParams()`.

**The body did not change.** This is a move plus a wrapper, not the section extraction F5 declined
on readability grounds.

---

## ▶ THE SANDBOX'S OWN SAFETY GUARD CAUGHT ME, AND THEN SHOWED TWO GAPS

It refused my first fixture immediately: sandbox emails must be `.invalid` (RFC 2606, resolves
nowhere), and I had written `.test`. That is the guard doing exactly its job.

Two gaps surfaced in the same pass, both the F6 shape:

- **It scanned `fixtures/` only.** The new surface carries its reviewer list inline in
  `surfaces.tsx` — fixture data outside the fixtures folder, on the very screen that lists people.
- **Its NRIC pattern matched only `\d{6}-\d{2}-\d{4}`.** An API payload carries an IC as twelve
  bare digits, which is what a fixture written from a payload holds — and mine did, and it passed.

Both widened: the scans now cover every sandbox file and both spellings. **A guard is blind to
whatever is not in its scope AND to whatever is not in its pattern, and a fixture written from a
real payload will use the real spelling.**

---

## ▶ `git checkout --` DESTROYED MY WORK AGAIN, AND THE WIP COMMIT IS WHY

F1's lesson: commit before bite-checking, then never restore by reaching for git.

I did commit. Then made further edits to `globals.css`. Then bit-checked `globals.css` with
`git checkout --`, which restored it to the WIP commit and deleted the base form-control rule and
three role fixes made after it.

**The commit is what created the false sense of safety** — "it is committed" was true of the file
and false of the change. Caught within a minute because two tests went red, and re-applied from
text I still had. The rule needs the sharper form: **restore to the state you are actually in —
commit immediately before each injection, or write the original back from a string in the same
process.**

---

## What the review found in the cockpit itself

Once the controls were fixed, the screen reads correctly in both modes, and F5's four judgement
calls — made without ever seeing them — all hold:

- the four verdict facts stay tellable apart (they are TONES, not categories)
- the two Save buttons carry the brand
- the HOLD badge is filled where a suspended chip is tinted
- the Check-2 briefing is INFO, and the capture chip is a CATEGORY

The fixture is deliberately mid-review — assigned, interviewed, one open resolution item, one amber
fact and one gap — because a freshly submitted application renders a third of the screen and would
have proved nothing about the rest.

---

## For F7d (the flip)

**There is still no switch a person can click**, and that is F7d's first task. Owner ruling
(2026-09-02): device-local, no account storage; mount it where `LanguageSelector` is, plus the
admin and sponsor shells.

Then: remove the flag, walk every surface in both modes — **all of which can now be walked** — and
settle **TD-223** (links are `info` on some surfaces and `brand` on others) and the eight category
swatches seen together on `/sandbox/course-guide`.
