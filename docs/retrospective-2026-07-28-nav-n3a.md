# Retrospective — Nav/IA N3a: the breadcrumb switchers

**Date:** 2026-07-28 · **Roadmap:** `docs/plans/2026-07-27-nav-ia-roadmap.md` (reopened for this
one item) · **Migration:** none. **New dependency:** none.

---

## Why this ran at all

The owner looked at the live console beside the design of record and asked why the top bar did not
show organisation then programme.

**It was not a regression, and the artefact was not wrong.** `AppShell.tsx:164` passed
`programmeName={undefined}` — hardcoded — and `Breadcrumb` renders that crumb as
`{programmeName && …}`, so it has been skipped on every render since N2. The organisation crumb did
render, but as static text with nothing to switch to. The Topbar docstring said so plainly:
*"The breadcrumb is static text this sprint… N3 adds the endpoint and turns these into switchers."*

So N2 shipped the shape and left the content for N3a — which I then parked. The owner un-parked it:
*"now that we have built PF-1, can we build n3a?"*

**The trigger I wrote never fired**, and the record says so. One organisation still owns everything.
This was an owner decision, not a condition being met, and conflating the two would have made the
parking mechanism look more predictive than it is.

---

## What Was Built

`GET /api/v1/admin/scholarship/scopes/` → the organisations and programmes a caller may look at,
and a `ScopeSwitcher` in the breadcrumb that renders them.

- **super** sees every active organisation and programme; **everyone else** exactly their own;
  **partner** nothing at all — a referral organisation is attribution, never an access scope, and
  offering a school a scope switcher would assert otherwise; **no organisation** gets empty lists
  rather than a 500, because a reviewer with `owning_organisation` NULL is a real production row.
- Programme codes are `Programme.code` — what PF-1 settled a programme is identified by. One
  vocabulary for "which programme", not two.
- **With one option, a crumb renders as PLAIN TEXT, not a dropdown of one.** A chevron that opens a
  menu with a single entry is a promise the data does not keep. This is production's state today,
  so it is the behaviour most likely to be "simplified" later; it has its own test.

**Numbers:** `pytest` **4968** (full scope) · `jest` **1047** / 68 suites · i18n **4153 × 3** ·
build compiled, 66/66 pages · **11 files**, no migration.

---

## What Went Well

- **The CI gate did its job before I could forget it.** `test_every_admin_endpoint_is_classified`
  fails the build for an unclassified `_AdminBase` subclass, so the fence classification was not
  something I had to remember — it was something the suite demanded. That gate was written in N1
  for exactly this moment.
- **The endpoint cannot widen access, by construction rather than by care.** It derives from the
  same `owning_organisation` the fence uses, so a client ignoring it entirely reaches identical
  data. That is worth more than any test asserting the two agree.
- **The junction lesson from M1 was applied at worktree creation** rather than at first failure, so
  the frontend tests ran immediately.
- **The Manual was checked and needed nothing.** The currency rule is satisfied by looking, not by
  assuming — the breadcrumb is not described in any chapter.

---

## What Went Wrong

**1. A hardcoded `undefined` survived four sprints because nothing made it resolve.**
*Symptom:* the owner found it, not a test.
*Root cause:* `programmeName={undefined}` was a placeholder with no ticket, no test and no failing
condition. The reserved nav slots from the same arc had all three — they render visibly as "soon"
and a test forces the flag off when the page appears — which is why they got filled and this did
not.
*System change:* recorded as a lesson. The distinction is not "placeholders are bad": it is that an
**invisible** placeholder has no mechanism to end it, while a **visible** one does. If a gap must
wait, make it show.

**2. I wrote the client against helper names I had not looked up.**
*Symptom:* `adminRequest` / `AdminApiOptions` — neither exists; the file uses `adminFetch` /
`ApiOptions`.
*Root cause:* pattern-matching from other codebases instead of reading the file I was appending to.
*System change:* caught by `tsc` in seconds, so the cost was trivial — but it is the same shape as
quoting a test count without measuring. Read the file you are extending.

**3. Three suites failed in a full jest run and all passed on a clean re-run.**
The M1 lesson said re-run rather than trust isolation, and that is exactly what happened. Recording
it because it has now occurred in two consecutive sprints on this box, which makes it a property of
the machine rather than an incident.

---

## Design Decisions

Logged in `docs/decisions.md` (2026-07-28):

1. **A single option renders as text, not a dropdown of one.**
2. **The selection is a display preference and is deliberately NOT persisted** — persisting a value
   nothing consumes is a placeholder asserting a future design.

---

## Numbers

| | Before | After |
|---|---|---|
| Breadcrumb crumbs that could render | 1 (org, static) | **2, switchable** |
| Sprints `programmeName={undefined}` survived | 4 | **0** |
| pytest | 4957 | **4968** |
| jest | 1039 | **1047** |
| Migrations | — | **0** |

---

## Carried Forward

- **▶ TD-192 — the switcher moves the breadcrumb and nothing else.** It does not filter any list.
  Deliberate: making it filter means per-endpoint scope parameters re-fenced server-side, which is a
  sprint. Triggered by a second organisation or programme going active.
- **▶ The nav/IA roadmap is now genuinely complete** — N1, N2, N3a, N3b, N4 all shipped. Nothing is
  owed on it.
- **▶ Themes next**, by the owner's sequencing, with its own planning exercise across admin,
  sponsor and student surfaces.
- **TD-182** unfixed; **TD-188** — six consecutive sprints have now closed without a browser pass,
  and the next one is a visual sprint. Fixing TD-182 first is worth more than working around it a
  seventh time.
