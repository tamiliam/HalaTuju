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
(Sprint F2) use the same command with a file built for `--families mara`:

    python manage.py ingest_tvet_courses --build-source --csv data/tvet/uptvet_2026-10-29.csv \\
        --pages data/tvet/pages --families mara --out data/tvet/uptvet_F2_source.json
    python manage.py ingest_tvet_courses --build-review --source data/tvet/uptvet_F2_source.json \\
        --families mara --out data/tvet/tvet_new_courses_F2.json
    python manage.py ingest_tvet_courses --file data/tvet/tvet_new_courses_F2.json --create-institutions

A built review file also carries a `summary` (Bumi-only vs open courses, the programmes split by a rule
difference, the flagged rows by reason) for the reviewer; the ingest never reads it.

ORDER ON PRODUCTION: no migration. The new rows need the F1 deploy (the "mara" / "tvet_other"
pathways in apps.py and the web chips), so: deploy, confirm the api AND web revisions serve 100%,
then dry run, `--create-institutions --apply`, and a re-revision (the running instances hold the
eligibility frame in memory). Runbook + rollback: halatuju_api/CLAUDE.md ("Bumi F1 order", "Bumi F2 order").
"""
import csv
import json
import os
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.courses.catalogue_ingest import CatalogueIngestMixin
from apps.courses.models import Course, CourseInstitution, Institution
from apps.courses.tvet_catalogue_rows import build_review, review_summary
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


def load_not_in_prod(path):
    """Held course ids the repo fixtures hold but prod does not (read-only SQL): never linked."""
    with open(path, encoding='utf-8') as f:
        return frozenset(json.load(f).get('not_in_prod', []))


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


#: Ids the printed SQL may carry (review round 1): a new course is TVET-<id_kursus>; a campus link may name
#: a held IJTM-* / IKBN-* course (F1); an institution is MARA-NNN (F2) or F1's IKBN- / ILKA- / IJTM-NNN.
_COURSE_ID = re.compile(r'^TVET-\d+$')
_HELD_COURSE_ID = re.compile(r'^(IJTM|IKBN)-[A-Z]+-\d{3}$')
_INSTITUTION_ID = re.compile(r'^(MARA|IKBN|ILKA|IJTM)-\d{3}$')


def check_sql_ids(data):
    """Refuse (CommandError) to print SQL for any id outside those shapes, or holding a quote: the SQL is
    pasted into a prod console, so nothing in it may come from a hand-edited file unchecked."""
    links = [x for x in data.get('held_links', []) if not x['already_linked']]
    bad = [f'course id {c["course_id"]!r}' for c in data.get('courses', []) if not _COURSE_ID.match(c['course_id'])]
    bad += [f'held course id {x["course_id"]!r}' for x in links if not _HELD_COURSE_ID.match(x['course_id'])]
    bad += [f'institution id {i!r}' for i in list(data.get('new_institutions', {})) + [x['institution_id'] for x in links]
            if not _INSTITUTION_ID.match(i)]
    if bad:
        raise CommandError('Refusing to print SQL for ids outside the expected shapes:\n  ' + '\n  '.join(bad))


def _in(values):
    return '(' + ', '.join(f"'{v}'" for v in values) + ')'


def precheck_sql(data):
    """The READ-ONLY SQL the lead runs on prod before `--apply` (Bumi F2): every query must return 0 rows."""
    ids = sorted(c['course_id'] for c in data['courses'])
    institutions = sorted(data.get('new_institutions', {}))
    pairs = sorted((x['course_id'], x['institution_id']) for x in data.get('held_links', []) if not x['already_linked'])
    out = [f'-- 1. none of the {len(ids)} new course ids is in the catalogue (expect 0 rows)',
           f'SELECT course_id FROM courses WHERE course_id IN {_in(ids)};',
           f'-- 2. none of the {len(institutions)} new institution ids exists (expect 0 rows)',
           f'SELECT institution_id FROM institutions WHERE institution_id IN {_in(institutions)};']
    if pairs:
        out += [f'-- 3. none of the {len(pairs)} new campus links to held courses exists (expect 0 rows)',
                'SELECT course_id, institution_id FROM course_institutions WHERE (course_id, institution_id) IN ('
                + ', '.join(f"('{c}', '{i}')" for c, i in pairs) + ');']
    return '\n'.join(out)


def rollback_sql(data):
    """The pre-rollback READ-ONLY checks, then the rollback in ONE transaction (Postgres has no cascade:
    Django's CASCADE is Python-side, so every child table goes first, then the courses, then the
    institutions once nothing points at them)."""
    ids = _in(sorted(c['course_id'] for c in data['courses']))
    institutions = _in(sorted(data.get('new_institutions', {})))
    pairs = sorted((x['course_id'], x['institution_id']) for x in data.get('held_links', []) if not x['already_linked'])
    out = ['-- BEFORE ANY ROLLBACK, read-only: who chose one of these courses (a JSON choice, not a foreign key,',
           '-- so a delete leaves it pointing at nothing). Non-zero -> the owner decides first.',
           f"SELECT id, status FROM scholarship_applications WHERE chosen_programme->>'course_id' IN {ids} OR EXISTS "
           f"(SELECT 1 FROM jsonb_array_elements(top_choices) e WHERE e->>'course_id' IN {ids});",
           f"SELECT count(*) FROM api_student_profiles WHERE chosen_programme->>'course_id' IN {ids};",
           f'SELECT count(*) FROM saved_courses WHERE course_id IN {ids};',
           f'SELECT count(*) FROM admission_outcomes WHERE institution_id IN {institutions};',
           f'SELECT count(*) FROM stpm_courses WHERE institution_id IN {institutions};',
           '-- ROLLBACK, one transaction:', 'BEGIN;']
    for table in ('saved_courses', 'admission_outcomes', 'course_tags', 'courses_career_occupations',
                  'course_requirements', 'course_institutions'):
        out.append(f'DELETE FROM {table} WHERE course_id IN {ids};')
    if pairs:
        out.append('DELETE FROM course_institutions WHERE (course_id, institution_id) IN ('
                   + ', '.join(f"('{c}', '{i}')" for c, i in pairs) + ');')
    out += [f'DELETE FROM courses WHERE course_id IN {ids};']
    if data.get('new_institutions'):
        out += [f'DELETE FROM institutions WHERE institution_id IN {institutions};']
    return '\n'.join(out + ['COMMIT;', '-- then a re-revision of halatuju-api so the eligibility frame reloads.'])


class Command(CatalogueIngestMixin, BaseCommand):
    help = 'Add public UP_TVET programmes from a reviewed JSON file (dry run unless --apply)'

    def add_arguments(self, parser):
        parser.add_argument('--file', help='The reviewed JSON file to ingest')
        parser.add_argument('--create-institutions', action='store_true',
                            help="Also create the file's new_institutions (only ids not yet held)")
        parser.add_argument('--apply', action='store_true', help='Write (default: report only)')
        parser.add_argument('--allow-update', action='store_true',
                            help='Let --apply rewrite a course id the catalogue already holds (a re-run after a '
                                 'reviewed edit). Without it an existing or non TVET- id is refused.')
        parser.add_argument('--build-source', action='store_true', help='Freeze catalogue rows + pages')
        parser.add_argument('--build-review', action='store_true', help='Build the review file from a source')
        parser.add_argument('--csv', default=os.path.join('data', 'tvet', 'uptvet_latest.csv'))
        parser.add_argument('--pages', default=os.path.join('data', 'tvet', 'pages'))
        parser.add_argument('--families', default=','.join(F1_FAMILIES), help='Comma list (tvet_families.py)')
        parser.add_argument('--source', default=os.path.join('data', 'tvet', 'uptvet_F1_source.json'))
        parser.add_argument('--held-links', default=os.path.join('data', 'tvet', 'held_tvet_links.json'))
        parser.add_argument('--out', help='Where --build-source / --build-review write')
        parser.add_argument('--sql', action='store_true',
                            help="Print the file's read-only prod pre-check (writes nothing, reads no DB)")
        parser.add_argument('--rollback-sql', action='store_true',
                            help="Print the pre-rollback checks and the one-transaction rollback (runs nothing)")

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
        if options['sql'] or options['rollback_sql']:
            check_sql_ids(data)
            return self.stdout.write(precheck_sql(data) if options['sql'] else rollback_sql(data))
        self._ingest(data, options['create_institutions'], options['apply'], options['allow_update'])

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
        review = build_review(source, load_held_links(held_links_path), held_courses_from_fixtures(), families,
                              load_not_in_prod(held_links_path))
        review['built_from'] = source_path.replace(os.sep, '/')
        review['summary'] = review_summary(review)
        write_json(out, review)
        self.stdout.write(json.dumps(review['counts'], indent=1))
        self.stdout.write(json.dumps({k: v for k, v in review['summary'].items() if k != 'split_programmes'},
                                     indent=1, ensure_ascii=False))
        self.stdout.write(f'-> {out}')

    # --- ingest ------------------------------------------------------------------------------

    def _ingest(self, data, create, apply, allow_update=False):
        courses, links = data.get('courses', []), data.get('held_links', [])
        to_create = self._tvet_institutions_to_create(data, courses, links, create)
        problems = self._entry_problems(courses)
        problems += self._id_problems(courses, allow_update)
        held_ids = {link['course_id'] for link in links}
        present = set(Course.objects.filter(course_id__in=held_ids).values_list('course_id', flat=True))
        problems += [f'held course {cid!r} does not exist (a campus link is added to a held course only)'
                     for cid in sorted(held_ids - present)]
        parents = {o['institution_id'] for c in courses for o in c['offerings']} | {x['institution_id'] for x in links}
        problems += self._missing_institutions(parents, set(to_create))
        new_links, clashes = self._new_links(links)
        if not allow_update:
            problems += clashes
        self._refuse_or_warn(problems, apply)
        for spec in to_create.values():
            self.stdout.write(f"CREATE INSTITUTION {spec['institution_id']} {spec['institution_name']} | "
                              f"{spec['type']} | {spec['category']} | {spec['subcategory']} | {spec['state']}")
        for entry in courses:
            exists = Course.objects.filter(course_id=entry['course_id']).exists()
            self.stdout.write(f"{'UPDATE' if exists else 'CREATE'} {entry['course_id']} {entry['course']} | "
                              f"{entry['field_key']} | bumi={entry['requirement'].get('req_bumiputera')} | "
                              f"campuses {', '.join(o['institution_id'] for o in entry['offerings'])}")
        for link in new_links:
            self.stdout.write(f"LINK {link['course_id']} -> {link['institution_id']} (id_kursus {link['id_kursus']})")
        held = sum(1 for x in links if x['already_linked'])
        self.stdout.write(f"{len(courses)} new courses ({sum(len(c['offerings']) for c in courses)} campus "
                          f"offerings); {len(new_links)} new campus links to held courses ({held} already held); "
                          f"{len(data.get('flagged', []))} flagged rows NOT ingested.")
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

    @staticmethod
    def _new_links(links):
        """(links to write, clashes). Only a link the file marks NEW (`already_linked` false) is written,
        and it must not exist yet: the rollback deletes exactly the file's new links, so a new link that
        prod already holds would be deleted by a rollback (review 2026-10-29: 22 such pairs). A clash
        refuses --apply unless --allow-update (a reviewed re-run of the same file)."""
        new, clashes = [], []
        for link in (x for x in links if not x['already_linked']):
            if CourseInstitution.objects.filter(course_id=link['course_id'],
                                                institution_id=link['institution_id']).exists():
                clashes.append(f"link {link['course_id']} -> {link['institution_id']} is marked new but already "
                               'exists (a rollback would delete a real link)')
            else:
                new.append(link)
        return new, clashes

    @staticmethod
    def _id_problems(courses, allow_update):
        """A new UP_TVET course is TVET-<id_kursus> and does not exist yet: anything else would rewrite a
        held course (IJTM-* / IKBN-*, or any other row) through the new-course path. --allow-update lets a
        reviewed re-run rewrite its OWN TVET- rows; it never lets a non TVET- id through."""
        ids = [c['course_id'] for c in courses]
        problems = [f'{cid}: a new UP_TVET course id must start with TVET-' for cid in ids
                    if not cid.startswith('TVET-')]
        if not allow_update:
            held = sorted(Course.objects.filter(course_id__in=ids).values_list('course_id', flat=True))
            problems += [f'{cid}: already in the catalogue (pass --allow-update to rewrite it on purpose)'
                         for cid in held]
        return problems

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
