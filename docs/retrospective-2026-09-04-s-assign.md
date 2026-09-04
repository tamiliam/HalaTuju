# Retrospective — S-ASSIGN: invited by the ORGANISATION, assigned to a GIFT (2026-09-04)

**Shipped and deployed.** `main` at `e07a09bb`; both Cloud Builds SUCCESS on `e07a09b`; serving
`halatuju-api-00975-nrj` / `halatuju-web-00823-pc5` at 100%. Migrations `courses/0073` +
`scholarship/0149` applied migrate-first and verified before the push.

pytest 5800 → **5844** · jest 1666 → **1692** · tsc **24** (baseline) · lint **0** ·
i18n 4722 → **4745 × 3** · `next build` clean · `makemigrations --check` clean.
Four guards bite-checked, each injection verified as landed first.

---

## What Was Built

The owner's model, stated on 2026-09-03: *"Reviewers, sponsors and sources are invited by the org.
So, they are subset of the org, and they could be assigned to the select programme by the org
admin."* That sentence merged what the Sabah roadmap had as two sprints, added a third piece, and
turned four remaining sprints into one.

**Three populations, one shape.** A nullable `programme` FK where **NULL means every gift**, a
picker where a person is looked at, and a narrowing — never a fence — on who is offered work.

| Who | Before | After |
|---|---|---|
| Sponsors | `SponsorProgrammeMembership` existed; the only writer hard-coded the flagship | Accept into any gift, take it back; the invitation carries the gift |
| Reviewers | **no field at all** | `PartnerAdmin.programme`; a picker; the assignment dropdown greys a mismatch |
| Sources | **no field at all** | `PartnerOrganisation.programme`; a picker on Sources |

**It is what blocked the RM100,000.** `record_admin_credit` refuses `sponsor_not_in_programme`
without an approved membership, and `sync_account_membership` could only ever write one against
`DEFAULT_PROGRAMME_CODE = 'brightpath-flagship'`. Recording a second gift's first credit needed a
developer with database access — the one thing the owner's acceptance test forbids.

Built in three commits so each half could be verified on its own: the backend (`adf471fe`), the
sponsor screens (`c208d8d5`), reviewers and sources (`6d38bc20`).

---

## What Went Well

**The three populations really were one shape, and building them that way held.** Same nullable
column, same "NULL = every gift", same permissive default with no backfill, same "flagged, never
filtered" treatment on every list. The third one took a fraction of the first because the
decisions were already made and written down.

**The fence guard did its job without being asked.** `AdminReviewerProgrammeView` was written,
and `test_org_fence.py` refused the build until it was classified. That is exactly the failure
mode it exists for — a new `_AdminBase` endpoint reaching an object with nobody remembering to
say how it is fenced — and it cost thirty seconds rather than a tenancy incident.

**Evidence replaced a guess without inventing a new mechanism.** `signup_programme_for` reads the
invitation the sponsor answered, then the platform's sole active gift, then returns None. None is
a real answer, and it is the same rule `resolve_open_cohort` already applies to a student's apply
link (PF-1). No new concept; an existing one extended to the money.

**The owner's own 2026-08-02 ruling was honoured rather than reversed.** The reviewer gift column
had been declined with a written trigger — *"it comes back when a second programme exists"* — and
the trigger had fired. So the column came back **and still renders only above one gift**, on
reviewers and on sources. The test that asserted its absence was rewritten in place with the
reason, not deleted.

---

## What Went Wrong

**1. Three tests from part one were broken and the report said the suite was green.**

*What happened.* At the end of part one I reported "45 existing sponsorship tests pass unmodified".
`test_sponsor_programme_membership.py` had three failures the whole time — two calling the removed
`sync_account_membership(sponsor, vetted_by=…)` signature, one asserting a membership that the new
resolver correctly declines to write.

*Why.* I ran the suites the work was **in** (`test_sponsor_into_gift.py`, the money suites, the org
fence) and reported that as the state of the project. It is the identical mistake the Sabah S2
close recorded three days ago — *"a test count is only a baseline if it was measured the same way
last time"* — arriving in its other form: not a wrong number, but a **wrong claim about what
passes**. A scoped run cannot report a suite-wide fact, and changing a shared function's signature
puts every caller in scope whether or not they are in the directory you are editing.

*Fix.* The existing lesson names the number and not the claim. Extended: **any statement of the
form "the existing tests pass" is a full-suite claim and needs a full-suite run**, and *"I changed
a shared signature"* is itself the trigger to run everything before saying anything.

**2. A bite-check anchor written with the wrong line ending, twice.**

*What happened.* Two bite-check scripts failed to find their anchor and reported "anchor missing" —
which reads exactly like *the code has moved*, i.e. like the fault I was probing for. Both were
line-ending mismatches: `officerCockpit.ts` is CRLF, `views_admin.py` is LF.

*Why.* I assumed one convention per repo. This repo has both, per file, and `newline=''` preserves
whatever is there verbatim — so the anchor silently matches nothing and the script's own failure
mimics a real finding.

*Fix.* Read the bytes before writing an anchor (`print(repr(t[i-80:i+120]))`), and treat "anchor
missing" as **unproven, never as evidence** — a bite that cannot be injected has told you nothing.
Both scripts now carry the warning at the anchor.

**3. A generated write put an Arabic mark into Tamil copy.**

*What happened.* The first message-file script emitted `٘` (an Arabic mark) where the Tamil
virama `்` belonged, inside a word in `giftsNote`. It parsed, passed i18n parity, and would
have rendered a broken glyph to a Tamil reader.

*Why.* The escape sequences were composed by hand at generation time, and no check looked at the
SCRIPT of what was written. The standing checklist item — *"never generate a regex, and sweep for
control bytes after any generated write"* — covers control bytes and stops one character class
short of this one.

*Fix.* Both later scripts scan for control bytes **and for characters outside the expected script
block** before finishing, and refuse rather than warn. The checklist item is widened from "control
bytes" to "bytes you did not intend, including the right character from the wrong alphabet".

---

## Design Decisions

Three logged in `docs/decisions.md`:

1. **NULL means every gift, with no backfill** — a permissive default cannot go stale the way
   migration `0123` did.
2. **One gift per person, not a list** — with two gifts "NULL = both" covers every case; the limit
   is unreachable until a third gift exists.
3. **A source's gift records intent and reaches no student yet** — shipped knowingly, with a test
   that fails on the day the apply form starts reading the registry.

---

## Numbers

| | Before | After |
|---|---|---|
| pytest (full `apps/`) | 5800 | **5844** |
| jest | 1666 | **1692** |
| tsc errors | 24 | **24** (baseline, TD-221) |
| lint errors | 0 | **0** |
| i18n keys × 3 | 4722 | **4745** |
| Migrations | courses 72 / scholarship 148 | **courses 73 / scholarship 149** |

**Production, measured before the push:** 21 staff, 10 organisations, 20 invitations — **0 of each
carry a gift**, so NULL means every gift everywhere and the deploy changed no behaviour.

Live smoke after: all public routes 200, `Server: Google Frontend`, both new endpoints 401 to a
stranger, no error logs.
