"""Record which exam's results each existing profile holds — where that is knowable.

`results_exam_type` is written going forward whenever a results form is COMPLETED. Every profile
that predates the column has nothing in it, so this fills in the ones whose answer is unambiguous
from the results already on file.

⚠ **A PROFILE HOLDING BOTH SETS IS LEFT BLANK, DELIBERATELY.** The field means *which was completed
LAST*, and for a row that carries both there is no record of the order — `updated_at` is one
timestamp for the whole profile. Guessing would move a live record on no evidence, and the reader
already falls back to the declared `exam_type`, which is what those rows show today. So blank is
both honest and behaviour-preserving. Application #15 is that shape: she declares SPM and carries a
4.0 CGPA she never sat, typed into the course guide to explore.

⚠ **PRESENT STPM DATA IS NOT PROOF SHE SAT IT** — the course guide shares this profile and lets
anyone type STPM grades. Only ABSENCE is conclusive. That is why the only rows filled here are the
ones where exactly one set exists.

    python manage.py backfill_results_exam_type            # report only
    python manage.py backfill_results_exam_type --apply
"""
from django.core.management.base import BaseCommand

from apps.courses.models import StudentProfile


def _has_spm(p):
    return bool(p.grades or {})


def _has_stpm(p):
    return bool(p.stpm_grades or {}) or p.stpm_cgpa is not None


def intended_value(p):
    """The value to record, or '' when the answer is not knowable from the results on file."""
    if (p.results_exam_type or '').strip():
        return ''                               # already recorded — never re-decide it
    spm, stpm = _has_spm(p), _has_stpm(p)
    if spm and stpm:
        return ''                               # order unknown; the reader falls back
    if stpm:
        return 'stpm'
    if spm:
        return 'spm'
    return ''                                   # nothing on file at all


class Command(BaseCommand):
    help = "Fill results_exam_type where exactly one set of results exists (read-only by default)."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write (default: report only).')
        parser.add_argument('--limit', type=int, default=0, help='Print at most N example rows.')

    def handle(self, *args, **opts):
        apply_ = opts['apply']
        printed = 0
        counts = {'spm': 0, 'stpm': 0}
        both = neither = already = 0

        for p in StudentProfile.objects.all().order_by('supabase_user_id').iterator():
            if (p.results_exam_type or '').strip():
                already += 1
                continue
            value = intended_value(p)
            if not value:
                if _has_spm(p) and _has_stpm(p):
                    both += 1
                else:
                    neither += 1
                continue
            counts[value] += 1
            if apply_:
                p.results_exam_type = value
                p.save(update_fields=['results_exam_type'])
            elif not opts['limit'] or printed < opts['limit']:
                self.stdout.write(f'  {p.supabase_user_id}: -> {value}')
                printed += 1

        self.stdout.write(self.style.SUCCESS(
            f'{"" if apply_ else "[report only] "}results_exam_type: '
            f'{counts["spm"]} spm, {counts["stpm"]} stpm, '
            f'{both} left blank (holds both — order unknown), '
            f'{neither} left blank (no results on file), {already} already recorded.'))
