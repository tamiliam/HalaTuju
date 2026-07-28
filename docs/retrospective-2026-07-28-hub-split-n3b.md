# Retrospective — Nav/IA N3b: the Administration hub becomes real pages

**Date:** 2026-07-28 · **Commits:** `e38e5eac` (N3b), `b26ba393` (auth callback, separate)
**Roadmap:** `docs/plans/2026-07-27-nav-ia-roadmap.md`
**Migration:** none. **Backend:** none. **New dependency:** none.

---

## What Was Built

The hub was one 414-line component doing five jobs. It is now four pages plus a redirect:
`/admin/organisation`, `/admin/organisation/staff`, `/admin/organisations`, `/admin/partners`.

- **`StaffAdmin`** carries the table, banner, page header and the invite/resend/revoke actions, so
  splitting one page into four did not produce four staff tables. Every component in it sits at
  **module scope** — the old file's own comment records that a sub-component declared inside its
  parent remounts the subtree and steals focus from the invite inputs.
- **`/admin/administration` is a permanent redirect**; `/admin/invite` was retargeted straight at
  Staff rather than left to bounce through it. Both light the correct sidebar row, asserted.
- **The registry** drops four reserved slots and marks the overview `exact` — `/admin/organisation`
  is a page, not a section, so it must not swallow `/admin/organisation/staff`.
- **Manual currency in the same commit:** all 16 "Administration" mentions rewritten.

**Numbers:** jest **905** / 61 suites · i18n **4065 × 3** · `tsc` clean · `next build` exit 0 ·
17 files.

---

## What Went Well

- **The shared module was written before the fourth page, not after.** Had the pages come first,
  the table would have been copied and the focus-theft comment lost with it.
- **The Manual rewrite found a statement that had become false.** The Finance chapter said *"there
  is no Payments item in the main menu — the Administration page is the way in."* There is one now.
  The currency rule earned its place: without it that sentence would have shipped as documentation.
- **The overview resisted becoming a link grid.** The sidebar already lists those pages; repeating
  them would have rebuilt the hub inside its own replacement.
- **The org-fence discipline held without being needed.** N3b touches no backend, so the endpoint
  classification gate never fired — worth noting because it means N3a still owes it.

---

## What Went Wrong

**1. I spent four of the owner's attempts debugging an auth flow this sprint does not own.**
*Symptom:* asked for a browser review, the owner hit a Google sign-in failure and retried four
times across two sprints before seeing any of the work.
*Root cause:* I diagnosed from a partial read — twice, confidently, and both times wrong — instead
of surfacing the error the page already held. Worse, I had written the lesson *"when a review is
blocked by infrastructure the sprint does not own, build the smallest thing that renders the work"*
one day earlier, in this same repo, and did not apply it.
*System change:* the callback now prints its own failure reason, which ended the guessing on the
first render. And the standing lesson is restated with the sharper trigger: **the moment a review
is blocked, build the preview — do not diagnose the blocker at all.**

**2. A scripted edit silently no-opped, for the second sprint running.**
*Symptom:* the registry rewrite reported success and changed nothing; caught only because a count
I happened to print did not move.
*Root cause:* Python `str.replace` returns the original string on a miss, and the search text had
LF where the file has CRLF.
*System change:* every subsequent scripted replacement in this sprint asserts the match first, and
the Edit tool — which errors on a miss — is now the default for anything structural.

**3. My own scripted edit corrupted copy, and the assertion did not catch it.**
*Symptom:* a Manual blurb became *"your team, your cases, sponsors and your team"*.
*Root cause:* the replacement was correct in isolation and wrong in context; asserting that the
search text EXISTS says nothing about whether the result reads properly.
*System change:* after any bulk copy edit, read the changed lines rather than trusting the count of
successful substitutions. Two further stale navigation paths were then found the same way — they
had survived because they did not contain the word being grepped for.

---

## Design Decisions

Logged in `docs/decisions.md` (2026-07-28):

1. **The Organisation overview is not a link grid.** It shows only what it can derive from calls the
   console already makes; a richer summary needs an endpoint that does not exist, and inventing a
   figure on a financial surface is worse than omitting it.
2. **The auth-callback change ships in its own commit**, not folded into the sprint that found it —
   the same rule TD-182 states for the real fix.

---

## Numbers

| | Before | After |
|---|---|---|
| jest | 890 | **905** |
| i18n keys × 3 | 4057 | **4065** |
| `administration/page.tsx` | 414 lines | **20** (redirect) |
| Reserved nav slots | 9 | **6** |
| Copies of the staff table | 1 (in a 414-line file) | **1** (shared module, 4 consumers) |

---

## Carried Forward — read this before picking the next sprint

- **▶ PF-1 outranks the rest of this roadmap.** `services.resolve_open_cohort()` selects the most
  recent active+open cohort **platform-wide, with no org context**. It is harmless only while one
  organisation has an open programme. The owner confirmed on 2026-07-28 that the **second-tenant
  meeting happened and looks credible**, which turns a date-parked note (~May/June 2027) into a live
  hazard: two open programmes silently route students into the wrong organisation's fence, and it
  fails with no error. **This should be fixed before tenant #2 has an open programme, not after.**
- **▶ Sprint E (erasure) is hard-blocking** before any real applicant data from a second tenant, and
  no entity can sign a DPA yet — BrightPath's CLBG is unregistered and HalaTuju is org-homeless.
  Both are gates on the tenant, not on engineering, and neither is closed.
- **▶ N3a still owed:** the scopes endpoint and the org/programme switchers, including the
  `FENCED_OR_EXEMPT` classification without which CI fails by design.
- **▶ TD-182:** cause confirmed, fix not written. Cookie-backed storage via `@supabase/ssr`; its own
  commit, its own test, verified on both origins.
- **Owner tasks:** re-capture the Manual screenshots (prose is correct, images are not); review the
  Malay and Tamil first drafts for the new pages.
- **The browser pass was not reported back.** The pages were served for review; no findings were
  returned, so this closes on tests and structural verification rather than on visual sign-off.
