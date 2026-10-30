"""Bring the held UP_TVET courses' three gate flags and remarks in line with their pages (Bumi F1b).

    # build the reviewed file (pure; a test rebuilds it from the committed source). The fixture now
    # carries the file's `new`, so a rebuild names the file it was built against:
    python manage.py fix_held_tvet_flags --build --out data/tvet/held_flag_fix_F1b.json \\
        --fixture-before data/tvet/held_flag_fix_F1b.json
    # the read-only prod check BEFORE the push (prints SQL; returns only rows that differ from `old`)
    python manage.py fix_held_tvet_flags --file data/tvet/held_flag_fix_F1b.json --sql
    # read it back against the database: prints each course's flag old -> new; nothing is written
    python manage.py fix_held_tvet_flags --file data/tvet/held_flag_fix_F1b.json
    #    ... then the same with --apply.  ROLLBACK: --reverse --apply (new -> old, same checks).

No migration. `--apply` writes ONE transaction and only `req_malaysian` / `no_colorblind` /
`no_disability` / `remarks`, and only a field whose `old` differs from its `new`. COMPARE-AND-SET: the
whole run is refused, with every mismatch printed, if a listed course does not exist, is not a held TVET
id (IJTM- / IKBN-), is listed twice, or any of its four fields in the database differs from the file's
`old` (`new` under `--reverse`). A course or column the file does not list is never
read for writing, let alone written. The running instances hold the eligibility frame in memory, so a
re-revision follows the write. Rules and the build: `apps/courses/tvet_held_flags.py`; runbook:
halatuju_api/CLAUDE.md ("Bumi F1b order").
"""
import json
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.courses.management.commands.ingest_tvet_courses import (
    held_courses_from_fixtures, load_held_links, write_json,
)
from apps.courses.models import CourseRequirement
from apps.courses.tvet_held_flags import FIELDS, before_fix, build_flag_fix, changes, check_sql

TVET = os.path.join('data', 'tvet')


class Command(BaseCommand):
    help = "Set the held UP_TVET courses' gate flags and remarks from a reviewed file (dry run unless --apply)"

    def add_arguments(self, parser):
        parser.add_argument('--file', help='The reviewed fix file')
        parser.add_argument('--apply', action='store_true', help='Write (default: report only)')
        parser.add_argument('--reverse', action='store_true', help='Roll back: write old over new')
        parser.add_argument('--build', action='store_true', help='Build the fix file (needs --out)')
        parser.add_argument('--sql', action='store_true',
                            help="Print the read-only prod check (rows whose flags differ from the file's "
                                 '`old`, or `new` with --reverse; a missing course too). No database access.')
        parser.add_argument('--source', default=os.path.join(TVET, 'uptvet_F1_source.json'))
        parser.add_argument('--held-links', default=os.path.join(TVET, 'held_tvet_links.json'))
        parser.add_argument('--f1-review', default=os.path.join(TVET, 'tvet_new_courses_F1.json'))
        parser.add_argument('--out', help='Where --build writes')
        parser.add_argument('--fixture-before', help="--build after the fixture took a fix file's `new`: "
                                                     "rebuild against that file's `old` (the test does the same)")

    def handle(self, *args, **options):
        if options['build']:
            return self._build(options)
        if not options['file']:
            raise CommandError('Pass --file <json>, or --build --out <json>.')
        with open(options['file'], encoding='utf-8') as f:
            fix = json.load(f)
        if options['sql']:
            return self.stdout.write(check_sql(fix, options['reverse']))
        self._fix(fix, options['apply'], options['reverse'])

    def _build(self, options):
        if not options['out']:
            raise CommandError('--build needs --out <json>.')
        with open(options['source'], encoding='utf-8') as f:
            source = json.load(f)
        with open(options['held_links'], encoding='utf-8') as f:
            prod_links = json.load(f)['links']
        with open(options['f1_review'], encoding='utf-8') as f:
            f1_new = [x for x in json.load(f)['held_links'] if not x['already_linked']]
        held = held_courses_from_fixtures()
        if options['fixture_before']:
            with open(options['fixture_before'], encoding='utf-8') as f:
                held = before_fix(held, json.load(f))
        fix = build_flag_fix(source, load_held_links(options['held_links']), prod_links, f1_new, held)
        write_json(options['out'], fix)
        for flag, n in fix['counts']['per_flag'].items():
            self.stdout.write(f"{flag}: {n['false_to_true']} false->true, {n['true_to_false']} true->false, "
                              f"{n['unchanged']} unchanged, {n['conflict']} conflict")
        self.stdout.write('remarks: ' + ', '.join(f'{k} {v}' for k, v in fix['counts']['remarks'].items()))
        self.stdout.write(f"{fix['counts']['courses']} courses ({fix['counts']['campus_pages']} campus pages); "
                          f"{fix['counts']['no_page_courses']} held courses with no page (unchanged); "
                          f"{fix['counts']['not_applied']} out-of-scope differences listed -> {options['out']}")

    def _fix(self, fix, apply, reverse):
        courses = fix.get('courses', [])
        expected = {c['course_id']: (c['new'] if reverse else c['old']) for c in courses}
        todo = changes(fix, reverse=reverse)
        with transaction.atomic():
            rows = {r['course_id']: r for r in CourseRequirement.objects.select_for_update()
                    .filter(course_id__in=list(expected)).values('course_id', *FIELDS)}
            problems = [f'{cid}: no such course requirement' for cid in sorted(set(expected) - set(rows))]
            if len(expected) != len(courses):
                problems.append('the file lists a course more than once')
            problems += [f'{cid}: not a held TVET course id (IJTM- / IKBN-)' for cid in sorted(expected)
                         if not cid.startswith(('IJTM-', 'IKBN-'))]
            for cid in sorted(set(expected) & set(rows)):
                for flag in FIELDS:
                    if rows[cid][flag] != expected[cid][flag]:
                        problems.append(f'{cid}.{flag}: database has {rows[cid][flag]!r}, the file expects '
                                        f'{expected[cid][flag]!r}')
            if problems:
                for problem in problems:
                    self.stderr.write(problem)
                raise CommandError(f'Refusing: {len(problems)} mismatch(es) between the file and the database; '
                                   'nothing written.')
            for cid, flag, before, after in todo:
                self.stdout.write(f'{cid} {flag}: {before!r} -> {after!r}')
            self.stdout.write(f"{len(todo)} field change(s) on {len({c for c, *_ in todo})} course(s); "
                              f"{len(courses)} courses checked{' (REVERSE)' if reverse else ''}.")
            if not apply:
                self.stdout.write(self.style.NOTICE('DRY RUN: nothing written. Re-run with --apply.'))
                return
            by_course = {}
            for cid, flag, before, after in todo:
                by_course.setdefault(cid, {})[flag] = after
            for cid, values in by_course.items():
                # Compare-and-set again in the UPDATE itself: the row must still hold every expected value.
                held = {flag: expected[cid][flag] for flag in FIELDS}
                written = CourseRequirement.objects.filter(course_id=cid, **held).update(**values)
                if written != 1:
                    raise CommandError(f'{cid}: changed under us; rolled back, nothing written.')
        self.stdout.write(self.style.SUCCESS(f'Applied {len(todo)} field change(s) on {len(by_course)} course(s). '
                                             'Now re-revision halatuju-api so the eligibility frame reloads.'))
