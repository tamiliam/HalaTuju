"""Bring every stored STPM CGPA into line with the grades, and keep the merit's co-curriculum —
STPM CGPA sprint C2 (2026-10-28).

Owner rulings (2026-10-28): an STPM student's CGPA is the PNGK worked out from their grades
(Pengajian Am + best three others, `apps.courses.stpm_pngk`), never typed. CGPA AND MERIT ARE
DIFFERENT: the merit stays `overall_from(CGPA, koko)` / 4 x 100 (0.9 x CGPA + 0.04 x koko, as
today), now with the PNGK as the CGPA. Since C2 every CGPA reader asks `stpm_cgpa_of` and the merit
asks `stpm_merit_overall`; this command makes the STORED columns agree, and — run before the
release — gives the owner the before/after list.

THE CO-CURRICULUM SCORE WAS NEVER STORED. The stored `stpm_cgpa` is the old onboarding calculator's
overall = round(0.9 x A + 0.04 x koko, 2), where A is `stpm_engine.calculate_stpm_cgpa` of the
grades (the plain average of ALL grades, 2 decimals). So each existing student's score is derived:

    koko = (stored stpm_cgpa - 0.9 x A) / 0.04

rounded HALF-UP to the calculator's koko step (0.01 — the step on the form's koko box) and clamped
to 0-10. It LANDS CLEANLY when the raw figure needed no clamping AND `overall_from(A, koko)` gives
back the stored figure exactly; anything else is reported (`KOKO NOT CLEAN`) and written clamped.
⚠ "Clean" catches only figures that need a score outside 0-10: with a 0.01 step almost any figure
in range reproduces, so a CGPA typed by hand can read clean. A stored figure outside (0, 4], no
stored figure, no grade on the scale, or a stored figure that is already the PNGK (written by the
C2 image) gives nothing to derive — `NO KOKO`, and that student has no merit until they re-enter
their co-curriculum score (`derive_koko` has the exact rule).

PREVIEW BY DEFAULT. It writes nothing unless `--apply` is passed.

The preview prints one line per application held as STPM: the application id and status (ids
only — no name, no NRIC, no profile or account id; the output may be pasted), the CGPA before ->
after ("not calculated" keeps the stored figure, owner ruling), the derived co-curriculum score,
the merit before -> after, and the academic gate before -> after against that application's own
intake (`min_stpm_pngk`). "Before" is each figure as the readers saw it before C2 (the stored
`stpm_cgpa` for both the CGPA and the merit); "after" is what they see once the columns are
written.

⚠ IT DOES NOT RE-SCORE ANYTHING. The gate runs at submit and again only through
`rescore_pending_decisions`; a decision already made stands. A row whose gate flips is marked
`GATE FLIPS` so the owner can decide what, if anything, to do about it.

`--apply` writes, on every STPM profile (applications or not — the course guide reads it too):
`stpm_koko` = the derived score where none is stored, and `stpm_cgpa` = the PNGK where the grades
give one that differs — but ONLY on a profile that has (or now gets) a co-curriculum score, because
the stored figure is the one thing the score can be derived from. Both from the figures as they
stood BEFORE this run, in one transaction, with `.update()` (no other column, nor `updated_at`,
moves). Idempotent: a second run derives nothing (the score is stored) and rewrites nothing (the
CGPA agrees, or was left as the only source). Readers never need the rewrite: they read through
(`stpm_cgpa_of`).

⚠ ORDER. Once the C2 image serves, a profile write that touches the STPM results stores the PNGK
over the old figure — and with it goes the only source of that student's derived score. So the
score is derived BEFORE the deploy, with `--koko-only` (it writes `stpm_koko` only; the image
serving then never reads that column, so nothing visible moves), and the CGPA column after:

    python manage.py backfill_stpm_cgpa --koko-only             # preview (the owner's list, pre-deploy)
    python manage.py backfill_stpm_cgpa --apply --koko-only     # after migrate, BEFORE deploy
    python manage.py backfill_stpm_cgpa --apply                 # after deploy: the CGPA column
"""
from copy import copy
from decimal import ROUND_HALF_UP, Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.courses.exam_questions import merit_100, overall_from, results_held
from apps.courses.models import StudentProfile
from apps.courses.stpm_engine import STPM_CGPA_POINTS, calculate_stpm_cgpa
from apps.courses.stpm_pngk import pngk_from_grades
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.shortlisting import _academic_ok

#: Two CGPAs closer than this are the same figure (both are two-decimal values).
_SAME = 0.005
#: The onboarding calculator's koko step (the form's koko box: step 0.01).
KOKO_STEP = Decimal('0.01')
KOKO_MAX = 10


def _stored(profile):
    try:
        return None if profile.stpm_cgpa is None else float(profile.stpm_cgpa)
    except (TypeError, ValueError):
        return None


def derive_koko(profile, pre_deploy=False):
    """(koko, clean) — the co-curriculum score the merit will read for this profile.

    The score is DERIVED (module docstring) only from a stored figure that is still the OLD
    calculator's: in (0, 4] — outside it the figure was never a calculator answer (a 0 saved before
    the calculator replied, a hand-sent value), so there is nothing to derive — and, when the grades
    give a PNGK, DIFFERENT from it. Once the C2 image serves, the writer stores the PNGK over the old
    figure, so a figure equal to the PNGK carries no co-curriculum to recover: deriving from it
    would invent one (review, HIGH). `pre_deploy=True` (`--koko-only`, run before the C2 image
    serves, when no row can yet hold a PNGK the writer put there) also derives where the old figure
    happens to equal the PNGK (all-A with koko 10 gives 4.00 both ways).

    A derived score REPLACES a stored one only when the stored CGPA is still an old figure beside a
    PNGK — the student re-saved on the old image after `--koko-only` ran. Otherwise a stored score
    stands, (score, True). Nothing to derive and nothing stored: (None, False)."""
    koko_now = getattr(profile, 'stpm_koko', None)
    stored = _stored(profile)
    grades = profile.stpm_grades if isinstance(profile.stpm_grades, dict) else {}
    calc = pngk_from_grades(grades)
    if stored is not None and 0 < stored <= 4.0 and any(g in STPM_CGPA_POINTS for g in grades.values()):
        old = calc is None or _differs(stored, calc)
        if (old and (koko_now is None or calc is not None)) or (pre_deploy and koko_now is None):
            return _from_old_figure(stored, calculate_stpm_cgpa(grades))
    if koko_now is not None:
        return float(koko_now), True
    return None, False


def _from_old_figure(stored, average):
    """(koko, clean) from an old calculator figure and the plain average it was made from.

    CLEAN means only: the raw figure needed no clamping and `overall_from(average, koko)` gives the
    stored figure back. With a 0.01 step that reproduction is almost always possible, so a clean
    score does NOT prove the figure came from the calculator — a CGPA typed by hand inside the
    reachable range reads clean too. Clamped figures (needing a score below 0 or above 10) are the
    ones it can catch."""
    raw = (Decimal(str(stored)) - Decimal('0.9') * Decimal(str(average))) / Decimal('0.04')
    rounded = raw.quantize(KOKO_STEP, rounding=ROUND_HALF_UP)
    clamped = min(max(rounded, Decimal(0)), Decimal(KOKO_MAX))
    koko = float(clamped)
    return koko, clamped == rounded and abs(overall_from(average, koko) - stored) < _SAME


def _after(profile, koko):
    """An unsaved copy of the profile as the readers will see it once `--apply` has written."""
    p = copy(profile)
    calc = pngk_from_grades(profile.stpm_grades)
    if calc is not None:
        p.stpm_cgpa = calc
    p.stpm_koko = koko
    return p


def _merit_before(stored):
    """The STPM merit before C2: the stored figure / 4 x 100, absent outside (0, 4]."""
    return None if stored is None or not 0 < stored <= 4.0 else round(stored / 4.0 * 100, 2)


def _gate(profile, cohort, reader):
    if cohort is None:
        return '-'
    ok, why = _academic_ok(profile, cohort, cgpa_of=reader)
    return 'PASS' if ok else f'REJECT ({why})'


def _fmt(v):
    return '-' if v is None else f'{v:.2f}'


def _differs(a, b):
    return (a is None) != (b is None) or (a is not None and abs(a - b) >= _SAME)


def preview_rows(applications, pre_deploy=False):
    """One dict per STPM-held application: what the readers saw before C2 and what they see once
    the columns are written."""
    rows = []
    for app in applications:
        p = app.profile
        if p is None or results_held(p) != 'stpm':
            continue
        stored = _stored(p)
        calc = pngk_from_grades(p.stpm_grades)
        after = calc if calc is not None else stored
        koko, clean = derive_koko(p, pre_deploy)
        gate_before = _gate(p, app.cohort, lambda _p, v=stored: v)
        gate_after = _gate(_after(p, koko), app.cohort, lambda _p, v=after: v)
        rows.append({
            'application': app.id, 'status': app.status,
            'stored': stored, 'calculated': calc, 'cgpa_after': after,
            'koko': koko, 'koko_clean': clean, 'koko_stored': p.stpm_koko is not None and koko == p.stpm_koko,
            'merit_before': _merit_before(stored), 'merit_after': merit_100(_after(p, koko)),
            'gate_before': gate_before, 'gate_after': gate_after,
            'changed': _differs(stored, after), 'gate_flips': gate_before != gate_after,
        })
    return rows


def profiles_to_write(koko_only=False):
    """[(profile pk, {column: value})] for every STPM profile with something to write — the derived
    co-curriculum score where none is stored, the PNGK where the stored CGPA disagrees (only beside
    a score, and never with `koko_only`) — and the number of derived scores not landing cleanly."""
    out, unclean = [], 0
    qs = StudentProfile.objects.select_for_update().filter(
        Q(stpm_cgpa__isnull=False) | ~(Q(stpm_grades={}) | Q(stpm_grades__isnull=True)))
    for p in qs.only('pk', 'stpm_grades', 'stpm_cgpa', 'stpm_koko').order_by('pk').iterator():
        write = {}
        koko, clean = derive_koko(p, pre_deploy=koko_only)
        if koko is not None and koko != p.stpm_koko:
            write['stpm_koko'] = koko
            unclean += not clean
        calc = pngk_from_grades(p.stpm_grades)
        if not koko_only and koko is not None and calc is not None and _differs(_stored(p), calc):
            write['stpm_cgpa'] = calc
        if write:
            out.append((p.pk, write))
    return out, unclean


class Command(BaseCommand):
    help = ('STPM CGPA = PNGK of the grades; derive the stored co-curriculum score for the merit. '
            'Preview unless --apply.')

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write (default: preview only).')
        parser.add_argument('--koko-only', action='store_true',
                            help='Write only the derived stpm_koko (run BEFORE the C2 deploy).')

    def handle(self, *args, **opts):
        apps_ = (ScholarshipApplication.objects.select_related('profile', 'cohort')
                 .filter(Q(profile__stpm_cgpa__isnull=False) | ~Q(profile__stpm_grades={}))
                 .order_by('id'))
        rows = preview_rows(apps_, pre_deploy=opts['koko_only'])
        w = self.stdout.write
        w('app\tstatus\tCGPA before -> after\tkoko\tmerit before -> after\tgate before -> after')
        for r in rows:
            calc = _fmt(r['cgpa_after']) if r['calculated'] is not None \
                else f"{_fmt(r['cgpa_after'])} (not calculated)"
            koko = _fmt(r['koko']) + ('' if r['koko_clean'] or r['koko'] is None else ' KOKO NOT CLEAN')
            koko += ' (stored)' if r['koko_stored'] else ''
            if r['koko'] is None:
                koko = '- NO KOKO'
            mark = '  GATE FLIPS' if r['gate_flips'] else ''
            w(f"#{r['application']}\t{r['status']}\t{_fmt(r['stored'])} -> {calc}\t{koko}\t"
              f"{_fmt(r['merit_before'])} -> {_fmt(r['merit_after'])}\t"
              f"{r['gate_before']} -> {r['gate_after']}{mark}")
        with transaction.atomic():       # read + write under one lock: no write in between is lost
            todo, unclean = profiles_to_write(koko_only=opts['koko_only'])
            if opts['apply']:
                for pk, columns in todo:
                    StudentProfile.objects.filter(pk=pk).update(**columns)
        derived = sum('stpm_koko' in c for _, c in todo)
        rewritten = sum('stpm_cgpa' in c for _, c in todo)
        w('')
        w(f"{len(rows)} STPM application(s): {sum(r['changed'] for r in rows)} change CGPA, "
          f"{sum(r['calculated'] is None for r in rows)} not calculated (fewer than PA + 3), "
          f"{sum(r['gate_flips'] for r in rows)} gate result(s) flip, "
          f"{sum(r['koko'] is not None and not r['koko_clean'] for r in rows)} koko not clean, "
          f"{sum(r['koko'] is None for r in rows)} with no koko.")
        w(f'{len(todo)} profile(s) to write: {derived} co-curriculum score(s) derived '
          f'({unclean} not clean), {rewritten} stpm_cgpa rewritten to the PNGK of their grades.')
        if not opts['apply']:
            w('PREVIEW — nothing written. Re-run with --apply to write.')
            return
        w(self.style.SUCCESS(f'Applied: {len(todo)} profile(s) updated.'))
