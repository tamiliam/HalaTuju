"""
Management command to backfill CourseTag rows for PISMP courses.

PISMP courses are all teacher training (high_people, regulated_profession,
stable career). What varies is the specialisation: science teachers work in
labs, PE teachers work on fields, music/art teachers work in workshops, etc.

Specialisation is detected by keyword matching against the course name.

Usage:
    python manage.py backfill_pismp_tags          # Dry run
    python manage.py backfill_pismp_tags --apply   # Apply changes
"""
from django.core.management.base import BaseCommand
from apps.courses.models import Course, CourseRequirement, CourseTag


# --- Specialisation keyword → tag overrides ---
# All PISMP courses share a common base (see PISMP_BASE_TAGS).
# Specialisation-specific overrides are applied on top.
SPECIALISATION_MAP = [
    # Order matters — first match wins. More specific keywords first.
    {
        'keywords': ['Sains'],
        'tags': {
            'cognitive_type': 'abstract',
            'environment': 'lab',
            'load': 'mentally_demanding',
            'learning_style': ['continuous_assessment', 'project_based'],
        },
    },
    {
        'keywords': ['Matematik'],
        'tags': {
            'cognitive_type': 'abstract',
            'environment': 'office',
            'load': 'mentally_demanding',
            'learning_style': ['continuous_assessment'],
        },
    },
    {
        'keywords': ['Jasmani'],
        'tags': {
            'work_modality': 'hands_on',
            'cognitive_type': 'procedural',
            'environment': 'field',
            'load': 'physically_demanding',
            'learning_style': ['project_based'],
        },
    },
    {
        'keywords': ['Seni Visual'],
        'tags': {
            'cognitive_type': 'abstract',
            'environment': 'workshop',
            'creative_output': 'expressive',
            'learning_style': ['project_based'],
        },
    },
    {
        'keywords': ['Muzik'],
        'tags': {
            'cognitive_type': 'abstract',
            'environment': 'workshop',
            'creative_output': 'expressive',
            'learning_style': ['project_based'],
        },
    },
    {
        'keywords': ['Reka Bentuk'],
        'tags': {
            'work_modality': 'mixed',
            'cognitive_type': 'problem_solving',
            'environment': 'workshop',
            'creative_output': 'design',
            'learning_style': ['project_based'],
        },
    },
    {
        'keywords': ['Kaunseling'],
        'tags': {
            'cognitive_type': 'abstract',
            'environment': 'office',
            'load': 'mentally_demanding',
            'service_orientation': 'high',
            'learning_style': ['continuous_assessment'],
        },
    },
    {
        'keywords': ['Khas Masalah'],
        'tags': {
            'cognitive_type': 'procedural',
            'environment': 'office',
            'load': 'mentally_demanding',
            'service_orientation': 'high',
            'learning_style': ['continuous_assessment'],
        },
    },
    {
        'keywords': ['Kanak-Kanak'],
        'tags': {
            'cognitive_type': 'procedural',
            'environment': 'office',
            'load': 'balanced_load',
            'learning_style': ['project_based', 'continuous_assessment'],
        },
    },
    {
        'keywords': ['Sejarah'],
        'tags': {
            'cognitive_type': 'abstract',
            'environment': 'office',
            'load': 'mentally_demanding',
            'learning_style': ['assessment_heavy'],
        },
    },
    {
        'keywords': ['Islam'],
        'tags': {
            'cognitive_type': 'abstract',
            'environment': 'office',
            'load': 'mentally_demanding',
            'learning_style': ['assessment_heavy'],
        },
    },
    # Language teaching — must be last (broadest match).
    # Covers: Bahasa Melayu, Bahasa Cina, Bahasa Tamil, Bahasa Arab,
    #         Bahasa Iban, Bahasa Inggeris
    {
        'keywords': ['Bahasa', 'Inggeris'],
        'tags': {
            'cognitive_type': 'abstract',
            'environment': 'office',
            'load': 'mentally_demanding',
            'learning_style': ['continuous_assessment'],
        },
    },
]

# Shared base tags for all PISMP courses
PISMP_BASE_TAGS = {
    'work_modality': 'theoretical',
    'people_interaction': 'high_people',
    'cognitive_type': 'abstract',
    'learning_style': ['continuous_assessment'],
    'load': 'mentally_demanding',
    'outcome': 'regulated_profession',
    'environment': 'office',
    'credential_status': 'regulated',
    'creative_output': 'none',
    'service_orientation': 'high',
    'interaction_type': 'collaborative',
    'career_structure': 'stable',
}


def _match_specialisation(course_name):
    """Return the specialisation override dict for a course name, or None."""
    for spec in SPECIALISATION_MAP:
        if any(kw in course_name for kw in spec['keywords']):
            return spec
    return None


class Command(BaseCommand):
    help = 'Backfill CourseTag rows for PISMP courses'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Apply changes (default is dry run)',
        )

    def handle(self, *args, **options):
        apply = options['apply']

        # Find all PISMP course IDs
        pismp_ids = set(
            CourseRequirement.objects.filter(source_type='pismp')
            .values_list('course_id', flat=True)
        )
        self.stdout.write(f'Found {len(pismp_ids)} PISMP courses')

        # Check which already have tags
        existing = set(
            CourseTag.objects.filter(course_id__in=pismp_ids)
            .values_list('course_id', flat=True)
        )
        if existing:
            self.stdout.write(
                f'  {len(existing)} already have tags (will skip)'
            )

        # Load course names
        courses = Course.objects.filter(course_id__in=pismp_ids)
        course_map = {c.course_id: c for c in courses}

        created = 0
        unmatched = []

        for cid in sorted(pismp_ids):
            if cid in existing:
                continue

            course = course_map.get(cid)
            if not course:
                self.stdout.write(
                    self.style.WARNING(f'  Course {cid} not found in courses table')
                )
                continue

            name = course.course
            spec = _match_specialisation(name)

            # Build tags: base + specialisation overrides
            tags = dict(PISMP_BASE_TAGS)
            if spec:
                tags.update(spec['tags'])
                label = spec['keywords'][0]
            else:
                label = 'DEFAULT (no specialisation match)'
                unmatched.append((cid, name))

            if apply:
                CourseTag.objects.create(course_id=cid, **tags)

            self.stdout.write(
                f'  {"Created" if apply else "Would create"} tags for '
                f'{cid}: {name} [{label}]'
            )
            created += 1

        if unmatched:
            self.stdout.write(self.style.WARNING(
                f'\n{len(unmatched)} courses matched no specialisation '
                f'(used base tags):'
            ))
            for cid, name in unmatched:
                self.stdout.write(f'  {cid}: {name}')

        verb = 'Created' if apply else 'Would create'
        self.stdout.write(self.style.SUCCESS(
            f'\n{verb} {created} CourseTag rows'
        ))
        if not apply and created:
            self.stdout.write('Run with --apply to write changes.')
