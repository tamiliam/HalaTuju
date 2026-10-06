# Retrospective — the nav/IA arc (N1 → N4), closed

**2026-07-27 to 2026-07-28 · four sprints, two days · roadmap
`docs/plans/2026-07-27-nav-ia-roadmap.md` (now closed)**

Per-sprint retrospectives already exist and are not repeated here:
`…-2026-07-27-nav-registry-n1.md`, `…-2026-07-28-nav-shell-n2.md`,
`…-2026-07-28-hub-split-n3b.md`, `…-2026-07-28-nav-rail-n4.md`.
**This one asks what the four together taught that no single one could.**

---

## What the arc actually delivered

| | Before | After |
|---|---|---|
| Admin nav | a 7-branch ternary over 8 links in `layout.tsx` | a route registry + 5 pure predicates |
| `admin/layout.tsx` | 220 lines | **60** (a guard, nothing else) |
| Copies of `is_super_admin ? 'super' : role` | **17** | 1 |
| Routes that highlighted nothing | 3 | 0 |
| Routes with no menu home | 6 | 0 |
| Largest page component | `administration/page.tsx`, **414 lines, five jobs** | 4 pages + a redirect |
| Sidebar at rest | 240px | **48px**, opens on hover |
| jest | 863 | **968** |
| Reserved slots for the programme layer | 0 | 6 (9 shipped, 3 filled) |

All four are live. Nothing was reverted.

---

## What the arc taught

**1. A preview is a cheaper decision instrument than a document — and it changed how the arc ran.**
N1 and N2 were specified in prose and approved in prose. N4 was approved from an interactive
mock-up, and the difference was not small: the open/close behaviour, the dot-versus-number badge and
the collapsed group boundary were all settled by the owner *looking*, in one message. Writing those
three as prose would have produced text nobody could evaluate, and I would have defaulted them.

The uncomfortable corollary is in **what the preview did not save me from** — see failure 1 below.
A preview settles the questions it *shows*. It says nothing about the questions beside it.

**2. Debt logged with its removing sprint named actually gets removed.**
TD-181 (transitional `chrome` / `hubParent` / `LEGACY_BAR_ORDER`) was written at the moment it was
*created*, in N1, naming N2 as the sprint that would delete it. N2 deleted it. That is one for one,
and it is the only mechanism in this project that has reliably closed its own debt. TD-187 was
logged the same way — with the trigger that ends it ("a menu past ~20 rows") rather than a vague
"revisit later".

Contrast: **TD-182 has now survived three sprints.** It was logged as a symptom with a guess
attached, and the guess was wrong twice. Debt logged as "here is what I think is happening" ages
into misinformation; debt logged as "here is the condition under which this matters" does not.

**3. The Manual currency rule found something false in three of four sprints.**
N3b: a Finance chapter claiming "there is no Payments item in the main menu". N4: *"The links along
the top are your workspace"*, false since N2, plus a self-contradicting FAQ answer. These were not
typos — each was a true sentence that a later sprint quietly falsified.

The rule as originally written ("update the role's chapter in the same commit") is necessary and
insufficient, because it only catches copy that *names* what changed. The version that works is:
grep for the **shape** the copy describes — "along the top", "on the left", "card", "tab" — not for
the noun you are replacing. That is now in `lessons.md` twice, from two different sprints, which is
itself the evidence that the first phrasing was too weak.

**4. Four sprints of console work closed without anyone looking at the console.**
N2, N3b and N4 all shipped on tests, type-checks and structural verification. The blocker is real
and not this arc's fault (TD-182 breaks admin Google sign-in on localhost), and the mitigation —
build a preview — genuinely worked. But a preview shows what I *built*; it cannot show what I broke
in the parts I did not touch. **TD-188 exists to stop that becoming normal.** The honest summary of
this arc's verification is: strong on structure, untested by a human.

---

## What went wrong across the arc

**1. I defaulted the owner's open questions twice — and the second time it was product scope.**
N4's preview asked five questions and got "looks good, proceed". I recorded all five as settled,
two of which were about theming. The owner corrected it: *"Themes should be its own planning. Not
just dark but other likely themes, as well, which may cover UX, etc."*

The correction was substantive, not procedural. My plan treated dark mode as the requirement, when
dark is one theme among several and the expensive part — naming 1,537 colours across 119 files — is
identical whether one theme or six sit on top. Planning around a single output would have picked the
token set that suited that output.

*Why it happened twice:* I had already done the smaller version in N1–N3b, where defaulting
implementation details was correct and cheap. The habit did not distinguish "how" from "what".
*System change:* recorded in `lessons.md` — split the questions before assuming; a HOW question can
take a stated default and be reversed in a line, a WHAT question stays open while you build the part
that does not depend on it.

**2. A reserved key smuggled a decision into code.**
`uiPrefs.ts` shipped with `PREF_KEYS.theme`, which silently asserted that a theme is a *device*
preference — the exact question that was open. Deleted. The general form is now a lesson: a
placeholder for future work encodes an assumption about that work.

**3. Two agents assigned the same technical-debt numbers, and only the close caught it.**
TD-185 and TD-186 exist twice — the sponsor agent's (credit-chain timestamps, sponsor PDPA consent)
and mine (rail scrolling, browser pass). Both branches appended to `docs/technical-debt.md` while
the other was in flight; the merge resolved the *file* cleanly because the additions did not touch
the same lines, and the numbering collision passed straight through. Mine were renumbered to
TD-187/188 during this close, in all seven referencing documents.

*Root cause:* a monotonically increasing ID allocated by reading the file, in a repo where two
agents work in parallel worktrees. Git cannot see that as a conflict.
*System change:* logged as a lesson. The mechanical fix — check `grep -o "TD-1[0-9][0-9]" | sort -u
| tail -1` **at close, not at logging time** — is what caught it here, so the habit is: allocate the
number when you write the row, but re-verify uniqueness at sprint close, when the merges have
landed.

**4. Estimates were wrong in the same direction every time.**
N3b was planned at 10 files and touched 17. N4 was described as ~12 and touched 24. Both undercounts
came from listing the files that hold the *feature* and forgetting the ones that describe it — the
Manual, the FAQ, the i18n triples, the screenshot manifest. The ripple is not incidental to this
project; the currency rule guarantees it. **A web sprint here costs its feature files plus roughly a
third again in copy.**

---

## Numbers

| | N1 | N2 | N3b | N4 |
|---|---|---|---|---|
| jest after | 863 | 890 | 905 | **968** |
| files | 12 | 21 | 17 | 24 |
| decisions logged | 3 | 2 | 2 | 5 |
| lessons logged | 4 | 4 | 3 | 5 |
| browser pass | ✅ | ❌ | ❌ | ❌ |

**Live:** `halatuju-web-00733-zpl`, build `b054af0`.

---

## Carried out of the arc

- **▶ PF-1 is next and is mine** (owner reassigned it 2026-07-28). Brief:
  `docs/plans/2026-07-28-pf1-open-cohort-org-context.md`. Its safety half does not depend on the
  open product question and ships first.
- **▶ Theming** — its own planning exercise across admin, sponsor and student surfaces, after PF-1.
- **⏸ N3a** — parked with a trigger: a second active organisation in production.
- **TD-182** (three sprints old, cause confirmed, unfixed) · **TD-187** (rail cannot scroll) ·
  **TD-188** (no browser pass in three sprints).
- **Owner tasks:** re-capture the Manual screenshots — wrong twice over now, and the manifest says
  to take them with the rail **pinned open**; review the ms/ta drafts.
