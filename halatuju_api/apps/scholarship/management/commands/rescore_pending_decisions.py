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
