"""Add new SPM-entry programmes to the course catalogue from a REVIEWED JSON file (Bumi Sprint D1).

Two steps, the second DRY RUN by default:

    # 1. build the human-reviewable file from a scrape (no database access)
    python manage.py ingest_spm_courses --build-from-csv data/spm/mohe_bumi_2026-10-29.csv \\
        --prefix UE --out data/spm/spm_new_courses_D1.json
    # 2. read it back: prints what it WOULD create / update; nothing is written
    python manage.py ingest_spm_courses --file data/spm/spm_new_courses_D1.json --institution-id <id>
    #    ... and only after the review and the read-only checks:
    python manage.py ingest_spm_courses --file data/spm/spm_new_courses_D1.json --institution-id <id> --apply

`--apply` writes `Course` + `CourseRequirement` + ONE `CourseInstitution` per course with
`update_or_create` (so a re-run is idempotent), all in one transaction. Owner ruling 2026-10-29:
each course links to ONE parent institution (`--institution-id`, which must already exist);
campuses come later. Rows in the file's `flagged` list (parser could not represent them
faithfully, `spm_syarat.py`) are never written. `field_key` must name a `FieldTaxonomy` row.

ORDER ON PRODUCTION: migration courses/0088 first, then the deploy that carries the engine's
Bumiputera gate, THEN `--apply` — an image without the gate would show the UiTM rows to everyone.
The running instances hold the eligibility frame in memory, so they see the new rows only after
their next start (a redeploy or a new revision).
"""
import csv
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.courses.models import (
    Course, CourseInstitution, CourseRequirement, FieldTaxonomy, Institution,
)
from apps.courses.spm_catalogue_rows import build_entry

COURSE_FIELDS = ('course', 'level', 'department', 'field', 'semesters')


class Command(BaseCommand):
    help = 'Add new SPM programmes from a reviewed JSON file (dry run unless --apply)'

    def add_arguments(self, parser):
        parser.add_argument('--file', help='The reviewed JSON file to ingest')
        parser.add_argument('--institution-id', help='The ONE parent Institution every course links to')
        parser.add_argument('--apply', action='store_true', help='Write (default: report only)')
        parser.add_argument('--build-from-csv', help='Build the review file from a scraped CSV instead')
        parser.add_argument('--prefix', default='', help='With --build-from-csv: only course ids with this prefix')
        parser.add_argument('--out', help='With --build-from-csv: where to write the review file')

    def handle(self, *args, **options):
        if options['build_from_csv']:
            return self._build(options['build_from_csv'], options['prefix'], options['out'])
        if not options['file']:
            raise CommandError('Pass --file <json> (or --build-from-csv <csv> --out <json>).')
        with open(options['file'], encoding='utf-8') as f:
            data = json.load(f)
        courses = data.get('courses', [])
        self._check(courses, options['institution_id'], options['apply'])
        for entry in courses:
            exists = Course.objects.filter(course_id=entry['course_id']).exists()
            self.stdout.write(f"{'UPDATE' if exists else 'CREATE'} {entry['course_id']} "
                              f"{entry['course']} | {entry['field_key']} | "
                              f"bumi={entry['requirement'].get('req_bumiputera')} "
                              f"merit={entry['requirement'].get('merit_cutoff')}")
        flagged = data.get('flagged', [])
        self.stdout.write(f'{len(courses)} courses in the file; {len(flagged)} flagged rows NOT ingested: '
                          + ', '.join(f['course_id'] for f in flagged))
        if not options['apply']:
            self.stdout.write(self.style.NOTICE('DRY RUN: nothing written. Re-run with --apply.'))
            return
        with transaction.atomic():
            for entry in courses:
                self._write(entry, options['institution_id'])
        self.stdout.write(self.style.SUCCESS(f'Applied {len(courses)} courses.'))

    def _check(self, courses, institution_id, apply):
        """Refuse a file that is not safe to write, before anything is written."""
        problems = [f"{e['course_id']}: unparsed {e['unparsed']}" for e in courses if e.get('unparsed')]
        known = set(FieldTaxonomy.objects.values_list('key', flat=True))
        problems += [f"{e['course_id']}: field_key {e['field_key']!r} is not a FieldTaxonomy key"
                     for e in courses if e['field_key'] not in known]
        if not institution_id:
            problems.append('--institution-id is required (owner ruling: ONE parent institution)')
        elif not Institution.objects.filter(institution_id=institution_id).exists():
            problems.append(f'Institution {institution_id!r} does not exist')
        if problems:
            report = 'Refusing to ingest:\n  ' + '\n  '.join(problems)
            if apply:
                raise CommandError(report)
            self.stdout.write(self.style.WARNING(report))

    @staticmethod
    def _write(entry, institution_id):
        course, _ = Course.objects.update_or_create(
            course_id=entry['course_id'],
            defaults={**{k: entry[k] for k in COURSE_FIELDS}, 'field_key_id': entry['field_key']},
        )
        # Every flag the file does not set is written False, so a re-run after a review edit can
        # also CLEAR a flag (update_or_create only touches the fields it is given).
        flags = {f.name: False for f in CourseRequirement._meta.get_fields()
                 if f.get_internal_type() == 'BooleanField'}
        CourseRequirement.objects.update_or_create(course=course, defaults={**flags, **entry['requirement']})
        CourseInstitution.objects.update_or_create(
            course=course, institution_id=institution_id,
            defaults={'hyperlink': entry.get('mohe_url', '')},
        )

    def _build(self, csv_path, prefix, out):
        if not out:
            raise CommandError('--build-from-csv needs --out <json>.')
        with open(csv_path, encoding='utf-8') as f:
            rows = [r for r in csv.DictReader(f) if r['course_id'].startswith(prefix)]
        entries = [build_entry(r) for r in rows]
        clean = [e for e in entries if not e['unparsed']]
        flagged = [{'course_id': e['course_id'], 'course': e['course'], 'reasons': e['unparsed'],
                    'source': e['source']} for e in entries if e['unparsed']]
        for e in clean:
            del e['unparsed']
        with open(out, 'w', encoding='utf-8', newline='\n') as f:
            json.dump({'built_from': csv_path, 'prefix': prefix,
                       'parser': 'apps/courses/spm_syarat.py (count-once: spm_count_once.py)',
                       'courses': clean, 'flagged': flagged}, f, ensure_ascii=False, indent=1)
            f.write('\n')
        self.stdout.write(f'{len(rows)} rows: {len(clean)} parsed, {len(flagged)} flagged -> {out}')
        for item in flagged:
            self.stdout.write(f"  FLAGGED {item['course_id']}: {'; '.join(item['reasons'])}")
