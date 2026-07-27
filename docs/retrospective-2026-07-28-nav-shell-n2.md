# Retrospective — Nav/IA Sprint N2: the console shell

**Date:** 2026-07-28 · **Commit:** `e07f8f2e` (branch `feat/nav-shell`, worktree-isolated)
**Plan:** `docs/plans/2026-07-27-nav-ia-roadmap.md` · **Design of record:**
<https://claude.ai/code/artifact/17d259a8-f15f-4f0a-858e-492f1cb157a6>
**Migration:** none. **Backend:** none. **New dependency:** none.

---

## What Was Built

N1 turned the menu into data. N2 turns it into a shell.

- **`admin/layout.tsx` is now only a guard — 220 lines to 60.** The role ternary, the
  hand-written active-route rule, the badge fetch and two copies of the nav markup are gone.
- **`AppShell`** owns the shared state: probes and the pending-sponsor count are fetched once
  and passed down, so the sidebar badge and the bell cannot disagree.
- **`Sidebar`** — the scope stack (Platform / Organisation / Programme), collapsible, each group
  headed by the thing it names with the scope as a quiet tag.
- **`Topbar`** — breadcrumb left; search, help, notifications, account right.
- **`Menu`** — one dropdown primitive: Escape closes and returns focus to the trigger, arrows
  wrap, click-outside dismisses. Used three times rather than approximated three times.
- **`CommandPalette`** — Ctrl-K over the menu, with a footer that states it does not search
  records.
- **`icons.tsx`** — ~25 single-colour stroke paths in `currentColor` (owner decision, mid-review).
- **Nine reserved slots** so a later sprint fills a slot instead of re-cutting the menu.
- **TD-181 closed** — `chrome`, `hubParent`, `LEGACY_BAR_ORDER` deleted exactly one sprint after
  they were introduced, as designed.

**Numbers:** jest **890** / 60 suites (+27) · i18n **4057 × 3** · `tsc` clean · `next build`
exit 0 · 17 files.

---

## What Went Well

- **The scaffolding died on schedule.** TD-181 was opened in N1 specifically so the transitional
  fields could not quietly become permanent, and N2 deleted all three. Writing the debt ticket at
  the moment of introduction, with the removing sprint named, is what made that automatic rather
  than remembered.
- **Tests caught both defects, not review.** The sidebar heading printed the scope label twice for
  any account with no organisation; the brand-guard refused a hardcoded tenant name in scaffolding.
  Neither would have been obvious reading the diff.
- **Worktree isolation was the right call.** Two other agents were committing to this repo during
  the sprint; nothing collided, and `main` was never touched until the work was finished.
- **The owner's design call improved the result.** Emoji were the console's existing convention and
  I followed it; on seeing it the owner asked for a single-colour set. That is straightforwardly
  better — the icons now inherit the row's text colour and will follow a tenant's brand ramp, which
  emoji structurally cannot.

---

## What Went Wrong

**1. I burned three attempts of the owner's time on an auth flow that was not my sprint.**
*Symptom:* asked to click through the shell, the owner hit a redirect to the live site (wrong
port), then stale PKCE state, then a genuine exchange failure — before ever seeing the work.
*Root cause:* I treated "give them a URL" as the goal and debugged the obstacle in front of me
instead of asking what the goal actually required. The review needed *the components rendered*,
not *an authenticated session*; those are only the same thing if you assume the login must work.
*System change:* when a review is blocked by infrastructure the sprint does not own, build the
smallest thing that renders the work (a stub page, a story, a screenshot) before debugging the
infrastructure. Recorded as a lesson.

**2. I ran the full test suite while the owner had the dev server open, and killed it.**
*Symptom:* the preview stopped resolving mid-review. `RangeError: Array buffer allocation failed`
— out of memory. The process stayed bound to port 3000, so it looked alive to `netstat` and dead
to the browser.
*Root cause:* I had already recorded in this repo that the 8 GB box OOMs when a build follows a
full suite, then ran jest anyway against a machine that was simultaneously serving a review.
*System change:* never run the suite while a review server is serving. The two are mutually
exclusive on this hardware, and "verify" is not urgent enough to interrupt a person looking at the
screen.

**3. `TaskStop` reported success twice while the node process kept running.**
*Symptom:* a stopped dev server continued serving stale code on port 3000; the second time it held
the port against a fresh start.
*Root cause:* `TaskStop` terminates the wrapper, not the child process tree. I trusted its success
message the first time and only caught it because a later start logged `EADDRINUSE` while `curl`
still returned 200 — two signals that could not both be true.
*System change:* after stopping a background server, confirm the port is free with `netstat`
before assuming it is down; kill by PID (never by image name — that would take out the MCP
servers). Recorded as a lesson.

**4. `cmd /c` silently does not execute from this shell.**
*Symptom:* two commands (`mklink` for a node_modules junction, then `taskkill`) printed the cmd
banner and returned success without running.
*Root cause:* Git Bash path mangling. A command that prints a banner and exits 0 is
indistinguishable from one that worked.
*System change:* use PowerShell (`powershell -NoProfile -Command`) for Windows-native operations
from this shell, and beware `$` in the command — bash expands it before PowerShell sees it, which
produced a third failed attempt. Recorded as a lesson.

---

## Design Decisions

Logged in full in `docs/decisions.md` (2026-07-28):

1. **Single-colour icon set replaces emoji in the shell** (owner). Emoji cannot take a theme;
   `currentColor` glyphs inherit the row's state and a tenant's brand ramp.
2. **The Administration hub keeps probing for itself.** It needs the request *count*, not merely
   liveness, and N3 deletes that page — refactoring a file about to be removed buys nothing.
3. **`manualRole()` delegates only the super rule.** `effectiveRole` falls back to `reviewer`,
   correct for a menu (show the least) and wrong for a manual (whose fallback must be no chapter
   at all), so the accepted list stays literal.

---

## Numbers

| | Before | After |
|---|---|---|
| jest | 863 / 57 suites | **890** / 60 suites |
| i18n keys × 3 | 4034 | **4057** |
| `admin/layout.tsx` | 220 lines | **60** |
| Copies of the role normalisation | 1 + `manualRole` | **1** |
| Transitional nav fields | 3 | **0** |
| New dependencies | — | **0** |

---

## Carried Forward

- **▶ N3:** organisation/programme switchers (one new org-fenced endpoint, classified in
  `test_org_fence.py`) + the Administration route split. The breadcrumb's shape is already right.
- **TD-182 (new):** admin Google sign-in fails on a local dev origin — the PKCE code is never
  exchanged, most likely because the globally-mounted student client consumes it first. Works in
  production. Deliberately not fixed here: it is production auth code and deserves its own commit.
- **Owner review:** the Malay and Tamil strings for the reserved slots and the shell are first
  drafts.
