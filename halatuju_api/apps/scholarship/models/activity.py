"""The student file's activity log (student maintenance Sprint 1, 2026-10-29) — model 70, NEW.

A CRM-style timeline for one funded student: what an officer wrote down (a note, a call, a
meeting, an email) and what the system did (a sub-state change, a payment, a closure, a result).
Written by ``apps/scholarship/activity.py`` (``log_event`` for system rows, ``add_entry`` for
manual ones); read by the admin Scholars file from Sprint 2. Points at ScholarshipApplication.

⚠ A ROW IS A RECORD, NOT A MESSAGE. Nothing here is ever shown to a sponsor; ``internal`` marks a
row the student must not see once a student view of the log exists.
"""
from django.db import models

#: Manual kinds an officer may write; ``system`` is for ``log_event`` only.
MANUAL_KINDS = ('note', 'call', 'meeting', 'email')
KIND_SYSTEM = 'system'
KIND_CHOICES = [
    ('note', 'Note'), ('call', 'Call'), ('meeting', 'Meeting'), ('email', 'Email'),
    (KIND_SYSTEM, 'System'),
]

# ── System event codes (the roadmap's full list; WIRED marks the ones Sprint 1 writes) ────────
EVENT_SUBSTATE_CHANGED = 'substate_changed'     # WIRED: maintenance.set_substate
EVENT_RESULT_SUBMITTED = 'result_submitted'     # WIRED: in_programme.record_semester_result
EVENT_RESULT_REVIEWED = 'result_reviewed'       # Sprint 4 (results review)
EVENT_LETTER_ISSUED = 'letter_issued'           # Sprint 6 (letters)
EVENT_MENTOR_ASSIGNED = 'mentor_assigned'       # Sprint 7 (mentors)
EVENT_SESSION_LOGGED = 'session_logged'         # Sprint 7 (mentors)
EVENT_PAYMENT_RELEASED = 'payment_released'     # WIRED: payments.complete, disbursement.release_tranche
EVENT_CLOSED = 'closed'                         # WIRED: closure.close_application
EVENT_RESULTS_OVERDUE = 'results_overdue'       # WIRED: results_expectations.flag_overdue (S4b)
EVENTS = (
    EVENT_SUBSTATE_CHANGED, EVENT_RESULT_SUBMITTED, EVENT_RESULT_REVIEWED, EVENT_LETTER_ISSUED,
    EVENT_MENTOR_ASSIGNED, EVENT_SESSION_LOGGED, EVENT_PAYMENT_RELEASED, EVENT_CLOSED,
    EVENT_RESULTS_OVERDUE,
)


class StudentActivity(models.Model):
    """One entry on a student's file timeline, newest first."""
    application = models.ForeignKey(
        'ScholarshipApplication', on_delete=models.CASCADE, related_name='activities')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    event = models.CharField(max_length=40, blank=True, default='',
                             help_text='A system event code (activity.EVENTS); blank for a manual entry')
    body = models.TextField(blank=True, default='')
    meta = models.JSONField(default=dict, blank=True,
                            help_text='Structured detail of a system event (old/new, amount, run reference)')
    actor_email = models.CharField(max_length=254, blank=True, default='')
    internal = models.BooleanField(default=False,
                                   help_text='Staff-only: never shown to the student')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'student_activity'
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['application', '-created_at'],
                                name='student_act_app_created_idx')]
        verbose_name_plural = 'Student activities'

    def __str__(self):
        return f'{self.kind}:{self.event or "-"} app={self.application_id}'
