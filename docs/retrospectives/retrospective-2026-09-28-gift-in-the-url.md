# Retrospective — the URL carries the gift (TD-296, with TD-298)

**Date:** 2026-09-28 · **Sprint:** TD-296, the owner's pick · **Scope:** the five Programme-scope
list pages (Overview, Applications, Configuration, Payments, Spending), the rail, the gift cards,
the run page's way back — and TD-298's stale replies on Payments, Spending and Applications.

The morning's sprint made the console remember which gift you are in while you move around it. It
could not survive a pasted link: `/admin/payments` in a colleague's chat opened with no gift, and by
that sprint's own ruling either redirected them to the Programmes page or asked. A reload did the
same. The record pages were already safe — a run and an application name their own gift from the
server payload — so the gap was the lists.

---

## What Was Built

| | before | after |
|---|---|---|
| `/admin/payments?programme=<code>` pasted, org_admin | redirected to Programmes | **opens in that gift** |
| …the same link on a cold load (list arrives later) | redirected | **waits, then opens in it** — nothing fetched first |
| a code the list does not know | — | **selects nothing** → redirect / ask / all gifts, as with no code |
| …on a single-gift tenant, money page | — | **still no gift** (never "the only one") |
| a DRAFT gift chosen, money page | its (empty) runs + a New-run button the server 404s | **asked, live gifts only**, every role |
| switching gift in the crumb | nothing in the URL | **`router.replace`**, no history entry |
| rail Programme rows / gift-card doors | bare paths | **carry the code** |
| run page → "Payments" | bare | **the run's gift** |
| applicant page → "Applications" | bare | **bare, by decision** (F2) |
| a slow reply for the gift you left (TD-298) | could overwrite the new gift's list | **dropped** |
| pytest | 7,117 / 3 skipped | **7,117 / 3 skipped** (no api change) |
| jest | 3,021 / 168 suites | **3,069 / 174** |
| First-load JS | median 256, worst 339 | **256 / 339** — with no headroom (TD-300) |

1. **`src/lib/useGiftInUrl.ts`** (new) — read once on mount into `select`; after mount, a change of
   `chosen` rewrites the query with `router.replace(…, { scroll: false })`. Returns `ready`: the
   address bar has been read and, if it named a gift, the scopes list has settled.
2. **`src/lib/giftHref.ts`** (new, no React) — `withGift`, `giftIn`, `withGiftHrefs`.
3. **`useGiftGate`** calls the hook first and does not decide until it is ready; adds
   `unrecognised` (new on the scope) and the draft rule.
4. **Pages.** Payments and Spending get the hook through the gate; Overview, Applications and
   Configuration call it. Overview and Applications do not fetch until it is ready.
5. **Rail** (`AppShell`): `withGiftHrefs(…, pinned ? '' : chosen)`. **Gift cards**
   (`GiftProgrammes`): both pushes carry the code. **Run page**: the way back names the run's gift.
6. **TD-298.** A `current` flag in the effect cleanup on Payments and Applications; a ticket
   (`useRef` counter) on Spending, taken by every read including the correction's re-read.

---

## Design Decisions

**The design in five sentences.** `?programme=` is read ONCE, on mount, into the scope's `select`,
so a link outranks an earlier pick and then meets the scope's existing guard — a code not in the
list resolves to nothing, never to the only gift. After mount the crumb is the control and the
address bar follows it with `router.replace`, so Back leaves the page rather than switching gifts.
**The query is sequenced before the gate by making the gate call the hook and answer `wait` until
it reports `ready`** — the read happens in the hook's mount effect together with a state flip, both
batched into one render, and when the URL named a gift `ready` also waits for the scopes list to
settle, so the redirect cannot fire on the render that was about to apply the link's gift. Every
link that moves between list pages (rail, gift cards, the run's way back) carries the code, except
the two that would narrow the all-gifts Applications list. Nothing is stored and nothing is sent
that the endpoints did not already re-fence.

**(c) — a draft in a Payments link: ASKED, for every role.** The F1 rule already says a draft
cannot be paid from (the server 404s a run against one, and the question offers live gifts only).
Opening the draft would draw a New-run button that can only fail; redirecting a door role would
land it on the Programmes page beside the draft's own card, one click from bouncing back. So with a
live gift to offer, a chosen draft gets the box. A tenant whose only gift is a draft still opens it,
as before. This also closes the same hole for a draft chosen through the crumb, which was reachable
before this sprint.

**(9) — the way back to every gift on Applications.** With no query and no earlier choice the list
is all gifts (tested). But the crumb has no "All gifts" entry, and nothing was invented. Before this
sprint a reload was the accidental escape; now the address bar remembers, so it is not. The only way
back is to load the bare `/admin/scholarship` fresh. Recorded as **TD-302** for the owner.

**Why the applicant page's way back stays bare (a deviation from the brief).** The brief asked for
it to carry the record's gift. Applications is the all-gifts list — a reviewer's only door — and a
link naming the applicant's gift would narrow it one click later: the defect the review removed as
F2, by another road. A bare link returns the person's OWN previous choice (all gifts, or the gift
they had chosen). Payments has no all-gifts mode, so its way back does carry the run's gift. The same
reasoning keeps the rail bare while a record is pinned. A test pins each choice, so a reversal is
one deliberate edit.

**Why only on a CHANGE after mount.** Writing whenever the URL lacked the gift would have rewritten
every single-gift page on arrival — and broken the 2026-09-28 tests that assert no `replace` on a
one-gift tenant, for a URL that told no lie. Consequence, accepted: on a cold load of a single-gift
tenant the gift is written once, when the list arrives.

**Why a new `unrecognised` flag.** `ambiguous` counts live gifts, so on a single-gift tenant a typo'd
link opened the only gift's money under a crumb that asked "which gift?" with no switch to answer
it. The flag is true only when the list is non-empty: an empty list is a failed fetch, which keeps
degrading as review F5 accepted.

---

## What Went Well

- **Seventeen of nineteen bite designs went red first time**, and NO-CRY-WOLF (a comment only)
  stayed green across 224 tests.
- **The sequencing needed no timing tricks.** Making the gate call the hook turned "read before the
  gate decides" into one boolean, and bite 6 (the gate ignoring it) turned nine tests red.
- **The sprint's own review found a real defect** (below) before the adversarial reviewer's turn.

---

## What Went Wrong

1. **Four TD-298 tests were SILENT.** *What:* all four out-of-order tests stayed green with their
   staleness guard deleted. *Why:* each resolved the stale promise and waited 20 ms with a plain
   timeout, outside `act`; nothing forced React to render the late update before the "absent"
   assertion looked. *Prevention:* the stale reply is resolved inside `act`; all four bites are now
   red. Recorded in `lessons.md`.
2. **The correction's ticket was taken too late** (found by `/code-review`, 4b). *What:* Spending
   took its ticket after the save came back, so a gift switch DURING the save let the correction
   re-read the old gift, outrank the new gift's read, and leave the page loading for ever — TD-298
   from the other direction. *Why:* the ticket guarded the reply, not the operation. *Fix:* taken
   before the save; the re-read is skipped if the person has moved on, and clears `loading` when it
   does land. A test and bite 4e pin it.
3. **The bundle median tipped (256 → 257) on the first build.** *What:* the run page imported
   `withGift`; `/admin/payments/[id]` went 256 → 257 and, with exactly 44 of 87 routes at or under
   256, took the median with it. *Why:* no headroom at all — six list routes also grew ~0.5 kB each.
   *Fix:* the run page spells its one link out. *Prevention:* **TD-300**, and a lesson: count the
   routes sitting at a median budget, not just whether it reads "ok".
4. **Three existing test files had no router mock** (Applications, Overview, Configuration). The
   pages now call `useRouter`; each file gained a one-line mock and no expectation changed.

---

## Existing expectations that changed (k) — for the lead

- `payments/page.test.tsx` ⚠ CANNOT LOOP (a 2026-09-28 gate test): the gift card's push is now
  `/admin/programme/overview?programme=bpb-sabah-2026`. The loop assertion (no `replace`) is unchanged.
- `payments/[id]/page.gift.test.tsx` "the way back to the list" (2026-09-28): its href now names the
  run's gift, and its source guard follows the new spelling. A new case pins a gift-less run's bare link.
- `GiftProgrammes.test.tsx` (2026-09-08/15): the two door pushes carry `?programme=test3`.

Every other 2026-09-28 gate test passes unedited.

---

## Bite-checks (the final run, against the bytes that ship; original bytes restored in a `finally`, verified by SHA-256; needles unique)

| | fault | result |
|---|---|---|
| 1 | the mount read dropped | red (15) |
| 2a | the scope lets an unknown code select | red (5) |
| 2b | `unrecognised` never set | red (2) |
| 3 | `push` instead of `replace` | red (6) |
| 4a | Payments: no staleness flag | **silent → test fixed → red (1)** |
| 4b | Spending: no ticket on load | **silent → test fixed → red (1)** |
| 4c | Spending: no ticket on the correction's re-read | **silent → test fixed → red (1)** |
| 4d | Applications: no staleness flag | **silent → test fixed → red (1)** |
| 4e | Spending: ticket after the save (the review defect) | red (1) |
| 5 | NO-CRY-WOLF: comment only | **green** (224) |
| 6 | the gate decides before the URL is read | red (9) |
| 7 | a draft counts as payable | red (3) |
| 8 | the rail names a PINNED gift | red (1) |
| 9 | the query written on mount too | red (4) |
| 10 | Applications fetches before the URL is read | red (3) |
| 11 | every rail row carries the gift | red (2) |
| 12 | the run's way back bare again | red (1) |
| 13 | a gift card pushes without the gift | red (3) |
| 14 | the Overview reads before the URL | red (2) |

---

## Numbers

- pytest **7,117 / 3 skipped → 7,117 / 3 skipped** (full run, `-n auto`, `halatuju_api/`).
- jest **3,021 / 168 → 3,069 / 174** (`npm run gates`: tsc, lint, i18n, jest).
- `manage.py check` clean; `makemigrations --check` no changes; no migration.
- `npm run bundle-budget` (builds): median **256 kB**, worst **339 kB**, before and after; six list
  routes +1 kB each in the printed figures; 44 of 87 routes at or under 256 (TD-300).
- `code_health.py` (read-only): 0 fails, 6 warnings (all pre-existing kinds).
- Ledgered files: `GiftProgrammes.tsx` 602 → 603 (allowance 622); `navigation.ts` 672 and
  `view.tsx` 1,342 untouched. No ledger gained a member; no budget moved; no new `eslint-disable`.

---

## After the adversarial review — verdict "ship after fixes"

| | finding | answer |
|---|---|---|
| F1 | HIGH — a save made mid-switch took the LIST ticket; the new gift's read was dropped, a failed save re-read nothing, and the page sat loading with the OLD gift's figures under the NEW crumb. The save also sent the new gift's code for the old table's row | **fixed:** saves share no token with list reads; the save carries `dataGift` (the gift of the table on screen, set in the same update as the table); success and failure both re-read the CURRENT gift through `load` (via a ref, so a stale closure cannot re-read the gift you left) |
| F2 | MEDIUM — an unrecognised query stayed stored as the pick; on a single-gift tenant every later plain money visit redirected and the rail hid the rows | **fixed:** the code is held only while its page is open; on unmount a pick the list still does not recognise is cleared. A real pick made meanwhile survives (a neighbour test pins it) |
| F3 | low — failed scopes fetch + a link naming a gift: the page opens with no gift and the server picks the only live one while the URL names another | **recorded as TD-303** (refuse the New-run button when the address names an unconfirmed gift) |
| F4 | low — the docstring said a page is "left exactly as it arrived"; a real fresh single-gift load has the gift written in once | **docstring corrected; a test pins the write (once, `replace`, no history entry)** |
| F5 | low — the "cold load" tests passed both gifts with the list unsettled, which no browser produces | **all four now start from an EMPTY list**; the `giftIn(search) === chosen` guard can now fail (bite F5: red in 4) |
| F6 | fine as recorded | — |

**Why the reviewer's first remedy option was dropped for F1.** A first cut also REFUSED a save while
`dataGift !== programme`. Its bite was silent: with `dataGift` carried, the save names the right
gift anyway, so the refusal protected nothing a test could see. It was deleted rather than kept as
an untested belt.

**What went wrong, again.** The first F1 fix's bite "save takes the list ticket again" was SILENT:
the unconditional re-read after the save healed the page, so every test passed. It does not heal
while a save hangs — the new gift's reply is dropped until the save returns. A test with a save that
never answers was written; the bite is now red. The lesson is in `lessons.md`.

**Bites, review round** (the final run, against the shipping bytes; SHA-256-verified restores):
F1a save carries the crumb's gift — red (1) · F1b save takes the list ticket — **silent → test
written → red (1)** · F1c failure does not re-read — red (3) · F1d re-read through the stale closure
— red (1) · F2a the code never forgotten — red (2) · F2b every pick forgotten — red (1) · F5 a link
naming the gift rewritten anyway — red (4) · F4 fresh single-gift load never written — red (1) ·
NO-CRY-WOLF comment only — **green** (224).

**Numbers after the review:** jest **3,076 / 174** · pytest **7,117 / 3 skipped** (api untouched) ·
bundle median **256** / worst **339** (44 of 87 routes at or under 256 — TD-300 unchanged) ·
`code_health` 0 fails.

## What Is Still Open

- **TD-303** — a failed scopes fetch with a link naming a gift (review F3).
- **TD-300** — the first-load median has no headroom. Before the next web sprint.
- **TD-301** — the Overview has TD-298's shape (not in this brief).
- **TD-302** — owner: an "All gifts" entry in the crumb, now that a reload remembers.
- TD-299, TD-297 — unchanged.
