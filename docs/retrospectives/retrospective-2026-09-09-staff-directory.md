# Retrospective — Invitations means waiting; People holds everybody who is in

**Date:** 2026-09-09 · **Branch:** `feat/staff-directory` · **Worktree:** `.worktrees/staff-directory`
**Base:** `origin/main` @ `1b042d8c` · **Migration:** none

---

## What Was Built

One rule — *what does "waiting" mean?* — landed in four surfaces that had been answering it
separately.

| Surface | Before | After |
|---|---|---|
| Invitations table | every invitation ever sent | only the unanswered ones (`open_only`) |
| The badge on each button | `open_only`, correctly | unchanged — the table now agrees with it |
| Organisation overview tile | `all staff − active staff`, called "not yet accepted" | the server's count, across all four kinds |
| Reviewers page | the reviewers directory | **People**, with `Reviewers` and `Admins` tabs |

Plus: **Revoke / Restore moved onto the person**, beside Pause; the dead Revoke arm on the
invitations table was deleted; and the empty state learned to say *which* empty it is.

**What the owner asked, and what was actually there.** The question was "reviewers are displayed in
two places, could this be consolidated?" Checked against production: **13 reviewer accounts, 13
reviewer invitations, set difference empty both ways** — not similar lists, the same list twice.
And 18 of the page's 20 rows were accepted invitations, with nothing filtering by status, so it
would have degraded further on its own as the two waiting sponsors registered.

---

## What Went Well

- **The answer was already in the codebase, written by somebody who had thought about it.**
  `navigation.ts` carried the rule from request #10 — *"Staff invites and revokes; Reviewers is
  where you LOOK at somebody"* — and `adminStaff.ts` carried the owner's own two categories from
  2026-08-03. The sprint finished an existing decision rather than inventing one, which is why the
  design conversation took three messages.
- **Checking the two lists against production changed the advice.** "They look similar" and "they
  are byte-for-byte the same 13 people" lead to different recommendations. The query took a minute.
- **`StaffTable` absorbed the Admins tab with no new table.** It already knew that revoked beats
  paused, already drew phone cards, already had `onToggle` and `soleOrgAdmin`. Its own docstring
  says it exists to stop the staff table being copied a third time — and it held.
- **Every one of the five bite-checks bit**, including the two "drive over the bump" ones: an
  always-empty table and an always-"everyone accepted" empty state both fail their own tests.

---

## What Went Wrong

**1. The overview tile had been wrong since it was written, and no test could see it.**

- *Symptom:* the tile said *"1 invited, not yet accepted"* on an organisation where nobody was
  waiting. The owner went looking on the Invitations page and found nobody — correctly, because the
  person it meant had accepted in June and been revoked afterwards.
- *Root cause:* two failures at once, from the same habit. It **derived** a number that another
  surface already owned (`staff.length − activeStaff`), and the thing that subtraction measures —
  who is switched off — is not what the label claimed. And because it read only staff, it could
  never see the two sponsor invitations that genuinely were waiting. **There was no rendered test
  for this page at all**, so both faults were invisible to the suite; the file is 143 lines and
  looked too simple to need one.
- *System change:* (a) the page now READS `waiting` from the same endpoint the Invitations page
  uses, with a comment saying a count here is read and never derived; (b) `page.test.tsx` exists
  now, and its first test is the owner's exact case — a revoked admin on the books, nobody waiting,
  the tile must say 0.

**2. The empty state would have replaced one false sentence with another.**

- *Symptom:* filtering the table to waiting-only left *"Nobody has been invited in this group yet"*
  standing over a group where thirteen people had been invited and all thirteen had accepted.
- *Root cause:* an empty list has two causes and the browser cannot tell them apart from an empty
  list. This is the 2026-08-18 lesson (*an empty card is usually asserting something, and on a
  settled record the assertion is usually false*) arriving in a new place — and it mattered more
  here than usual, because after this change **the empty state is the page's normal state**.
- *System change:* the server sends `kind_totals` beside `waiting_counts`, and the page picks
  between two sentences. A test drives over the bump: a page that always said "everyone accepted"
  fails.

**3. I nearly shipped a tab bar that `finance` could not see.**

- *Symptom:* caught while editing, not by a test. `PanelTabs` on the reviewers page rendered only
  when `mayEditEmails`, which excludes `finance`.
- *Root cause:* that gate was harmless while Emails was the only other panel — the bar existed to
  reach an editing tab. Adding a **reading** tab behind an **editing** gate would have hidden
  Admins from a role that may read it, which is the same shape as the 2026-09-08 stranding lesson
  (*a role loses a page because a container was gated for a different reason*).
- *System change:* the bar renders for everyone who may read the page and each tab keeps its own
  gate; a test asserts `finance` sees the Admins tab and not the Emails tab.

---

## Design Decisions

- **People, not a new menu row.** The alternative was a 12th row in a group that already has 11,
  for a list of five. Folding it into the page next door mirrors the gift-programmes move of
  2026-09-03, and the two tabs are the owner's own categories rather than a new vocabulary.
- **The route stays `/admin/organisation/reviewers` though the label is "People"** — the same
  ruling the Staff → Invitations rename made, for the same reason: bookmarks, the ⌘K chord and the
  highlight rules keep working, and only the word changes. The nav `id` stays `reviewers` too; it
  is the snapshot key and is never derived from the label.
- **`?all=1` keeps the full history reachable** rather than deleting the capability. Nothing in the
  console passes it today; it exists so "only the waiting ones" is a default, not a wall.
- **Revoke's gate moved with the control and was not widened.** `super` + `org_admin`, exactly as
  on Invitations. `admin` and `finance` read the tab; the endpoint remains the authority.
- **The two Emails tabs were left alone.** They are not duplicates: Invitations → Emails is the
  four invitation letters, People → Emails is the five emails a volunteer receives while working.

---

## Numbers

| Gate | Result |
|---|---|
| pytest | **6081** passed (+13), 219 subtests |
| jest | **1919** passed (+16), 118 suites |
| `tsc --noEmit` | **24** errors — unchanged baseline (TD-221) |
| `next lint` | **0** errors |
| `check-i18n` | ALL PASSED, **4919 × 3** (+22 keys) |
| `next build` | exit 0 |
| `makemigrations --check` | No changes detected |
| Migrations added | **0** |
| Bite-checks | 5 fault injections, all bit |

**Files touched: 14** — 3 backend, 6 frontend, 4 test, 1 changelog (plus this retro, decisions and
lessons at close).
