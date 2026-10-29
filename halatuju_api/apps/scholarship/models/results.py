"""When a funded student's next semester result is DUE (student maintenance Sprint 4b, 2026-10-29).

One row per (application, term): the term's end, the date its result is due, and the accepted result
that satisfied it. Written ONLY by ``results_expectations`` (generation, reconcile) and the two daily
jobs (the ``reminded_at`` / ``overdue_flagged_at`` stamps); the term model is explained there and in
``docs/decisions.md`` (2026-10-29, S4b).

⚠ ``due_on`` is STORED when the term's row is made, from the organisation's settings at that moment.
An expectation is a date she was told; a later change to the settings moves the terms that come
after it, never one already promised.
"""
from django.db import models

from .applications import ScholarshipApplication
from .review import SemesterResult


class ResultsExpectation(models.Model):
    application = models.ForeignKey(
        ScholarshipApplication, on_delete=models.CASCADE, related_name='results_expectations')
    #: The k-th result term since she was funded (1-based); `SemesterResult.term_index` mirrors it.
    term_index = models.PositiveSmallIntegerField()
    term_ends_on = models.DateField()
    due_on = models.DateField()
    #: The ACCEPTED result that met it; SET_NULL — a deleted result reopens the term, never the row.
    satisfied_by = models.ForeignKey(
        SemesterResult, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reminded_at = models.DateTimeField(null=True, blank=True)
    overdue_flagged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'results_expectations'
        ordering = ['application_id', 'term_index']
        constraints = [
            models.UniqueConstraint(fields=['application', 'term_index'],
                                    name='results_expectation_app_term_uniq'),
        ]
        indexes = [models.Index(fields=['due_on'], name='results_expectation_due_idx')]

    def __str__(self):
        return f'ResultsExpectation app={self.application_id} term={self.term_index} due={self.due_on}'
