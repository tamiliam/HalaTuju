"""Normalise recommender Institution display names for consistency (Title Case is already
the norm; this fixes the two remaining classes):
  1. Expand the matriculation abbreviations — "KM <State>" → "Kolej Matrikulasi <State>",
     "KMK <State>" → "Kolej Matrikulasi Kejuruteraan <State>".
  2. Upper-case a handful of mis-cased acronyms (Kte→KTE, leading Smk→SMK), by institution_id.
Only the display name (`institution_name`) changes; `institution_id` (the FK key) is untouched,
so all CourseInstitution links and pages follow automatically. Idempotent; pass --apply to write.
"""
from django.core.management.base import BaseCommand
from apps.courses.models import Institution

# Explicit fixes for mis-cased acronyms that a generic rule can't safely infer.
ACRONYM_FIX = {
    'KEE2104': 'SMK Tunku Abd. Aziz',
    'CEA5061': 'SMK (LKTP) Chini',
    'CEA9060': 'SMKTAA Chenor',
    'AEB2061': 'KTE Seri Ipoh',
    'AEB2059': 'KTE Seri Putera',
    'PEA2089': 'KTE Desa Murni',
}


def normalised_name(institution_id: str, name: str) -> str:
    """The canonical display name for one institution, or the same name if already canonical."""
    if institution_id in ACRONYM_FIX:
        return ACRONYM_FIX[institution_id]
    if name.startswith('KMK '):
        return 'Kolej Matrikulasi Kejuruteraan ' + name[4:]
    if name.startswith('KM '):
        return 'Kolej Matrikulasi ' + name[3:]
    return name


class Command(BaseCommand):
    help = "Normalise Institution display names (expand matric abbreviations; fix mis-cased acronyms)."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write changes (default: dry-run).')

    def handle(self, *args, **opts):
        apply = opts['apply']
        changed = 0
        for inst in Institution.objects.all():
            new = normalised_name(inst.institution_id, inst.institution_name)
            if new == inst.institution_name:
                continue
            self.stdout.write(f"  {inst.institution_id}: {inst.institution_name!r} -> {new!r}")
            if apply:
                inst.institution_name = new
                inst.save(update_fields=['institution_name'])
            changed += 1
        self.stdout.write(self.style.SUCCESS(
            f'{"[APPLIED] " if apply else "[dry-run] "}{changed} institution name(s) normalised.'))
