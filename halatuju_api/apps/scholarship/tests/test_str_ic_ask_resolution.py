"""TD-316: the Check-2 ask for an IC that would settle whose STR it is resolves only when the
rule that RAISED it — `income_str_ownership.str_ic_slots`, which also offers the TD-309 card — no
longer names the member. Before, any IC upload whose verdict was 'ok' (the NAME read) cleared it,
even when the field the STR needs (here the NRIC) still had not read; the next sync re-opened it
and the student was emailed again.

One fact decides the ask, the offer and the resolution (docs/decisions.md, 2026-10-01).
"""
from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from apps.scholarship.check2_queries import sync_check2_queries
from apps.scholarship.resolution import doc_match_verdict, resolve_doc_items_for_upload
from apps.scholarship.services import send_due_query_emails
from apps.scholarship.tests.test_income_evidence_homes import _doc
from apps.scholarship.tests.test_income_whose_str_vouches import (
    MOTHER_NAME, MOTHER_NRIC, WhoseStrBase)

ASK = 'mother_ic_for_str_unreadable'


@override_settings(CHECK2_STUDENT_QUERIES_ENABLED=True)
class TestTheStrIcAskResolvesOnTheSameFact(WhoseStrBase):

    def _asked(self):
        """The mother's STR offers ONLY her NRIC; her IC on file read only her NAME. Submitted,
        so Check 2 asks her IC again as UNREADABLE — and the one-time notice already went out."""
        app = self.build('salary', 'mothers_nric_str_her_ic_read_name', True, 'none',
                         submitted=True)
        sync_check2_queries(app)
        ask = app.resolution_items.get(code=ASK)
        self.assertEqual(ask.status, 'open')
        app.query_raised_notified_at = timezone.now() - timedelta(days=2)
        app.save(update_fields=['query_raised_notified_at'])
        return app, ask

    def test_an_ic_whose_NAME_reads_but_not_the_NRIC_leaves_the_ask_open_and_sends_nothing(self):
        app, ask = self._asked()
        again = _doc(app, 'parent_ic', 'mother', name=MOTHER_NAME)       # the NRIC did not read
        self.assertEqual(doc_match_verdict(again), 'ok', 'the shape TD-316 names: verdict ok')
        self.assertEqual(resolve_doc_items_for_upload(app, again), 'ok')  # what the FE is told
        ask.refresh_from_db()
        self.assertEqual((ask.status, ask.resolved_by), ('open', ''))
        # The next sync finds it still open: same row, the notice is not re-armed, no email.
        sync_check2_queries(app)
        app.refresh_from_db()
        self.assertEqual(list(app.resolution_items.filter(code=ASK).values_list('id', 'status')),
                         [(ask.id, 'open')])
        self.assertIsNotNone(app.query_raised_notified_at)
        self.assertEqual(send_due_query_emails()['sent'], 0)

    def test_the_ic_that_SETTLES_it_resolves_the_ask(self):
        app, ask = self._asked()
        settles = _doc(app, 'parent_ic', 'mother', name=MOTHER_NAME, nric=MOTHER_NRIC)
        self.assertEqual(resolve_doc_items_for_upload(app, settles), 'ok')
        ask.refresh_from_db()
        self.assertEqual((ask.status, ask.resolved_by), ('resolved', 'student'))
        sync_check2_queries(app)
        self.assertFalse(app.resolution_items.filter(code__contains='_ic_for_str_',
                                                     status='open').exists())

    def test_the_ownership_rule_is_read_ONLY_when_an_str_ic_ask_is_open(self):
        """The cost of the fix lands only where the fix applies: a parent-IC upload with no STR
        ask open never reads the STR."""
        from unittest import mock
        app = self.build('salary', 'own_both', True, 'none', submitted=True)
        doc = _doc(app, 'parent_ic', 'mother', name=MOTHER_NAME, nric=MOTHER_NRIC)
        with mock.patch('apps.scholarship.income_str_ownership.str_owner_ic_asks') as asks:
            resolve_doc_items_for_upload(app, doc)
        asks.assert_not_called()
