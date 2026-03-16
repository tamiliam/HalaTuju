"""
Management command to map courses to MASCO career occupations via Gemini AI.

Two modes:
  --output FILE   Generate mode: AI picks ~3 MASCO codes per unmapped course,
                  writes a review CSV for human approval.
  --apply FILE    Apply mode: reads a reviewed CSV and creates M2M links in DB.

Usage:
  # Generate review CSV for polytechnic courses
  python manage.py map_course_careers --source-type poly -o review_poly.csv

  # Generate for STPM courses
  python manage.py map_course_careers --stpm -o review_stpm.csv

  # Apply reviewed CSV
  python manage.py map_course_careers --apply approved_poly.csv
"""
import csv
import logging
import os
import re
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.courses.masco_mapping import filter_masco_by_field_key

logger = logging.getLogger(__name__)

# Gemini model cascade — same order as report_engine.py
MODEL_CASCADE = [
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
    'gemini-2.0-flash',
]

# Regex to extract MASCO codes like "2141-01" from Gemini response
MASCO_CODE_RE = re.compile(r'\b(\d{4}-\d{2})\b')


def call_gemini(course_name: str, field_key: str, masco_list: list[dict]) -> list[str]:
    """
    Ask Gemini to pick the 3 most relevant MASCO codes for a course.

    Args:
        course_name: Display name of the course (BM).
        field_key: Field taxonomy key (e.g. 'mekanikal').
        masco_list: List of dicts with 'masco_code' and 'job_title' keys.

    Returns:
        List of up to 3 valid masco_code strings.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '') or os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        logger.warning('GEMINI_API_KEY not configured — skipping AI mapping')
        return []

    try:
        from google import genai
    except ImportError:
        logger.error('google-genai not installed')
        return []

    # Build the candidate list string
    candidates = '\n'.join(
        f"  {m['masco_code']}  {m['job_title']}"
        for m in masco_list
    )

    prompt = (
        f"Anda pakar kerjaya Malaysia. Kursus ini:\n"
        f"  Nama: {course_name}\n"
        f"  Bidang: {field_key}\n\n"
        f"Senarai pekerjaan MASCO yang berkaitan:\n{candidates}\n\n"
        f"Pilih TEPAT 3 kod MASCO yang PALING sesuai untuk graduan kursus ini.\n"
        f"Jawab HANYA dengan 3 kod, satu per baris. Contoh:\n"
        f"2141-01\n7233-01\n2141-03\n"
        f"Jangan tulis apa-apa lain."
    )

    valid_codes = {m['masco_code'] for m in masco_list}
    client = genai.Client(api_key=api_key)

    last_error = None
    for model_name in MODEL_CASCADE:
        try:
            response = client.models.generate_content(
                model=model_name, contents=prompt
            )
            text = response.text

            # Parse codes from response
            found = MASCO_CODE_RE.findall(text)
            # Keep only codes that exist in the filtered list
            validated = [c for c in found if c in valid_codes]
            # Deduplicate while preserving order
            seen = set()
            result = []
            for c in validated:
                if c not in seen:
                    seen.add(c)
                    result.append(c)
                if len(result) >= 3:
                    break

            logger.info(f'Gemini ({model_name}) matched {len(result)} codes for "{course_name}"')
            return result

        except Exception as e:
            last_error = str(e)
            logger.warning(f'Gemini {model_name} failed: {e}')
            continue

    logger.error(f'All Gemini models failed for "{course_name}": {last_error}')
    return []


class Command(BaseCommand):
    help = 'Map courses to MASCO career occupations using Gemini AI'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source-type',
            choices=['poly', 'kkom', 'tvet', 'ua', 'pismp'],
            help='Filter SPM courses by source_type',
        )
        parser.add_argument(
            '--stpm',
            action='store_true',
            help='Process STPM courses instead of SPM',
        )
        parser.add_argument(
            '--output', '-o',
            help='CSV output path for generate mode',
        )
        parser.add_argument(
            '--apply',
            help='CSV path to apply (creates M2M links)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Max courses to process (0 = all)',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.0,
            help='Seconds between Gemini calls (default 1.0)',
        )

    def handle(self, *args, **options):
        if options['apply']:
            self._apply(options['apply'])
        elif options['output']:
            self._generate(options)
        else:
            raise CommandError('Must specify --output FILE (generate) or --apply FILE (apply)')

    def _generate(self, options):
        """Generate mode: call Gemini for unmapped courses, write review CSV."""
        from apps.courses.models import Course, StpmCourse

        stpm_mode = options['stpm']
        source_type = options.get('source_type')
        limit = options['limit']
        delay = options['delay']
        output_path = options['output']

        if stpm_mode:
            # STPM courses — filter to unmapped only
            qs = StpmCourse.objects.filter(career_occupations__isnull=True).distinct()
            course_type = 'stpm'
        else:
            # SPM courses — filter by source_type and unmapped
            qs = Course.objects.filter(career_occupations__isnull=True).distinct()
            if source_type:
                qs = qs.filter(requirement__source_type=source_type)
            course_type = 'spm'

        if limit > 0:
            qs = qs[:limit]

        courses = list(qs)
        self.stdout.write(f'Found {len(courses)} unmapped {course_type} courses')

        rows = []
        for i, course in enumerate(courses):
            if stpm_mode:
                name = course.course_name
                fk = course.field_key_id
                cid = course.course_id
            else:
                name = course.course
                fk = course.field_key_id
                cid = course.course_id

            # Get filtered MASCO list for this field
            masco_qs = filter_masco_by_field_key(fk)
            masco_list = list(masco_qs.values('masco_code', 'job_title'))

            if not masco_list:
                self.stdout.write(self.style.WARNING(
                    f'  No MASCO candidates for {cid} (field_key={fk}), skipping'))
                continue

            # Call Gemini
            codes = call_gemini(name, fk, masco_list)

            if not codes:
                self.stdout.write(self.style.WARNING(
                    f'  No matches from Gemini for {cid}'))
                continue

            # Build rows for CSV
            masco_lookup = {m['masco_code']: m['job_title'] for m in masco_list}
            for code in codes:
                rows.append({
                    'course_id': cid,
                    'course_name': name,
                    'field_key': fk,
                    'masco_code': code,
                    'job_title': masco_lookup.get(code, ''),
                    'type': course_type,
                })

            self.stdout.write(f'  [{i + 1}/{len(courses)}] {cid}: {len(codes)} codes')

            # Rate limiting between Gemini calls
            if delay > 0 and i < len(courses) - 1:
                time.sleep(delay)

        # Write CSV
        fieldnames = ['course_id', 'course_name', 'field_key', 'masco_code', 'job_title', 'type']
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        self.stdout.write(self.style.SUCCESS(
            f'Wrote {len(rows)} rows to {output_path}'))

    def _apply(self, csv_path):
        """Apply mode: read reviewed CSV and create M2M links."""
        from apps.courses.models import Course, MascoOccupation, StpmCourse

        if not os.path.exists(csv_path):
            raise CommandError(f'CSV file not found: {csv_path}')

        applied = 0
        skipped = 0

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                course_id = row['course_id']
                masco_code = row['masco_code']
                course_type = row.get('type', 'spm')

                # Find the MASCO occupation
                try:
                    occ = MascoOccupation.objects.get(masco_code=masco_code)
                except MascoOccupation.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f'  MASCO {masco_code} not found, skipping'))
                    skipped += 1
                    continue

                # Find the course and add M2M link
                if course_type == 'stpm':
                    try:
                        course = StpmCourse.objects.get(course_id=course_id)
                    except StpmCourse.DoesNotExist:
                        self.stdout.write(self.style.WARNING(
                            f'  STPM course {course_id} not found, skipping'))
                        skipped += 1
                        continue
                else:
                    try:
                        course = Course.objects.get(course_id=course_id)
                    except Course.DoesNotExist:
                        self.stdout.write(self.style.WARNING(
                            f'  Course {course_id} not found, skipping'))
                        skipped += 1
                        continue

                course.career_occupations.add(occ)
                applied += 1

        self.stdout.write(self.style.SUCCESS(
            f'Applied {applied} links, skipped {skipped}'))
