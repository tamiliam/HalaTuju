# Retrospective — Assignment-based review permission (2026-07-02)

## What shipped
Decoupled **view** (role) from **act** (assignment) in the admin B40 surface. A `role='admin'` keeps
full read-all visibility and can now **write on only the applications assigned to them**; `reviewer`
unchanged (assigned-only); `super` any; `partner` none. A view-all admin is now an assignable target.
Also trimmed Guide/FAQ from the partner nav.

Driver: Suresh — a view-all admin **and** a funding sponsor — needed to review a selective set of
students without being handed the whole programme, which the old role-only model (admin=see-all-no-edit
XOR reviewer=assigned-only-edit) couldn't express.

## Implementation
- One shared gate: `_AdminBase._can_review_app` / `_require_app_write` (super OR `assigned_to == me`,
  partner excluded). Replaced the role-only `_require_reviewer` across **25** per-application write
  endpoints; 2 special endpoints (disbursement/resolution actions, pk ≠ application) authorise via the
  tranche/item's application; 4 non-application writes (sponsor review, graduation review, reviewer
  profile) correctly kept the role gate.
- `services._can_review` + assignable-admins list now include `admin`; role endpoint returns `admin_id`;
  FE cockpit `canWrite = super || assigned-to-me`.
- No DB migration (reuses `assigned_to`).

## What went well
- The bulk `replace_all` of the identical 6-line preamble converted 17 endpoints in one edit; the
  variant/comment/role-only/special cases (8) were handled individually — a grep census first made the
  split safe.
- Existing endpoints already called `_scoped_application` after the role gate, so reviewers were already
  assignment-scoped — the change was smaller than feared (the only blocker was the role gate).
- Two failing tests after the change were *expected* (admin is now assignable) — updated to assert the
  new rule rather than patched around.

## What to watch
- **Governance:** a funding sponsor can now also hold review-write. Assign such a person only students
  they do **not** fund (conflict-of-interest guard — assignment choice, not code).
- Three profile writes (anon-publish/profile-edit/publish) were previously role-only and are now
  assignment-scoped — a deliberate tightening; confirm no reviewer workflow relied on acting on a
  non-assigned application.

## Lessons
- **Check `max(TD-NNN)` on main before numbering a new TD** — a draft TD-152 collided with another
  branch's TD-152 (bursary donor) and had to be renumbered to TD-153 mid-sprint. Same failure mode as
  the migration-number rule; treat TD numbers the same way.
- A delegated implementation agent died on a transient API 529 with 0 tool uses — verify the tree is
  untouched before re-running, and prefer doing auth-critical breadth directly with a grep census.

## Verification
- 3066 backend tests pass (scholarship + courses), incl. 13 new (`test_assignment_write_permission.py`)
  + 2 updated. `next build` clean.
