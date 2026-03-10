"""
Backfill missing MASCO career_occupations for courses.

Strategy:
1. EXACT FIELD MATCH: If a course's field has MASCO codes from other courses, copy them.
2. FUZZY FIELD MATCH: Map unmapped fields to similar mapped fields (e.g. "Kejuruteraan Pembuatan" → "Kejuruteraan Mekanikal (Pembuatan)").
3. DEPARTMENT FALLBACK: If field still unmatched, try department-level match.

Usage:
  python manage.py backfill_masco          # dry run (shows what would be linked)
  python manage.py backfill_masco --apply  # actually create the links
"""

from django.core.management.base import BaseCommand
from apps.courses.models import Course, MascoOccupation


# Manual mapping for fields that don't exactly match any existing field
FIELD_ALIASES = {
    # Unmapped field → existing field(s) to copy MASCO from
    'Kejuruteraan': ['Kejuruteraan Mekanikal', 'Kejuruteraan Awam'],
    'Kejuruteraan Bahan': ['Kejuruteraan Mekanikal (Bahan)'],
    'Kejuruteraan Pembuatan': ['Kejuruteraan Mekanikal (Pembuatan)'],
    'Kejuruteraan Elektrik Dan Elektronik': ['Kejuruteraan Elektrik & Elektronik'],
    'Kejuruteraan Kimia (Minyak Dan Gas)': ['Kejuruteraan Kimia', 'Kejuruteraan Proses (Petrokimia)'],
    'Kejuruteraan Komputer': ['Kejuruteraan Elektronik (Komputer)'],
    'Kejuruteraan Teknologi Pertanian': ['Kejuruteraan Mekanikal (Pertanian)', 'Agroteknologi'],
    'Perniagaan': ['Pengajian Perniagaan', 'Perniagaan Antarabangsa'],
    'Pengurusan': ['Pengurusan Hotel', 'Pengurusan Acara', 'Pengurusan Logistik dan Rantaian Bekalan'],
    'Pengurusan Dan Strategi': ['Pengurusan Logistik dan Rantaian Bekalan'],
    'Sains': ['Bioteknologi', 'Teknologi Makanan'],
    'Sains Sosial': ['Insurans', 'Kewangan'],
    'STEM': ['Bioteknologi', 'Teknologi Maklumat'],
    'Umum': [],  # Too generic — skip
    'Bahasa': [],  # No suitable MASCO match
    'Bahasa Inggeris': [],
    'Pengajian Islam': [],
    'E-Commerce': ['Sistem Maklumat Perniagaan', 'Teknologi Maklumat'],
    'Seni Reka': ['Rekabentuk Grafik', 'Rekabentuk Industri'],
    'Perubatan': [],  # Medical — needs specific codes
    'Fisioterapi': [],
    'Kesihatan': [],
    'Kesihatan Haiwan Dan Peternakan': ['Agroteknologi'],
    'Kecergasan Pertahanan': [],
    'Pertanian': ['Agroteknologi', 'Teknologi Hortikultur Landskap'],
}


class Command(BaseCommand):
    help = 'Backfill MASCO career_occupations for courses missing them'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually create the M2M links (default is dry run)',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        mode = 'APPLY' if apply else 'DRY RUN'
        self.stdout.write(f'\n=== Backfill MASCO Links ({mode}) ===\n')

        # Build field → MASCO codes mapping from existing links
        field_to_masco = {}
        for course in Course.objects.prefetch_related('career_occupations').all():
            codes = list(course.career_occupations.values_list('masco_code', flat=True))
            if codes:
                field = course.field or ''
                if field not in field_to_masco:
                    field_to_masco[field] = set()
                field_to_masco[field].update(codes)

        self.stdout.write(f'Fields with existing MASCO: {len(field_to_masco)}')

        # Find courses without MASCO links
        unmapped = Course.objects.filter(career_occupations__isnull=True)
        self.stdout.write(f'Courses without MASCO: {unmapped.count()}\n')

        linked_count = 0
        skipped = []

        for course in unmapped:
            field = course.field or ''
            masco_codes = set()

            # Strategy 1: Exact field match
            if field in field_to_masco:
                masco_codes = field_to_masco[field]
                source = f'exact field: {field}'

            # Strategy 2: Fuzzy/alias match
            elif field in FIELD_ALIASES:
                alias_fields = FIELD_ALIASES[field]
                for af in alias_fields:
                    if af in field_to_masco:
                        masco_codes.update(field_to_masco[af])
                if masco_codes:
                    source = f'alias: {field} -> {alias_fields}'
                else:
                    skipped.append((course.course_id, course.course, field))
                    continue

            # Strategy 3: Department fallback — find any course in same department with MASCO
            else:
                dept = course.department or ''
                dept_courses = Course.objects.filter(
                    department=dept,
                    career_occupations__isnull=False,
                ).prefetch_related('career_occupations').distinct()
                for dc in dept_courses[:5]:
                    masco_codes.update(
                        dc.career_occupations.values_list('masco_code', flat=True)
                    )
                if masco_codes:
                    source = f'department: {dept}'
                else:
                    skipped.append((course.course_id, course.course, field))
                    continue

            # Apply links
            occupations = MascoOccupation.objects.filter(masco_code__in=masco_codes)
            if occupations.exists():
                self.stdout.write(
                    f'  {course.course_id}: {course.course} '
                    f'<- {occupations.count()} codes ({source})'
                )
                if apply:
                    course.career_occupations.add(*occupations)
                linked_count += 1

        self.stdout.write(f'\nLinked: {linked_count} courses')
        if skipped:
            self.stdout.write(f'Skipped (no match): {len(skipped)}')
            for cid, name, field in skipped:
                self.stdout.write(f'  {cid}: {name} (field: {field})')

        if not apply:
            self.stdout.write('\nThis was a dry run. Use --apply to create links.')
