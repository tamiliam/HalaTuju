# Retrospective — Sponsored-student detail page (Sprint 2) — 2026-07-21

## What Was Built

Clicking a My-students card now opens a read-only detail page for the student you support — the
missing companion to Sprint 1's card. Header + single status badge + journey (with a "Withdrew" stop
for discontinued) + your commitment + the full anonymised profile + a reserved Spending panel. No
funding controls (this is not the discovery page).

- NEW endpoint `GET /api/v1/sponsor/my-students/<pk>/` — a student the caller sponsors, ANY status,
  gated to the caller's own sponsorship. Serves students past the grace window (the discovery-pool
  detail 404s those). Reuses `SponsorSponsorshipSerializer` + the reviewed anon profile.
- Web: new `/sponsor/my-students/[id]` route; My-students cards wrapped in a Link; `getMyStudentDetail`
  client; `sponsorPortal.myStudents.detail.*` i18n.

## What Went Well

- **The Stitch detour didn't block us.** The Stitch generation timed out and the API wouldn't surface
  the screen (known flakiness). Rather than fight it, the already-approved Tailwind artifact mock served
  as the design reference — the "design before code" gate was met, and the page was built straight from
  it with no lost time.
- **A clean new endpoint, not an overload of the discovery one.** The discovery-pool detail is scoped to
  the pool (404s a funded student past the grace window). Adding a sponsor-owned `my-students` endpoint
  kept that boundary intact and made the ownership gate explicit (the caller's own sponsorship), rather
  than widening the pool queryset again.
- **Reused everything.** The card serializer (portfolio_status, supported_semesters), the journey lib,
  and the anon profile all already existed — the page is composition, and the endpoint is a thin
  ownership-gated wrapper.

## What Went Wrong

- **Stitch round-trip cost time and tokens for no artifact.** Root cause: the Stitch MCP often times out
  and its `list_screens` doesn't reliably return a just-generated screen. Prevention: when a
  high-fidelity approved artifact already exists, treat it as the design of record and skip the Stitch
  regeneration unless the user specifically wants to iterate in Stitch. Noted in the Stitch memory.
- Two mid-flight label requests ("student's own words" toggle) were raised then retracted ("ignore the
  last two comments") — no code churn resulted because they came before I'd written that section.

## Design Decisions

- **A separate sponsor-owned `my-students` detail endpoint** (vs reusing/widening the discovery-pool
  detail) — see `docs/decisions.md`.

## Numbers

- Files touched: 10 (4 backend incl. test, 6 web incl. new page + 3 i18n). Commit `ad52c799`. No migration.
- Tests: full suite 2942 pass (5 new). Deploy: api + web. Behind `SPONSOR_POOL_ENABLED`.

## Next (Sprint 3, deferred)

- The **Vircle spending** panel/tab on this page (space is reserved). Owner: Tamil review of the new
  `myStudents.detail.*` first-drafts.
