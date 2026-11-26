"""Re-score un-released (pending) applications under the CURRENT shortlisting engine.

Run ON DEMAND after a threshold/policy change (e.g. the B40 income-ceiling rule) so
applicants whose decision has not yet gone out are judged by the new rule. Decisions
already released (and emailed) are never touched. Idempotent.

    python manage.py rescore_pending_decisions
"""
from django.core.management.base import BaseCommand

from apps.scholarship.services import rescore_pending_decisions


class Command(BaseCommand):
    help = "Re-score pending (un-released) applications under the current engine."

    def handle(self, *args, **options):
        result = rescore_pending_decisions()
        self.stdout.write(
            f"rescore_pending_decisions: {result['rescored']} pending re-scored; "
            f"{len(result['changed'])} changed → {result['changed']}"
        )
        if result['held']:
            # Owner ruling 6 (criteria Sprint 2): kept as decided, for a person to look at. Ids only.
            self.stdout.write(
                f"HELD (stored decision kept; the criteria tree would decide differently): "
                f"{len(result['held'])} → {result['held']}"
            )
        if result.get('refused_intakes'):
            # TD-774 (criteria Sprint 3b): an intake whose stored rules are refused is skipped whole.
            self.stderr.write(
                f"SKIPPED (stored entry rules refused; no row of these intakes re-scored): "
                f"{result['refused_intakes']}"
            )
