# Retrospective — request #39, staff permissions and Finance approval (the whole arc, Sprints 1-4, 2026-10-19 → 2026-10-21)

Roadmap: `docs/plans/2026-10-19-staff-permissions-roadmap.md` (owner "a", 2026-10-19: hold the quote at
34 h). Decisions: `docs/decisions.md` 2026-10-19 (S1-S3) and 2026-10-21 (S4). Role matrix restructured as
catalogue + presets + lead tier (`docs/scholarship/role-matrix.md`). Sprints 1-3 and TD-360 are live;
Sprint 4 is built on `perm-s4`, **not pushed, not deployed, its adversarial review still to come**, and
needs migration scholarship 0175 applied by hand first.

## What the owner asked for, and what exists now

> "Can we change all to admin and control only access permission? So, a reviewer is someone with review
> permission. A QC likewise is an admin with QC permission."

- **S1 (foundation):** eight catalogue keys, presets that reproduce the day's powers, `PartnerAdmin.permissions`
  (NULL = the preset, no backfill), `/admin/role/` serving the resolved set, the golden table written
  green on the unconverted code, the invite's "already exists" message fixed without leaking another
  organisation's accounts.
- **S2 (money, owner option A):** Admin prepares, Finance approves and that approval releases the money;
  the organisation admin approves only under a per-run fallback. Wallet credits deliberately unchanged.
- **S3 (the gates):** applications scope, files, QC, assignment and Spending read permissions; presets
  provably unchanged.
- **S4 (the editor):** People → a person → *What <name> can do*, with a server dry run behind every
  toggle, refusals that keep cases from being stranded, chips on People, Change role resetting a custom
  set, a history table, and the Guide opening the sections for permissions a person was given.
  **Rohini (Reviewer + Spending) can be set up the day S4 is live** — proven on a local server by the
  same calls the screen makes (`perm-s4` local run, 2026-10-21) and by `test_permission_editor.py`.

## What went well

- **The golden table first.** Writing every converted gate × every preset against the OLD code before
  converting anything meant S2 and S3 could each say exactly which cells moved (the `s2` rows) and that
  nothing else did. S4 never had to argue about presets at all.
- **NULL = preset.** No backfill, no change to six staff-creating doors, and "custom" falls out as
  `permissions IS NOT NULL`. The re-invite and role-change resets became one-line writes.
- **The door list in the plan.** Every sprint's adversarial review was handed the list and asked for the
  door not on it; S2's review found the one that mattered most (an edit or cancel racing an approval
  could pay a run twice — an old bug on the door list).
- **TD-360 before S4,** as the plan recommended: ~25 new keys per language cost the budgeted student
  routes nothing, so the editor kept its words in the message files (visible to Sol) instead of serving
  them from the api.

## What went less well

- **Each review round added roughly a quarter to its sprint.** S1 gained 7 golden rows and the re-invite
  reset; S2 a HIGH double-payment race, per-run check arming and the never-signed-in approver; S3 the R1
  override needing `see_all`. All were right to fix; the estimate's 1.25 h per review was light.
- **Stitch timed out twice for S4.** The owner approved a clickable HTML mock instead (recorded in the
  plan as the design of record). Faster than Stitch would have been; worth keeping as the fallback.
- **A planned rule needed sharpening in the build.** "Refuse removing `review` from someone holding cases"
  was only half the stranding rule; S3's review found the `see_all` half (an admin given a case by a super
  reaches it only through `see_all`). S4 refuses both, and closes the race with assignment under one row
  lock — the first sprint to touch `assign_reviewer`'s transaction shape.
- **Mid-run edits contaminated a baseline.** S4's first full api run started before the edits and finished
  after some had landed, so it reported two of S4's own failures as "baseline". Take baselines on a clean
  tree, or in a second worktree.

## Hours (honest estimate — no timesheet was kept)

| Sprint | Planned | Estimated actual | Why the difference |
|---|---|---|---|
| S1 | 9.0 | ~10.0 | review fixes (7 golden rows, re-invite reset, case-insensitive match, unmanageable-colleague wording) |
| S2 | 8.0 | ~10.0 | two hardenings beyond the plan (row lock on sign, cross-organisation signer) + six review fixes incl. the HIGH double-pay race |
| S3 | 10.0 | ~10.5 | five review fixes (R1 needs `see_all`, legacy super flag row, landing, org-fence tests) |
| S4 | 9.0 | ~8.5 so far + review | no Stitch rounds (mock instead, −0.5); assignment lock and Guide section tags (+0.5); adversarial review + fixes still to come (1.25 planned) |
| **Total** | **36.0** | **~39-40** | |

**Against the 34 h quoted, the arc is about 5-6 h (15 %) over; against the 36 h planned, about 3-4 h.**
The overrun is almost entirely review-fix work on money and identity, which the house rule requires and
which the quote did not price at its real size. TD-360 (≈ one sprint) is platform hygiene and not counted.
The owner promised the organisation not to exceed 34 h without coming back first: **this needs that
conversation before S4 is billed** — recommend absorbing the difference, as option A already did for the
first 2 h.

## For next time

- Price an adversarial review on money / identity at 2 h, not 1.25 h.
- A "refuse X while Y" rule in a plan should name every path by which the person reaches Y.
- Keep a clickable mock as the standing fallback when Stitch will not answer.
