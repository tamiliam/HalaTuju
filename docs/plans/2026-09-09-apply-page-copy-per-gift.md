# Plan — the apply page's public copy belongs to the GIFT, not the platform

**Status:** PLANNED, NOT BUILT. Owner approved building on 2026-09-09; asked for a plan first.
**Size:** one sprint. ~14 files. ONE migration (additive, one column).
**Trigger:** BrightPath **Sabah** is expected live in ~2 weeks. Today the apply page advertises
BrightPath's B40 criteria to every gift on the platform, so Sabah's own apply link would tell its
applicants they must be B40 with 5 A's.

---

## 1. The defect, stated precisely

`/scholarship/apply?p=<code>` renders one fixed card, identical for every gift:

| Element | Source today |
|---|---|
| `Apply for B40 Education Assistance` | `scholarship.apply.title` |
| `Financial assistance for B40 students continuing to IPTA/ILKA…` | `scholarship.apply.intro` |
| `Who can apply` | `scholarship.apply.criteriaTitle` |
| 4 bullets | `scholarship.apply.criteria1..4`, a **hard-coded array of exactly four keys** at `halatuju-web/src/app/scholarship/apply/page.tsx:426` |

**⚠ THE NUMBERS BEING LOOSER THAN THE ENGINE IS NOT THE BUG.** Sprint 8 (2026-05-24) ruled that the
public page advertises the stricter bar (5 A's / PNGK 3.0) while `shortlisting.evaluate()` runs
looser (4 A− / PNGK 2.9) deliberately, to catch near-misses. The owner reaffirmed that on
2026-09-09: *"the public facing text need not be exactly same as the internal filter."*
**Do not "fix" the copy to match the Rules tab.** Any implementation that derives this text from
`min_spm_a_count` / `min_stpm_pngk` is wrong and reverses a standing ruling.

**The bug is that there is exactly ONE of these strings for the whole platform.** A second gift
inherits the first gift's advertisement.

---

## 2. Scope — the owner drew this line himself, hold it

> *"I am only looking at one page: the page that the apply link points to, and nothing else."*

**IN:** the heading, the intro paragraph, and the bullet list on `/scholarship/apply`.

**OUT, and each for its own reason:**
- `Who can apply` — generic; works for any gift; keep it a platform string.
- The **landing page** (`scholarship.landing.req.item2`) and the **sign-in prompt**
  (`authGate.applyReason`). Same class of defect, not this page. Log separately.
- **The 13 officer-facing B40 strings** (`admin.scholarship.verdict.fact.income` = "Income (B40)",
  the verdict item lines, the anomaly facts). Those describe the **means-test engine**, which is
  genuinely a B40 income engine. Renaming them is a different, larger argument. **Do not fold in.**
- The **sponsor landing** (2 strings).

Measured 2026-09-09: 19 strings in `en.json` mention B40. This sprint changes the behaviour of
**6** of them and deletes none.

---

## 3. Three rulings, taken 2026-09-09. Build to these.

1. **BLANK MEANS THE PLATFORM DEFAULT.** A gift with no copy configured renders today's exact
   English/Malay/Tamil text from the existing `scholarship.apply.*` keys. **BrightPath therefore
   needs zero data entry and is byte-identical after this ships.** This is the
   `OrganisationConfiguration` pattern: the stored row holds only what the tenant changed, never a
   copied default (a copied default rots when the platform default moves).
2. **ENGLISH REQUIRED, MALAY AND TAMIL OPTIONAL**, each falling back to English when blank. Mirrors
   `Programme.name_en/_ms/_ta` and the `branding.py` fallback convention. An organisation must not
   be blocked from advertising because nobody on staff writes Tamil.
3. **THE TAB IS ON EVERY GIFT, AND ON A CLOSED GIFT ITS TEXT IS A PLACEHOLDER FOR THE NEXT
   INTAKE.** The flagship gets the tab too. Its round is closed, so the words sit there unused and
   go live the day the round opens.

   ⚠ **THE FIRST DRAFT OF THIS PLAN SAID THE OPPOSITE AND WAS WRONG.** It claimed the card renders
   while a round is closed. It does not: `page.tsx:173` is `if (!r.open) router.replace('/scholarship')`,
   so a closed apply link **bounces to the landing page** and the card is never drawn. That is what
   the owner saw on 2026-09-09 when both the old and new links "ended up at /scholarship". Owner's
   reading (2026-09-09) is the correct one and is the ruling.

---

## 4. Data model

One additive JSON column on `Programme` (`scholarship_programmes`).

```python
apply_copy = models.JSONField(
    default=dict, blank=True,
    help_text='Public apply-page copy per language. Blank/absent = the platform default.',
)
```

Shape:

```json
{
  "en": {"title": "…", "intro": "…", "criteria": ["…", "…", "…"]},
  "ms": {"title": "…", "intro": "…", "criteria": ["…"]},
  "ta": {}
}
```

**⚠ JSON, NOT NINE COLUMNS, and the reason is the bullets.** The criteria list is variable-length —
the owner's ruling is that a gift may have three bullets or five, because Sabah is not B40 and its
conditions are its own. A column-per-field model cannot hold a list, so the list would need a JSON
column anyway; splitting title/intro into six more columns then buys nothing but six migrations'
worth of drift. House precedent for tenant-editable JSON config: `OrganisationConfiguration`,
`requirements_snapshot`.

**Migration `scholarship/0154`** — additive, nullable-in-effect (`default=dict`), no backfill.
**MIGRATE-FIRST via Supabase MCP before the push.** Hand-write the Postgres DDL in the migration's
own docstring (`sqlmigrate` renders SQLite on this box). No new table ⇒ **no RLS work and no
Security Advisor step.**

---

## 5. The read path — and the one trap in it

The apply page **already calls the public intake endpoint** (`GET /api/v1/scholarship/intake/`,
`AllowAny`) and already reads `choices` off it (`page.tsx:177`). So the copy rides on a call the
page makes anyway: no new endpoint, no auth, and **the retired-code alias keeps working for free**.

Add one key to the reply — **the per-locale map exactly as stored, nothing folded in**:

```json
{"open": false, "cohort_name": "", "choices": [],
 "apply_copy": {"en": {"title": "…", "intro": "…", "criteria": ["…"]}, "ms": {}, "ta": {}}}
```

### ⚠ CORRECTED AT SPRINT-START: the server does NOT resolve the platform default

The first draft had the server fold the platform default in and serve one resolved string. That
would have put the English, Malay and Tamil of `scholarship.apply.title/intro/criteria1..4` into
**Python as well as the message files** — 21 strings duplicated across two deployables, which is
the `_SUBJECT_BM`↔`subjects.ts` drift trap, recorded in `lessons.md` three times.

**The house pattern already exists and is the branding endpoint's:** `GET /api/v1/branding/<code>/`
serves `programme_name` as a `Partial<Record<Locale, string>>` and the browser resolves it with
`branding.resolveLang`. Copy that. **The platform default stays in the message files, its one
home**, and the browser reaches for it only when the gift supplies nothing.

Split of responsibility:
- **Server** — WHICH GIFT (live code, else alias), and the stored map verbatim.
- **Browser** — which locale, and the fall-through to `t('scholarship.apply.*')`.

This is not a "serve, don't derive" breach: that rule bans a screen PREDICTING A SERVER REFUSAL.
There is no refusal here, and the platform default is the browser's own text to begin with.

### ⚠ ALL-OR-NOTHING PER GIFT, AND ms/ta FALL BACK TO THE GIFT'S OWN ENGLISH

Two fallback rules that look like fussiness and are the opposite:

1. **A gift either supplies its whole card or none of it.** The tab requires English **title +
   intro + at least one bullet** together, or all three blank. Per-FIELD fallback would render
   *"Apply for B40 Education Assistance"* above Sabah's own bullets — a heading from one gift over
   the criteria of another, with nothing failing.
2. **A blank `ms`/`ta` falls back to the GIFT's English, never to the platform's Malay/Tamil.**
   This deliberately DIFFERS from `resolveLang`'s behaviour for branding, and the difference is the
   whole point: falling back to the platform's *name* is harmless, but falling back to the
   platform's *criteria* would tell a Malay-reading Sabah applicant they must be B40 with five A's.
   **A wrong-language truth beats a right-language falsehood.** Write this reason at the helper —
   the next person will otherwise "make it consistent" with branding.

### ⚠⚠ THE REAL TRAP, AND IT IS A SECOND DEFECT SABAH WILL HIT IN TWO WEEKS

**`getScholarshipIntake()` sends no programme code** (`lib/api.ts:1600` — the function takes no
argument), so the apply page's open/closed gate at `page.tsx:173` is **platform-wide**, not
per-gift. It asks *"is anything open anywhere?"*, never *"is THIS gift open?"*.

Harmless while one gift runs. **It breaks the day two gifts have different round states**, which is
Sabah:

| Situation | What a student on `?p=brightpath-flagship` gets today |
|---|---|
| Nothing open (today) | bounced to `/scholarship`. Correct. |
| **Sabah open, BrightPath closed** | intake says `open:true` → **the whole BrightPath form renders** → they fill it in → `resolve_open_cohort('brightpath-flagship')` returns `None` at submit → **refused after all that typing** |

That is PF-1's "right refusal, wrong moment" in a new costume — the same fault the choices screen
was built to cure, still live on the per-gift-closed path.

**Fix, and it is the same one line the copy needs anyway:** give `getScholarshipIntake` the
programme code from the URL and pass it as `?programme=`. The gate then answers for the gift the
student actually followed, and the copy arrives on the same call.

**And resolve the PROGRAMME independently of the round**, because a closed gift must still be
identifiable to answer "closed" *about the right gift*. Extract the live-code-then-alias fallback
that already sits inside `resolve_open_cohort` (`services.py` ~264–285) into a shared

```python
def resolve_programme_by_code(code):   # live code first, alias only as a fallback
```

and have **both** `resolve_open_cohort` and the intake view call it. One home for "which gift does
this code mean". `resolve_open_cohort`'s behaviour must not change — it is on the money path.

**Resolution order in the intake view:**

| Caller | Copy served |
|---|---|
| `?programme=<live or retired code>` | that gift's copy → platform default per missing field |
| no code, exactly one round open | that round's gift's copy |
| no code, several rounds open (`AmbiguousOpenCohort`) | **platform default** — nobody has chosen a gift yet; the page is showing the chooser |
| no code, nothing open | platform default |
| unknown code | platform default — **never 404.** This endpoint is public and unauthenticated; distinguishing "no such gift" from "not open" lets anyone enumerate the platform's tenants. The existing docstring says so; the copy must obey the same rule. |

**⚠ NO NEW STUDENT-FACING i18n KEYS.** The platform default IS the existing `scholarship.apply.*`
block, resolved on the server. So this sprint adds **zero** Malay/Tamil translation debt on the
student side — which is the whole reason the fallback is server-side rather than a browser `||`.

---

## 6. The write path

A **4th Configuration tab**, in the owner's order:

> **Intake year · Rules · What we ask for · How it's advertised**

- Register it in `TABS` at `halatuju-web/src/app/admin/programme/page.tsx:57` (`'copy'`), add
  `admin.programme.tab.copy`, add the panel. `?tab=copy` deep-links it (read from
  `window.location`, **never `useSearchParams`** — that needs a Suspense boundary or `next build`
  refuses; the F7c trap).
- New component `halatuju-web/src/components/admin/ApplyCopyTab.tsx`. **Every sub-component at
  MODULE scope** — a component declared inside the body remounts the inputs on every keystroke
  (the 2026-07-21 invite-form defect, repeated 2026-09-03).
- Language sub-tabs EN / MS / TA. EN's title+intro are required; MS/TA show *"Blank uses the
  English text"*.
- The bullet list is add / remove / reorder-free (order = list order).
- Save through the **existing** `AdminProgrammeDetailView.patch` (`views_admin.py` ~6990) — it
  already takes `name_en/ms/ta` and `code` on this exact object, is already org-fenced
  (cross-tenant ⇒ 404, never 403), and already writes an `AUDIT programme_updated` line. **Do not
  add a new endpoint.**
- Save bar: `components/admin/SaveBar.tsx`, buttons **right**, **idle renders nothing at all**.
  Keep this tab's own `dirty` — do not share one dirtiness rule across the four tabs.

### Validation, server-side, mirrored on the form

Lengths, because a `varchar` overflow on a free-text box is a solved lesson here
(`parents_occupation`, 2026-06-07): title ≤ 120, intro ≤ 400, each bullet ≤ 200, **≤ 8 bullets**,
blank bullets dropped. Reject `<` and `>` outright — this text renders on a public page and is not
markup. A refusal returns a field-level 400 the tab renders beside the offending box, never a
blanket "could not save".

### One sentence of copy that is not decoration

Under the bullet editor:

> *Applicants read this. If it promises easier terms than your Rules, people will apply and be
> turned down automatically.*

The owner accepted the divergence between advertisement and engine deliberately; the tab has to
say out loud what that costs, or the next org_admin discovers it through a rejected student.

---

## 6b. ⚠⚠ A STANDING DECISION THIS SPRINT COULD BREACH — found at sprint-start, 2026-09-09

`docs/decisions.md`, **2026-05-25, "Drop 'Indian descent' from all public copy"**:

> *The B40 public copy makes **no mention of Indian descent / ethnicity anywhere — not even as a
> pilot framing**… MyNadi Foundation's **Section 44(6)** tax-exempt status requires the programme
> not to discriminate on the basis of race.*

**This sprint hands an organisation a free-text box that renders on that exact public page.** An
org_admin typing *"Open to students of Indian descent"* into a criteria bullet publishes precisely
the sentence that decision removed, on the page it was removed from, with nothing to stop them.
The decision predates multi-tenancy and was written when the copy was ours to control; this sprint
is what takes it out of our hands.

**⚠ A PLATFORM-WIDE HARD BAN IS NOT OBVIOUSLY RIGHT.** Ethnicity-scoped scholarships are ordinary
and lawful in Malaysia, and a future tenant may run one legitimately. The constraint above is
**MyNadi's**, arising from how *this* foundation is funded — not a platform invariant.

**✅ OWNER RULING, 2026-09-09 — OPTION A: WARN, DO NOT REFUSE.**

The tab names the s44(6) constraint beside the criteria box; the save goes through. Rejected:
refusing platform-wide (safest today, wrong for tenant three, and un-doing it later is a real
argument) and a per-organisation refusal (correct in principle, but a new stored setting bought
for a tenant that does not exist).

**Why a warning is proportionate here, stated so it can be re-judged rather than re-guessed:** the
person typing is that same foundation's own administrator, who carries the s44(6) risk themselves;
the text is on a PUBLIC page, so a mistake is highly visible; and the fix is one edit. None of
those hold for the tax-relief ban on donor copy, which is why that one refuses and this one does
not.

**⚠ BUILD THE WORD LIST ANYWAY, EVEN THOUGH NOTHING REFUSES.** The detector ships and drives the
warning; only the ACTION is soft. Tightening to a refusal is then one branch, not a new feature —
and the phrases are written down where the next person can read them instead of re-deriving which
words were meant. Reuse `email_templates.banned_phrases(banned, *parts)`, the same helper behind
the "tax deductible" refusal, so there is one matcher on the platform.

**Revisit if:** a tenant asks to run an ethnicity-scoped programme (then the scope becomes
per-organisation, shape 2), or MyNadi's s44(6) position changes.

---

## 6c. Lessons applied (sprint-start step 2 — `docs/lessons.md`)

Each one is live in this sprint's scope, not a recital:

- **"A prop that is never fed will stay never fed"** (gift-first nav, 2026-09-08). This sprint's
  whole shape is a new value threaded end to end: `apply_copy` onto the payload, and a programme
  code INTO `getScholarshipIntake()`. A default parameter and a starved one render identically.
  **→ the jest test must PASS the code and assert the request URL carries `?programme=`**, not
  merely that the function accepts an argument.
- **"i18n parity only proves en == ms == ta — it does NOT prove a key EXISTS"** (Sponsor R7) and
  **"a key ASSEMBLED at runtime is invisible to a static scanner"** (2026-07-23). The platform
  fallback resolves `scholarship.apply.criteria1..4` **server-side**, so those keys move from a
  static `t('…')` literal in `page.tsx` to strings built in Python. **→ the FE scanner will stop
  seeing them; add a backend test asserting every platform-default key resolves in all three
  locale files**, or they become deletable-by-accident.
- **"When you filter a list down, re-read its empty state"** (staff directory, 2026-09-09) and
  **"an empty list is two facts"** (2026-09-08). `apply_copy = {}` means *"use the platform
  default"*, never *"this gift advertises nothing"*. **→ the tab's empty state must NAME the
  default underneath each blank box** (the `OrganisationConfiguration` pattern), and the payload
  must never serve an empty criteria list.
- **"A sentence in the UI can be a claim about the system, and it goes stale"** (2026-09-09).
  **→ before shipping, grep all three message files for copy asserting this text is fixed or
  platform-wide.**
- **"A presence grep cannot verify a RENAME — verify by ABSENCE"** (2026-09-08). **→ the deploy
  read-back proves BrightPath is unchanged by finding its text still present, and proves the tab
  shipped by finding the new admin strings — two different questions, both asked.**
- **"Imported/external text will overflow any `CharField(max_length=N)`"** (2026-07-21) and the
  `parents_occupation` overflow (2026-06-07). Caps live in §6 and are enforced **server-side**,
  not only on the form.
- **"`sqlmigrate` renders for SQLite — never paste it into a Postgres migrate-first"**
  (2026-06-21). **→ hand-write the DDL in the migration docstring.**
- **"`git checkout --` destroyed a real edit during a bite-check"** (2026-09-08) and **"restoring
  by string replacement hit the wrong occurrence"** (2026-09-09). **→ restore by writing the
  original bytes back, anchored uniquely, and re-run expecting GREEN.**
- **"`next build` OOMs on the 8 GB box after a full pytest run"** (2026-07-02). The box is 32 GB
  now, but **→ do not run the full suite and `next build` back to back** without watching for it.
- **"A change that breaks no test is the moment to ask what SHOULD have broken"** (2026-09-08).
  Applies to the platform-default path: it is the branch that keeps BrightPath identical, so a
  broken implementation of it looks exactly like success.

---

## 7. Gates

Run **inside a worktree** (`.worktrees/apply-copy`, branch `feat/apply-copy`), never the shared
checkout — another agent works in this repo.

| Gate | Expected |
|---|---|
| `python -m pytest apps/` | baseline + ~18 |
| `npx jest --maxWorkers=2` | baseline + ~12 |
| `npx tsc --noEmit` | **exactly 24** (TD-221 baseline) |
| `npx next lint` | **0 Errors** |
| `node scripts/check-i18n.js` | parity ×3; only `admin.*` keys added |
| `npx next build` | exit 0 |
| `makemigrations --check` | clean |

**Backend tests that must exist**, each of which fails against today's code:
1. A **retired** code serves its gift's copy (the alias path).
2. **⚠ THE GATE ANSWERS PER GIFT.** With gift A's round OPEN and gift B's CLOSED,
   `intake/?programme=<B>` returns `open: false`. This is the §5 defect and the one that costs a
   real Sabah applicant a wasted form. Pair it with a jest test that the page **bounces** in that
   case instead of rendering the form.
3. A closed gift is still **identified** — `intake/?programme=<closed gift>` names that gift's copy
   beside `open: false`, so the answer is about the right gift.
3. Blank gift ⇒ platform default, field by field (a gift with a title but no bullets gets its own
   title and the default bullets).
4. Blank `ms` falls back to `en`, not to the platform default.
5. Unknown code ⇒ platform default, **200 not 404**.
6. Over-length title / 9 bullets / angle brackets ⇒ 400 with the field named.
7. Cross-tenant PATCH ⇒ 404.
8. A reviewer cannot PATCH it.

**Bite-check** at least three of those: inject the fault, **verify the injection landed**, run the
suite, then **restore by writing the original bytes back — never `git checkout --`**, using an
anchor unique to the injection site, and **re-run expecting GREEN** (2026-09-09: a restore hit the
wrong occurrence of an identical line and only the still-red suite caught it).

---

## 8. Deploy

1. Apply **`scholarship/0154` MIGRATE-FIRST** via Supabase MCP; record its `django_migrations` row
   **before** the push. Reconcile the ledger after.
2. Push. **Python changes, so expect BOTH builds.** Read the serving revision from
   `status.latestReadyRevisionName`, **never `status.traffic[0]`** (that is a tagged revision on
   halatuju-api carrying no traffic).
3. No env vars, no data step, no backfill.
4. **Nothing a current student sees changes** — BrightPath's `apply_copy` is `{}`, so its page is
   byte-identical. Prove it by reading the served page back, not by assuming.

**Owner post-check** (as the BrightPath `org_admin`, elanjelian@me.com):
1. **The flagship's tab exists and its text is a placeholder.** Programme → Configuration →
   **How it's advertised** on BrightPath: the boxes are there and blank, naming today's default
   underneath. Nothing a student sees changes — its round is closed, so the words wait for the next
   intake.
2. `https://halatuju.xyz/scholarship/apply?p=brightpath-flagship` still bounces to `/scholarship`,
   exactly as it does today.
3. On the **Test** gift: write three bullets → save → open its round → `?p=testing` shows them, and
   `?p=test` (the retired code) shows the same. Close the round again.
4. **⚠ THE TWO-GIFT CHECK, and it is the one worth doing properly.** With the Test round OPEN and
   BrightPath CLOSED, open `?p=brightpath-flagship`. It must **bounce to /scholarship** — not
   render a BrightPath form that would be refused at submit. That is the §5 defect, and this is the
   only way to see it.
5. Clear the boxes → the page returns to the default text.
6. ms/ta left blank still render English.

---

## 9. What must not be tidied

- **The advertised bar is deliberately stricter than the engine.** Never derive this copy from the
  Rules tab.
- **`Who can apply` stays a platform string.** It is not gift-specific and giving orgs a fourth box
  to fill is friction with no gain.
- **The intake endpoint stays public and 200-on-unknown.** A 404 leaks the tenant list.
- **One home for code→gift.** If `resolve_programme_by_code` gets a second implementation, a
  renamed gift will advertise correctly in one place and wrongly in the other.
- **Blank is a real answer, never a copied default.**

## 10. Follow-ups this sprint deliberately leaves open

- The landing page's own B40 requirement line + `authGate.applyReason` — same defect, other pages.
- The 13 officer-facing B40 strings — the engine's own vocabulary; needs an owner ruling, not a
  sweep.
- Whether a gift should be able to hide the criteria card entirely. Not asked for; do not invent it.
