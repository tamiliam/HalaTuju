# Sprint P1 — Who, when, and a lighter activity box (brief, 2026-11-09)

Executor: Opus agent. Architect: main session. Roadmap: `docs/plans/2026-11-08-activity-box-roadmap.md` (P1).
Mockup (owner-approved 2026-11-09, version 2, private): https://claude.ai/artifact/L3dutEaMiD51cytQSjrTKz
Branch `p1-activity-box`, cut from `activity-box` (87baefa1). Independent of T2/T3; no G6 file.

## Goal
On a scholar's file, the activity box shows who and when the way Podio does, with a lighter box:
- **Who:** a name and photo (or initials) per entry, never an email.
- **When:** "9 days ago", with the exact time available.
- **Order:** oldest at the top, newest at the bottom, with the box below; "Show older" at the top.
- **Size:** a fixed-height list that scrolls inside itself.
- **Filter:** on the Activity tab.

## Facts (verified by the architect; confirm before relying on them)
- **Web:** `halatuju-web/src/components/admin/ScholarActivity.tsx` (133 lines).
  - It is used twice on `app/admin/scholars/[id]/page.tsx`: the Overview side panel (`compact`, newest 6) and the Activity tab.
  - The composer is on top: Note/Call/Meeting pills, a 3-row textarea, the Staff only `Toggle`, and Save.
  - The wording comes from `lib/scholarActivity.ts` (`activityText`, `activityDot`).
- **API:** `AdminScholarActivityView` (`scholarship/views_admin/scholars.py` ~214).
  - GET is paginated newest first: `?page=`, `?page_size=` (default 50, at most `MAX_PAGE_SIZE`), returning `{count, page, page_size, results}`.
  - Mentoring events are excluded for a viewer without `may_read_mentoring` (keep this).
  - POST `{kind, body, internal}`, with kind among `MANUAL_KINDS`; a closed file returns 409.
  - The payload is `scholars.activity_dict`, which carries `actor_email` only.
- **System rows:** `activity.log_event(..., actor_email=...)` records the person who caused the row when there is one. It is blank when the row is fully automatic.
- **Names and photos:**
  - Staff and mentors: `PartnerAdmin.name` (looked up by email).
  - Photos: `StaffProfile.photo_path`, signed through `staff_photo.signed_url` (about 1 hour).
  - The scholar: their own email on the application or profile.

## Settled decisions (owner, 2026-11-09)
| # | Decision |
|---|---|
| P1-a | **Notes only.** The box is "Add a note…". No Note/Call/Meeting choice; new entries are `kind='note'`. Existing call/meeting/email rows keep their word. The server keeps accepting the other kinds (no API break), the web stops sending them. A plain note shows no kind word; Call, Meeting, Email and System do. |
| P1-b | **Oldest at the top, newest at the bottom, box below the list (Podio).** Reverses roadmap D3. Only the latest few show; "Show older (n)" at the top loads the rest in place, keeping the reader's position. Side panel: latest 6. Activity tab: latest 20 per load. |
| P1-c | **Fixed height, scrolls inside.** About 420 px in the side panel and 560 px in the tab; on a phone about 55vh. Opens scrolled to the newest. After Save, it scrolls to the new entry. The page around it does not grow. |
| P1-d | **Who is shown.** If a person had any hand in the row (a manual entry, or a system row with `actor_email`), show their name and photo, or initials when there is no photo. Only a fully automatic row (blank `actor_email`) shows the System icon and "System". The scholar's own email shows as the scholar ("The scholar" or their name: pick the existing convention). An email that matches nobody is shown as written (the roadmap rule). No email is shown for a known person. |
| P1-e | **Time.** Relative ("2 hours ago", "Yesterday" = the previous calendar day in Asia/Kuala_Lumpur, "9 days ago", then a date past about 30 days). The exact date and time go in `title` and in screen-reader text. New `relativeTime` in `lib/formatDate.ts` in en/ms/ta. If T3's `lib/lastSeen.ts` exists on main by build time, share one helper; otherwise write it so the two can merge later. |
| P1-f | **Filter.** All · Notes · System with counts, on the Activity tab only; the side panel stays mixed. "Notes" means every manual kind. The filter is applied ON THE SERVER (`?show=notes|system`), so "Show older" and the counts stay correct with pagination. |
| P1-g | **Composer.** One line until focused. Then a 3-row textarea, the Staff only `Toggle` (never a checkbox), Cancel and Save. Save, or Esc on an empty box, closes it. A closed file stays read-only (no composer) as today. |
| P1-h | "See all (n)" from the roadmap is dropped: "Show older" replaces it. |

## Build
- **API:**
  - `activity_dict` gains `actor: {name, photo_url, kind}` or `null`, where kind is staff, mentor, scholar or unknown.
  - Look each actor up **once per distinct email per request**, and sign each photo once per person (never per row). Assert the query count.
  - Add the `?show=` filter, and the per-filter counts for the tab (one grouped query).
  - No migration.
- **Web:**
  - `ScholarActivity.tsx`: the new layout, a reversed display over newest-first pages, "Show older" that fetches the next page and keeps the scroll position, the fixed-height scroller, and the collapsed composer.
  - Split the file if it grows past the repo's size rule.
  - i18n en/ms/ta. Delete the keys the pills used if they become unused (keep the kind words still shown on old rows).
- **Mobile:** the side panel and tab at 360 px; tap targets per mobile-check. Add a sandbox surface if mobile-check does not already reach the scholar file.

## Done when
- **Web tests:**
  - A staff row shows the name and photo; initials show when there is no photo.
  - A system row with an actor shows that person; a fully automatic row shows the System icon.
  - No email is visible for a known person.
  - Order is oldest to newest, with the box after the list.
  - "Show older (n)" loads the next page.
  - The filter shows and hides the right rows.
  - The composer opens and closes, and Esc closes it when empty.
  - Save posts `kind: 'note'`.
- **API tests:** the `actor` block; one photo signing per person, not per row (assert the count); `?show=` and the counts; the mentoring exclusion still holds under every filter; the query budget.
- **Gates:** targeted tests while building, then the full gates once through `test_queue.py`: API pytest + `check` + `makemigrations --check`, `npm run gates`, bundle-budget, mobile-check. mobile-check needs `halatuju-web/.env.local`: copy it from the main checkout and delete it afterwards.
- **Docs:** CHANGELOG, plus `docs/decisions.md` (P1-a to P1-h; note that P1-b reverses D3).

## Risks
- **Names and photos widen what a viewer sees:** a staff member's name and photo now appear on a scholar's file. Every role that reads the file already sees staff names elsewhere, but check for a viewer (a reviewer, QC) who could not otherwise see a mentor's name. The mentoring rows are already excluded for them; the `actor` for any remaining row must not name a mentor to them either. Record the result in `docs/scholarship/role-matrix.md`.
- **Bundle headroom is small.** Keep the component light and never raise a budget.
- **Signed photo links expire** in about 1 hour. Fine for a page view; don't cache them in the client beyond the page.
