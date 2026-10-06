# Retrospective — Layer 1 A1: a theme belongs to an organisation

**Date:** 2026-09-01
**Branch:** `feat/layer1-a1-tenant-theme`
**Roadmap:** `docs/plans/2026-07-29-layer1-themes-roadmap.md`, arc A sprint 1
**Migration:** `courses/0071_organisationtheme` — ADDITIVE, one new table. Migrate-first.

---

## What was built

The first sprint of arc A. Where arc F repainted every surface onto a token vocabulary, A1 gives
that vocabulary a per-organisation home: **an organisation's colours are stored, served and
applied.**

| Piece | File |
|---|---|
| The ramp maths, the fence, the read filter | `apps/courses/theme_tokens.py` (new) |
| One theme per organisation | `courses.OrganisationTheme` + migration `0071` |
| The writer | `manage.py set_organisation_theme` (new) |
| Served publicly | `branding.Branding.theme` → `views_branding` `theme` key |
| Painted | `branding.ts` `applicableTokens` + `branding-context` `applyColourOverride` |

Nothing a visitor sees changes. BrightPath has no theme row, deliberately, and a tenant without one
behaves exactly as it did yesterday.

---

## The decision this sprint turns on

**The stored value is the TOKEN SET, not the hex.**

The derivation already existed (`brandRamp()` has produced ten shades from one colour since Sprint
6), so storing the hex and deriving on the way out is one column smaller and looks equivalent. It is
not, for two independent reasons:

1. **A tenant approved *those* shades.** Derived per request, an improvement to the ramp silently
   restyles every tenant's product without anyone asking. That is the same reasoning already
   settled twice in this codebase — a student's requirements freeze at submit, a terms version
   freezes at publish. Storing what was approved is correct here on its own merits.
2. **It keeps A4 out of a migration.** A2's picker becomes a UI that WRITES this shape; A4's full
   palette becomes a SECOND EDITOR over the same storage. A hex column would have made it two
   storage shapes, a backfill, and every reader taught both.

The roadmap called this out in A2's section. Building it in A1 is the honest reading: A1 is where
the storage lands, so A1 is where the shape is chosen.

**And it is deliberately not a reserved key.** The standing constraint on arc A forbids shipping a
`tokens` column that nothing fills, so `set_organisation_theme` shipped in the same sprint. The
owner can set a tenant colour today, without A2.

---

## The fence

Three things are guarded, in descending order of how badly it would matter if they broke.

### 1. A tone is never a tenant's

The four tone families and the category family are how the product says *this went well* / *read
this carefully* / *this is broken*. A meaning that changes per tenant is not a meaning.

The lesson from F3b — *a guard that forbids a whole family also forbids the fix; state the RULE* —
shaped how this is written. `PLATFORM_FAMILIES` is the rule, and `test_a_tone_is_never_a_tenants`
asserts it **per family and independently of the allow-list**. So widening what a tenant may tint
(A4 adds ground) cannot quietly widen it into a tone: the tone check runs first and has its own
test, which does not consult `TENANT_FAMILIES` at all.

`TENANT_FAMILIES` is today's allow-list and it is just `brand`. The owner's eventual boundary is
brand + ground, but nothing writes a ground tint yet — adding it is one word on the day a writer
exists.

### 2. `brand-500` is byte-identical across the modes

The 2026-07-29 ruling, moved **down to the storage fence**. F3b enforced it on the function that
derives; A1 enforces it on the value that is stored, so it holds for a hand-written set as well as
a derived one.

### 3. The fence runs three times, and the third earns its place

On write (`OrganisationTheme.save()`), on read (`applied_tokens`), and in the browser
(`applicableTokens`).

The write guard covers writers. A row edited in a console, restored from a backup, or touched by a
future migration **has no writer** — hence the read filter. And the browser filter is the only one
that runs on the bytes the page actually received. Three copies of one rule is normally a smell;
here each copy sits on a different trust boundary, and all three are bite-checked.

---

## Two implementations of one sum

`theme_tokens.brand_ramp` (Python, save-time) mirrors `brandRamp` (TypeScript, the fallback for a
tenant with no stored set). Two copies of one calculation is a drift risk with a nasty symptom: a
tenant's colours would shift by a channel the moment a theme row was created, and nobody would read
that as a bug.

**Both sides assert the same golden fixture** for `#a21caf` — `GOLDEN` in
`test_organisation_theme.py`, `GOLDEN` in `branding.test.ts`. If either drifts, that language's own
suite fails. The corner values were hand-computed and checked against the implementation, not taken
from it, so the fixture pins a verified answer rather than merely a consistent one.

A concrete instance the fixture caught, before it could ever ship: **Python's `round()` is banker's
rounding and JavaScript's `Math.round` is not.** `round(100.5) == 100` in Python, `101` in JS. The
ramp lands on an exact `.5` for this colour, so the naive implementation would have disagreed with
the browser by one in a channel — invisible on screen and permanently confusing in a diff.
`_round_half_up` exists for exactly that, and `test_rounding_is_javascripts_not_pythons` pins the
helper directly rather than relying on the fixture happening to exercise it.

---

## What went wrong

**1. The jsdom test could not mount the provider, and the reason was not the test.**

*Symptom.* Every case in `branding-context.test.tsx` failed with
`Cannot read properties of null (reading 'useState')`.

*Root cause.* `NEXT_PUBLIC_ORG_CODE` was read at MODULE scope, so the only way to give each case a
different org was `jest.resetModules()` + a fresh import — which hands the freshly-imported provider
a **second copy of React**, one that has no hook dispatcher because the renderer is holding the
first. The env read being module-scope was not a bug, but it made the module untestable in the one
way that mattered.

*Fix.* The env read moved into `orgCode()` / `apiUrl()`. Next inlines every
`process.env.NEXT_PUBLIC_*` textually at build time, so production is byte-identical either way —
and the module now takes a different code per mount with no `resetModules` anywhere. The comment at
that function says why, so nobody hoists it back to a constant for tidiness.

*System change.* Recorded as a lesson: a module-scope env read is a testability decision, not just
a performance one.

**2. A security hook blocked two file writes on a false positive.**

*Symptom.* Writing `branding.ts` was refused with a warning about shell command injection, as was
the first draft of this retrospective.

*Root cause.* The code called the regular-expression form of `RegExp.prototype` matching, whose
method name is spelled identically to the shell-execution function the hook screens for. The hook
matches on the bare substring, so a regex call and a process call are indistinguishable to it.

*Fix.* Switched to `name.match(TOKEN_NAME)`, which reads slightly better here anyway. Worth knowing
rather than fixing: that method name will trip the hook anywhere in this repo, prose included.

---

## What went well

- **The bite-check discipline paid, six for six.** Every guard was broken on purpose, the injection
  was verified as landed before the suite ran (the F4 lesson), and every one failed loudly:

  | Injection | Caught by |
  |---|---|
  | Remove the `PLATFORM_FAMILIES` check | `test_a_tone_is_never_a_tenants` |
  | Disable the identity-stop check | `test_the_identity_stop_may_not_differ_between_modes` |
  | Make `applied_tokens` stop filtering | 2 tests, model level AND endpoint level |
  | Delete the stored-theme branch in the painter | 2 jsdom cases |
  | Delete the browser family filter | 3 cases |
  | Swap to Python's `round()` | 3 tests, incl. the shared golden |

- **Every regex was hand-written.** F4's lesson held without needing to be re-learned.
- **The scope did not creep.** No picker, no screen, no ground family, no versioning. Each of those
  belongs to a named later sprint and would have been a reserved key here.

---

## Numbers

| Gate | Before | After |
|---|---|---|
| pytest | 5677 | **5706** |
| jest | 1534 | **1548** |
| `tsc --noEmit` | 24 | **24** (unchanged — TD-221) |
| `next lint` | 0 errors | **0 errors** |
| i18n parity | 4581 × 3 | **4581 × 3** (no new keys) |
| `next build` | clean | clean |

Files touched: 11. One migration.

---

## At deploy

1. **MIGRATE-FIRST.** Apply `courses/0071` on production before the push — the hand-written
   Postgres DDL is in the migration's docstring, including `ENABLE ROW LEVEL SECURITY` and the one
   `service_role` policy, in the same step. Record the `django_migrations` row.
2. Confirm the Supabase Security Advisor is clean.
3. Push. Both services rebuild; nothing a visitor sees changes, because no theme row exists.
4. **Dark mode stays unreachable.** `NEXT_PUBLIC_THEME_SWITCH` is still unset in production.

Post-check: `GET /api/v1/branding/brightpath/` returns `"theme": null`.

---

## Next

**A2 — the colour picker and the contrast gate.** Its prerequisites now exist: the storage shape is
settled, so the picker is a screen that writes it.

Two things A2 must carry, both already written down:

- **A Stitch prototype approved before any page code.** House rule, and the tab strip it joins
  already exists (`/admin/programme`, built by Layer 0 Sprint 5).
- **The contrast gate checks token PAIRS, not "is this hex safe".** Deterministic
  relative-luminance maths, tested, **blocking at save — it refuses, it does not warn.** A tenant
  will pick a colour that renders 4:1 against white, and a warning is dismissed while a student
  cannot read the page.
