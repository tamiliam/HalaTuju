"""Add new SPM-entry programmes to the course catalogue from a REVIEWED JSON file (Bumi Sprints D1, D2).

Two steps, the second DRY RUN by default:

    # 1. build the human-reviewable file from a scrape (no database access)
    python manage.py ingest_spm_courses --build-from-csv data/spm/mohe_bumi_2026-10-29.csv \\
        --prefix UE --out data/spm/spm_new_courses_D1.json                      # D1: by id prefix
    python manage.py ingest_spm_courses --build-from-csv data/spm/mohe_bumi_2026-10-29.csv \\
        --ids-file data/spm/spm_new_courses_D2.ids --out data/spm/spm_new_courses_D2.json   # D2
    # 2. read it back: prints what it WOULD create / update; nothing is written
    python manage.py ingest_spm_courses --file data/spm/spm_new_courses_D1.json --institution-id <id>
    python manage.py ingest_spm_courses --file data/spm/spm_new_courses_D2.json --create-institutions
    #    ... and only after the review and the read-only checks, the same with --apply.

`--apply` writes `Course` + `CourseRequirement` + ONE `CourseInstitution` per course with
`update_or_create` (so a re-run is idempotent), all in one transaction. Owner ruling 2026-10-29:
each course links to ONE parent institution, campuses later. The parent is the entry's own
`institution_id` (D2 files carry one per row, `spm_catalogue_rows.INSTITUTION_IDS`) or, for a file
without it (D1), `--institution-id`; an entry whose `institution_id` is null (a synthetic matric
row) gets no link. Every parent must already exist, EXCEPT one the file proposes under
`new_institutions` — that is created only with `--create-institutions` (and `--apply`), only when
no row has that id, and the dry run prints it first. Never silently. Rows in the file's `flagged`
list (parser could not represent them faithfully, `spm_syarat.py`) are never written.
`field_key` must name a `FieldTaxonomy` row.

ORDER ON PRODUCTION (D1): migration courses/0088 first, then the deploy that carries the engine's
Bumiputera gate, THEN `--apply`. D2 needs no migration, but its rows use the D2 engine (`any_of`
count-once groups) and the two Bumi matric tracks need the D2 `pathways.py`, so: deploy first,
confirm the api AND web revisions serve 100%, THEN dry run, `--create-institutions --apply`, and a
re-revision. The running instances hold the eligibility frame in memory, so they see the new rows
only after their next start (a redeploy or a new revision). Runbook + rollback: halatuju_api/CLAUDE.md.
"""
import csv
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.courses.catalogue_ingest import CatalogueIngestMixin, _parent
from apps.courses.models import Course, Institution
from apps.courses.spm_catalogue_rows import NEW_INSTITUTIONS, build_entry

class Command(CatalogueIngestMixin, BaseCommand):
    help = 'Add new SPM programmes from a reviewed JSON file (dry run unless --apply)'

    def add_arguments(self, parser):
        parser.add_argument('--file', help='The reviewed JSON file to ingest')
        parser.add_argument('--institution-id', help='The ONE parent Institution for a file whose rows carry none')
        parser.add_argument('--create-institutions', action='store_true',
                            help="Also create the file's new_institutions (only ids not yet held)")
        parser.add_argument('--apply', action='store_true', help='Write (default: report only)')
        parser.add_argument('--build-from-csv', help='Build the review file from a scraped CSV instead')
        parser.add_argument('--prefix', default='', help='With --build-from-csv: only course ids with this prefix')
        parser.add_argument('--ids-file', help='With --build-from-csv: only the course ids listed in this file')
        parser.add_argument('--out', help='With --build-from-csv: where to write the review file')

    def handle(self, *args, **options):
        if options['build_from_csv']:
            return self._build(options['build_from_csv'], options['prefix'], options['ids_file'], options['out'])
        if not options['file']:
            raise CommandError('Pass --file <json> (or --build-from-csv <csv> --out <json>).')
        with open(options['file'], encoding='utf-8') as f:
            data = json.load(f)
        courses, cli_id = data.get('courses', []), options['institution_id']
        to_create = self._institutions_to_create(data, courses, cli_id, options['create_institutions'])
        self._check(courses, cli_id, set(to_create), options['apply'])
        for spec in to_create.values():
            self.stdout.write(f"CREATE INSTITUTION {spec['institution_id']} {spec['institution_name']} "
                              f"| {spec['acronym']} | {spec['type']} | {spec['state']}")
        for entry in courses:
            exists = Course.objects.filter(course_id=entry['course_id']).exists()
            self.stdout.write(f"{'UPDATE' if exists else 'CREATE'} {entry['course_id']} "
                              f"{entry['course']} | {entry['field_key']} | {_parent(entry, cli_id)} | "
                              f"bumi={entry['requirement'].get('req_bumiputera')} "
                              f"merit={entry['requirement'].get('merit_cutoff')}")
        flagged = data.get('flagged', [])
        self.stdout.write(f'{len(courses)} courses in the file; {len(flagged)} flagged rows NOT ingested: '
                          + ', '.join(f['course_id'] for f in flagged))
        if not options['apply']:
            self.stdout.write(self.style.NOTICE('DRY RUN: nothing written. Re-run with --apply.'))
            return
        with transaction.atomic():
            for spec in to_create.values():
                Institution.objects.create(**spec)
            for entry in courses:
                self._write(entry, _parent(entry, cli_id))
        self.stdout.write(self.style.SUCCESS(
            f'Applied {len(courses)} courses; created {len(to_create)} institutions.'))

    def _build(self, csv_path, prefix, ids_file, out):
        if not out:
            raise CommandError('--build-from-csv needs --out <json>.')
        ids = None
        if ids_file:
            with open(ids_file, encoding='utf-8') as f:
                ids = [line.split('#')[0].strip() for line in f if line.split('#')[0].strip()]
        with open(csv_path, encoding='utf-8') as f:
            rows = [r for r in csv.DictReader(f) if r['course_id'].startswith(prefix)
                    and (ids is None or r['course_id'] in ids)]
        if ids is not None and len(rows) != len(set(ids)):
            missing = sorted(set(ids) - {r['course_id'] for r in rows})
            raise CommandError(f'--ids-file names ids the CSV does not hold: {missing}')
        entries = [build_entry(r) for r in rows]
        clean = [e for e in entries if not e['unparsed']]
        flagged = [{'course_id': e['course_id'], 'course': e['course'], 'reasons': e['unparsed'],
                    'source': e['source']} for e in entries if e['unparsed']]
        for e in clean:
            del e['unparsed']
        needed = {e.get('institution_id') for e in clean}
        payload = {'built_from': csv_path, 'prefix': prefix,
                   'parser': 'apps/courses/spm_syarat.py (count-once: spm_count_once.py)',
                   'courses': clean, 'flagged': flagged}
        if ids_file:
            payload['ids_file'] = ids_file
            payload['new_institutions'] = {k: v for k, v in NEW_INSTITUTIONS.items() if k in needed}
        with open(out, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
            f.write('\n')
        self.stdout.write(f'{len(rows)} rows: {len(clean)} parsed, {len(flagged)} flagged -> {out}')
        for item in flagged:
            self.stdout.write(f"  FLAGGED {item['course_id']}: {'; '.join(item['reasons'])}")
