"""Add public UP_TVET programmes to the course catalogue from a REVIEWED JSON file (Bumi Sprint F1).

Three steps; the last is a DRY RUN by default:

    # 1. freeze the inputs (catalogue rows + the saved pages, read; no contact person) into one file
    python manage.py ingest_tvet_courses --build-source --csv data/tvet/uptvet_latest.csv \\
        --pages data/tvet/pages --out data/tvet/uptvet_F1_source.json
    # 2. build the human-reviewable file from it (pure; a test rebuilds it byte for byte)
    python manage.py ingest_tvet_courses --build-review --source data/tvet/uptvet_F1_source.json \\
        --out data/tvet/tvet_new_courses_F1.json
    # 3. read it back: prints what it WOULD create / link; nothing is written
    python manage.py ingest_tvet_courses --file data/tvet/tvet_new_courses_F1.json --create-institutions
    #    ... and only after the review and the read-only checks, the same with --apply.

`--apply` writes, in one transaction: the file's `new_institutions` that the catalogue lacks (only with
`--create-institutions`; an existing institution id is NEVER overwritten); each new `Course` +
`CourseRequirement` (shared writer: `catalogue_ingest.py`) and ONE `CourseInstitution` per campus
(hyperlink, fees); and, for HELD courses (prod's IJTM-* / IKBN-*), the campus links the file lists
that do not exist yet. A held course's own row and requirement are never touched; the file's
`held_rule_differences` are for a person to review. Rows in `flagged` are never written. MARA rows
(Sprint F2) use the same command with a file built for `--families mara`.

ORDER ON PRODUCTION: no migration. The new rows need the F1 deploy (the "mara" / "tvet_other"
pathways in apps.py and the web chips), so: deploy, confirm the api AND web revisions serve 100%,
then dry run, `--create-institutions --apply`, and a re-revision (the running instances hold the
eligibility frame in memory). Runbook + rollback: halatuju_api/CLAUDE.md ("Bumi F1 order").
"""
import csv
import json
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.courses.catalogue_ingest import CatalogueIngestMixin
from apps.courses.models import Course, CourseInstitution, Institution
from apps.courses.tvet_catalogue_rows import build_review
from apps.courses.tvet_families import F1_FAMILIES, family_of
from apps.courses.tvet_pages import read_page

FIXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'fixtures')
CATALOGUE_COLUMNS = ('id_kursus', 'kod_tauliah', 'name', 'institution', 'sektor', 'reg_fee', 'tuition_fee',
                     'info_url')
OFFERING_FIELDS = ('hyperlink', 'tuition_fee_semester', 'registration_fee')


def held_courses_from_fixtures(fixtures=FIXTURES):
    """{course_id: {'course', 'requirement'}} for the held TVET courses (IJTM-* / IKBN-*), read from the
    repo's catalogue fixtures (the copy the golden master proves), so the review build needs no DB."""
    with open(os.path.join(fixtures, 'courses.json'), encoding='utf-8') as f:
        courses = {c['pk']: c['fields'] for c in json.load(f) if c['pk'].startswith(('IJTM-', 'IKBN-'))}
    with open(os.path.join(fixtures, 'requirements.json'), encoding='utf-8') as f:
        requirements = {r['pk']: r['fields'] for r in json.load(f) if r['pk'] in courses}
    return {cid: {'course': fields['course'], 'requirement': requirements.get(cid, {})}
            for cid, fields in courses.items()}


def load_held_links(path):
    with open(path, encoding='utf-8') as f:
        return {link['id_kursus']: (link['course_id'], link['institution_id']) for link in json.load(f)['links']}


def write_json(path, payload, compact=False):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        if compact:   # one page per line: reviewable in a diff, a third of the indented size
            f.write('{\n')
            for n, (key, value) in enumerate(payload.items()):
                f.write(f'{json.dumps(key)}: {{\n')
                items = list(value.items())
                for m, (k, v) in enumerate(items):
                    sep = ',' if m < len(items) - 1 else ''
                    f.write(f'{json.dumps(k)}: {json.dumps(v, ensure_ascii=False, sort_keys=True)}{sep}\n')
                f.write('}' + (',' if n < len(payload) - 1 else '') + '\n')
            f.write('}\n')
        else:
            json.dump(payload, f, ensure_ascii=False, indent=1)
            f.write('\n')


class Command(CatalogueIngestMixin, BaseCommand):
    help = 'Add public UP_TVET programmes from a reviewed JSON file (dry run unless --apply)'

    def add_arguments(self, parser):
        parser.add_argument('--file', help='The reviewed JSON file to ingest')
        parser.add_argument('--create-institutions', action='store_true',
                            help="Also create the file's new_institutions (only ids not yet held)")
        parser.add_argument('--apply', action='store_true', help='Write (default: report only)')
        parser.add_argument('--build-source', action='store_true', help='Freeze catalogue rows + pages')
        parser.add_argument('--build-review', action='store_true', help='Build the review file from a source')
        parser.add_argument('--csv', default=os.path.join('data', 'tvet', 'uptvet_latest.csv'))
        parser.add_argument('--pages', default=os.path.join('data', 'tvet', 'pages'))
        parser.add_argument('--families', default=','.join(F1_FAMILIES), help='Comma list (tvet_families.py)')
        parser.add_argument('--source', default=os.path.join('data', 'tvet', 'uptvet_F1_source.json'))
        parser.add_argument('--held-links', default=os.path.join('data', 'tvet', 'held_tvet_links.json'))
        parser.add_argument('--out', help='Where --build-source / --build-review write')

    def handle(self, *args, **options):
        families = tuple(f.strip() for f in options['families'].split(',') if f.strip())
        if options['build_source']:
            return self._build_source(options['csv'], options['pages'], families, options['out'])
        if options['build_review']:
            return self._build_review(options['source'], options['held_links'], families, options['out'])
        if not options['file']:
            raise CommandError('Pass --file <json>, or --build-source / --build-review with --out.')
        with open(options['file'], encoding='utf-8') as f:
            data = json.load(f)
        self._ingest(data, options['create_institutions'], options['apply'])

    # --- build -------------------------------------------------------------------------------

    def _build_source(self, csv_path, pages, families, out):
        if not out:
            raise CommandError('--build-source needs --out <json>.')
        with open(csv_path, encoding='utf-8') as f:
            rows = [r for r in csv.DictReader(f) if (r.get('sektor') or '').lower() == 'awam'
                    and family_of(r['institution']) in families]
        catalogue, read = {}, {}
        for row in rows:
            path = os.path.join(pages, f"{row['id_kursus']}.html")
            if not os.path.exists(path):
                raise CommandError(f"page {row['id_kursus']} is not cached: run scrape_uptvet_syarat first")
            with open(path, encoding='utf-8') as f:
                read[row['id_kursus']] = read_page(f.read())
            catalogue[row['id_kursus']] = {k: row.get(k, '') for k in CATALOGUE_COLUMNS}
        write_json(out, {'catalogue': catalogue, 'pages': read}, compact=True)
        self.stdout.write(f'{len(rows)} public rows of {", ".join(families)} -> {out}')

    def _build_review(self, source_path, held_links_path, families, out):
        if not out:
            raise CommandError('--build-review needs --out <json>.')
        with open(source_path, encoding='utf-8') as f:
            source = json.load(f)
        review = build_review(source, load_held_links(held_links_path), held_courses_from_fixtures(), families)
        review['built_from'] = source_path.replace(os.sep, '/')
        write_json(out, review)
        self.stdout.write(json.dumps(review['counts'], indent=1))
        self.stdout.write(f'-> {out}')

    # --- ingest ------------------------------------------------------------------------------

    def _ingest(self, data, create, apply):
        courses, links = data.get('courses', []), data.get('held_links', [])
        to_create = self._tvet_institutions_to_create(data, courses, links, create)
        problems = self._entry_problems(courses)
        held_ids = {link['course_id'] for link in links}
        present = set(Course.objects.filter(course_id__in=held_ids).values_list('course_id', flat=True))
        problems += [f'held course {cid!r} does not exist (a campus link is added to a held course only)'
                     for cid in sorted(held_ids - present)]
        parents = {o['institution_id'] for c in courses for o in c['offerings']} | {x['institution_id'] for x in links}
        problems += self._missing_institutions(parents, set(to_create))
        self._refuse_or_warn(problems, apply)
        for spec in to_create.values():
            self.stdout.write(f"CREATE INSTITUTION {spec['institution_id']} {spec['institution_name']} | "
                              f"{spec['type']} | {spec['category']} | {spec['subcategory']} | {spec['state']}")
        for entry in courses:
            exists = Course.objects.filter(course_id=entry['course_id']).exists()
            self.stdout.write(f"{'UPDATE' if exists else 'CREATE'} {entry['course_id']} {entry['course']} | "
                              f"{entry['field_key']} | bumi={entry['requirement'].get('req_bumiputera')} | "
                              f"campuses {', '.join(o['institution_id'] for o in entry['offerings'])}")
        new_links = [x for x in links if not CourseInstitution.objects.filter(
            course_id=x['course_id'], institution_id=x['institution_id']).exists()]
        for link in new_links:
            self.stdout.write(f"LINK {link['course_id']} -> {link['institution_id']} (id_kursus {link['id_kursus']})")
        self.stdout.write(f"{len(courses)} new courses ({sum(len(c['offerings']) for c in courses)} campus "
                          f"offerings); {len(new_links)} new campus links to held courses ({len(links) - len(new_links)} "
                          f"already held); {len(data.get('flagged', []))} flagged rows NOT ingested.")
        if not apply:
            self.stdout.write(self.style.NOTICE('DRY RUN: nothing written. Re-run with --apply.'))
            return
        with transaction.atomic():
            for spec in to_create.values():
                Institution.objects.create(**spec)
            for entry in courses:
                self._write_tvet_course(entry)
            for link in new_links:
                CourseInstitution.objects.get_or_create(
                    course_id=link['course_id'], institution_id=link['institution_id'],
                    defaults={k: link[k] for k in OFFERING_FIELDS})
        self.stdout.write(self.style.SUCCESS(
            f'Applied {len(courses)} courses, {len(new_links)} held-course links; '
            f'created {len(to_create)} institutions.'))

    def _tvet_institutions_to_create(self, data, courses, links, create):
        """The file's proposed institutions a row needs and the catalogue lacks (never an existing id)."""
        if not create:
            return {}
        wanted = {o['institution_id'] for c in courses for o in c['offerings']} | {x['institution_id'] for x in links}
        held = set(Institution.objects.filter(institution_id__in=wanted).values_list('institution_id', flat=True))
        return {iid: spec for iid, spec in data.get('new_institutions', {}).items()
                if iid in wanted and iid not in held}

    def _write_tvet_course(self, entry):
        course = self._write_course(entry)
        Course.objects.filter(pk=course.pk).update(description=entry.get('description', ''))
        for offering in entry['offerings']:
            CourseInstitution.objects.update_or_create(
                course=course, institution_id=offering['institution_id'],
                defaults={k: offering[k] for k in OFFERING_FIELDS})
