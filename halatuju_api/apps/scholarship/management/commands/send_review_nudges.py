"""Verdict-completion SLA nudges (TD-131).

Run frequently (e.g. daily) via the internal cron endpoint job 'review-nudges'. For every
assigned application with no recorded verdict yet, the verdict is due at
``assigned_at + REVIEW_SLA_DAYS``. We:

  • nudge the assigned reviewer REVIEW_NUDGE_SOON_DAYS before the due date (approaching),
  • nudge them again once it's overdue (at/after the due date),
  • escalate to all super-admins REVIEW_ESCALATE_GRACE_DAYS after the due date.

Idempotent: each of the three fires at most once, gated on per-application stamps
(review_nudged_soon_at / review_nudged_overdue_at / review_escalated_at), which assign_reviewer
resets on every (re)assignment. A recorded verdict (verdict_decided_at) drops the application
from the population entirely. Inert unless REVIEW_NUDGES_ENABLED. Best-effort emails.
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship import emails
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.pool import pool_ref

# Statuses where a verdict is no longer expected (terminal / already-decided).
_TERMINAL = {'recommended', 'awarded', 'active', 'maintenance', 'closed', 'rejected', 'withdrawn', 'expired'}


class Command(BaseCommand):
    help = 'Nudge reviewers on verdicts due/overdue and escalate to super-admins (idempotent).'

    def handle(self, *args, **options):
        if not getattr(settings, 'REVIEW_NUDGES_ENABLED', False):
            self.stdout.write('REVIEW_NUDGES_ENABLED is off — no review nudges sent.')
            return
        now = timezone.now()
        sla_days = getattr(settings, 'REVIEW_SLA_DAYS', 10)
        soon_days = getattr(settings, 'REVIEW_NUDGE_SOON_DAYS', 2)
        grace_days = getattr(settings, 'REVIEW_ESCALATE_GRACE_DAYS', 3)

        super_emails = [
            e for e in PartnerAdmin.objects
            .filter(is_super_admin=True, is_active=True)
            .values_list('email', flat=True) if e]

        qs = (ScholarshipApplication.objects
              .filter(assigned_to__isnull=False, assigned_at__isnull=False,
                      verdict_decided_at__isnull=True)
              .exclude(status__in=_TERMINAL)
              .select_related('profile', 'assigned_to'))

        soon, overdue, escalated = [], [], []
        for app in qs:
            due = app.assigned_at + timedelta(days=sla_days)
            ref = pool_ref(app.id)
            applicant_name = getattr(app.profile, 'name', '') if app.profile else ''
            due_by = (app.assigned_at + timedelta(days=sla_days)).date().strftime('%d %b %Y')
            reviewer = app.assigned_to
            reviewer_email = getattr(reviewer, 'email', '') if reviewer else ''
            reviewer_name = getattr(reviewer, 'name', '') if reviewer else ''
            updates = []

            # Approaching — only before the due date.
            if (app.review_nudged_soon_at is None
                    and (due - timedelta(days=soon_days)) <= now < due):
                if reviewer_email:
                    emails.send_reviewer_verdict_due_email(
                        reviewer_email, reviewer_name=reviewer_name, applicant_name=applicant_name,
                        ref=ref, due_by=due_by, overdue=False)
                app.review_nudged_soon_at = now
                updates.append('review_nudged_soon_at')
                soon.append(app.id)

            # Overdue — at/after the due date.
            if app.review_nudged_overdue_at is None and now >= due:
                if reviewer_email:
                    emails.send_reviewer_verdict_due_email(
                        reviewer_email, reviewer_name=reviewer_name, applicant_name=applicant_name,
                        ref=ref, due_by=due_by, overdue=True)
                app.review_nudged_overdue_at = now
                updates.append('review_nudged_overdue_at')
                overdue.append(app.id)

            # Escalation — grace days after the due date, to all super-admins.
            if app.review_escalated_at is None and now >= due + timedelta(days=grace_days):
                for sup in super_emails:
                    emails.send_super_verdict_escalation_email(
                        sup, applicant_name=applicant_name, ref=ref,
                        reviewer_name=reviewer_name, due_by=due_by)
                app.review_escalated_at = now
                updates.append('review_escalated_at')
                escalated.append(app.id)

            if updates:
                app.save(update_fields=updates)

        self.stdout.write(
            f'Review nudges sent. soon={soon} overdue={overdue} escalated={escalated} '
            f'(escalation recipients: {super_emails})')
