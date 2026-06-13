"""
Coverage inventory for the UP_TVET catalogue (reads a scrape_uptvet CSV; NO DB writes).

Answers the questions a future TVET ingest needs before touching the eligibility engine:
  - How many programmes does the public UP_TVET catalogue actually hold?
  - What is the Awam vs Swasta split? (the catalogue mixes both — the ingest scope decision)
  - Which institutions/providers are entirely NEW vs the ILJTM + ILKBS we already hold?

Coverage is reported BY INSTITUTION NAME, not by course code: the portal's Kod Tauliah
(`TVET/QP…`, `SLW…`) does not match our internal synthetic IDs (`IJTM-*`/`IKBN-*`), so a
code-based diff is meaningless (cf. the SPM `course_id` mismatch). Institution-name overlap
is the honest signal for "do we already cover this provider?".

Usage:
    python manage.py audit_uptvet --csv data/tvet/uptvet_latest.csv
"""
import csv
import re
from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from apps.courses.models import Institution, CourseInstitution, CourseRequirement


def _norm_inst(name):
    """Normalise an institution name for overlap matching (case/space/punct-insensitive)."""
    return re.sub(r'[^a-z0-9]+', ' ', (name or '').lower()).strip()


def summarise(rows):
    """Pure aggregation over scraped rows → coverage summary dict."""
    total = len(rows)
    sektor = Counter((r.get('sektor') or '').strip().lower() or 'blank' for r in rows)
    by_inst = Counter((r.get('institution') or '').strip() for r in rows)
    return {
        'total': total,
        'awam': sektor.get('awam', 0),
        'swasta': sektor.get('swasta', 0),
        'other': total - sektor.get('awam', 0) - sektor.get('swasta', 0),
        'distinct_institutions': len([k for k in by_inst if k]),
        'by_institution': by_inst.most_common(),
    }


def coverage_gap(rows, existing_inst_names):
    """Split the scraped institutions into NEW vs already-held, by normalised name overlap.

    existing_inst_names: iterable of institution names HalaTuju already has TVET courses for.
    Returns new/existing institution name lists + the Awam-only new count (the likely ingest scope).
    """
    have = {_norm_inst(n) for n in existing_inst_names if n}
    seen, new_insts, existing_insts = set(), [], []
    awam_new = 0
    for r in rows:
        inst = (r.get('institution') or '').strip()
        if not inst:
            continue
        key = _norm_inst(inst)
        if key in seen:
            continue
        seen.add(key)
        if key in have:
            existing_insts.append(inst)
        else:
            new_insts.append(inst)
    # Awam-scoped new programme count (per-row, not per-institution).
    for r in rows:
        if (r.get('sektor') or '').strip().lower() == 'awam' and _norm_inst(r.get('institution')) not in have:
            awam_new += 1
    return {
        'new_institutions': sorted(new_insts),
        'existing_institutions': sorted(existing_insts),
        'awam_new_programmes': awam_new,
    }


class Command(BaseCommand):
    help = 'Coverage inventory for a UP_TVET catalogue CSV (no DB writes)'

    def add_arguments(self, parser):
        parser.add_argument('--csv', type=str, required=True, help='Path to a scrape_uptvet CSV')
        parser.add_argument('--top', type=int, default=25, help='Show the top-N institutions by programme count')

    def handle(self, *args, **options):
        try:
            with open(options['csv'], 'r', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
        except FileNotFoundError:
            raise CommandError(f'CSV not found: {options["csv"]}')

        if not rows:
            raise CommandError('CSV has no rows — run scrape_uptvet first.')

        s = summarise(rows)

        # Institution names we already have TVET courses for (source_type='tvet').
        existing_names = list(
            Institution.objects.filter(
                courses_offered__course__requirement__source_type='tvet'
            ).values_list('institution_name', flat=True).distinct()
        )
        gap = coverage_gap(rows, existing_names)

        self.stdout.write('\n=== UP_TVET Coverage Inventory ===')
        self.stdout.write(f'Scraped programmes:      {s["total"]}')
        self.stdout.write(f'  Sektor Awam (public):  {s["awam"]}')
        self.stdout.write(f'  Sektor Swasta:         {s["swasta"]}')
        self.stdout.write(f'  Other/blank:           {s["other"]}')
        self.stdout.write(f'Distinct institutions:   {s["distinct_institutions"]}')
        self.stdout.write(f'\nWe already hold TVET courses for {len(existing_names)} institution(s).')
        self.stdout.write(self.style.SUCCESS(
            f'NEW institutions (not currently covered): {len(gap["new_institutions"])}'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'≈ Awam-sektor NEW programmes (likely ingest scope): {gap["awam_new_programmes"]}'
        ))

        self.stdout.write(f'\n--- Top {options["top"]} institutions by programme count ---')
        for inst, n in s['by_institution'][:options['top']]:
            held = ' (already held)' if _norm_inst(inst) in {_norm_inst(x) for x in existing_names} else ''
            self.stdout.write(f'  {n:4d}  {inst}{held}')

        self.stdout.write(self.style.NOTICE(
            '\nNo DB writes. Use this to decide the Awam/Swasta ingest scope + the per-institution '
            'priority before the (golden-master-adjacent) TVET ingest sprint.'
        ))
