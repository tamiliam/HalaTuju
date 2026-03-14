"""
Management command to load STPM degree programme data from CSV files.

Usage:
    python manage.py load_stpm_data
    python manage.py load_stpm_data --data-dir /path/to/csvs
"""
import csv
import json
import os

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.courses.models import StpmCourse, StpmRequirement


# Default data directory relative to this file
DEFAULT_DATA_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'stpm'
)

# Boolean fields stored as 0/1 in the CSV
BOOL_FIELDS = [
    'stpm_req_pa', 'stpm_req_math_t', 'stpm_req_math_m',
    'stpm_req_physics', 'stpm_req_chemistry', 'stpm_req_biology',
    'stpm_req_economics', 'stpm_req_accounting', 'stpm_req_business',
    'spm_credit_bm', 'spm_pass_sejarah', 'spm_credit_bi', 'spm_pass_bi',
    'spm_credit_math', 'spm_pass_math', 'spm_credit_addmath',
    'spm_credit_science',
    'req_interview', 'no_colorblind', 'req_medical_fitness',
    'req_malaysian', 'req_bumiputera',
]

# JSON fields stored as JSON strings in the CSV
JSON_FIELDS = ['stpm_subject_group', 'spm_subject_group']

# CSV files to load
CSV_FILES = [
    'stpm_science_requirements_parsed.csv',
    'stpm_arts_requirements_parsed.csv',
]

# Words that should remain lowercase (unless they are the first word)
_LOWERCASE_WORDS = {
    # Malay connectors
    'dan', 'dengan', 'atau', 'di', 'ke', 'untuk', 'dalam', 'bagi', 'oleh', 'yang',
    # English connectors
    'and', 'of', 'with', 'in', 'for', 'at', 'the', 'or', 'by',
}


def _case_token(token: str, is_first: bool) -> str:
    """Title-case a single word token, lowercasing connectors (unless first).

    Also handles hyphenated words (e.g. LAIN-LAIN -> Lain-Lain).
    """
    if not token:
        return token
    lower = token.lower()
    if not is_first and lower in _LOWERCASE_WORDS:
        return lower
    # Capitalise each hyphen-separated segment
    return '-'.join(part.capitalize() for part in lower.split('-'))


def proper_case_name(name: str) -> str:
    """Convert an all-caps programme name to proper title case.

    Rules:
    - Every word is title-cased by default.
    - Malay/English connector words are lowercased (except the first word).
    - Parenthesised campus suffixes are cased with the same rules.
    - The trailing '#' marker is preserved as-is.
    """
    if not name:
        return name

    import re

    # Strip and split trailing '#' marker
    suffix = ''
    stripped = name.strip()
    if stripped.endswith('#'):
        suffix = ' #'
        stripped = stripped[:-1].rstrip()

    # Split into: plain text segments and parenthesised segments
    # e.g. 'FOO BAR (BAZ QUX) DAN X' -> ['FOO BAR ', '(BAZ QUX)', ' DAN X']
    segment_re = re.compile(r'(\([^)]*\))')
    segments = segment_re.split(stripped)

    result_parts = []
    first_word_seen = False

    for seg in segments:
        if seg.startswith('(') and seg.endswith(')'):
            # Bracketed segment — case the inside independently
            inner = seg[1:-1]
            inner_tokens = re.split(r'(\s+)', inner)
            cased_inner = []
            inner_first = True
            for it in inner_tokens:
                if not it.strip():
                    cased_inner.append(it)
                else:
                    cased_inner.append(_case_token(it, inner_first))
                    inner_first = False
            result_parts.append('(' + ''.join(cased_inner) + ')')
            first_word_seen = True
        else:
            # Plain text segment — tokenise on whitespace
            tokens = re.split(r'(\s+)', seg)
            for tok in tokens:
                if not tok.strip():
                    result_parts.append(tok)
                else:
                    result_parts.append(_case_token(tok, not first_word_seen))
                    first_word_seen = True

    return ''.join(result_parts) + suffix


def parse_bool(value):
    """Parse a boolean from 0/1/empty string."""
    return str(value).strip() in ('1', 'true', 'True')


def parse_float(value, default=None):
    """Parse a float, returning default on failure."""
    try:
        val = str(value).strip()
        if val:
            return float(val)
    except (ValueError, TypeError):
        pass
    return default


def parse_int(value, default=None):
    """Parse an integer, returning default on failure."""
    try:
        val = str(value).strip()
        if val:
            return int(float(val))  # int(float()) handles "2.0"
    except (ValueError, TypeError):
        pass
    return default


def parse_json(value):
    """Parse a JSON string, returning None on failure."""
    try:
        val = str(value).strip()
        if val:
            return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        pass
    return None


class Command(BaseCommand):
    help = 'Load STPM degree programme data from CSV files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-dir',
            type=str,
            default=DEFAULT_DATA_DIR,
            help='Path to directory containing STPM CSV files',
        )

    def handle(self, *args, **options):
        data_dir = os.path.abspath(options['data_dir'])
        self.stdout.write(f'Loading STPM data from: {data_dir}')

        created = 0
        updated = 0

        with transaction.atomic():
            for filename in CSV_FILES:
                csv_path = os.path.join(data_dir, filename)
                if not os.path.exists(csv_path):
                    self.stdout.write(
                        self.style.WARNING(f'  Skipping {filename} (not found)')
                    )
                    continue

                c, u = self._load_csv(csv_path)
                created += c
                updated += u
                self.stdout.write(f'  {filename}: {c} created, {u} updated')

        total = created + updated
        self.stdout.write(
            self.style.SUCCESS(
                f'Done: {created} created, {updated} updated. '
                f'Total: {total} programmes.'
            )
        )

        # Load merit scores
        self._load_merit_data(data_dir)

    def _load_merit_data(self, data_dir):
        """Load UPU merit percentages from slim merit CSVs."""
        merit_files = [
            os.path.join(data_dir, 'stpm_science_merit.csv'),
            os.path.join(data_dir, 'stpm_arts_merit.csv'),
        ]
        updated = 0
        for filepath in merit_files:
            if not os.path.exists(filepath):
                self.stdout.write(
                    self.style.WARNING(f'Merit file not found: {filepath}')
                )
                continue
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    program_id = row.get('program_id', '').strip()
                    merit_raw = row.get('merit', '').strip()
                    if not program_id:
                        continue
                    merit_val = None
                    if merit_raw and merit_raw != 'Tiada':
                        try:
                            merit_val = float(merit_raw.replace('%', ''))
                        except ValueError:
                            pass
                    StpmCourse.objects.filter(
                        course_id=program_id
                    ).update(merit_score=merit_val)
                    updated += 1
        self.stdout.write(
            self.style.SUCCESS(f'Updated {updated} merit scores')
        )

    def _load_csv(self, csv_path):
        """Load a single CSV file. Returns (created_count, updated_count)."""
        created = 0
        updated = 0

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                program_id = row.get('program_id', '').strip()
                if not program_id:
                    continue

                # --- StpmCourse fields ---
                course_defaults = {
                    'course_name': proper_case_name(row.get('program_name', '').strip()),
                    'university': row.get('university', '').strip(),
                    'stream': row.get('stream', 'both').strip() or 'both',
                }

                course, _ = StpmCourse.objects.update_or_create(
                    course_id=program_id,
                    defaults=course_defaults,
                )

                # --- StpmRequirement fields ---
                req_defaults = {
                    'min_cgpa': parse_float(row.get('min_cgpa'), default=2.0),
                    'stpm_min_subjects': parse_int(
                        row.get('stpm_min_subjects'), default=2
                    ),
                    'stpm_min_grade': row.get('stpm_min_grade', 'C').strip() or 'C',
                    'min_muet_band': parse_int(
                        row.get('min_muet_band'), default=1
                    ),
                }

                # Boolean fields
                for field in BOOL_FIELDS:
                    req_defaults[field] = parse_bool(row.get(field, ''))

                # JSON fields
                for field in JSON_FIELDS:
                    req_defaults[field] = parse_json(row.get(field, ''))

                _, was_created = StpmRequirement.objects.update_or_create(
                    course=course,
                    defaults=req_defaults,
                )

                if was_created:
                    created += 1
                else:
                    updated += 1

        return created, updated
