# Retrospective — B40 Phase E/F Sprint 1: Sponsor landing + live counter (F1)

**Date:** 2026-06-08
**Branch:** `main` (ships dark behind `SPONSOR_POOL_ENABLED`; no deploy this sprint)
**Migration:** none

## What Was Built

The first sponsor-recruitment surface of the B40 Phase E/F roadmap.

- **Public count endpoint** — `GET /api/v1/sponsor/pool/count/` → `{count, enabled}`. No auth (a public marketing
  page calls it; the NRIC gate already skips anonymous callers and `/api/v1/sponsor/` is prefix-whitelisted).
  Count-only — it returns nothing but an integer and a boolean, so there is no student data to leak. Gated by
  `SPONSOR_POOL_ENABLED`: while off it returns `{count: 0, enabled: false}`. `SponsorPoolCountView(AllowAny)` in
  `views_sponsor.py`, routed before the `<int:pk>` detail in `urls.py`.
- **Sponsor landing** — `components/SponsorLanding.tsx`: a self-contained marketing page (own sponsor top bar with a
  language selector, hero + live counter pill, three promise cards, four-step "how it works", FAQ accordion, closing
  CTA, shared `AppFooter`). Mirrors the proven structure of `app/scholarship/page.tsx`; blue accents match the existing
  sponsor portal and the project's Stitch design system.
- **Gating** — `app/sponsor/page.tsx` fetches the public count on mount and, for signed-out visitors, renders the
  landing **only when `enabled`**. While the flag is off (current prod state) signed-out visitors keep the existing
  sign-in card unchanged, so the whole programme stays dark until the lawyer-gated go-live (Sprint 12).
- **i18n** — `sponsorLanding.*` in en/ms/ta (40 keys each, key-identical). Tamil is a best-effort first pass pending
  the owner's refinement.
- **Tests** — +3 to `test_sponsor_pool.py` (count hidden when flag off; count reflects the eligible pool when on;
  response carries no identifiers and only `{count, enabled}`).

## What Went Well

- **Stitch-first held.** Prototyped the landing, got visual sign-off, then coded — zero rework on layout. The one
  human-only decision in the sprint (visual approval) was the only pause.
- **Reused a proven pattern.** Mirroring the scholarship landing (sections, card grid, FAQ accordion, `useT`) meant
  the new page typechecked first try and needed no new primitives.
- **Dark-by-construction.** Routing the "is the programme live?" signal through the count endpoint's `enabled` flag
  means there is one source of truth (the backend setting) and the FE has no separate flag to drift. Off → the page is
  literally never rendered; the existing auth flow is untouched.
- **No migration.** F1 is FE + a read-only count, so there was no schema change and no collision risk with the parked
  `0048` family-redesign migration on the other agent's branch.

## What Went Wrong

- **Local `Read` couldn't open a Stitch screenshot URL; first temp-download landed on an unreachable path.**
  *What happened:* `Read` on the `lh3.googleusercontent.com` URL failed (it only reads local files), and the first
  `curl -o` wrote to git-bash `/tmp`, which `Read` then couldn't resolve against the Windows filesystem.
  *Why:* mixing the git-bash POSIX path space with the Windows-path `Read` tool. *Fix:* download Stitch screenshots to
  an explicit Windows temp path (`C:/Users/.../AppData/Local/Temp/...`) before `Read`, and delete after. (Captured as a
  lesson.)
- **`generate_screen_from_text` timed out (expected).** Not a real failure — the screen persisted. Handled per the
  existing lesson (poll `list_screens`, verify the rendered content matches the prompt, don't retry). No new action.

## Design Decisions

- **Gate the marketing page behind `enabled`, not just the counter.** The whole sponsor programme is lawyer-gated, so
  even the recruitment page waits for go-live; signed-out visitors see the already-live sign-in card until then. (Logged
  in `decisions.md`.)
- **Self-contained sponsor header rather than the student `AppHeader`.** `AppHeader` carries the student auth context
  and nav; a public sponsor page wants sponsor CTAs + a language selector only.

## Numbers

- **Backend:** 29 sponsor-pool pytest (3 new) green; full scholarship suite unaffected.
- **Frontend:** `next build` clean (`/sponsor` 6.25 kB); **276 jest** green.
- **i18n:** `sponsorLanding` = 40 keys × en/ms/ta (parity verified).
- **Files touched:** 8 (3 BE, 5 FE incl. 3 message files) + 1 new component.
- **Migrations:** none. **Deploys:** 0 (ships dark; deploy gated on owner go-ahead).
