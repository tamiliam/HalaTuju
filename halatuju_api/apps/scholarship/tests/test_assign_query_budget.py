"""A2.3 / TD-519 — HOW MANY DATABASE QUERIES ONE ASSIGN COSTS, and that it sends no email inline.

Assign p95 was about 45 s: the reply rebuilt the whole case (`_detail_payload`, hundreds of
queries) and the request waited on two Brevo sends. Since A2.3 the reply is slim and the emails go
to the assign-emails queue (`assign_notify`). These readings pin both: the count may only go DOWN,
and the two email functions are asserted NOT called inside the request.

The numbers live in `halatuju_api/code-standards.json` (`_admitted`, ledger `query_budgets`), read
directly from that file; `ASSIGN_BUDGETS` is merged into that file's `MEASURED` so a
record nothing here measures is refused there.

Fixtures, on SQLite through the test client: an org-admin assigns an org reviewer to a submitted
case (`first-assign`), and moves an assigned case to a second reviewer (`reassign`). Both with the
student email ON (so its gate would be asked, if it were still inline) and the first-assign profile
draft (`CHECK2_AUTO_GENERATE`) OFF — that draft is a billable Gemini call and its own question.
One warm-up assign on a twin case first, so the auth layer's first-use reads are not counted.
"""
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import resolve

from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme,
)

ASSIGN_ROUTE = 'api/v1/admin/scholarship/applications/<int:pk>/assign/'
FIXTURES = ('first-assign', 'reassign')


def _budgets():
    """Read the `_admitted` records directly (not through `test_query_budgets.RECORD`): that file
    imports this dict into its `MEASURED`, so importing it back here would be circular."""
    import json
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))), 'code-standards.json')
    with open(path, encoding='utf-8') as fh:
        admitted = {r['key']: r['value'] for r in json.load(fh).get('_admitted', [])
                    if isinstance(r, dict) and r.get('ledger') == 'query_budgets'}
    keys = [f'{ASSIGN_ROUTE}::POST::{name}' for name in FIXTURES]
    return {key: admitted.get(key) for key in keys}


ASSIGN_BUDGETS = _budgets()


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   STUDENT_ASSIGNMENT_EMAIL_ENABLED=True, CHECK2_AUTO_GENERATE=False)
class TestTheAssignQueryBudget(TestCase):

    def _reading(self, key):
        fixture = key.split('::')[2]
        org = make_org()
        cohort = make_cohort(programme=make_programme(organisation=org), owning_organisation=org)
        first = make_admin('reviewer', owning_org=org, name='First')
        second = make_admin('reviewer', owning_org=org, name='Second')

        def case():
            if fixture == 'reassign':
                return make_application('assigned', cohort=cohort, reviewer=first,
                                        notify_email='s@example.test')
            return make_application('profile_complete', cohort=cohort, notify_email='s@example.test')

        warm, app = case(), case()
        client = authed_client(make_admin('org_admin', owning_org=org))
        url = '/' + ASSIGN_ROUTE.replace('<int:pk>', '{}')
        with patch('apps.scholarship.emails.send_reviewer_assigned_email') as rev, \
                patch('apps.scholarship.emails.send_student_assigned_reviewer_email') as stu:
            self.assertEqual(client.post(url.format(warm.id), {'reviewer_id': second.id},
                                         format='json').status_code, 200)            # warm-up
            with CaptureQueriesContext(connection) as captured:
                response = client.post(url.format(app.id), {'reviewer_id': second.id}, format='json')
            rev.assert_not_called()          # A2.3: no email inside the request
            stu.assert_not_called()
        self.assertEqual(response.status_code, 200, response.content[:200])
        self.assertEqual((response.json()['id'], response.json()['assigned_to_id']), (app.id, second.id))
        return len(captured.captured_queries)

    def test_each_reading_stays_inside_its_budget(self):
        for key, limit in ASSIGN_BUDGETS.items():
            with self.subTest(key=key):
                now = self._reading(key)
                self.assertLessEqual(now, limit, f'{key} now costs {now} queries; budget {limit}. '
                                     '⚠ DO NOT RAISE IT — the reply has grown back towards the full case.')

    def test_a_budget_that_now_sits_above_the_code_is_lowered(self):
        from apps.scholarship.tests.test_query_budgets import LOWER_IT, SHRINK_SLACK
        loose = [f'ASSIGN_BUDGETS["{k}"]: budget {limit}, code {m} — LOWER it to {m}'
                 for k, limit in ASSIGN_BUDGETS.items() for m in (self._reading(k),)
                 if limit - SHRINK_SLACK > m]
        self.assertEqual(loose, [], LOWER_IT + '\n' + '\n'.join(loose))

    def test_the_budgeted_route_still_resolves(self):
        self.assertEqual(resolve('/' + ASSIGN_ROUTE.replace('<int:pk>', '1')).route, ASSIGN_ROUTE)
