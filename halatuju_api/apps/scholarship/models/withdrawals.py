"""An award withdrawal REQUEST — the maker and checker of A1.13b (owner ruling 2026-11-08, TD-198).

One person (holding ``award_withdraw_request``) asks, with a required explanation; a DIFFERENT person
(holding ``award_withdraw_approve``) approves, or refuses with a required reason. Nothing about the case
changes until the approval, which runs the withdrawal itself (`award_withdrawal._apply`). A super may read
a request but never sits in either seat. The rules live in `award_withdrawal_chain`.

⚠ ONE PENDING REQUEST PER CASE, held by the database (the partial unique constraint), not only by the
code's check. ⚠ A pending request older than `award_withdrawal_chain.EXPIRY_DAYS` is EXPIRED: read as such
everywhere, and set to ``expired`` under the lock by the next action that touches it (no scheduler job).

The people are kept by email and name as well as by link (SET_NULL), so a deleted staff row never erases
who asked or who decided (the `StaffPermissionChange` pattern). ``snapshot`` is what the maker saw — the
holding sponsorships (ids and amounts), the amount that would be freed, the tranches that would be
withheld — and the approval refuses (``stale``) when the holding sponsorships no longer match it.
"""
from django.db import models


class AwardWithdrawalRequest(models.Model):
    KIND_UNPAID = 'unpaid'
    KIND_PAID = 'paid'   # reserved for TD-591 (a paid withdrawal); refused today
    KIND_CHOICES = [(KIND_UNPAID, 'An unpaid award'), (KIND_PAID, 'A paid award (TD-591, not yet)')]

    PENDING, APPROVED, REFUSED, CANCELLED, EXPIRED = 'pending', 'approved', 'refused', 'cancelled', 'expired'
    STATUS_CHOICES = [
        (PENDING, 'Waiting for a checker'),
        (APPROVED, 'Approved: the award was withdrawn'),
        (REFUSED, 'Refused by the checker'),
        (CANCELLED, 'Cancelled by the person who asked'),
        (EXPIRED, 'Expired: nobody decided in time'),
    ]

    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.CASCADE, related_name='withdrawal_requests')
    # The org fence: the request belongs to the case's organisation, and only its people act on it.
    organisation = models.ForeignKey(
        'courses.PartnerOrganisation', on_delete=models.PROTECT, related_name='award_withdrawal_requests')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_UNPAID)
    # 'breach' / 'our_fault' — reserved for TD-591; blank today.
    reason_type = models.CharField(max_length=20, blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    explanation = models.TextField()

    requested_by = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='award_withdrawals_requested')
    requested_by_email = models.CharField(max_length=254, blank=True, default='')
    requested_by_name = models.CharField(max_length=255, blank=True, default='')
    requested_at = models.DateTimeField(auto_now_add=True)

    decided_by = models.ForeignKey(
        'courses.PartnerAdmin', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='award_withdrawals_decided')
    decided_by_email = models.CharField(max_length=254, blank=True, default='')
    decided_by_name = models.CharField(max_length=255, blank=True, default='')
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True, default='')

    snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'award_withdrawal_requests'
        ordering = ['-requested_at']
        constraints = [
            models.UniqueConstraint(fields=['application'], condition=models.Q(status='pending'),
                                    name='award_withdrawal_one_pending_per_case'),
        ]

    def __str__(self):
        return f'withdrawal request {self.pk} app={self.application_id} {self.status}'
