"""What `ingest_spm_courses` and `ingest_tvet_courses` share (Bumi coverage Sprint F1): the safety
check before anything is written, the proposed institutions, and the course + requirement writer.
Moved verbatim from `ingest_spm_courses` (a moves-only commit) so the two commands cannot drift.
"""
from django.core.management.base import CommandError

from apps.courses.models import (
    Course, CourseInstitution, CourseRequirement, FieldTaxonomy, Institution,
)

COURSE_FIELDS = ('course', 'level', 'department', 'field', 'semesters')
_UNSET = object()


def _parent(entry, cli_id):
    """The entry's parent institution id: its own (None = no link), else the command line's."""
    own = entry.get('institution_id', _UNSET)
    return cli_id if own is _UNSET else own


class CatalogueIngestMixin:
    """The shared half of the catalogue ingest commands (see the module doc)."""

    def _institutions_to_create(self, data, courses, cli_id, create):
        """The file's proposed institutions that a course needs and the catalogue lacks — only
        with --create-institutions (else none, and `_check` refuses the missing parent)."""
        if not create:
            return {}
        wanted = {_parent(e, cli_id) for e in courses}
        held = set(Institution.objects.filter(institution_id__in=wanted).values_list('institution_id', flat=True))
        return {iid: spec for iid, spec in data.get('new_institutions', {}).items()
                if iid in wanted and iid not in held}

    def _check(self, courses, cli_id, creating, apply):
        """Refuse a file that is not safe to write, before anything is written."""
        problems = self._entry_problems(courses)
        own = [e for e in courses if 'institution_id' in e]
        if own and cli_id:
            problems.append('--institution-id given, but the file names each row\'s own institution')
        for entry in courses:
            parent = _parent(entry, cli_id)
            if parent is None and 'institution_id' not in entry:
                problems.append('--institution-id is required (owner ruling: ONE parent institution)')
                break
            if parent is None and entry['requirement'].get('source_type') != 'matric':
                problems.append(f"{entry['course_id']}: no institution, but it is not a matric row")
        problems += self._missing_institutions({_parent(e, cli_id) for e in courses} - {None}, creating)
        self._refuse_or_warn(problems, apply)

    @staticmethod
    def _entry_problems(courses):
        """A row the parser flagged, or a field_key that names no FieldTaxonomy row."""
        problems = [f"{e['course_id']}: unparsed {e['unparsed']}" for e in courses if e.get('unparsed')]
        known = set(FieldTaxonomy.objects.values_list('key', flat=True))
        return problems + [f"{e['course_id']}: field_key {e['field_key']!r} is not a FieldTaxonomy key"
                           for e in courses if e['field_key'] not in known]

    @staticmethod
    def _missing_institutions(parents, creating):
        held = set(Institution.objects.filter(institution_id__in=parents).values_list('institution_id', flat=True))
        return [f'Institution {iid!r} does not exist (a row the file proposes under new_institutions '
                'is created only with --create-institutions)' for iid in sorted(parents - held - creating)]

    def _refuse_or_warn(self, problems, apply):
        if problems:
            report = 'Refusing to ingest:\n  ' + '\n  '.join(problems)
            if apply:
                raise CommandError(report)
            self.stdout.write(self.style.WARNING(report))

    @staticmethod
    def _write_course(entry):
        """`Course` + its `CourseRequirement`, idempotently; returns the course."""
        course, _ = Course.objects.update_or_create(
            course_id=entry['course_id'],
            defaults={**{k: entry[k] for k in COURSE_FIELDS}, 'field_key_id': entry['field_key']},
        )
        # Every flag the file does not set is written False, so a re-run after a review edit can
        # also CLEAR a flag (update_or_create only touches the fields it is given).
        flags = {f.name: False for f in CourseRequirement._meta.get_fields()
                 if f.get_internal_type() == 'BooleanField'}
        CourseRequirement.objects.update_or_create(course=course, defaults={**flags, **entry['requirement']})
        return course

    @classmethod
    def _write(cls, entry, institution_id):
        course = cls._write_course(entry)
        if institution_id:
            CourseInstitution.objects.update_or_create(
                course=course, institution_id=institution_id,
                defaults={'hyperlink': entry.get('mohe_url', '')},
            )
