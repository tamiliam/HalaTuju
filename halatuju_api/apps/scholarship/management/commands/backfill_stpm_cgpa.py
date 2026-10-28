"""Bring every stored STPM CGPA into line with the grades — STPM CGPA sprint C2 (2026-10-28).

Owner ruling: an STPM student's CGPA is worked out from their grades (PNGK = Pengajian Am + best
three others, `apps.courses.stpm_pngk`), never typed. Since C2 every reader asks `stpm_cgpa_of`,
so the merit, the gate, the cockpit and the sponsor line already follow the grades; this command
makes the STORED column agree, and — run before the release — gives the owner the before/after
list the roadmap asks for.

PREVIEW BY DEFAULT. It writes nothing unless `--apply` is passed.

The preview prints one line per application held as STPM: the application id and status, the
profile id (no name, no NRIC — the output may be pasted), the stored CGPA, the calculated one (or
"not calculated" when the grades are fewer than PA + three), the merit before → after, and the
academic gate before → after against that application's own intake (its `min_stpm_pngk`).
"Before" asks the gate with the stored figure, exactly as it ran before C2; "after" with the PNGK.

⚠ IT DOES NOT RE-SCORE ANYTHING. The gate runs at submit and again only through
`rescore_pending_decisions`; a decision already made stands. A row whose gate flips is marked
`GATE FLIPS` so the owner can decide what, if anything, to do about it.

`--apply` writes `stpm_cgpa` = the PNGK on every profile whose grades give one and whose stored
figure differs (applications or not — the course guide reads it too). A profile with too few
grades keeps its figure. Writes with `.update()`, so no other column (nor `updated_at`) moves.

    python manage.py backfill_stpm_cgpa              # preview
    python manage.py backfill_stpm_cgpa --apply
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.courses.exam_questions import results_held
from apps.courses.models import StudentProfile
from apps.courses.stpm_pngk import pngk_from_grades
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.shortlisting import _academic_ok

#: Two CGPAs closer than this are the same figure (both are two-decimal values).
_SAME = 0.005


def _stored(profile):
    try:
        return None if profile.stpm_cgpa is None else float(profile.stpm_cgpa)
    except (TypeError, ValueError):
        return None


def _merit(cgpa):
    """The STPM merit as `exam_questions.merit_100` computes it (overall CGPA / 4 x 100, absent
    outside (0, 4])."""
    return None if cgpa is None or not 0 < cgpa <= 4.0 else round(cgpa / 4.0 * 100, 2)


def _gate(profile, cohort, reader):
    if cohort is None:
        return '-'
    ok, why = _academic_ok(profile, cohort, cgpa_of=reader)
    return 'PASS' if ok else f'REJECT ({why})'


def _fmt(v):
    return '-' if v is None else f'{v:.2f}'


def _differs(a, b):
    return (a is None) != (b is None) or (a is not None and abs(a - b) >= _SAME)


def preview_rows(applications):
    """One dict per STPM-held application: what the readers saw before C2 and what they see now."""
    rows = []
    for app in applications:
        p = app.profile
        if p is None or results_held(p) != 'stpm':
            continue
        stored = _stored(p)
        calc = pngk_from_grades(p.stpm_grades)
        after = calc if calc is not None else stored
        gate_before = _gate(p, app.cohort, lambda _p, v=stored: v)
        gate_after = _gate(p, app.cohort, lambda _p, v=after: v)
        rows.append({
            'application': app.id, 'status': app.status, 'profile': p.pk,
            'stored': stored, 'calculated': calc,
            'merit_before': _merit(stored), 'merit_after': _merit(after),
            'gate_before': gate_before, 'gate_after': gate_after,
            'changed': _differs(stored, after), 'gate_flips': gate_before != gate_after,
        })
    return rows


def profiles_to_write():
    """[(profile, pngk)] for every profile whose grades give a PNGK the stored figure disagrees with."""
    out = []
    qs = StudentProfile.objects.exclude(Q(stpm_grades={}) | Q(stpm_grades__isnull=True))
    for p in qs.only('pk', 'stpm_grades', 'stpm_cgpa').iterator():
        calc = pngk_from_grades(p.stpm_grades)
        if calc is not None and _differs(_stored(p), calc):
            out.append((p, calc))
    return out


class Command(BaseCommand):
    help = 'Recalculate stored STPM CGPAs from the grades (PA + best three). Preview unless --apply.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write (default: preview only).')

    def handle(self, *args, **opts):
        apps_ = (ScholarshipApplication.objects.select_related('profile', 'cohort')
                 .filter(Q(profile__stpm_cgpa__isnull=False) | ~Q(profile__stpm_grades={}))
                 .order_by('id'))
        rows = preview_rows(apps_)
        w = self.stdout.write
        w('app\tstatus\tprofile\tstored\tcalculated\tmerit before -> after\tgate before -> after')
        for r in rows:
            mark = '  GATE FLIPS' if r['gate_flips'] else ''
            calc = _fmt(r['calculated']) if r['calculated'] is not None else 'not calculated'
            w(f"#{r['application']}\t{r['status']}\t{r['profile']}\t{_fmt(r['stored'])}\t{calc}\t"
              f"{_fmt(r['merit_before'])} -> {_fmt(r['merit_after'])}\t"
              f"{r['gate_before']} -> {r['gate_after']}{mark}")
        todo = profiles_to_write()
        w('')
        w(f"{len(rows)} STPM application(s): {sum(r['changed'] for r in rows)} change CGPA, "
          f"{sum(r['calculated'] is None for r in rows)} not calculated (fewer than PA + 3), "
          f"{sum(r['gate_flips'] for r in rows)} gate result(s) flip.")
        w(f'{len(todo)} profile(s) would have stpm_cgpa rewritten to the PNGK of their grades.')
        if not opts['apply']:
            w('PREVIEW — nothing written. Re-run with --apply to write.')
            return
        with transaction.atomic():
            for p, calc in todo:
                StudentProfile.objects.filter(pk=p.pk).update(stpm_cgpa=calc)
        w(self.style.SUCCESS(f'Applied: {len(todo)} profile(s) updated.'))
