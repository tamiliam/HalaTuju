# The apply page's copy belongs to the gift — 2026-09-09

**Shipped, not deployed** (the owner gates it). Worktree `.worktrees/apply-copy`, branch
`feat/apply-copy`, base `origin/main` at `728a1ace`. api + web, 22 files.
**⚠ MIGRATION `scholarship/0154` — ADDITIVE, ONE COLUMN, NOT YET APPLIED. MIGRATE-FIRST.**

Gates, all run INSIDE the worktree: pytest **6106** (+25) · jest **1931** (+12) · tsc **24**
(baseline, TD-221) · lint **0 Errors** · i18n **4944 × 3** (+25) · `next build` exit 0 ·
`makemigrations --check` clean. **Three bite-checks landed**, each injection verified first and
each restored by writing the original bytes back.

---

## What the owner asked for, and what the sprint actually found

The ask was narrow and they drew the line themselves: *"I am only looking at one page: the page
that the apply link points to, and nothing else."* One card — heading, intro, four bullets.

Reading the code to plan it turned up a **second defect nobody had reported**, and it is the one
that would have cost a real applicant something.

### ⚠⚠ THE GATE ANSWERED PLATFORM-WIDE, NOT PER GIFT

`getScholarshipIntake()` took no arguments. It asked *"is anything open ANYWHERE?"*, never *"is
THIS gift open?"* — so the apply page's own open/closed bounce was a platform answer on a
per-gift page.

Harmless while one gift runs. The day Sabah opens beside a closed BrightPath:

| | A student on an old BrightPath poster gets |
|---|---|
| Today (nothing open) | bounced to `/scholarship`. Correct. |
| **Sabah open, BrightPath closed** | the WHOLE BrightPath form renders → they fill it in → `resolve_open_cohort('brightpath-flagship')` returns `None` at submit → **refused after all that typing** |

That is PF-1's *"right refusal, wrong moment"* in a new costume — the exact fault the choices
screen was built to cure, still live on the per-gift-closed path. It was folded in because the
fix is **the same one line the copy needed anyway**: send the gift's code with the question.

---

## The rulings, and why each one is the way it is

### 1. Blank means the platform default

An unconfigured gift renders today's exact wording. **BrightPath therefore needs zero data
entry and its page is byte-identical after this ships.** The stored map holds only what an
organisation wrote — never a copied default, which rots the day the platform's own wording moves
(the `OrganisationConfiguration` rule).

### 2. ⚠ ALL-OR-NOTHING PER LANGUAGE — the load-bearing rule

Title + intro + at least one bullet, or nothing at all. Per-**field** fallback would render
*"Apply for B40 Education Assistance"* — the platform's heading — above Sabah's own bullets: one
gift's title over another gift's criteria, with nothing failing anywhere. Refused server-side
(`apply_copy.normalise` → `incomplete`); the tab only has to explain it.

### 3. ⚠ ms/ta FALL BACK TO THE GIFT'S OWN ENGLISH, NEVER THE PLATFORM'S MALAY

This **deliberately differs from `branding.resolveLang`**, which falls back per locale to the
platform — and the difference is the whole point. Falling back to the platform's *name* is
harmless; falling back to the platform's *criteria* would tell a Malay-reading Sabah applicant
they must be B40 with five A's. **A wrong-language truth beats a right-language falsehood.** The
reason is written at the helper, because the next person will otherwise "make it consistent".

### 4. ⚠ THE PLATFORM DEFAULT STAYS IN THE MESSAGE FILES

The first draft of the plan had the SERVER resolve it. That would have put seven strings × three
languages into Python **as well as** the message files — the `_SUBJECT_BM` ↔ `subjects.ts` drift
trap, recorded three times in `lessons.md`. Corrected at sprint-start after checking the house
pattern: the branding endpoint serves `programme_name` as a per-locale map and the browser
resolves it. Copied that. **Server answers WHICH GIFT; browser answers which locale and whether
to fall back.** A happy consequence: **no new student-facing strings in any language**, so no
Tamil translation debt on the student side.

### 5. ⚠ THE ADVERTISED BAR IS DELIBERATELY STRICTER THAN THE ENGINE — DO NOT "FIX" IT

Sprint 8 (2026-05-24) ruled that the public page advertises 5 A's / PNGK 3.0 while
`shortlisting.evaluate()` runs 4 A− / PNGK 2.9, to catch near-misses. The owner reaffirmed it on
2026-09-09. **Anything that derives this copy from a round's thresholds reverses a standing
ruling.** Said at the top of `apply_copy.py`, at the top of `ApplyCopyTab.tsx`, and in the plan.

### 6. "Who can apply" stays a platform string

Generic, works for any gift, and a fourth box on the editor would be friction with no gain.

---

## ⚠⚠ A STANDING DECISION THIS SPRINT COULD HAVE BREACHED — found at sprint-start

`decisions.md`, **2026-05-25**: the B40 public copy makes **no mention of Indian descent or
ethnicity anywhere**, because MyNadi Foundation's **Section 44(6)** tax-exempt status requires
the programme not to discriminate on the basis of race.

**That decision was written when the copy was ours. This sprint takes it out of our hands** — it
hands an org_admin a free-text box rendering on that exact page.

Reading `docs/decisions.md` as sprint-start requires is the only reason this surfaced. It is not
findable from the code.

**Owner ruling, option A: WARN, DO NOT REFUSE.** Rejected: a platform-wide refusal (safest today,
wrong for tenant three — ethnicity-scoped scholarships are ordinary and lawful in Malaysia, and
the constraint follows MyNadi's funding rather than the platform) and a per-organisation refusal
(correct in principle, a new stored setting bought for a tenant that does not exist).

**⚠ THE WORD LIST SHIPS ANYWAY, EVEN THOUGH NOTHING REFUSES.** The detector drives the warning;
only the ACTION is soft. Tightening later is one branch rather than a new feature, and the words
are written down instead of re-derived. It reuses `email_templates.banned_phrases`, the same
matcher behind the "tax deductible" refusal.

**⚠ A LANGUAGE IS NOT AN ETHNICITY.** "Bahasa Melayu" and "Bahasa Tamil" are SUBJECT names a real
criterion will mention (*"a credit in Bahasa Melayu"*), so those phrases are stripped before the
scan. Without it the guard would cry wolf on the most ordinary bullet anybody writes — and a
warning that fires on everything is a warning nobody reads. Pinned by a test.

---

## Two guards fired during the gates, and both were right

1. **`brand-guard`** refused the warning copy: it named **BrightPath** in a message VALUE. The
   guard exists so tenant-facing copy does not hardcode the platform's brand — and it caught
   something worse than a style breach. The sentence was *factually wrong for a second tenant*:
   the s44(6) constraint is the FUNDER's, not every organisation's. Reworded generically in all
   three languages. **The guard found a correctness bug while enforcing a style rule.**
2. **The tab-list snapshot** pinned *"exactly the three tabs"*. A fourth is what the owner asked
   for, so the test was updated deliberately — with the reason written into it, not silently
   renumbered.

Four **exact-payload** snapshots in `test_open_cohort_scope.py` also failed, correctly: PF-1
pins the whole intake body, so a new key breaks them by design. Each gained `apply_copy` and
nothing else.

---

## What must not be tidied

- **The advertised bar is not derived from the Rules tab.** §5.
- **`resolve_programme_by_code` is the ONE home for code → gift.** It was written inline inside
  `resolve_open_cohort`, so only the open-round path understood a retired code. Two copies and a
  renamed gift advertises correctly in one place and wrongly in the other.
- **It answers about ANY gift, active or not, open or closed.** Narrowing is the caller's job:
  `resolve_open_cohort` still applies `is_active`, and the intake endpoint needs a closed gift to
  stay identifiable so it can answer "closed" about the RIGHT one.
- **An unknown code reads closed, never 404.** The endpoint is public and unauthenticated;
  the difference would let anyone enumerate the platform's tenants.
- **The admin row serves the stored map VERBATIM**, not `for_wire`. The tab is an EDITOR: a blank
  Malay box must render blank, or the first save silently promotes English into a field nobody
  typed.
- **Every sub-component in `ApplyCopyTab` is at MODULE scope** — the 2026-07-21 invite-form
  remount defect, repeated 2026-09-03.
- **Blank is a real answer, never a copied default.**

## Honest gaps

- **Not click-tested in a browser** (TD-182 still breaks admin Google sign-in on localhost).
  The tab has rendered-adjacent coverage through its pure helpers and the endpoint tests, but
  nobody has typed into it.
- **ms and ta are first drafts** for the 25 new admin strings.
- The **landing page** and **sign-in prompt** carry the same platform-wide B40 copy. Same class,
  different pages, deliberately out of scope — still unlogged as work.
- The **eleven officer-facing "B40" strings** are their own planned sprint
  (`docs/plans/2026-09-09-officer-income-vocabulary.md`).
