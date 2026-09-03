# Sabah self-serve — roadmap

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

#### S1 — the payment run says which gift *(original scoping)* · complexity: LOW · **must ship before any Sabah row exists**

**Goal.** The screen that creates a monthly run states the programme, and survives a second one.

**Scope.** `createPaymentRun` gains `programme_id`; a picker on the payments screen that
**preselects and hides itself when the org runs one** (so nothing changes for BrightPath today);
`programme_required` mapped to real copy in en/ms/ta; the run list and detail already show the
programme (P2b) — confirm, don't rebuild.

**Acceptance.**
- A test with **two** active programmes proves the screen creates a run against the chosen one.
- With **one**, the payload and the screen are unchanged — proven by the existing suite passing
  unmodified.
- The error path is exercised, not just the happy one.

**Why first.** It is the only item that protects money already moving.

### ✅ S2 — SHIPPED **AND DEPLOYED** 2026-09-03. **The screens exist.**

Retro `docs/retrospective-2026-09-03-sabah-s2-programme-screens.md`; lessons x3. **Migration `0148`
applied migrate-first + verified.** web + api. pytest **5742**, jest **1631**, i18n **4714 x 3**.
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

#### S2 — original scoping · complexity: HIGH · **Stitch first**

**Goal.** An `org_admin` creates the gift and opens its first year without an engineer.

**Scope.** The **Intake years** placeholder slot becomes real. Create/edit `Programme` (code, three
names, active) and `ScholarshipCohort` (code, name, year, open/closed, deadlines). Org-fenced on
`organisation_id`, **404 not 403**, matching the Layer 0 configuration view exactly. `org_admin` +
`super` only.

**⚠ One gift per programme** (owner ruling) — creating the programme IS creating the bursary. Do
**not** build two creation steps.

**Acceptance.** Suresh creates "BrightPath Sabah", opens `sabah-2026`, and the apply link
`/apply?p=brightpath-sabah` routes a student into it. A cross-org attempt is a 404.

**Risk.** Opening an intake is the switch that lets real students in. The open/close control needs
the same "name a real counted number" treatment Layer 0's live-applicant warning got.

### S3 — the rules screen · complexity: MEDIUM · **Stitch first**

**Goal.** The **Rules** placeholder becomes the 13 thresholds, editable and explained.

**Scope.** `min_spm_a_count`, `min_spm_bplus_count`, `min_stpm_pngk`, `income_ceiling`,
`per_capita_ceiling`, `bucket_b_margin`, `funding_envelope`, and the four email-timing fields.
Per-intake (they live on the cohort). **These feed the decision engine** — every change wants an
audit line and a "this changes who qualifies" warning, the Layer 0 pattern.

**Acceptance.** Changing a threshold changes who shortlists, is audited, and warns first. A
cohort mid-intake refuses a change that would strand a decided applicant, or says plainly that it
will not be retro-applied — **owner's call, raised in the Stitch pass.**

**Could merge into S2** if fewer handoffs are wanted — same model, two screens. Kept separate
because S2 is structural and S3 is behaviour-sensitive, and mixing those is how a config screen
quietly changes a verdict.

### S4 — accepting a sponsor into a gift · complexity: MEDIUM · **unblocks the RM100,000**

**Goal.** An `org_admin` accepts a benefactor into a programme; the flagship literal dies.

**Scope.** `DEFAULT_PROGRAMME_CODE` stops being a tenant literal in production code. An acceptance
surface on the existing sponsor detail page (memberships already render there). Endpoint fenced on
`programme__organisation_id` like the credits endpoints.

**⚠ The pool is fail-closed and must stay so.** No membership → empty pool. Every channel narrows
through `pool.for_sponsor`, **including the weekly digest and the real-time alert** — P3's source
guard exists precisely because those two routed around the fence once. Do not add a sixth channel
without extending that guard.

**Acceptance.** The Sabah benefactor is accepted into Sabah only, sees Sabah students only, and the
RM100,000 credit is accepted where it was previously refused `sponsor_not_in_programme`. A flagship
sponsor's visibility is byte-identical.

### S5 — reviewers bound to one gift · complexity: MEDIUM · not launch-blocking

**Goal.** P1b's remaining third: Sabah's volunteers see Sabah applications.

**Scope.** Nullable `programme` on `PartnerAdmin`, **NULL = organisation-wide** (owner's ruling —
no backfill, existing staff unaffected). Assignment lists filter by the application's programme when
the reviewer is bound. `org_admin` / `finance` stay org-wide. The **Reviewer scoping** placeholder
becomes the screen. Set from the invite.

**Acceptance.** A Sabah-bound reviewer is offered Sabah applications only. Every existing BrightPath
reviewer keeps working with no change — proven by the existing suite passing unmodified.

**Why last.** Org-wide reviewing is correct-but-broad, not wrong. It is the only gap of the five
that does not block the launch or endanger money.

---

## Sequencing rationale

S1 protects a live payout path and must land before any Sabah row exists — **including an inactive
one**, so the launch never depends on remembering a flag. S2 is the hard dependency for everything
Sabah. S4 unblocks the money and is worthless before S2 (there is no programme to be accepted into).
S3 can slip after launch if the first intake's thresholds are set once at creation. S5 is a
narrowing, not a fence, and the org fence is unchanged either way.

**Minimum to hand Suresh the keys: S1 + S2 + S4.** S3 and S5 make it comfortable rather than
possible.

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
