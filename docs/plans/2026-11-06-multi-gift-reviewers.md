# Multi-gift reviewer tagging (owner-approved design, 2026-11-06)

## Goal

A reviewer can cover **several** of the organisation's gifts, not just one or all. The default is
still **every gift**: a reviewer with no gift rows covers every gift. QC reviewers do not change.
The server keeps refusing `gift_mismatch` (400) when a case's gift is not one the reviewer covers.

## Model change

- New join table `ReviewerGift` (`reviewer_gifts`) in `apps/courses/models_staff.py`:
  `partner_admin` FK (CASCADE, `related_name='gift_rows'`), `programme` FK to
  `'scholarship.Programme'` (CASCADE, a string reference — no `courses -> scholarship` import),
  `created_at`, unique pair (`reviewer_gift_one_row_per_pair`).
- Each gift must belong to the reviewer's own organisation. Enforced in the API (the one writer,
  `staff_gift.set_gifts`, is only ever handed gifts resolved inside that organisation).

## Data migration

- `courses 0092_reviewergift`: CreateModel, then RunPython — every `PartnerAdmin` with a non-null
  `programme` gets one row. NULL gets none (every gift, as before). Reverse: nothing to undo (the
  table goes with the CreateModel reverse).
- RLS in the same step as the CREATE (house convention). Postgres DDL + the copy + the ledger row are
  written out in the migration docstring for a hand apply. **The live apply needs the owner's yes.**

## How the old FK is handled

- **No reader** of `PartnerAdmin.programme` is left (assignment, `me.programmes_of`, reviewers list
  and detail, assignable admins, invite, re-invite, `staff_gift_report`).
- The column is **not dropped**. `set_gifts` keeps it as a WRITE-ONLY rollback mirror: exactly one
  gift -> that id, otherwise NULL (NULL = every gift for the old image, the permissive side).
- New TD (>= TD-540): drop the column and the mirror once the deploy is proven.

## API

- `staff_gift.resolve_gifts(raw_ids, organisation)`: list of ids -> gifts of THAT organisation;
  anything else (unknown, other organisation, not an id) is 404 `not_found`, never 403.
- Invite (`AdminInviteView`): a reviewer invite sends `programme_ids` (list; empty = every gift).
  The old `gift_scope` + `programme_id` form is still read during the deploy window. Neither sent
  is still 400 `gift_required`.
- `POST admin/reviewers/<pk>/programme/` is **extended**, not replaced (the access-matrix fixtures
  pin this URL): `{programme_ids: [...]}` sets the list; the old `{programme_id}` still works.
  Same gate (super or org_admin), same org fence on the target, gifts must be in the TARGET's
  organisation (fixes a super being able to tag another organisation's gift), same AUDIT line.
- Served: `gifts: [{id, code, name}]` (empty = every gift) on the reviewer row and on the
  assignable-admins row, replacing `programme_id` / `programme_name`. The gift choices gain
  `organisation_id` so a super's pop-over lists only the reviewer's organisation's gifts.
- TD-531 (b): one source of truth for a case's gifts — `case_gifts` = {application.programme,
  cohort.programme}, the same pair the lists filter on. `gift_allows` = reviewer covers every gift,
  or the case gift is unknown, or the two sets meet.
- TD-531 (a): with the owner's "default is every gift" rule, Team -> Add and the role switch leave
  no rows (every gift) and the org admin narrows with the pencil. Recorded in the TD.

## Web

- `ReviewerGifts` component (new file): grey chip per gift, or one soft blue "Every gift" chip; a
  pencil opens a pop-over (Every gift tick; the gift tick list, greyed while Every gift is ticked;
  Cancel / Save). Ticking a gift un-ticks Every gift; clearing every tick goes back to Every gift.
- Reviewers list (phone cards + desktop table) and reviewer detail use it.
- Staff invite: the same tick list, Every gift ticked by default, helper line "Match reviewers to
  gifts by their strengths and interests."
- Case-assign picker: a reviewer who does not cover the case's gift is greyed, "Does not cover
  <gift>".
- en / ms / ta strings (Tamil per the style guide).

## Tests

- API: model + data migration (FK -> one row, NULL -> none); `gift_allows` with 0, 1, 2 gifts and
  the cohort/programme pair; assignment refused for a wrong gift, allowed for a covered or every-gift
  reviewer; set-gifts permissions (own org, other org refused, super, gift of another org refused);
  invite with several gifts; reviewer row exact key set.
- Web jest: chips + pop-over; invite tick list; picker greying.

## Risks

- **API and web must deploy together** (served keys change from `programme_id` to `gifts`).
- Migration must be applied by hand before the deploy (migrate-first); without the table every
  reviewer read 500s.
- A parallel builder adding `courses 0092` would clash — renumber on merge.

## Deploy steps

1. **Migration first.** Apply `courses 0092_reviewergift` to the live database immediately before the deploy (migrate-first; without the `reviewer_gifts` table every reviewer read 500s).
2. **API first, then web.** Deploy the API, confirm it is live (read the build status, hit a reviewers read), then deploy the web.
3. **Right after, run this read-only check** and backfill any rows it returns (a reviewer who had a gift in the old column but no row, e.g. tagged between the migration and the deploy):

```sql
SELECT pa.id, pa.programme_id
FROM partner_admins pa
WHERE pa.programme_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM reviewer_gifts rg WHERE rg.partner_admin_id = pa.id);
```

   The matching backfill (columns checked against migration 0092: `partner_admin_id`, `programme_id`, `created_at`). **Needs the owner's yes before it is run:**

```sql
INSERT INTO reviewer_gifts (partner_admin_id, programme_id, created_at)
SELECT pa.id, pa.programme_id, now()
FROM partner_admins pa
WHERE pa.programme_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM reviewer_gifts rg WHERE rg.partner_admin_id = pa.id);
```
