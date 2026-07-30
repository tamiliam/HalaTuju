"""TD-201 — the Requests thread as a DISCUSSION, and the visibility line through it.

The highest-consequence assertion in this file is that an **internal** comment never reaches the
requesting organisation. That is a ROW-level leak: `OrgRequestOrgSerializer` is an allowlist and
cannot leak a field it does not name, but it names `body`, and it will render an internal comment's
body just as happily as a shared one. So the filter lives in `org_requests.comments_for` and is
asserted here at BOTH the service and the endpoint.
"""
from unittest import mock

import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import org_requests
from apps.scholarship.models import OrgRequest
from apps.scholarship.serializers_admin import OrgRequestOrgSerializer, OrgRequestOwnerSerializer

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
BASE = '/api/v1/admin/scholarship/requests/'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REQUESTS_ENABLED=True)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='cm', name='Comment Org')
        cls.other = PartnerOrganisation.objects.create(code='cm2', name='Other Org')
        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='cm-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Dina', email='dina@cm.test')
        # A SECOND admin of the same org — the owner's point was that they could only watch.
        cls.oa2 = PartnerAdmin.objects.create(
            supabase_user_id='cm-oa2', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Farid', email='farid@cm.test')
        cls.other_oa = PartnerAdmin.objects.create(
            supabase_user_id='cm-oa-x', role='org_admin', is_active=True,
            owning_organisation=cls.other, name='Intruder', email='x@cm2.test')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='cm-su', is_super_admin=True, is_active=True,
            name='Super', email='su@cm.test')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _req(self, status='submitted'):
        return OrgRequest.objects.create(
            organisation=self.org, submitted_by=self.oa, kind='feature',
            title='t', description='d', status=status)


class TestVisibility(_Base):
    """The line that matters. An internal comment is ours; a shared one is the conversation."""

    def _both(self, req):
        org_requests.post_comment(req, self.super, 'shared with them',
                                  author_kind=org_requests.AUTHOR_OWNER,
                                  visibility=org_requests.VISIBILITY_SHARED)
        org_requests.post_comment(req, self.super, 'OUR PRIVATE ASSESSMENT',
                                  author_kind=org_requests.AUTHOR_OWNER,
                                  visibility=org_requests.VISIBILITY_INTERNAL)

    def test_the_org_serializer_carries_shared_only(self):
        req = self._req()
        self._both(req)
        data = OrgRequestOrgSerializer(req).data
        bodies = [c['body'] for c in data['comments']]
        self.assertEqual(bodies, ['shared with them'])
        self.assertNotIn('OUR PRIVATE ASSESSMENT', str(data))

    def test_the_owner_serializer_carries_both(self):
        req = self._req()
        self._both(req)
        bodies = [c['body'] for c in OrgRequestOwnerSerializer(req).data['comments']]
        self.assertEqual(bodies, ['shared with them', 'OUR PRIVATE ASSESSMENT'])

    def test_the_ENDPOINT_hides_an_internal_comment_from_the_org(self):
        # The serializer is only half the answer — this is what the requester's browser receives.
        req = self._req()
        self._both(req)
        self._auth('cm-oa')
        body = self.client.get(f'{BASE}{req.id}/').json()
        self.assertEqual([c['body'] for c in body['comments']], ['shared with them'])
        self.assertNotIn('OUR PRIVATE ASSESSMENT', str(body))

    def test_an_org_author_can_NEVER_be_internal(self):
        # There is no org-internal tier. If one is ever wanted it is a THIRD value, not a reuse
        # of this one — otherwise 'internal' would mean two different audiences.
        req = self._req()
        with self.assertRaises(org_requests.OrgRequestError) as e:
            org_requests.post_comment(req, self.oa, 'x', author_kind=org_requests.AUTHOR_ORG,
                                      visibility=org_requests.VISIBILITY_INTERNAL)
        self.assertEqual(e.exception.code, 'bad_visibility')

    def test_an_org_admin_cannot_POST_an_internal_comment(self):
        req = self._req()
        self._auth('cm-oa')
        r = self.client.post(f'{BASE}{req.id}/comments/',
                             {'body': 'sneaky', 'visibility': 'internal'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(req.comments.count(), 0)


class TestWhoMayPost(_Base):
    def test_a_second_org_admin_of_the_same_org_may_comment(self):
        """The owner's complaint: another org_admin could open the request and only watch.
        They can already READ it (requests are org-fenced), so this adds no visibility."""
        req = self._req()
        self._auth('cm-oa2')
        r = self.client.post(f'{BASE}{req.id}/comments/', {'body': 'I hit this too'},
                             format='json')
        self.assertEqual(r.status_code, 200)
        c = req.comments.get()
        self.assertEqual(c.author_kind, org_requests.AUTHOR_ORG)
        self.assertEqual(c.author_admin, self.oa2)
        self.assertEqual(c.visibility, org_requests.VISIBILITY_SHARED)

    def test_a_cross_org_admin_gets_404_not_403(self):
        # The org fence is the request LOOKUP — a foreign pk does not exist for this caller, and
        # a 403 would confirm it does.
        req = self._req()
        self._auth('cm-oa-x')
        r = self.client.post(f'{BASE}{req.id}/comments/', {'body': 'nosy'}, format='json')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(req.comments.count(), 0)

    def test_the_denied_roles_stay_denied(self):
        req = self._req()
        for role in ('admin', 'reviewer', 'qc', 'finance'):
            PartnerAdmin.objects.create(
                supabase_user_id=f'cm-{role}', role=role, is_active=True,
                owning_organisation=self.org, name=role, email=f'{role}@cm.test')
            self._auth(f'cm-{role}')
            r = self.client.post(f'{BASE}{req.id}/comments/', {'body': 'x'}, format='json')
            self.assertEqual(r.status_code, 403, role)


class TestTheWindow(_Base):
    """Commenting runs until TERMINAL — deliberately wider than OPEN_FOR_SHAPING."""

    def test_open_after_the_quote_is_accepted(self):
        # The whole point of the owner's Bugzilla framing: discussion continues after assignment.
        for status in ('quoted', 'approved', 'scheduled'):
            with self.subTest(status=status):
                req = self._req(status=status)
                self.assertTrue(org_requests.can_comment(req))
                org_requests.post_comment(req, self.super, 'still talking',
                                          author_kind=org_requests.AUTHOR_OWNER)
                self.assertEqual(req.comments.count(), 1)

    def test_closed_once_terminal(self):
        for status in ('done', 'declined'):
            with self.subTest(status=status):
                req = self._req(status=status)
                self.assertFalse(org_requests.can_comment(req))
                with self.assertRaises(org_requests.OrgRequestError) as e:
                    org_requests.post_comment(req, self.super, 'too late',
                                              author_kind=org_requests.AUTHOR_OWNER)
                self.assertEqual(e.exception.code, 'bad_transition')

    def test_asking_a_NEW_question_stays_narrower_than_commenting(self):
        """Two windows, deliberately. A question can re-price a quoted request; a remark cannot."""
        req = self._req(status='quoted')
        self.assertTrue(org_requests.can_comment(req))
        with self.assertRaises(org_requests.OrgRequestError) as e:
            org_requests.ask_question(req, self.super, 'one more thing?')
        self.assertEqual(e.exception.code, 'bad_transition')


class TestTheStatementVerb(_Base):
    """`comment` is the verb the module never had — the reason TD-201 exists."""

    def test_the_owner_posts_a_conclusion_and_it_awaits_nothing(self):
        req = self._req()
        org_requests.comment(req, self.super, 'We would build an invite, not a direct add.')
        c = req.comments.get()
        self.assertEqual(c.author_kind, org_requests.AUTHOR_OWNER)
        self.assertFalse(c.awaiting_reply, 'a statement expects no reply')
        self.assertEqual(c.visibility, org_requests.VISIBILITY_SHARED)

    def test_a_statement_does_not_spend_the_reviewer_s_question_budget(self):
        req = self._req()
        for i in range(3):
            org_requests.comment(req, self.super, f'thought {i}')
        self.assertEqual(len(org_requests._open_ai_questions(req)), 0)

    def test_only_a_super_may_post_a_statement_through_the_service(self):
        req = self._req()
        with self.assertRaises(org_requests.OrgRequestError) as e:
            org_requests.comment(req, self.oa, 'not mine to make')
        self.assertEqual(e.exception.code, 'forbidden')


class TestTheReviewerReadsTheThread(_Base):
    def test_the_prompt_carries_internal_comments_too(self):
        """The reviewer is platform-side. The owner's private judgement is exactly what a re-run
        should reason WITH — it is the ORG serializer that keeps it from the requester, not the
        prompt."""
        req = self._req()
        org_requests.post_comment(req, self.super, 'privately: this smells like consent',
                                  author_kind=org_requests.AUTHOR_OWNER,
                                  visibility=org_requests.VISIBILITY_INTERNAL)
        prompt = org_requests._build_review_prompt(req)
        self.assertIn('privately: this smells like consent', prompt)
        self.assertIn('(internal)', prompt)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REQUESTS_ENABLED=True, GEMINI_API_KEY='k')
class TestTheAiQuestionsAreComments(_Base):
    _GOOD = ('{"classification": "feature", "lane": "sprint", '
             '"clarifying_questions": ["Which report?"], "rationale": "r"}')

    def test_an_ai_question_lands_as_a_comment_awaiting_a_reply(self):
        req = self._req()
        with mock.patch('apps.scholarship.contracts._gemini_generate', return_value=self._GOOD):
            org_requests.run_ai_review(req)
        c = req.comments.get()
        self.assertEqual(c.body, 'Which report?')
        self.assertEqual(c.author_kind, org_requests.AUTHOR_AI)
        self.assertIsNone(c.author_admin, 'the reviewer has no PartnerAdmin row')
        self.assertTrue(c.awaiting_reply)
        self.assertEqual(c.visibility, org_requests.VISIBILITY_SHARED)
