# Scholar file — the Activity box, learning from Podio (roadmap, 2026-11-08)

Status: **DRAFT — awaiting the owner's further suggestions, then approval.** Branch `activity-box` (from main
`0fec1c69`), docs only. Nothing is built, pushed or deployed until the owner approves; the audit agent sets the pace.

## Why
The owner, 2026-11-08, comparing Podio's activity/comment panel with ours: *"I like how the activity/comment box is
done in podio. Can ours copy its best features?"* — then *"Write this up as a plan. I have a few other suggestions for
improvement. I want to bundle them as well."*

## What exists (measured 2026-11-08)
- **Web:** `halatuju-web/src/components/admin/ScholarActivity.tsx` (133 lines), used twice on
  `app/admin/scholars/[id]/page.tsx`: the Overview side panel (`compact`, newest 6) and the Activity tab (all).
  Composer on top: Note / Call / Meeting pills, a 3-row box, the Staff only toggle, Save. Each row: a coloured dot,
  the text, then `kind · actor email · date and time` and a Staff only chip. Wording from `lib/scholarActivity.ts`.
- **API:** `GET/POST admin/scholarship/scholars/<pk>/activity/` (`views_admin/scholars.py:214`), payload
  `scholars.activity_dict` — `actor_email` only, no name or photo. Writers in `activity.py`: `log_event` (system,
  inside the caller's transaction) and `add_entry` (manual).
- **Model:** `StudentActivity` (`models/activity.py`, table `student_activity`): kind, event, body, meta, actor_email,
  internal, created_at. 15 system events, all about staff or system actions (status, payments, results, letters,
  mentoring, closure). **Nothing the scholar changes on their own file is logged.**
- **Names and photos exist elsewhere:** `PartnerAdmin.name` (by email); `StaffProfile.photo_path` with
  `staff_photo.signed_url` (~1 hour signed link).
- No relative-time helper in `lib/formatDate.ts`; no @mentions anywhere.

## Podio compared with ours

| Podio | Ours | Decision |
|---|---|---|
| Name + photo per entry; a group icon for automatic entries | Email address, or "System" | **Copy** (P1) |
| "9 days ago", exact date on hover | Full date and time only | **Copy** (P1) |
| Activity / Comments tabs: what people wrote apart from what the system did | One mixed list | **Copy as a filter**: All · Notes · System (P1) |
| Comment box is one line until you click it | 3-row box, pills and toggle always open | **Copy** (P1) |
| The person's own edits appear (e.g. a scholar updating details) | Not logged | **Copy, with care** (P2) |
| Field values shown in full (a whole card number in the owner's screenshot) | — | **Do not copy.** Log "Bank details changed", at most the last 4 digits. No PII in logs. |
| A lightning icon on every row | — | Do not copy: noise. |
| Pale grey text | — | Do not copy: fails our contrast checks. |
| Tasks inside the stream | No tasks on a scholar file | Not a copy — a new feature. Only if the owner adds it below. |

Also found: the side panel shows 6 entries with no way to the full list — add **"See all (n)"** to the Activity tab.

## Owner's further suggestions (to be added)
*Waiting for the owner. Each will be placed into P1, P2 or a new sprint, with any ruling it needs.*

1. …

## Decisions needed from the owner
- **D1. Which scholar edits are logged (P2)?** Recommend: bank details, phone, email, home address, guardian contact
  — the fields an officer must know changed. Not every profile field.
- **D2. How much of a value is shown?** Recommend: bank account — last 4 digits only; phone/email/address — "changed"
  with no value (the current value is on the file already).
- **D3. Newest first stays?** Podio lists oldest first with the box at the bottom. Recommend we keep newest first with
  the box on top — officers want the latest; the side panel shows only the newest few.
- **D4. Can a scholar's edit be Staff only?** Recommend: these rows are always staff-only (`internal`), as a status
  change is today, until a student view of the log exists.

## Sprints
Each sprint: own commit(s) on its branch, targeted tests while building, full API + web gates once, a fresh reviewer
on the diff, CHANGELOG + decisions.md. Nothing pushed without the owner.

### P1 — Who, when, and a lighter box · complexity: medium
- **Goal:** each entry shows a name and photo and "9 days ago"; a filter separates notes from system rows; the box is
  one line until used; the side panel links to the full list.
- **Stitch first** (house rule for a layout change): one screen of the panel and one of the tab, phone and desktop,
  for the owner's approval before coding.
- **API:** `activity_dict` gains `actor` = `{name, photo_url, role}` — looked up once per distinct email per request
  (staff and mentors by their `PartnerAdmin` login row, the scholar as "the scholar"; an unknown email shows as
  written), photo signed once per person, never
  per row. No migration.
- **Web:** `ScholarActivity.tsx` — avatar (photo, or initials; a system icon for system rows), name in bold, text
  under it; relative time with the exact time as `title` and screen-reader text; All · Notes · System filter (the
  Activity tab only; the side panel stays mixed); collapsed composer that opens on focus and closes on Save or Esc
  when empty; "See all (n)" in compact mode. New `relativeTime` in `lib/formatDate.ts` (en/ms/ta).
- **Files (≈12):** `scholars.py`, its test; `ScholarActivity.tsx`, `lib/scholarActivity.ts`, `lib/formatDate.ts`,
  `admin-api.ts` (type), en/ms/ta.json, tests; CHANGELOG.
- **Done when:** a test asserts name + photo for a staff row, initials when no photo, the system icon for a system
  row, and no email shown; the filter hides and shows the right rows; mobile-check passes on the scholar file; the
  read makes one photo signing per person, not per row.

### P2 — The scholar's own edits appear · complexity: high (personal data: Opus build + Opus review, phone check)
- **Goal:** when a scholar changes the fields ruled in D1, a staff-only system row says so, per D2.
- **API:** new events (e.g. `details_changed` with `meta.fields` = the field names, and `meta.last4` for a bank
  account only), written by `log_event` inside the save that changes them; a guard test that no event's meta carries
  a full account number, phone, email or address.
- **Web:** `activityText` sentences for the new event; en/ms/ta.
- **Migration:** none (the event list is code; `meta` is JSON).
- **Files (≈12).** **Phone check before go-live.**
- **Done when:** a scholar changing their bank account produces one row "Bank details changed (…1234)" visible to
  staff only; changing a field outside D1 produces none; the PII guard test passes.

## Order and rationale
P1 first — no rules and no personal data, and it builds the row layout P2's entries drop into. P2 second, on its own,
because it touches personal data and needs the owner's D1/D2 rulings and a phone check; bundling it with layout work
would hide a privacy change inside a cosmetic diff. The owner's further suggestions are slotted in once received.
