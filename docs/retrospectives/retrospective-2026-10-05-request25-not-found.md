# Retrospective — request #25: "missing pages" (2026-10-05)

Web-only sprint. Lane: sprint (analysis #61, approved). Built locally, **not pushed, not deployed**
— the owner gates the push.

---

## 1. What was actually broken was not what was reported

The request was about missing pages. There were two different situations wearing the same coat, and
only one of them was broken.

* **An address that matches no route** (`/admin/nonsense`) already rendered the root
  `app/not-found.tsx` and already answered 404. Not touched, and deliberately not "fixed".
* **An address that matches a route whose RECORD is gone** (`/admin/payments/999999`) answered 200,
  mounted the page, failed its GET, called `setError(…)` — and an **earlier**
  `if (!run) return <Loading/>` fired, so the message was set and the only place it is drawn sat
  further down the same file. **The screen spun on "Loading…" for ever.** No error, no empty state,
  no way out but the browser's Back button.

So the deliverable was a state machine, not a page.

### The part of the brief that was wrong, and how it was found

The brief named **five** screens with the spinner bug, at five exact line numbers. Re-verifying each
at HEAD `9c0fe4a3` before editing, **only one of the five actually had it**:

| Screen | Line | What it really did |
|---|---|---|
| `admin/payments/[id]/page.tsx` | 98 | **SPUN.** No `error` guard before `if (!run)`; `error` is only drawn at line 193. |
| `admin/scholarship/[id]/view.tsx` | 788 | Already `if (error && !app)` **above** the loading line. |
| `admin/sponsors/[id]/page.tsx` | 150 | Already `if (error)` above `if (!detail)`. |
| `admin/students/[id]/page.tsx` | 32 | Already `if (error)` above `if (!data)`. |
| `admin/organisation/reviewers/[id]/page.tsx` | 119 | Already `if (error)` above `if (!detail)`. |

The brief also said `admin/contracts/[id]/page.tsx` "uses `notFound()`". It does not — it holds a
local `const [notFound, setNotFound] = useState(false)`. **Nothing in the repo called Next's
`notFound()` before this sprint.**

**The lesson is not "the brief was sloppy".** Four of those five were still wrong, just not in the
way reported: each said something different on a failed load (`admin.scholarship.loadFailed`,
`admin.sponsors.detail.loadFailed`, `admin.reviewers.detail.loadFailed`,
`apiErrors.studentNotFound`), two of those sentences named a cause the rejection does not carry, and
the order of the two early returns was invisible at a glance in every one of them. Converging all
five on one shared state is the fix whether or not a given screen happened to be spinning — and the
one that WAS spinning is now the one with a test that fails if the order goes back.

The honest reading: the five had been written by four different people-moments in four different
orders, and the only reason four of them were right is that somebody happened to put the lines in
the lucky order. That is the defect. The spinner was its loudest symptom.

---

## 2. The design was forced by two line budgets

`halatuju-web/code-standards.json` holds an `oversize_files` ledger that **may only shrink**, read by
`src/lib/__tests__/codeStandards.test.ts` inside the Cloud Build deploy gate.

* `src/app/admin/scholarship/[id]/view.tsx` is listed at **1338** with `FILE_GROWTH_ALLOWANCE = 20`,
  so its ceiling is **1358**. It stood at **1354**: four lines.
* `src/app/admin/sponsors/[id]/page.tsx` stood at **597** and is **not** listed, so it had three
  lines before it would have had to join a ledger that cannot gain a member.

That is why the answer is a shared component with a **one-line call site** and not a block of markup
per screen:

```tsx
if (!app) return <RecordState loading={!error} />
```

One line replacing two, plus one import line — a net zero on the file with four lines of room, and
`sponsors/[id]` at 598 of 600. The budget did not merely permit the good design; it refused the bad
one. A per-screen block would have been three or four lines each and would have pushed one file into
a ledger and the other past its allowance, and the deploy gate would have said so.

Written into `RecordState.tsx` itself: **if a state ever needs more markup it goes in the component,
never back into a call site.**

---

## 3. The wording is a correctness rule, and it is tested as one

The admin organisation fence answers **404, never 403**, for a record belonging to another
organisation — precisely so that the record's existence is never leaked (docs/decisions.md, the
org-fence rule and "an unknown programme reads CLOSED, never 404").

Therefore the copy must claim nothing about why:

> **"We could not find that."**

* **Never "this record does not exist"** — that is simply *false* for a cross-org record, which
  exists.
* **Never "you do not have access"** — that *leaks* that it exists.

Both are the natural improvement to make, which is why this is a test and not a comment:
`src/components/admin/__tests__/RecordState.test.tsx` pins the English sentence verbatim and refuses
a forbidden phrase in **all three locales**, because the leak can be introduced in Malay or Tamil
alone where fewer readers would catch it.

Two per-screen sentences that named the wrong cause were **deleted**, not left orphaned:
`admin.reviewers.detail.loadFailed` and `admin.sponsors.detail.loadFailed` (5402 → 5400 keys). Those
two pages now hold a `loadFailed` **boolean**, because a string nobody renders is copy pretending to
be a message. `apiErrors.studentNotFound` survives — `lib/error-i18n.ts` still maps a server string
to it — but the students screen no longer claims it on a failed GET.

---

## 4. The gap that was not in the original report: `adminFetch` threw a bare Error

`src/lib/admin-api/client.ts` has two helpers side by side:

* `adminMutate` (the **write** path) attached `err.status` and `err.code` from the day it was
  written, because a refused write has to be told apart from a broken one;
* `adminFetch` (the **read** path) threw `new Error(message)` with **neither**.

Every one of these five screens loads by GET. So a 404 — a record that is gone, or one the fence
refuses to admit exists — arrived at the caller *indistinguishable from a dropped connection*. A
screen could only ever say "something failed", which is a fair part of why five of them said four
different things. `adminFetch` now attaches `status` and `code` in exactly `adminMutate`'s shape,
deliberately **without** `body` (that carries refusal detail a GET does not have, and a second shape
is how two helpers begin to disagree).

It is tested through `getPartnerStudent`, not by importing `adminFetch` — the helper is private to
its folder by decision, and its own docblock says a test reaching for it is reaching past the seam.

---

## 5. The surprise: the console's 404 costs the 404 STATUS

`app/admin/[...notFound]/page.tsx` + `app/admin/not-found.tsx` do what was asked — a mistyped
console address now lands on the console's own 404, inside the shell, with a way back **derived**
from the route registry (`adminLanding(role)`) rather than the public site's "Back to home".

**But `/admin/<nonsense>` now answers HTTP 200 where it used to answer 404.** In Next 14.2 only the
**root** `not-found.tsx` sets the response status; a nested boundary renders the right page and
leaves the status alone.

This was **measured, not assumed.** Two throwaway probe routes were built and served with
`next start`: one under a server-only layout chain, one under a `'use client'` layout. **Both
answered 200**, while `/nonsense` — which reaches the root boundary — answered 404. So it is the
router, not our client layout and not the catch-all. (The first attempt at this probe proved
nothing: the folder was named `__nfprobe`, and Next ignores a folder starting with `_`, so both URLs
fell through to the root 404 and looked like a clean result. Worth remembering.)

The trade was taken deliberately and written up in docs/decisions.md and in the catch-all's own
docblock, with a note to **re-test on a Next upgrade**: the addresses that lost the status are all
behind the admin auth gate and are not indexed, and what was gained is an officer not being ejected
from the console they are signed in to. If this had not been checked, the sprint would have shipped
a silent status regression while every gate was green.

`navigation.test.ts` had to learn about the catch-all: its two route-drift tests cannot read one
honestly (no registry row, and no non-dynamic ancestor to hang off). The exclusion is a **rule** —
a `[...x]` segment — and it is paid for by a new test that fails if the sink is deleted, renamed, or
joined by a second one.

---

## 6. Malay and Tamil are unreviewed first drafts

Four new `errors.*` keys per locale. **The Malay and Tamil are my own first drafts and have not been
reviewed by the owner or anyone else. Do not treat them as approved copy.**

The Tamil follows the project style guide's sandhi rules deliberately — dative `கு` + `த`
(`கன்சோலுக்குத் திரும்பு`, `பட்டியலுக்குத் திரும்பி`), accusative `ஐ` + `ச`
(`முகவரியைச் சரிபார்க்கவும்`), verbal participle in `இ` + `ச` (`திரும்பிச் செல்லவும்`), and
infinitive + `இல்லை` joined (`முடியவில்லை`) — and it reuses the vocabulary already in the catalogue
(`கன்சோல்`, `ஆதரவாளர் போர்ட்டல்`) rather than minting new terms. That makes it *consistent*; it does
not make it *reviewed*.

---

## 7. Gates

| Gate | Result |
|---|---|
| `npx tsc --noEmit` | clean, no output |
| `npx jest` | **3372 passed / 3372, 218 suites, 0 failures** (baseline 3328, so +44) |
| `npx next build` | green, cold (`.next` moved aside first) |
| `npm run bundle-budget` | **ok** — 88 routes, median **227.776 kB** against the 229 budget, worst 309.75 kB, shared 87.3 kB |
| `node scripts/check-i18n.js` | ALL PASSED, 0 warnings, 5400 keys per locale |
| `src/messages/__tests__/namespaces-i18n.test.ts` | green (inside the jest run) |
| `npx next lint` | no errors; only the pre-existing warnings |

The first cold build died on `ENOENT: rename .next/export/500.html` — a Windows file-move flake, not
a code fault; the immediate retry built cleanly and every figure above comes from that build.

---

## 8. What to carry forward

1. **Re-verify a brief's line numbers before editing.** Four of five claims did not hold. The work
   was still right; the reasons in the commit message would have been wrong.
2. **A wrong guess about a *symptom* can still point at a real *defect*.** Four screens were
   accidentally correct. "Accidentally correct" is a defect with a delay on it.
3. **A line budget is a design tool.** Two tight files made the shared component the only option
   that fits, and that is the design anyone would have wanted anyway.
4. **Check the HTTP status, not just the screen.** Nothing in jest, tsc, lint, `next build` or the
   bundle budget would have noticed `/admin/*` going from 404 to 200. It took `next start` and
   `curl`.
5. **Do not name a probe folder with a leading underscore.** Next ignores it, and the probe then
   "passes" by answering from somewhere else entirely.
