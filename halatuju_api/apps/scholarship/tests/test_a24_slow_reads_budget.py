"""A2.4 / SP-05, SP-07 - HOW MANY DATABASE QUERIES the officer's slow case writes and reads cost.

Interview submit, qc-decision and resolution-items each answer with the whole case, and the case
is built from `applicant_documents` by dozens of engines. The GET opens a document snapshot for
that; the POSTs did not, so each paid the engines' re-reads again (TD-282). `_detail_payload` now
opens the snapshot itself, and the submit's agenda check reads inside one too.

Budgets are numbers pinned here (SQLite, the test client, one warm-up request first so the auth
layer's first-use reads are not counted). They may only go DOWN: DO NOT RAISE ONE.
"""
import json
import os
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.scholarship.models import InterviewSession
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, answered_findings, authed_client, make_admin, make_application, make_cohort,
)

ROOT = '/api/v1/admin/scholarship/applications/{}/'
#: reading name -> budget (queries). Measured 2026-11-08, see CHANGELOG A2.4.
#: Before A2.4: 334, 333 and 319 (the engines re-read the documents on every call).
BUDGETS = {'interview-submit': 41, 'qc-reopen': 51, 'resolution-item-add': 37}


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheSlowOfficerWritesQueryBudget(TestCase):

    def _reading(self, name):
        cohort = make_cohort()
        org = cohort.owning_organisation
        reviewer = make_admin('reviewer', owning_org=org)
        qc = make_admin('qc', owning_org=org)

        def case():
            if name == 'interview-submit':
                app = make_application('interviewing', cohort=cohort, reviewer=reviewer)
                InterviewSession.objects.create(
                    application=app, status='draft', findings=answered_findings(app))
                return app
            if name == 'qc-reopen':
                return make_application('awaiting_qc', outcome='recommend', cohort=cohort,
                                        reviewer=reviewer)
            return make_application('interviewing', cohort=cohort, reviewer=reviewer,
                                    profile_completed_at='2026-01-01T00:00:00Z')

        def call(client, app):
            if name == 'interview-submit':
                return client.post(ROOT.format(app.id) + 'interview/submit/')
            if name == 'qc-reopen':
                return client.post(ROOT.format(app.id) + 'qc-decision/',
                                   {'decision': 'reopen', 'comments': 'income unclear'},
                                   format='json')
            return client.post(ROOT.format(app.id) + 'resolution-items/',
                               {'kind': 'explanation', 'prompt': 'Please explain'}, format='json')

        client = authed_client(qc if name == 'qc-reopen' else reviewer)
        warm, app = case(), case()
        with patch('apps.scholarship.views_admin.verdict._email_reviewer'):
            self.assertEqual(call(client, warm).status_code, 200)
            with CaptureQueriesContext(connection) as captured:
                response = call(client, app)
        self.assertEqual(response.status_code, 200, response.content[:300])
        return len(captured.captured_queries)

    def test_each_reading_stays_inside_its_budget(self):
        for name, limit in BUDGETS.items():
            with self.subTest(name=name):
                now = self._reading(name)
                self.assertLessEqual(now, limit, f'{name} now costs {now}; budget {limit}. DO NOT RAISE IT.')

    def test_a_budget_that_now_sits_above_the_code_is_lowered(self):
        loose = [f'BUDGETS["{k}"]: budget {limit}, code {m} - LOWER it to {m}'
                 for k, limit in BUDGETS.items() for m in (self._reading(k),) if limit - 2 > m]
        self.assertEqual(loose, [], 'A budget may only go down:\n' + '\n'.join(loose))
