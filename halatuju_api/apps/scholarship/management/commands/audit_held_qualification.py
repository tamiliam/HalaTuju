"""READ-ONLY: which applications change qualification tag / merit basis, OLD and NEW in ONE pass.

BrightPath request #14. `held_qualification` corrects a declared qualification with no results
behind it, and both the tag and the ranking score read it — so this alters a DERIVED value, and
the standing rule for those is to compute the old answer and the new answer together rather than
running the same report a deploy apart. Drift then stops being an available explanation.

The rule this exists to catch is request #9's, verbatim: *when a change alters a derived value,
the blast radius is every record satisfying your predicate, not the ones you had in mind.* That
one changed 72 records instead of 4, and every test passed, because the tests described the shape
the author meant rather than the predicate they wrote.

⚠ Writes NOTHING. There is no `--apply`, deliberately — nothing is stored. `qualification` and
`merit_score` are computed live at every read, so the deploy IS the change and this only says what
it will do.

    python manage.py audit_held_qualification            # live applications
    python manage.py audit_held_qualification --all      # closed ones too
"""
from django.core.management.base import BaseCommand

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.serializers_admin import held_qualification

#: Rejected/withdrawn/expired records are not read on any surface this touches.
_ENDED = ('rejected', 'withdrawn', 'expired')


def _old_merit_basis(p):
    """What the merit score was taken from BEFORE the fix — the declared exam type."""
    return 'stpm_cgpa' if (getattr(p, 'exam_type', '') or '') == 'stpm' else 'spm_merit'


def _new_merit_basis(p):
    return 'stpm_cgpa' if held_qualification(p) == 'stpm' else 'spm_merit'


class Command(BaseCommand):
    help = 'Report which applications change qualification tag or merit basis (read-only).'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true',
                            help='Include rejected / withdrawn / expired applications.')

    def handle(self, *args, **opts):
        qs = ScholarshipApplication.objects.select_related('profile').order_by('id')
        if not opts['all']:
            qs = qs.exclude(status__in=_ENDED)

        changed = unchanged = no_profile = 0
        for app in qs:
            p = app.profile
            if p is None:
                no_profile += 1
                continue
            old_tag = (getattr(p, 'exam_type', '') or '')
            new_tag = held_qualification(p)
            old_basis, new_basis = _old_merit_basis(p), _new_merit_basis(p)
            if old_tag == new_tag and old_basis == new_basis:
                unchanged += 1
                continue
            # The figure itself, so "gains a score" is visible rather than inferred: an absent
            # CGPA is why #106 carried no merit at all, and that is the point of the change.
            old_value = p.stpm_cgpa if old_basis == 'stpm_cgpa' else '(computed from SPM)'
            new_value = p.stpm_cgpa if new_basis == 'stpm_cgpa' else '(computed from SPM)'
            self.stdout.write(
                f'  app {app.id} ({app.status}): tag {old_tag or "—"} -> {new_tag or "—"}; '
                f'merit from {old_basis} [{old_value}] -> {new_basis} [{new_value}]')
            changed += 1

        self.stdout.write(self.style.SUCCESS(
            f'held-qualification audit: {changed} change, {unchanged} unchanged, '
            f'{no_profile} without a profile.'))
