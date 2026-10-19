# Retrospective — sources and referral partners, Sprints B, C and D, and the arc (2026-10-19)

Roadmap: `docs/plans/2026-10-09-sources-and-referrals-roadmap.md` (marked complete). Decisions:
`docs/decisions.md` 2026-10-09 (the two columns), 2026-10-18 (sources become their own table),
2026-10-19 (each application keeps its own answer) and 2026-10-19 (Sprint D). Sprint A has its own
retrospective (`retrospective-2026-10-18-sources-a.md`). Cutovers: `sources-b-cutover-sql.md`,
`sources-c-cutover-sql.md`, `sources-d-cutover-sql.md` (all in `docs/scholarship/`).

| Sprint | What | Live |
|---|---|---|
| A | Two independent columns on the student; referral partners marked | 2026-10-18 (`bfa547d9`, `4570eb8f`) |
| B | Sources become their own table, owned by an organisation; the fence; invites refuse | 2026-10-19 (`bbe6fac6`, api-01122-nw4; then 0080 by the owner) |
| C | Each application keeps its own answer; witness = the application's source, super only | 2026-10-19 (`e90179c6`, api-01123-nbw / web-00973-rdj) |
| D | Clean-up: the bursary writes nothing on the profile; old rows off; referral-partner path | BUILT 2026-10-19, not yet live |

## What Was Built

**The arc's result.** One table that held three things in three moods (`partner_organisations`:
tenants, sources, referral partners) became three categories that never write each other:
- **ORGANISATIONS** — `PartnerOrganisation.objects.tenants()`, unchanged.
- **SOURCES** — `referral_sources` (`ReferralSource`), OWNED by an organisation, fenced on every
  surface (Sprint B); the student's answer lives on EACH APPLICATION (`referral_code` / `source`,
  Sprint C), and every bursary reader — partner emails, milestones, Sources counts, the Applications
  filter, the cockpit pill, the witness — reads it there.
- **REFERRAL PARTNERS** — `partner_organisations` rows marked `is_referral_partner` (CUMIG), owned by
  nobody; a `?ref=` link writes `referred_by_org` and the course-selector chip, first touch; a super
  marks and unmarks them (Sprint D, API only).

**Sprint B** — copied every source row into the new table KEEPING ITS ID, so five foreign keys moved
by constraint swaps (no value rewritten); fenced Sources, gift Configuration, partner emails and the
witness choice by the owning organisation; invites REFUSE rather than mark; TD-379's column dropped
image-first.

**Sprint C** — `ScholarshipApplication.referral_code` + `.source`, written once at submit from the
request and resolved inside the application's own organisation; every chip reader moved; a
source-names endpoint for every list role; the witness is the application's source and only a super
records it; `?ref` never pre-fills the bursary form.

**Sprint D** — (1) the bursary submit writes NO referral column on the profile; (2)
`StudentProfile.source` left the model (courses 0082, image-first, owner-run, with a backup); (3) the
chip is re-scoped to the course selector's `?ref=` code — no bursary answer reaches a referral
partner's Source column any more; (4) the cockpit's old `referred_by_org` key removed, api and web;
(5) the sources' old rows switched off, never deleted (courses 0081, migrate-first), and
`partner_organisations.show_in_apply` given a database default and then dropped; (6) the super-only
referral-partner list / mark / unmark API; the screen is TD-387.

## What Went Well

- **The ids-preserving copy (B) made everything after it cheap.** Five FKs moved without a data
  rewrite, the old image kept working through the window, and C and D could each be a short
  additive step plus an image-first contract.
- **Every cutover read its expected values at apply time.** B's copy found 15 sources (the 10-18
  reading said 13 — GSS and TIC had been added); C's backfill 249 / 124 / 0 mismatched / 0 cross-org.
  The lessons.md 2026-10-09 rule ("read the expected result at cutover") turned both differences into
  non-events.
- **Expand-contract held for four sprints with no 5xx.** Each drop ran after its image served.
- **The adversarial reviews found the real seams** — B's: an `org_admin` invite could turn a source's
  old row into a second tenant, and three cross-organisation seams (TD-386); C's: backlog milestone
  emails, a `?ref` code becoming an application's answer, a witness with no organisation. All fixed
  before their pushes.
- **Bite-checks every sprint** (B 18, C 17, D 12): each named rule broken on purpose turned its test
  red, and bytes were restored and verified by digest.

## What Went Wrong

1. **Sprint D found a leak the earlier sprints walked past: the bursary answer on the partner's
   Source column.** Symptom: CUMIG's `partner` logins see a Source column (the chip); since Sprint A
   the bursary submit wrote its answer there, so a `?ref=cumig` student who named SMC showed "smc" to
   CUMIG. Root cause: Sprint A's rule was "a bursary answer never puts a student ON the partner's
   list" — the list's membership (`referred_by_org`), not the list's columns. The chip was left with
   two writers "for the course-selector readers", and nobody asked what the partner's own screen
   showed from it. Fix (Sprint D): the bursary no longer writes the chip, and — after the review
   found the existing case (production: 1 of CUMIG's 254 showed `social`) — courses 0081 aligns every
   referral partner's student's chip to the partner's code after a dated backup; tests pin that the
   partner login sees the `?ref` code and never the bursary answer, for new and existing students. System change: when a rule says
   "X must never reach role R", the test is written against R's SCREEN PAYLOAD (every column it
   serves), not against the query that selects its rows. (lessons.md 2026-10-19.)
2. **A column dropped from the model had no database default — caught by reading the DDL, not by a
   test.** Symptom: `partner_organisations.show_in_apply` is `NOT NULL` with only a Python default, so
   the Sprint D image (which no longer names it) would have failed EVERY insert into
   `partner_organisations` — a partner invite creating a referral partner, the organisation form
   creating a tenant — between the deploy and the drop. Root cause: TD-379's drop (B) was a NULLABLE
   column, so "remove from the model, deploy, drop" was safe there and was copied as the pattern. No
   test can see it: the test database runs 0082 too, so the column is already gone. Fix: courses 0081
   adds `DEFAULT false` migrate-first; a structural test pins that the expand carries the default and
   the contract follows it. System change: before removing a field from a model ahead of its drop,
   read the LIVE column's nullability and default; a `NOT NULL` column without a database default
   gets one migrate-first. (lessons.md 2026-10-19.)
3. **The roadmap's "retire the chip" was not reachable as written.** The chip has a live reader the
   roadmap itself told every sprint not to break (CUMIG's list / CSV). Sprint D re-scoped it instead
   (one meaning, one writer) and says so in the roadmap and decisions.md. System change: none beyond
   the usual — a roadmap item that retires a column lists the column's readers first.
4. **The referral-partner screen moved twice and still is not built** (B → D → TD-387). Each time the
   API half was cheap and the screen half met a rule (Stitch first; en.json at its bundle line). It
   is the right outcome, but the roadmap should have split "the rule" from "the screen" from the
   start.
5. **Sprint D retired six tests** (0173's production-shaped copy) because they ran a migration's data
   step against the live models. Sprint B retired 0078's for the same reason. System change: a data
   migration's test runs it against the migration's OWN historical apps (`MigrationExecutor`
   project state) or is written knowing it will be retired once its inputs leave the model — say which
   in the test's docstring.

## Design Decisions

See decisions.md. The Sprint D ones: the chip is re-scoped rather than retired (its only reader is
the partner dashboard, and it can carry `?ref` codes that are not referral partners); `source_twin`
stays (the invite refusal still needs "is this a source's old row?" after the rows are off) and
reaches `ReferralSource` through the app registry; `StudentProfile.source` is dropped rather than left
(a live FK nobody owns); an unmark waits for the partner logins to be revoked.

## Numbers

| Sprint | pytest (passed, `-n auto`) | jest | Bite-checks | Migrations |
|---|---|---|---|---|
| B | 8347 → 8374 | 4245 | 18 | scholarship 0173 + courses 0079 migrate-first; courses 0080 image-first (owner) |
| C | 8384 → 8410 | 4255 → 4266 | 17 | scholarship 0174 migrate-first |
| D | 8410 → 8410 (+10 new, 6 retired, 4 merged); subtests 3567 → 3569 | 4266 → 4266 | 12 | courses 0081 migrate-first; courses 0082 image-first (owner) |

Sprint D bundle: median 228.527 → 228.528 kB, worst 273.495 → 273.496 kB (no strings added). Sprint D
api sizes: `profile_sync.py` 189 → 176, `serializers_admin.py` 1230 → 1225, `referral_links.py` 182 →
220, new `views_referral_partners.py` 76. Live figures for D are appended when it ships.
