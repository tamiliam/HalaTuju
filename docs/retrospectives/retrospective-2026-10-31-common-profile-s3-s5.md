# Retrospective — Common profile S3 + S4 + S5: My activity (2026-10-31)

Roadmap: `docs/plans/2026-10-31-common-profile-roadmap.md` (arc DONE). Mock-ups (owner-approved, the My activity
column is on board 1): https://claude.ai/artifact/2w7vJhKNhjpkNuy8oa5582.
Shipped together: main `d85eedbc` (api-01220-drw, web-01044-mjt), migration `scholarship/0195_staff_activity`
applied by hand first, then the back-fill through the `release-decisions` job.

## What Was Built

- **S3 — the list and the case actions.** Table `staff_activity` (ids only, closed verbs and meta keys, no free
  text; rows go with the person). One best-effort writer `staff_activity.record()` — a savepoint in the caller's
  transaction, never raises, a None actor writes nothing — wired into the case, sign-in and profile verbs.
  Courses-side actions go through `apps/courses/staff_activity_hook.py` (the import budget was full).
- **S4 — money, contracts, requests, the reader, the back-fill.** Every verb in the `WIRED` registry (an AST drift
  test pins writers to it). `GET admin/me/activity/`: own rows only, cursor paging, filters, names decided at READ
  time by the screens' own predicates (`surface_gates.py`), removed subjects read "(removed)", source users and
  mentors are outsiders. `backfill_staff_activity --dry-run | --apply`: idempotent, twin-guarded, an email maps
  only to a staff row that existed at the time, and two event kinds that cannot be credited safely are counted,
  never rebuilt.
- **S5 — the card.** The My activity column on `/admin/profile` (day groups, chips per person, Show older, rebuilt
  marks, "only you can see this"), en/ms/ta words with a drift test against the server's lists, a Guide section
  and an FAQ entry. **Live:** 961 past actions rebuilt for 28 people (2026-06-10 → 2026-10-31); a second dry run
  rebuilt 0.

## What Went Well

- **The S4 adversarial review earned its place again:** nine findings (one HIGH: QC accepts credited to the wrong
  person by the back-fill; mediums: an email mapped to a later account with the same address, labels shown after
  a power was taken away, interview submits mis-attributed). All fixed before anything shipped.
- **Read-time labels via the screens' own gate functions.** Moving each screen's inline check into
  `surface_gates.py` and calling it from both places means the list can never show more than the screen would.
- **Shipping three sprints at one deploy point** kept it to one migration and one push for the whole list, with
  the branch backed up on GitHub (triggers fire on `^main$` only) while it waited.
- **Peer coordination held:** four sessions pushed HalaTuju today; every push was announced and waited for.

## What Went Wrong

1. **Debt numbers collided twice (TD-440, then TD-441).** Why: a TD number is picked on a branch while another
   session picks the next free number on main; the clash appears only at rebase. Prevention: at every rebase,
   grep the incoming main for the TD numbers the branch adds, and renumber in the same rebase (done: mine is now
   TD-444). Added to lessons.
2. **The merged-tree typecheck failed on a package the shared `node_modules` lacked.** Why: worktrees junction to
   the main checkout's `node_modules`, which predated Mobile M0's new devDependency (`@playwright/test`). Nothing
   installs into the shared folder when a peer adds a dependency. Prevention: after a rebase that changes
   `package.json`, diff its dependencies against the shared `node_modules` before running gates (fixed here with
   `npm install --no-save @playwright/test@1.64.1` in the main checkout). Added to lessons.
3. **`npm run mobile-check` timed out on 77 public cells, twice.** Why: a cold `next dev` compile of the public
   routes under three workers on a busy machine (the first run shared the CPU with the 18-minute pytest run).
   No public page changed; every sandbox cell passed and none got worse; one public cell re-run alone passed.
   Recorded as not a finding with the Mobile session's agreement. Prevention: Mobile M1 adds a route warm-up and a
   timer-based wait; until then run it on a quiet box with `--workers=1` if a public page changed.
4. **The first rebase onto Mobile M0 was wasted work** (tests started, then Maintenance pushed and a second
   rebase was needed). Why: started the long gates while a peer push was announced but not yet green.
   Prevention: start the full gates only after every announced peer push reports green.

## Code review of the S5 diff (step 4b)

No high or medium findings. Two lows, both accepted and logged rather than fixed now (a fix is a third deploy of
this feature, and neither shows wrong data):
- **TD-445** — a visible subject with an empty name shows the server's English neutral word as its name (ms/ta).
- **TD-446** — the card goes back to page one when the sign-in token refreshes.
The reviewer confirmed: the superseded-answer guard, both links match their pages' own gates, nothing hidden or
removed leaks, the Monday rule, the chip matrix, the phone layout, and identical en/ms/ta keys.
**Bite check:** the drift test turned red when one Tamil verb key was renamed (restored and verified by digest).

## Design Decisions

See `docs/decisions.md`: the S3/S4 activity-list entries and "My activity on the Profile page" (own rows only,
labels decided when read, neutral words translated on the web, chips per person). Lead choices the owner may
overturn: the Guide entry is English only (the manual is); "this week" means since Monday; only students and
payment runs are links.

## Numbers

- pytest 11,203 passed / 3 skipped (`-n auto`) · jest 5,813 / 354 suites · typecheck 0 · lint 0 · i18n 6,789 keys.
- Bundle: median 147.097 kB (0.9 kB under 148); `/admin/profile` 166 kB; `/scholarship/application` 0.247 kB of
  room (TD-433, pre-existing).
- Back-fill: 961 rebuilt, 241 skipped by design; a re-run rebuilt 0.
- Deploys for this feature: 2 (S1+S2, S3–S5). Open debt from the arc: TD-439, TD-442, TD-443, TD-444, TD-445,
  TD-446.
