# Retrospective — the spending screen, S6–S8, TD-241, and the September blackout

**2026-09-11 → 2026-09-12.** Five deploys. No migrations. Every change owner-driven: this arc had
no roadmap, only a person using the screen and saying what was wrong with it.

---

## What was built

| | |
|---|---|
| **S6** | The officer screen split into three tabs; a super can open it at all |
| **S7** | Search, filters, tab counts; the duplicate "model decided" list deleted |
| **S8** | The Vircle wallet door emails a person when it moves money |
| **TD-241** | Payments **and** Spending moved from Organisation to Programme, together |
| **The blackout** | Every September transaction was being dropped. Fixed, and the month recovered |
| **Follow-ups** | Names not numbers, a Balance column, formal copy, and the Drive summary stops duplicating itself |

Gates at close: **6537 pytest**, **2183 jest**, lint 0 errors, `next build` exit 0.

---

## What went well

**The owner found the bug that mattered, and the system was shaped so the answer was recoverable.**
`spending-reread` did not exist when the blackout was discovered — but "keep no state of our own"
did, and `ingest` dedups on `txn_id`, so a re-read was safe to build and run the same hour. The
lost month came back exactly: **1,377 → 1,597 rows, RM10,650.22 → RM13,353.03**.

**Bite-checking earned its keep, repeatedly.** Twenty-odd injected faults across the arc. Five were
silent, and every single silent one was a real gap in the tests rather than a false alarm — see
below. A guard that cannot fail on purpose has never been tested, and that held every time.

**Reversals were cheap because the original decisions named their triggers.** The S4a `no_org`
refusal said *"revisit if a genuine platform-wide spending view is ever wanted"*. When the owner
hit it, the reversal took minutes and left a clean record instead of an argument.

**`main` moved under me nine times** (two other agents shipping in parallel) and not one merge lost
anything. Merging `origin/main` **into** the branch and pushing `HEAD:main` — never checking `main`
out — is now the written default.

---

## What went wrong

### 1. A month of live data was silently deleted, and my tests said everything was fine

**What happened.** `_DATE_FORMATS` accepted `%d %b %Y` (`Sep`) and `%d %B %Y` (`September`). The
corpus writes **`Sept`**, which matches neither. Every September row failed to parse, was counted
as an unparsed date, and was never stored. The owner found it by comparing the sheet (230 rows to
6 September) against the screen (9 rows, stopping at 31 August).

**Why it happened.** The date tests asserted **the spellings the corpus happened to use in July and
August**. That is a statement about the past wearing the clothes of a test. September is the one
English month whose everyday short form is four letters, so the fault could not appear until the
calendar turned — eleven days after the feature shipped.

**System change.** `test_EVERY_MONTH_IN_EVERY_SPELLING_A_PERSON_MIGHT_WRITE` walks all twelve
months through every abbreviation length and case. **Enumerate; do not sample.** Plus a sibling
test that a word merely *starting* like a month (`Marble`) is not a date, because the lazy repair
is worse than the bug.

### 2. The one document that could have answered the owner's question was being thrown away

**What happened.** Asked why five students had no spending, I could not say — unknown wallets?
unparsed dates? — because the import's report existed nowhere.

**Why it happened.** Under cron, `call_command(..., stdout=out)` captures the report into the HTTP
response body. Cloud Scheduler reads the status code and discards the body. The only other channel
was an alert email that fires *solely* when something "needs attention" — and a question is not
always a fault.

**System change.** The report is logged (WARNING on a finding, INFO otherwise). **stdout is not a
destination when nobody is at a terminal.**

### 3. Fixing the parser would have recovered nothing

**What happened.** The corrected reader would have skipped the very file it had misread.

**Why it happened.** "New or changed" is the right rule and is exactly what makes a parser fix
incomplete — the file was already marked read.

**System change.** `--reread` and the `spending-reread` door shipped *with* the fix. **Any bug that
changes how input is INTERPRETED needs a re-read plan, not just a code change.**

### 4. I fixed a defect and left its twin one page over

**What happened.** A super was refused Spending with `no_org` on 11 September; fixed. The Payments
funding summary carried the identical line and was missed, so a super's money summary stayed blank
for another day. Found in the live ERROR logs, not reported — the page around it still renders.

**System change.** **After fixing an access defect, grep for the CONDITION across every sibling
endpoint**, not for the endpoint's name.

### 5. Five silent bites — five tests that proved nothing

Each one passed while the code was deliberately wrong:

| Bite that stayed silent | Why the test was blind |
|---|---|
| Every caller given the platform scope | No endpoint test proved the VIEW picks the right scope — only the service was covered |
| Sorted the page, not the list | The fixture arrived already in the sorted order |
| Paged before filtering | Four rows fit one page, so both orders agree |
| The run LIST ignored the gift | The create path was covered three ways, the read path not at all |
| A balance floored at zero | Nothing asserted a negative survives |

**The pattern is one sentence: a test whose fixture cannot distinguish the right answer from the
wrong one is decorative.** For any "do X then slice", the fixture must be longer than a page and
must select rows on both sides of the boundary. For any narrowing, bite the **read** — the write is
the one you were thinking about, which is exactly why it is not the gap.

### 6. I printed a live secret into the transcript

**What happened.** Asked where a Drive folder was, I dumped every `VIRCLE_*` env var and
`VIRCLE_AIRTABLE_SECRET` went with them.

**Why it happened.** I filtered the *output* by prefix instead of naming the *key* I needed — and
secrets are named after the systems they belong to, so they always match that prefix.

**System change.** Name the keys. The response mattered more than the slip: said so immediately,
checked the logs (nothing has ever come through that door), and let the owner decide on rotation
with the blast radius spelled out. **Rotation is still outstanding and needs Vircle.**

---

## Design decisions worth remembering

- **`ALL_ORGS` is a sentinel object, never `None`.** Every accident that loses an organisation
  produces `None`, which filters to nothing — safe. Had the platform scope been spelled `None`,
  each of those accidents would have widened a tenant's page to the whole platform.
- **The gift narrows *inside* the organisation fence, never instead of it** — and that is tested
  from the widening side, because the narrowing side passes either way.
- **Two controls answering "which gift" is a defect on a money screen**, not redundancy. The
  Payments picker was deleted rather than kept as a confirmation.
- **The officer's balance is not floored at zero; the sponsor's is.** A donor must never read a
  negative as "your student overspent your money". The officer is the person who should ask.
- **A read-only list beside an editable table of the same data is a filter wearing a section's
  clothes.** The tell: you cannot answer "what action does this expect?".

## Numbers

| | |
|---|---|
| Deploys | 5, all verified by build ID + serving revision |
| Migrations | 0 |
| pytest | 6537 |
| jest | 2183 |
| Live spending after recovery | **RM13,353.03** across 1,597 transactions, 47 students |
| Still unexplained | 5 students paid since July with no spending — a question for Vircle, not a fault |
