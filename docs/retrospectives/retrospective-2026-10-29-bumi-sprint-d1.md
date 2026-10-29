# Retrospective — Bumi coverage Sprint D1 (UiTM SPM courses, foundations) — 2026-10-29

Live in `f5282643` (api-01182-shl then the ingest re-revision api-01183-jll; web-01015-vcw). Migration
`courses/0088` applied migrate-first. 84 UiTM rows ingested; 3 flagged rows wait for D2.

## What Was Built

- `CourseRequirement.req_bumiputera` + the SPM engine gate; the five SPM doors (eligibility, both
  scholarship pickers forced to `bumiputera: true`, search + pick-lists, course page row).
- `scrape_mohe_stpm --with-syarat-am`; the Syarat Am + Khas parser (`spm_syarat.py`); the
  `count_once` construct (a matching); `ingest_spm_courses` (dry run by default).
- Moves-only splits first: `engine_merit.py`, `models_course_tag.py`, `views_stpm_quiz.py`.

## What Went Well

- **Plan, owner questions, build, two review rounds, deploy, live smoke — in one day, with no rework
  after the push.** The planner's door list went into the builder's brief AND the reviewer's brief,
  so round 1 found the doors that were NOT on it (partner-admin inference, old web bundles) rather
  than re-finding the listed ones.
- **Flag, never guess.** 3 of 87 rows (ATAU; "A- in ONE AND B in THREE") were held back instead of
  being approximated. The old catalogue's hand approximations (e.g. UZ0520001) are what this avoided.
- **The golden master was made a proof, not a count:** the original 389 courses are frozen by id
  digest and per-student set digest, so "5,319" now means "identical", not "same total".
- **Deploy order held.** Migrate, push, wait for BOTH revisions at 100%, dry run (84 CREATE, 0 UPDATE),
  apply, re-revision, smoke. The smoke checked all three people who matter: non-Bumi (0 UiTM), Bumi
  (81), foreigner answering yes (0).

## What Went Wrong

1. **A first-fit-style double count reached the new data.** *What:* "Sains Pertanian" and "Pertanian"
   fold to one engine key, so a "DUA (2)" clause counted one grade twice (UE4621001, UE4620002).
   *Why:* Sprint C fixed count-once on the STPM side only; the SPM `or_groups` loop still counted
   listed codes, and no SPM row had ever listed one key twice — until a parser produced one.
   *Fix:* the SPM loop counts distinct student subjects and the parser emits each key once; the
   reviewer proved no original row lists a key twice, so the change is a no-op there. Lesson below.
2. **The first reading of "belum diambil kira" made those clauses empty.** *What:* BM and Sejarah from
   Syarat Am always filled the "N more" slots, so ten UiTM rows asked for nothing extra. *Why:* the
   builder read Am and Khas as independent and "selain di atas" as "not used"; a clause every applicant
   meets automatically is the tell that a reading is wrong. *Fix:* owner ruled the strict reading;
   regression tests on the real rows. Lesson below.
3. **I ran `git pull` in the shared main checkout.** *What:* it merged another session's unpushed
   commit and conflicted. *Why:* habit from single-session work. *Fix:* aborted at once and told the
   owning session; the rule "work only in worktrees, never pull in the shared checkout" is already in
   `lessons.md` (two sessions, one checkout) — I did not apply it. No new lesson; the existing one
   stands.
4. **The first rollback DELETE would have aborted.** *Why:* Postgres has no cascade here (Django's
   CASCADE is Python-side), and `saved_courses`, `admission_outcomes`, `course_tags` point at `courses`.
   *Fix:* the docstring and CLAUDE.md delete those first.

## Design Decisions

- Strict reading of "belum diambil kira / selain di atas" (owner, decisions.md 2026-10-29).
- Partner-admin inference of the Bumi answer from a saved course accepted (owner, decisions.md).
- One parent institution per UiTM course; campuses later (owner).
- `count_once` lives inside `complex_requirements` JSON — no migration.

## Bite-checks (step 4b)

The golden-master digest tests, the count-once order tests and the strict-reading regression tests were
each turned red by the reviewer's probes before the fixes and green after (probe scripts in the
session scratchpad). No separate injection was run at close.

## Numbers

- 10,091 pytest / 3 skipped (`-n auto`, the gate's command) · 4,875 jest / 311 suites · tsc 0.
- Golden masters: original 389 = 5,319 identical; full bumi=False 5,319; bumi=True 5,865; STPM 2,025.
- Bundle median 146.3 / 148 kB.

## Follow-ups (D2)

- The other 63 SPM courses, the 2 Bumi Matrikulasi tracks, the 3 flagged UiTM rows (ATAU, "A- in ONE
  AND B in THREE").
- Search page: a Bumi student's pick-lists load once with `bumi=false` and never refresh (no leak the
  other way). One-line fix; needs a test harness for `search/page.tsx` — do it in D2.
- 4 farm subjects in UE4621001 / UE4620002 have no engine key, so they are dropped from the any-of lists.
- Prod has 2 MOHE-coded rows the fixture lacks (UL0481001, FB0500001) — not Bumi; reconcile in D2.
