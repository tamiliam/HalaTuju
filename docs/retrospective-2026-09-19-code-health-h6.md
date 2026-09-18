# Retrospective — Code health H6: the cockpit gets a rendered test, and the text guards retire

**Date:** 2026-09-19 · **Roadmap:** `docs/plans/2026-09-18-code-health-roadmap.md` · **Sprint:** H6 of H19
**Built by:** an Opus 5 agent to a written brief; the lead verified the findings against the code
and the locale files, re-ran the gates, and closed.
**Freeze status:** in force. **Phase 2 (tests that can fail) is complete** — six of the ten sprints
to *stabilised*. Run under the owner's standing word. **One finding needs the owner's decision
(TD-259) — it does not block the arc, and is raised in the close-out message, not acted on.**

## What Was Built

- **The reviewer cockpit is mounted by a real test for the first time.** `src/test/` holds a typed
  fixture builder (`buildApplicationDetail(stage, overrides)` — every field of
  `AdminScholarshipDetail` written out, no `any`, no casts; 15 stages mirroring the backend factory
  from H5, both roads to QC included) and `renderCockpit.tsx`, which mounts the real `view.tsx` per
  role and **fails any test that produces a `console.error`**. A drift test reads the Python
  factory and compares the stage lists.
- **59 rendered tests in four files** beside the page (`view.decision`, `view.closed`,
  `view.roles`, `view.actions`), all under 200 lines, asserting what a user sees and can do — roles,
  accessible names, i18n keys. No source reading, no snapshots, no Tailwind classes.
- **Four stopgap text guards retired or rebuilt.** `approveLockoutGuard` deleted (all seven claims
  re-made from the DOM); `docFileLayout`'s source half replaced by rendered assertions;
  `ActionCentre.vircle` turned into a mount (it was cheap after all); `screenshotInput` kept its
  **disk walk** — and strengthened it — while every claim about what a paste *does* moved to mounts,
  including a new one for the create form, the surface that had none.
- **Eleven near-identical i18n guards became one**, and its reach went from **11 namespaces to all
  35**. Every special case was carried over; two hand-written exclusion lists were generalised.
- **The suite halved: 42 s → 21 s** (the eleven guards each walked the whole tree; one does it once).

## What Went Well

- **Sixteen bite-checks, none silent — three of them real incidents re-injected** (#24's decline
  arm, #21's stuck lock, #56's decline credit). Each went red on the named test. Four
  cry-wolf checks stayed green: reformatted JSX, renamed Tailwind classes, LF instead of CRLF,
  two sibling panels reordered. H14 can now move this file's panels with evidence.
- **The agent corrected the brief three times, each time in favour of the code.** The lead wrote
  2b backwards: *stuck* means the panel is **not** locked — that is the whole point of #21. The
  agent tested the incident's meaning and added the two neighbouring cases so the trio cannot pass
  vacuously. It also found that `closed` is deliberately *not* a closed case (it is the successful
  end of a funded lifecycle), and that the org-admin reject takes no category.
- **One app-source edit, and it is an improvement.** A `type="date"` input had no accessible name;
  a screen reader announced nothing. An `aria-label` on an existing key; nothing visible changes.

## What Went Wrong

**1. Widening the i18n guard found eight keys that exist in no locale — four shown raw to users,
and they sit on top of TD-254.**
- *Symptom.* On the "this NRIC is already registered — is this you?" step of `AuthGateModal`, the
  question and both buttons render as `authGate.icExistsMessage`, `authGate.icNotMe`,
  `authGate.icYesMe`; the claim error renders as `authGate.claimError`. Also raw:
  `admin.householdIncome` / `admin.householdSize` on the admin student page, and a field name in one
  save error.
- *Root cause.* One idiom: `t(key) || 'English fallback'`. `t` returns **the key** when it cannot
  resolve one — a truthy string — so the fallback can never fire. And the guard that would have
  caught it covered 11 of 35 namespaces; `authGate` was not one.
- *Why it was NOT fixed.* Under the freeze a user-visible text change is the owner's. But the real
  reason is sharper: **this is the IC-claim screen of TD-254** (HIGH, security — a signed-in student
  can claim another's profile). The English fallback interpolates the *holder's name*. Today the
  missing key hides it by accident. Adding the message the obvious way would put another student's
  name on screen and make TD-254 worse. The two must be fixed together. Filed as **TD-259**, tied to
  TD-254; the eight keys sit in a shrink-only `KNOWN_MISSING` ledger that fails the day one resolves.
- *System change.* All 35 namespaces are now guarded, and a new namespace cannot appear unguarded
  (the list is asserted against the catalogue). The `||` idiom is named in TD-259 for a sweep.

**2. The lead's brief had the central behaviour backwards.** See above. A brief that names
behaviours must quote the code or the incident, not paraphrase from memory. The agent's habit of
checking the brief against the code is the only reason a wrong test was not written.

## The deploy

Web only. **`halatuju-web-00905-rht`**, first attempt; 2,511 jest passed inside the build on the
2-vCPU worker, with no flake — the first full run of the rendered cockpit suites under the gate's
load, and the first since `jest.setup.ts` raised the async limits. Site 200.

## Numbers

| | Before | After |
|---|---|---|
| jest | 2,397 / 142 suites · 42 s | **2,511 / 137 suites · 21 s** (Node 18: 36 s) |
| Rendered tests that mount the cockpit | 0 | **59** |
| `guard%` (web tests reading source text) | 18 | **10** — target was ≤ 12 |
| i18n namespaces guarded | 11 | **35 (all)** |
| Cockpit suites, 5 runs in a row | | 5 / 5 green, 4.4–6.2 s |
| tsc · lint · i18n parity · `next build` | | 0 · 0 errors · ok · exit 0 |
| App source changed | | 3 lines (`aria-label` + comment); `view.tsx` 3,587 → 3,590 |
