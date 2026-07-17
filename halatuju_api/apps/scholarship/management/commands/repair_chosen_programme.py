"""Repair mis-slotted ``chosen_programme`` values from ALREADY-STORED fields — the residual
correction path for offer-extraction faults (app #125: an institution name in the course slot,
a "Tarikh dan Masa Daftar…" line in the institution slot; app #47: a bare numbered-clause header
"2.4."/"2.5." latched as the stream/institution value).

**NEVER re-runs Vision/Gemini** (standing rule: local re-extraction destroys ``vision_fields``).
It only re-reads the stored ``chosen_programme`` + the catalogue, applying the same
``card_display`` sanity/resolution the read-side uses, and fills ``reporting_date`` from a
mis-slotted date when currently null.

Scope: ONLY the corruption signature (a date/'Tarikh' or clause-number institution, or an
institution-shaped / date-shaped / clause-number course name). A secondary-school name in the
institution slot is LEFT ALONE — it is
legitimate officer data; the sponsor-card school-block (card_display.resolve_institution) keeps
it off sponsor cards at read time. This command never deletes a school.

    python manage.py repair_chosen_programme            # report only (default, no writes)
    python manage.py repair_chosen_programme --apply     # perform the reported repairs
"""
from django.core.management.base import BaseCommand

from apps.scholarship import card_display
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.pathway_engine import parse_reporting_date


def propose_repair(app):
    """Return ``{course_name, institution, reporting_fill}`` when the row's chosen_programme is
    CORRUPT (junk course/institution), else None. Derived from stored fields + catalogue only."""
    cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
    course_name = (cp.get('course_name') or '').strip()
    institution = (cp.get('institution') or '').strip()
    course_id = (cp.get('course_id') or '').strip()

    course_bad = bool(course_name) and (card_display.looks_like_institution(course_name)
                                        or card_display.looks_like_date(course_name)
                                        or card_display.looks_like_clause_number(course_name))
    inst_is_date = bool(institution) and card_display.looks_like_date(institution)
    inst_bad = inst_is_date or (bool(institution) and card_display.looks_like_clause_number(institution))
    if not (course_bad or inst_bad):
        return None  # not the corruption signature (school-in-institution is handled read-side)

    # Recover the institution: the institution-shaped course_name IS the real institution;
    # else the current institution when it isn't a date; else the catalogue single institution.
    new_inst = ''
    if course_bad and card_display.looks_like_institution(course_name):
        new_inst = course_name
    elif institution and not inst_bad:
        new_inst = institution
    else:
        new_inst = card_display.catalogue_single_institution(course_id)
    if card_display.looks_like_school(new_inst):
        new_inst = ''

    # Recover the programme name: catalogue via course_id; else the current name only if sane.
    new_course = card_display.catalogue_course_name(course_id)
    if not new_course and course_name and not course_bad and not card_display.looks_like_school(course_name):
        new_course = course_name

    reporting_fill = None
    if inst_is_date and app.reporting_date is None:
        reporting_fill = parse_reporting_date(institution)

    if new_course == course_name and new_inst == institution and reporting_fill is None:
        return None
    return {'course_name': new_course, 'institution': new_inst, 'reporting_fill': reporting_fill}


class Command(BaseCommand):
    help = 'Repair mis-slotted chosen_programme from stored fields (report; --apply to write). No re-extraction.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Perform the reported repairs (default is report only).')

    def handle(self, *args, **opts):
        apply = opts['apply']
        qs = (ScholarshipApplication.objects
              .exclude(chosen_programme={})
              .select_related('profile').order_by('id'))
        repaired = 0
        for app in qs:
            rep = propose_repair(app)
            if not rep:
                continue
            repaired += 1
            cp = app.chosen_programme if isinstance(app.chosen_programme, dict) else {}
            self.stdout.write(f'\n#{app.id} ({app.status})')
            self.stdout.write(f'  course_name : {cp.get("course_name","")!r} -> {rep["course_name"]!r}')
            self.stdout.write(f'  institution : {cp.get("institution","")!r} -> {rep["institution"]!r}')
            if rep['reporting_fill'] is not None:
                self.stdout.write(f'  reporting_date: (null) -> {rep["reporting_fill"].isoformat()}')
            if apply:
                new_cp = dict(cp)
                new_cp['course_name'] = rep['course_name']
                new_cp['institution'] = rep['institution']
                new_cp['source'] = 'repair_chosen_programme'
                app.chosen_programme = new_cp
                fields = ['chosen_programme']
                if rep['reporting_fill'] is not None:
                    app.reporting_date = rep['reporting_fill']
                    fields.append('reporting_date')
                app.save(update_fields=fields)

        verb = 'Repaired' if apply else 'Would repair'
        self.stdout.write(self.style.SUCCESS(f'\n{verb} {repaired} application(s).'
                          + ('' if apply else '  (report only — pass --apply to write.)')))
