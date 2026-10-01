"""TD-257 — the six Requests verbs no test had driven with the flag on and the right role.

The Requests module is TD-219's own ground: `AdminOrgRequestAnswerView` called its service with a
keyword the service had dropped, and every answer 500-ed for eighteen days while the route sat in a
dark-ship 404 sweep and a role-fence loop — "covered", and never once POSTed for real. These six
were in the same position: listed in `test_org_requests_endpoints.TestFlagOff`, refused in
`TestRoleDenials`, and never sent by the role that may send them with `REQUESTS_ENABLED` on.

  requote   — deferred -> quoted, super           (AdminOrgRequestRequoteView)
  modify    — quoted/deferred -> submitted, org_admin; supersedes the analysis (AdminOrgRequestModifyView)
  decline   — -> declined, super (reason required) or org_admin withdraw  (AdminOrgRequestDeclineView)
  ask       — the owner's question, awaiting a reply, super               (AdminOrgRequestAskView)
  schedule  — triaged bug / approved -> scheduled, super                  (AdminOrgRequestScheduleView)
  done      — scheduled -> done, super                                    (AdminOrgRequestDoneView)

STATES ARE REACHED THROUGH THE ENDPOINTS, not by writing `status=`: triage, the engineer's analysis
and its approval, the quote, the defer and the accept are all already-driven routes, so the request
each verb receives is one the product actually produced (BrightPath #24 was a fixture that could
not exist). The only row written by hand is the SUBMITTED request itself, which is what
`create_request` writes and what every other suite here starts from. The AI seam is never live:
there is no GEMINI_API_KEY in the test settings, and the auto-run after `modify` swallows that.
"""
import datetime

from django.test import TestCase, override_settings

from apps.scholarship import org_requests
from apps.scholarship.models import OrgRequest
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_org,
)

BASE = '/api/v1/admin/scholarship/requests/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REQUESTS_ENABLED=True,
                   # `modify` runs auto_run_ai_review, which reaches Gemini when a key is set. The
                   # suite must never pay for a call because of a developer's shell (review F3).
                   GEMINI_API_KEY='')
class _RequestsCase(TestCase):
    def setUp(self):
        self.org = make_org()
        self.org_admin = make_admin('org_admin', owning_org=self.org)
        self.super = make_admin('super', super_admin=True)
        self.owner = authed_client(self.super)
        self.requester = authed_client(self.org_admin)
        self.req = OrgRequest.objects.create(
            organisation=self.org, submitted_by=self.org_admin, kind='feature',
            title='An export button', description='We want the list as a spreadsheet.')

    # ── walking a request forward through routes that are already driven ──────────────────
    def _ok(self, response):
        self.assertEqual(response.status_code, 200, response.content)
        return response

    def _triage(self, kind='feature'):
        lane = 'sprint' if kind == 'feature' else 'small_change'
        self._ok(self.owner.post(f'{BASE}{self.req.id}/triage/',
                                 {'triaged_kind': kind, 'lane': lane}, format='json'))

    def _quoted(self):
        """triaged feature + an APPROVED analysis citing files (TD-204) + a quote."""
        self._triage('feature')
        self._ok(self.owner.post(f'{BASE}{self.req.id}/analysis/',
                                 {'body': 'Reuses the list query.',
                                  'cited_files': ['apps/scholarship/org_requests.py']},
                                 format='json'))
        aid = self.req.analyses.get().id
        self._ok(self.owner.post(f'{BASE}{self.req.id}/analysis/{aid}/approve/', {},
                                 format='json'))
        self._ok(self.owner.post(f'{BASE}{self.req.id}/quote/', {'hours': 10, 'note': 'v1'},
                                 format='json'))

    def _deferred(self):
        self._quoted()
        self._ok(self.requester.post(f'{BASE}{self.req.id}/defer/', {}, format='json'))

    def _reload(self):
        self.req.refresh_from_db()
        return self.req


class TestRequote(_RequestsCase):
    def _requote(self, client, **body):
        return client.post(f'{BASE}{self.req.id}/requote/', body, format='json')

    def test_the_owner_requotes_a_deferred_request(self):
        self._deferred()
        first_quoted_at = self._reload().quoted_at
        r = self._ok(self._requote(self.owner, hours=12, margin_pct=40, note='v2'))
        req = self._reload()
        self.assertEqual((req.status, float(req.quote_hours), req.quote_margin_pct, req.quote_note),
                         ('quoted', 12.0, 40, 'v2'))
        self.assertGreater(req.quoted_at, first_quoted_at)
        self.assertEqual(r.json()['status'], 'quoted')

    def test_only_a_deferred_request_can_be_requoted(self):
        self._quoted()
        r = self._requote(self.owner, hours=12)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_transition'))
        self.assertEqual(float(self._reload().quote_hours), 10.0)

    def test_the_requester_cannot_set_their_own_price(self):
        self._deferred()
        self.assertEqual(self._requote(self.requester, hours=1).status_code, 403)
        self.assertEqual(self._reload().status, 'deferred')


class TestModify(_RequestsCase):
    def _modify(self, client, description):
        return client.post(f'{BASE}{self.req.id}/modify/', {'description': description},
                           format='json')

    def test_the_requester_amends_a_quoted_request_and_it_goes_back_to_triage(self):
        self._quoted()
        self.assertIsNotNone(org_requests.approved_analysis(self.req))
        self._ok(self._modify(self.requester, 'A spreadsheet AND a PDF, please.'))
        req = self._reload()
        self.assertEqual((req.status, req.description),
                         ('submitted', 'A spreadsheet AND a PDF, please.'))
        # The old text is kept in the thread, authored by the org …
        history = req.comments.get(body__startswith='Description amended.')
        self.assertIn('We want the list as a spreadsheet.', history.body)
        self.assertEqual(history.author_kind, 'org')
        # … and the analysis that priced the OLD text no longer stands behind a quote (TD-204).
        self.assertIsNone(org_requests.approved_analysis(req))

    def test_a_blank_amendment_is_refused(self):
        self._quoted()
        r = self._modify(self.requester, '   ')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'description_required'))
        self.assertEqual(self._reload().status, 'quoted')

    def test_the_owner_cannot_rewrite_the_requesters_request(self):
        self._quoted()
        self.assertEqual(self._modify(self.owner, 'owner text').status_code, 403)


class TestDecline(_RequestsCase):
    def _decline(self, client, reason=''):
        return client.post(f'{BASE}{self.req.id}/decline/', {'reason': reason}, format='json')

    def test_the_owner_declines_with_a_reason(self):
        self._ok(self._decline(self.owner, 'Out of scope for the platform.'))
        req = self._reload()
        self.assertEqual((req.status, req.declined_by_role, req.decline_reason),
                         ('declined', 'super', 'Out of scope for the platform.'))

    def test_the_owner_must_say_why(self):
        r = self._decline(self.owner)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'reason_required'))
        self.assertEqual(self._reload().status, 'submitted')

    def test_the_requester_may_withdraw_without_a_reason(self):
        self._quoted()
        self._ok(self._decline(self.requester))
        req = self._reload()
        self.assertEqual((req.status, req.declined_by_role), ('declined', 'org_admin'))

    def test_a_finished_request_cannot_be_declined(self):
        self._triage('bug')
        self._ok(self.owner.post(f'{BASE}{self.req.id}/schedule/', {}, format='json'))
        self._ok(self.owner.post(f'{BASE}{self.req.id}/done/', {}, format='json'))
        r = self._decline(self.owner, 'too late')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_transition'))


class TestAsk(_RequestsCase):
    def _ask(self, client, question):
        return client.post(f'{BASE}{self.req.id}/ask/', {'question': question}, format='json')

    def test_the_owner_asks_and_the_question_waits_for_the_requester(self):
        self._ok(self._ask(self.owner, 'Would an emailed weekly export do?'))
        q = self._reload().comments.get()
        self.assertEqual((q.body, q.author_kind, q.awaiting_reply, q.visibility),
                         ('Would an emailed weekly export do?', 'owner', True, 'shared'))
        # The requester's count badge now has something for them.
        r = self.requester.get(f'{BASE}count/')
        self.assertEqual(r.json()['count'], 1)

    def test_the_same_question_twice_is_a_slip_and_is_refused(self):
        self._ask(self.owner, 'Which list?')
        r = self._ask(self.owner, 'which list?')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'duplicate_question'))
        self.assertEqual(self._reload().comments.count(), 1)

    def test_a_quoted_request_takes_no_new_questions(self):
        # The quote was priced against what was known when it was sent.
        self._quoted()
        r = self._ask(self.owner, 'One more thing?')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_transition'))

    def test_the_requester_cannot_ask_themselves(self):
        self.assertEqual(self._ask(self.requester, 'Hello?').status_code, 403)


class TestScheduleAndDone(_RequestsCase):
    def _schedule(self, client, when=''):
        return client.post(f'{BASE}{self.req.id}/schedule/', {'scheduled_for': when},
                           format='json')

    def _done(self, client):
        return client.post(f'{BASE}{self.req.id}/done/', {}, format='json')

    def test_a_triaged_bug_is_scheduled_with_its_date_and_then_done(self):
        self._triage('bug')
        self._ok(self._schedule(self.owner, '2026-10-15'))
        req = self._reload()
        self.assertEqual((req.status, req.scheduled_for), ('scheduled', datetime.date(2026, 10, 15)))
        self._ok(self._done(self.owner))
        self.assertEqual(self._reload().status, 'done')

    def test_an_accepted_feature_is_schedulable(self):
        self._quoted()
        self._ok(self.requester.post(f'{BASE}{self.req.id}/approve/', {}, format='json'))
        self._ok(self._schedule(self.owner))
        req = self._reload()
        self.assertEqual((req.status, req.scheduled_for), ('scheduled', None))

    def test_a_triaged_feature_must_be_quoted_before_it_is_scheduled(self):
        self._triage('feature')
        r = self._schedule(self.owner)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_transition'))
        self.assertEqual(self._reload().status, 'triaged')

    def test_only_scheduled_work_can_be_marked_done(self):
        self._triage('bug')
        r = self._done(self.owner)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'bad_transition'))
        self.assertEqual(self._reload().status, 'triaged')

    def test_the_requester_cannot_book_or_close_the_work(self):
        self._triage('bug')
        self.assertEqual(self._schedule(self.requester).status_code, 403)
        self.assertEqual(self._done(self.requester).status_code, 403)
        self.assertEqual(self._reload().status, 'triaged')
