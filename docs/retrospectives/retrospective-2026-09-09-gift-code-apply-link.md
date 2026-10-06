# The apply link, and a gift code that can change — 2026-09-09

**Worktree** `.worktrees/gift-code`, branch `feat/gift-code-alias`, base `8dcd2310`.
**Migration `scholarship/0153` — a REAL new table. MIGRATE-FIRST, WITH RLS.** api + web.

Gates, all run inside the worktree: pytest **6059** (+25) · jest **1903** (+11) · tsc **24**
(baseline, TD-221) · lint **0 Errors** · i18n **4910 × 3** (+9) · `next build` exit 0 ·
`makemigrations --check` clean. **Five bite-checks landed** (three backend, two frontend).

---

## What the sprint was for

The owner had approved two halves of one idea: put the **apply link** on the gift card, and make
the **short code editable**. They are one sprint because the second is unsafe without the first
being understood.

`resolve_open_cohort` filters on `programme__code`. An unknown code does not error — it returns
"no open round". So renaming a gift's code with nothing else in place would have made every
poster, every school letter and every forwarded message already in circulation tell a student
**"applications are closed"**, with no error anywhere and nobody to notice. That is why the alias
is not a nicety.

## What shipped

- **`ProgrammeCodeAlias`** — one row per retired code, unique platform-wide, cascading with its
  gift. Written by exactly ONE caller: `AdminProgrammeDetailView.patch`. No backfill (a gift never
  renamed has no alias, and that is correct).
- **`services.resolve_open_cohort` falls back to an alias** — live code first, alias second.
- **`models.code_is_free(code, exclude_programme=None)`** — uniqueness across both tables, called
  by the create path and the rename path.
- **`apply_url` on each gift row**, built from `branding.for_organisation(...).frontend_url`.
- **The ⋮ menu gained two items:** *Copy apply link* and *Change the short code*; the rename dialog
  shows the current link beside the box that changes it.
- **The manual gained a section**, and `codeWarning` was corrected in all three languages.

## The rulings that must not be tidied

**⚠ THE ALIAS SERVES THE STUDENT PATH ONLY.** The admin console's breadcrumb switcher resolves live
codes. An administrator's URL is never printed; letting a stale one keep working there would hide
a rename from the person who made it. Written up in `docs/decisions.md`.

**⚠ LIVE CODE FIRST, ALIAS AS A FALLBACK.** `code_is_free` forbids the collision, so the order
cannot change an answer today. It is written that way so that if one ever existed, the CURRENT
owner of a code beats a ghost of it.

**⚠ UNIQUENESS HAS TO BE IN CODE.** Neither table's unique constraint can see the other, and a
retired code still routes students — handing one to a second gift is PF-1's fault in a new costume.

**⚠ THE LINK IS SERVED WHOLE, NEVER ASSEMBLED IN THE BROWSER.** `window.location.origin + …` is
right today, because the console and the student site share an origin, and would go silently wrong
the day a tenant is served from its own domain. It is also the one string somebody copies onto a
poster; a half-built one is worse than none.

**⚠ THE COPY FAILURE PATH CARRIES THE LINK.** `navigator.clipboard.writeText` rejects on an
insecure origin and wherever the permission is withheld. A bare `await` — the shape the repo's one
existing copy control uses — leaves somebody pressing a menu item that does nothing at all. On a
refusal the banner prints the link, which is what they came for.

**⚠ RE-SELECT ONLY THE GIFT THAT WAS CHOSEN.** The breadcrumb holds a code; renaming the gift
somebody is inside would leave the shell holding a code the scope list no longer knows, and that
is the dead "which gift?" screen from 2026-09-07. Re-selecting unconditionally would be worse — it
would move the reader into a gift they were not in. Both halves have a test.

**⚠ RENAMING BACK IS A REAL CASE.** A gift may return to a code it used to answer to; its own
aliases are excluded from the uniqueness check, and the handler deletes the alias row that would
otherwise duplicate the live code.

## What went wrong, and is worth reading

**A restore-by-string-replacement hit the wrong occurrence.** The frontend bite-check turned
`if (wasChosen) select(wanted)` into `select(wanted)`; the restore replaced the FIRST
`select(wanted)` in the file, which belongs to the *create* flow three functions higher. The
lesson file's standing rule — restore by writing the original bytes back, never `git checkout --`
— was followed, and was not enough on its own: the anchor has to be unique to the site injected
into. **Only the suite staying red caught it.** Re-run after every restore and expect green.

**A UI sentence was asserting the opposite of the feature.** `codeWarning` had told every reader
for months that the code "cannot be changed after creation". It appeared in no test, in no grep for
the feature, and in no diff of anything being changed. When a capability arrives, grep the message
file for copy asserting its absence.

## At deploy, in order

1. **Apply `scholarship/0153` MIGRATE-FIRST** via Supabase MCP. `sqlmigrate` renders SQLite here —
   the hand-written Postgres DDL, **including `ENABLE ROW LEVEL SECURITY` and the one
   `service_role` policy**, is in the migration's own docstring. Record the `django_migrations` row
   BEFORE the push.
2. Confirm the Security Advisor reports no new finding.
3. Push (**api + web** — Python changed, so expect both builds).
4. No env vars. No backfill. No data step.

**Nothing a student sees changes** unless somebody renames a code — and then their old link still
works, which is the whole point.

## Owner post-check (as the BrightPath `org_admin`, elanjelian@me.com)

1. Organisation → Overview → **⋮ on a gift → Copy apply link.** Paste it somewhere: it should read
   `https://halatuju.xyz/scholarship/apply?p=<code>`, and the card should say "Link copied".
2. **⋮ → Change the short code.** The dialog shows the current link above the box, and says the old
   code keeps working.
3. Change a spare gift's code, then **open the OLD link** — it must still reach the apply page.
4. Try renaming to the other gift's code — it should be refused.
5. **ms and ta are first drafts** for the nine new strings.
6. Not click-tested in a browser (TD-182 still breaks admin Google sign-in on localhost).
