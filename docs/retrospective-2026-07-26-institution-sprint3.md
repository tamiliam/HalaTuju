# Retrospective — Institution must-fill, Sprint 3: sponsor surface parity (2026-07-26)

Final sprint of `docs/plans/2026-07-25-institution-must-fill-roadmap.md`. Backend + one frontend
link. No migration. **No data insert** — which is the finding worth keeping.

## What was built

- `card_display.course_href(app)` + `course_href` on the sponsor pool card/detail allowlist; the
  programme name on the sponsor DETAIL page is now a link to its public HalaTuju course page.
- One specialisation format everywhere (owner D2): ` · `, matching the cockpit.
- The catalogue resolvers can now see the **post-STPM catalogue**, which is what #132/#136 actually
  needed.

## The item that dissolved on investigation

The roadmap said: *"Catalogue `course_institutions` rows for #132 (UUM law) and #136 (UPSI education)
— a courses-app data fix, migrate-first if it needs one."* I had classified them as courses with zero
campus links.

Querying first showed `UU6380001` and `UA6145019` are **not in the `courses` table at all**. They are
`stpm_courses` rows — the separate post-STPM catalogue — each already carrying its university and an
`institution_id`. The trailing `#` in their stored names ("Sarjana Muda Undang-Undang dengan Kepujian
#") was the tell I had read past twice: that is e-Panduan's STPM data, not SPM catalogue data.

So there was no missing data. `_campus_rows` and `catalogue_course_name` only ever queried the SPM
side, so every STPM-degree student read as a catalogue gap. Teaching both resolvers about
`StpmCourse` fixes the class, with **no production write at all** — and because a `StpmCourse` row is
one programme at one university by construction, the single-campus rule then applies natively, so
their institution and tick resolve on the next read with nothing else to do.

Two rows of data entry would have looked like a fix and left every future STPM-degree applicant
broken. The general habit: when a plan says "add the missing rows", verify the rows are missing from
the table you think they are missing from.

## Two duplicates removed — both mine, from the day before

`card_display.catalogue_single_institution` and `offer_pathway.sole_catalogue_institution` were
separate implementations of "the single campus for this course"; and `sole_catalogue_institution`
carried its own `CourseInstitution` query instead of using `_campus_rows`, the helper in the same
module. Either divergence would have let the STPM fix land in one function and not the other — which
is exactly the failure mode of yesterday's regression, and exactly the lesson written that day. It
took finding it a third time to apply it. All three call sites now route through one definition.

## What went wrong

Nothing broke, but two things are worth recording:

1. **I planned a data fix from an unverified premise.** The roadmap's "catalogue gap" classification
   came from `CourseInstitution` returning zero rows, which I read as "the links are missing" rather
   than "this course isn't in this catalogue". Root cause: I inferred a cause from one query's
   absence of results. Fix: the by-cause report in `backfill_institution` now has a genuinely
   distinct cause for it — but the durable fix is the habit, recorded in lessons.
2. **The duplicate-definition lesson didn't transfer to its own author within 24 hours.** I wrote
   "two functions answering the same question must share the predicate" on 2026-07-26 morning and
   found two more instances of it in my own 2026-07-25 code that afternoon. Recorded as a checklist
   item rather than a principle: when adding a catalogue lookup, grep the module for an existing one.

## Numbers

+14 pytest, +2 jest; `makemigrations --check` clean; `next build` clean. No migration, no data write.

## Deliberate non-change

The programme link is **not** on the sponsor browse card. That card is already a `<Link>` to the
detail page; a nested anchor is invalid HTML and would steal the card's click. Linking the detail
page's heading is both correct and better UX — the card navigates to the student, the heading
navigates out to the course.
