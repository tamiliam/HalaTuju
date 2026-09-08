# Retrospective — the gift switcher (the owner's item 3)

**Date:** 2026-09-08 · **Worktree:** `.worktrees/gift-switcher`, branch `feat/gift-switcher`
**Migration:** none. **api + web.**

## What was built

The breadcrumb's gift switcher now decides what the Applications list shows, and the heading names
the gift you are actually looking at.

1. **The heading stopped lying.** `admin.scholarship.title` is `'{programmeName} Applicants'`, and
   `programmeName` is one of the five **branding auto-tokens** `t()` injects beneath explicit
   call-site params — the tenant's *flagship* name, never the selected gift. So it read
   "BrightPath Bursary Applicants" while the crumb said Test Programme, over 143 people who were
   not Test Programme's. Passing `programmeName` **explicitly** shadows the auto-token, so the one
   string serves both and ms/ta needed no new translation. Nothing chosen → a neutral
   `admin.scholarship.titleAll`.
2. **The list narrows.** `?programme=<code>` on `AdminApplicationListView`, resolved by a new
   `_AdminBase._programme_by_code` inside the caller's own organisation.

## The one number that shaped the scope

Only **two** admin routes carry `scope: 'programme'` in the route registry —
`/admin/programme` (Configuration, which already filtered) and `/admin/scholarship` (Applications,
which did not). Everything else — Reviewers, Sources, Payments, Sponsors — is `organisation` scope,
where `ScopeSwitcher` renders **no gift crumb at all**. So "the switcher filters nothing" was, on
what a person can actually see, one page. Reading the registry before planning turned a five-surface
guess into a one-surface sprint. **Do not widen this by assumption**: making those pages gift-aware
means moving them to programme scope, and each needs its own ruling on what a blank column means.

## Design decisions

- **Omitted means EVERY gift, and that is deliberate.** With several gifts and no choice, the list
  shows all of them. It reads as the opposite of `programmeScope`'s own "never pick silently" rule
  and it is not: that rule guards a screen that would otherwise **edit** the wrong gift. A list is a
  READ, so a wider answer is true — just less specific — while hiding 143 people behind a chooser
  would be worse than either.
- **Unknown or cross-tenant is 404, never "show everything".** A narrowing that cannot be resolved
  must refuse. Silently dropping it puts the wrong people under a named heading, which is the exact
  defect this sprint exists to fix; and a cross-tenant code must not confirm that gift exists.
- **The filter reaches THROUGH the cohort** — `Q(programme=p) | Q(cohort__programme=p)`, the same
  predicate `programme_delete_blocker` uses. `ScholarshipApplication.programme` is denormalised and
  **set once**, so a cohort moved between gifts leaves its old applications pointing at the OLD
  gift; the column alone would report a gift's own round as empty.

## What went wrong

- **The heading fix nearly went into the wrong layer.** The first instinct was a new key with the
  gift name baked in. Root cause: not knowing that `t()` injects branding tokens *beneath* explicit
  params, so the existing string was already parameterised for exactly this. Reading `AUTO_TOKENS`
  and the injection order first turned three new keys into one. **System change:** the code comment
  at the call site now states the shadowing, so the next reader does not re-add a key.
- **The test fixture collided with a seeded organisation.** `PartnerOrganisation.code` is unique
  platform-wide and a migration seeds the real BrightPath row, so `code='brightpath'` failed on a
  `UNIQUE` constraint — twice, because the first fix supplied codes without checking what already
  existed. `test_org_fence.py` had solved this months ago by prefixing (`proof-…`). **System
  change:** the new suite prefixes and says why in a comment.
- **A new `tsc` error was introduced and FIXED, not waived.** `mock.calls[0][0]` is optional on the
  client, so reading `.programme` off it is possibly-undefined. An optional chain alone would have
  passed vacuously when the call carried no filters at all, so the test asserts the argument exists
  first. Back to the 24 baseline (TD-221).

## Numbers

- pytest **5997** (+8, `test_application_programme_filter.py`)
- jest **1849** (+4, `admin/scholarship/page.test.tsx`)
- tsc **24** (baseline) · lint **0 Errors** · i18n **4887 × 3** (+1) · `next build` exit 0
- `makemigrations --check` clean — **no migration**
- **Four bite-checks**, each injection verified as landed before the suite ran: the filter removed
  (3 fail), the refusal removed (2 fail), the heading back on the branding token (2 fail), the
  chosen gift never sent (1 fail).

## What is NOT done, and why

- **Reviewers · Sources · Payments · Sponsors still ignore the gift.** They show no gift crumb, so
  nothing on those screens currently misleads. Making them gift-aware is a real decision per screen:
  a reviewer's `programme` is nullable and **NULL means every gift**, so a naive filter would hide
  the organisation-wide reviewers — the same trap for sources. Owner's call.
- **The application DETAIL page** (`/admin/scholarship/143`) still shows whichever gift the crumb is
  on. Arriving from the filtered list this always agrees; only a direct link across gifts can
  disagree. Named rather than fixed.
