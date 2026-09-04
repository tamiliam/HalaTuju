# Sabah self-serve — roadmap · ✅ **COMPLETE 2026-09-04**

**Every sprint has shipped and deployed: S1 ✅ → S2 ✅ → S0 (the shape) ✅ → S-ASSIGN ✅.**
The acceptance test below is met **in the product**: an org_admin can create a gift, configure its
rules and what it asks for, open an intake year, accept a benefactor into it, scope a reviewer and a
source to it, and have the credit recorded — with no engineer touching the database.

**⚠ WHAT IS STILL OWED IS NOT ENGINEERING.** The standing owner gate at the foot of this file
remains in force: **record nothing for Sabah until the programme is inked AND the money has changed
hands**, with a bank reference for `external_reference`. No sprint here created a Sabah row.

**⚠ ONE THING BLOCKS A SABAH STUDENT SIGNING: TD-229**, now RULED (2026-09-04, decisions.md) — the
agreement template is **per gift** — but not built. `BURSARY_AGREEMENT_ENABLED` is OFF, so nothing
signs anything today. Also open: **TD-230** (a source's gift reaches no student yet — the apply
form's referring-school list is still a hard-coded constant) and the Sabah **apply link**
(`/scholarship/apply?p=<code>`, PF-1), which needs publicising when the intake opens.

**Drafted 2026-09-02** per `Settings/_workflows/implementation-planning.md`, on the owner's word that
**BrightPath Sabah is ready to launch — no longer a possibility.**

**The requirement, in the owner's words:**

> *"I should simply say, Suresh, as org admin you may start the new programme, and you can do
> everything on your own without any work from me."*

That is the acceptance test for the whole roadmap. Not "Sabah runs" — **Sabah runs without an
engineer touching the database.**

---

## The pleasant half — what already works

Verified in code on 2026-09-02, not read off the July notes:

| | Evidence |
|---|---|
| A programme owns its own money | P2a: `sponsor_balance(sponsor, programme)`, programme required, no default |
| A payment run pays ONE gift | P2b: `create_run(org, programme, …)` positional and required |
| A sponsor is accepted per gift | P3: `SponsorProgrammeMembership`, fail-closed pool |
| An off-platform gift can be recorded and signed | P4a/P4b: `Donation.source` + `external_reference`, maker→[finance]→approver, **and the screen exists** on the sponsor detail page |
| Applications route to the right programme | PF-1: `resolve_open_cohort` **raises** on ambiguity; the apply link carries `Programme.code` |
| "Which application is this request about" | **M1 shipped** — `_current_application` refuses rather than guessing "latest wins" across 13 endpoints |
| What a programme asks for | Layer 0: per-programme, `org_admin` writes it, 404-fenced on the organisation |
| Colours | Layer 1: per-organisation, `org_admin` writes it |

**The money model and the routing are sound.** Nothing in this roadmap re-opens them.

## The gap — five things, and one of them breaks a LIVE system

| # | What | Today | Who can do it |
|---|---|---|---|
| 1 | Create the Programme | no endpoint, no screen, **not in Django admin either** (`scholarship` registers no models) | engineer, by SQL |
| 2 | Create + open the intake Year | same — and it carries **13 rule and funding fields** | engineer, by SQL |
| 3 | Accept the benefactor into Sabah | `sync_account_membership` hard-codes `DEFAULT_PROGRAMME_CODE = 'brightpath-flagship'`; no endpoint writes any other | engineer, by SQL |
| 4 | Bind a reviewer to one programme | **no field exists** — P1b's third, never started | nobody |
| 5 | Create a payment run | FE `createPaymentRun` sends no `programme_id` | **breaks — see below** |

**#3 blocks the money.** `record_admin_credit` refuses `sponsor_not_in_programme`, so the RM100,000
cannot be recorded until the benefactor holds a Sabah membership.

### ⚠ #5 is a regression in the LIVE payout path, not a Sabah feature

`views_admin.py` (create-run): omitted `programme_id` + the org runs **exactly one** active
programme → that one is used; **more than one → 400 `programme_required`, never a silent pick.**

The front end never sends it, and **nothing in the front end handles that error code** — the credit
form and the Layer 0 config tab both do; the payments screen does not.

**So the day a second ACTIVE programme row exists, BrightPath's own monthly run stops working from
the screen, with an unexplained failure.** The API is right; the screen is behind it.

> **This is why S1 comes first and is not negotiable.** A workaround exists — create Sabah with
> `is_active=False`, since the query filters on it — but that only moves the moment, and it makes
> the launch depend on remembering a flag.

---

## What is NOT in scope, and why

- **M2–M4 (a student holding two applications).** Not needed for this launch: the flagship's 2026
  intake is **closed** (verified live 2026-09-02, `scholarship/intake/` → `{"open":false}`) and
  reopens ~May/June 2027, so only one round can be open. M1 already makes the ambiguous case
  **refuse** rather than mis-attribute, so the failure mode is honest. **⚠ This becomes live work
  on a DATE, not a trigger** — May/June 2027, when the flagship reopens beside a live Sabah intake.
- **Moving rule tunables from cohort to Programme** (defaults + overrides). Behaviour-sensitive —
  it feeds the verification engine — and unnecessary: a new programme's first intake authors its
  own thresholds on its own cohort.
- **Sprint E (erasure) and the DPA.** Still hard-blocking *Inspire* (a second organisation with new
  applicant data). Sabah is a second **programme inside BrightPath**, whose data agreement position
  is unchanged, so it does not gate this.
- **The CLBG.** Money stays off-platform (sponsors pay Suresh personally; he credits by hand) — the
  same interim BrightPath already runs on. Not a new condition for Sabah.

---

## Sprints

Five, sequenced by **live risk first, then hard dependency, then value.**

### ✅ S1 — SHIPPED **AND DEPLOYED** 2026-09-02. **The armed regression is disarmed.**

**LIVE: `halatuju-web-00819-9zw`** (build `c684a867` SUCCESS), api unchanged at `00971-ck4` — only
the web trigger fired, a fifth observation that it follows PYTHON. Verified in the served bundle.
**A Sabah `Programme` row may now be created without breaking the flagship's payouts.**

Retro `docs/retrospective-2026-09-02-sabah-s1-payment-run-programme.md`; lessons ×2. NO migration.
web only. jest 1618 → **1623**; i18n 4644 → **4648 × 3**. Two guards bite-checked.

**▶ IT WAS NOT A SABAH FEATURE.** P2b made the API refuse `programme_required` rather than pick —
correct — and the screen neither sent a programme nor knew that error code. The refusal was right;
the screen was behind it, and the gap was invisible until the exact condition it guards for.

**▶ ONE GIFT → NO PICKER, NOTHING SENT, BYTE-IDENTICAL.** Two → the operator states which, nothing
preselected. `createPaymentRun` takes `programme_id` **required positionally, nullable in value** —
required so no call site sneaks past the dimension (P2a), nullable because absence cannot produce a
wrong answer, only a resolution or a 400 (PF-1's precedent).

**▶ THE FALLBACK IS SAFE, NOT MERELY QUIET.** A failed scope fetch → empty list → no picker →
nothing sent → today's behaviour exactly. Pinned as its own test.

**Also fixed in passing:** the dialog's date and month labels were never associated with their
inputs. **Pinned, not fixed:** every create failure renders twice (one `error` state feeds both the
page banner and the dialog) — pre-existing, and asserting one node would have hidden it.

### ✅ S2 — SHIPPED **AND DEPLOYED** 2026-09-03. **The screens exist.**

Retro `docs/retrospective-2026-09-03-sabah-s2-programme-screens.md`; lessons x3. **Migration `0148`
applied migrate-first + verified.** web + api. pytest **5790** (full suite), jest **1631**, i18n **4714 x 3**.
Five guards bite-checked. LIVE `halatuju-web-00820-r2r` / `halatuju-api-00972-jrg`.

**Approved design:** the Artifact mock, drafts 1-4 (Stitch timed out and never surfaced the screens
across ~10 minutes and two polls — the memory note's own fallback). Owner rulings folded in:
"Gift Programme" as the wording; two screens because one act is org-level and one programme-level;
requirements as **tick boxes with an open value**; neutral labels so another organisation reads the
same screen; and shortlisting on **self-declaration**, which is the design, not a gap.

**▶ THE REAL FIND WAS A LIVE, INVISIBLE DEFECT.** Every threshold was `NOT NULL` with a default, so
every test always ran. BrightPath never asked for an STPM requirement; PNGK >= 2.90 applied to all
nine of its STPM applicants for an intake anyway, rejecting none of them.

**▶ THE VALUE IS THE SWITCH** — no companion boolean, because two columns can disagree and one
cannot. **▶ MERIT DOES NOT REUSE THE ADMIN LIST'S FUNCTION**, whose docstring says "NOT A GATE, AND
MUST NOT BECOME ONE".

### ✅ S0 — THE SHAPE · SHIPPED 2026-09-03. **Not on the original plan; the owner added it.**

The owner opened the console, read the sidebar and said the parts did not fit: *"We cannot open new
branches that are disconnected."* One question — **what is a subset of what** — answered from the
database rather than from the menu, and it re-cut three of the four sprints below.

Retro `docs/retrospective-2026-09-03-console-shape.md`; decisions ×2; lessons ×5; **TD-193 resolved
(programme half)**; TD-228 + TD-229 raised. NO migration. web + a two-line backend audit.
pytest **5792** (full suite); jest 1631 → **1657**; tsc **24**; lint **0**;
i18n 4714 → **4722 × 3**; build clean. Two guards
bite-checked.

**Menu 16 rows → 12. Reserved slots 4 → 1.**
- Gift programmes moved onto **Organisation → Overview** (the gifts you run are what the
  organisation IS, and the row listed one thing). Old route redirects.
- **Programme → Configuration** became three tabs in the owner's order: **Rules · What we ask for ·
  Intake year**. `/admin/programme/years` redirects here.
- **Colours moved to Organisation → Settings.** It writes `OrganisationTheme` — one row for the
  whole tenant — and was being set from inside a single gift. Silent with one gift, wrong with two.
- **The breadcrumb switcher works** (TD-193). The chosen gift is passed to each endpoint as an
  explicit `?programme=<code>` the server re-fences; it never became ambient, and it never picks
  silently.

**▶ THE OWNER'S MODEL RE-CUT THE REST OF THIS ROADMAP.** Their words: *"Reviewers, sponsors and
sources are invited by the org. So, they are subset of the org, and they could be assigned to the
select programme by the org admin."* That is **one pattern, three times** — which merges S4 and S5
and adds a third piece, as **S-ASSIGN** below. And *"I see the rules as a configuration item"* means
S3 is not a sprint at all: it shipped as a tab in S0.

### ~~S3 — the rules screen~~ · **SUPERSEDED by S0, 2026-09-03**

It was never a page. The six thresholds are columns on the intake year that S2b's create form
already wrote, so a Rules screen was a second view of an existing form. It is the FIRST tab of
Programme → Configuration, with the one thing the original scope was right about: a warning, because
these thresholds are read LIVE by `shortlisting.evaluate()` while "what we ask for" is frozen per
application at submit. Threshold changes also write an audit line carrying old → new (TD-203's
lesson, applied before it bit twice).


### ~~S-ASSIGN — invited by the ORGANISATION, assigned to a GIFT~~ · ✅ **SHIPPED + DEPLOYED 2026-09-04**

Absorbed S4 and S5 and added sources. Migrations `courses/0073` + `scholarship/0149`.
Detail in `docs/retrospective-2026-09-04-s-assign.md`; the rules that must not be tidied are in
`halatuju_api/CLAUDE.md` → Next Sprint, and the map of who is scoped to what is in
`.claude/ARCHITECTURE_MAP.md`.

**The acceptance test is met:** a benefactor can be accepted into any gift and their credit
recorded where it was previously refused `sponsor_not_in_programme`; a reviewer and a source can
each be scoped to a gift; every existing BrightPath sponsor, reviewer and source is untouched
(NULL = every gift, no backfill — 0 of 21 staff, 0 of 10 organisations, 0 of 20 invitations carry
one). Raised **TD-230**: a source's gift reaches no student yet.

**⚠ Still true and still binding: the pool is FAIL-CLOSED.** No membership → empty pool. Every
channel narrows through `pool.for_sponsor`, **including the weekly digest and the real-time
alert** — P3's source guard exists precisely because those two routed around the fence once. Do
not add a sixth channel without extending that guard.


## Sequencing rationale

S1 protects a live payout path and must land before any Sabah row exists — **including an inactive
one**, so the launch never depends on remembering a flag. S2 is the hard dependency for everything
Sabah. S4 unblocks the money and is worthless before S2 (there is no programme to be accepted into).
S3 can slip after launch if the first intake's thresholds are set once at creation. S5 is a
narrowing, not a fence, and the org fence is unchanged either way.

**Minimum to hand Suresh the keys: S1 + S2 + S4.** S3 and S5 make it comfortable rather than
possible.

> **⚠ RE-CUT 2026-09-03.** The owner added **S0 (the shape)** and it changed the rest. S3 shipped as
> a tab inside it; S4 and S5 merged into **S-ASSIGN** with a third piece (sources). So the sequence
> is now **S1 ✅ → S2 ✅ → S0 ✅ → S-ASSIGN**, and **S-ASSIGN is the only thing left between the owner
> and the sentence to Suresh.** Four remaining sprints became one.
>
> Also owed, and not engineering: **TD-229 — is the agreement wording one per organisation, or one
> per gift?** Asked twice, unanswered. It does not block S-ASSIGN, and it does block a Sabah student
> ever signing anything.

## Standing owner gate — still in force

**Record nothing until the programme is inked AND the money has changed hands**, with a bank
reference for `external_reference` (decisions.md, 2026-07-26). "Ready to launch" starts the
BUILDING. **No sprint in this roadmap creates a Sabah row**; S2 creates the *screen* that lets
Suresh create it when both conditions are met.

## Verification, every sprint

- Org fence: cross-org is **404, never 403**.
- The existing suite passes **unmodified** wherever "nothing changes for BrightPath" is claimed —
  that claim is only worth what proves it.
- Every guard bite-checked: inject the fault, **verify the injection landed**, restore by writing
  the original back — never `git checkout --`.
- Migrations applied **migrate-first**, before the push.
- `next build` before believing `tsc`, `jest` or `lint`.
