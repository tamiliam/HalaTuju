"""TD-204 — the engineer's analysis, and the quote gate standing on it.

Owner ruling, 2026-07-31: *"Gemini's role is only initial analysis. It has no access to the codebase
and cannot reliably do much. You have to do the proper analysis and estimate the workload, and I
want you to post as well, with my approval."*

Two claims carry the most weight here, and each is asserted from more than one angle:

1. **The requesting organisation never sees the cited files or the engineer's hours.** Not secrecy —
   a citation the requester cannot open buys them nothing, the paths are the internal shape of a
   multi-tenant platform, and a second hours figure in front of them recreates precisely what
   removing the AI's estimate fixed (TD-202). The PROSE is shared, because a price whose reasoning
   is invisible looks arbitrary. Asserted against the payload's VALUES, not just its key set — a
   key-set snapshot cannot catch a path smuggled inside a string.

2. **Both quote twins refuse without an analysis.** `quote()` and `requote()` are byte-identical
   apart from a transition string, and a guard on one of two twins is the exact shape of the
   `award_amount` defect (a rule kept at one caller out of three, which left money on two
   production records for eleven days).
"""
from decimal import Decimal
from unittest import mock

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import org_requests
from apps.scholarship.models import OrgRequest, OrgRequestAnalysis
from apps.scholarship.serializers_admin import OrgRequestOrgSerializer, OrgRequestOwnerSerializer

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
BASE = '/api/v1/admin/scholarship/requests/'

# A real path from this repo — the command validates existence, and a test citing a fictional file
# would drift from what production actually stores.
A_REAL_FILE = 'apps/scholarship/org_requests.py'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REQUESTS_ENABLED=True)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(code='an', name='Analysis Org')
        cls.other = PartnerOrganisation.objects.create(code='an2', name='Other Org')
        cls.oa = PartnerAdmin.objects.create(
            supabase_user_id='an-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='Dina', email='dina@an.test')
        cls.other_oa = PartnerAdmin.objects.create(
            supabase_user_id='an-oa-x', role='org_admin', is_active=True,
            owning_organisation=cls.other, name='Intruder', email='x@an2.test')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='an-su', is_super_admin=True, is_active=True,
            name='Super', email='su@an.test')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _req(self, status='triaged', kind='feature', triaged_kind='feature'):
        return OrgRequest.objects.create(
            organisation=self.org, submitted_by=self.oa, kind=kind,
            triaged_kind=triaged_kind, title='t', description='the original description',
            status=status)

    def _draft(self, req, *, body='It reuses the existing invite engine.', hours='4.0',
               files=(A_REAL_FILE,)):
        return org_requests.record_analysis(
            req, self.super, body=body, estimated_hours=hours, cited_files=list(files),
            authored_by='claude-opus-5', repo_sha='a' * 40)

    def _approved(self, req, **kw):
        return org_requests.approve_analysis(self._draft(req, **kw), self.super)


class TestStagingADraft(_Base):
    def test_a_draft_is_recorded_and_posts_NOTHING(self):
        # The whole two-actor split: staging is free, approval is the control. If a draft posted,
        # the owner's approval would be theatre.
        req = self._req()
        a = self._draft(req)
        self.assertIsNone(a.approved_at)
        self.assertEqual(req.comments.count(), 0)
        self.assertEqual(a.cited_files, [A_REAL_FILE])
        self.assertEqual(a.estimated_hours, Decimal('4.0'))
        self.assertEqual(a.authored_by, 'claude-opus-5')

    def test_the_description_it_was_written_against_is_stamped(self):
        req = self._req()
        a = self._draft(req)
        self.assertEqual(a.description_sha, org_requests._description_sha(req))
        self.assertEqual(len(a.description_sha), 64)

    def test_an_empty_body_is_refused(self):
        req = self._req()
        with self.assertRaises(org_requests.OrgRequestError) as e:
            self._draft(req, body='   ')
        self.assertEqual(e.exception.code, 'body_required')

    def test_citing_NOTHING_is_refused_at_record_time(self):
        # The standing rule: the estimate must cite its files. An analysis citing nothing is the
        # thing this record exists to prevent, so it cannot even be staged.
        req = self._req()
        with self.assertRaises(org_requests.OrgRequestError) as e:
            self._draft(req, files=())
        self.assertEqual(e.exception.code, 'files_required')

    def test_hours_are_optional(self):
        # An analysis may legitimately say "this is bigger than it looks, I cannot price it yet".
        req = self._req()
        a = org_requests.record_analysis(req, self.super, body='b', cited_files=[A_REAL_FILE])
        self.assertIsNone(a.estimated_hours)

    def test_a_terminal_request_cannot_be_analysed(self):
        # Nothing left to analyse, and approval could never post it (post_comment would refuse).
        req = self._req(status='declined')
        with self.assertRaises(org_requests.OrgRequestError) as e:
            self._draft(req)
        self.assertEqual(e.exception.code, 'bad_transition')


class TestTheCitationList(_Base):
    """`_clean_cited_files`, exercised THROUGH `record_analysis` — a unit test on the helper would
    pass just as happily with the helper unwired."""

    def _files(self, req, values):
        return org_requests.record_analysis(
            req, self.super, body='b', cited_files=values).cited_files

    def test_blanks_are_dropped_and_order_is_preserved(self):
        # Order matters: the first file named is usually the one that decides the estimate.
        req = self._req()
        self.assertEqual(self._files(req, ['  b.py ', '', '   ', 'a.py']), ['b.py', 'a.py'])

    def test_duplicates_collapse_keeping_the_first_position(self):
        req = self._req()
        self.assertEqual(self._files(req, ['a.py', 'b.py', 'a.py']), ['a.py', 'b.py'])

    def test_a_string_is_not_a_list_of_files(self):
        # The trap: a bare string IS iterable, so a naive loop would cite 40 single characters.
        req = self._req()
        with self.assertRaises(org_requests.OrgRequestError) as e:
            self._files(req, 'apps/scholarship/org_requests.py')
        self.assertEqual(e.exception.code, 'bad_cited_files')

    def test_non_string_entries_are_refused(self):
        req = self._req()
        for garbage in ([{'path': 'a.py'}], [None], [42]):
            with self.subTest(garbage=garbage):
                with self.assertRaises(org_requests.OrgRequestError) as e:
                    self._files(req, garbage)
                self.assertEqual(e.exception.code, 'bad_cited_files')

    def test_the_list_is_capped(self):
        req = self._req()
        with self.assertRaises(org_requests.OrgRequestError) as e:
            self._files(req, [f'f{i}.py' for i in range(org_requests.MAX_CITED_FILES + 1)])
        self.assertEqual(e.exception.code, 'bad_cited_files')


class TestApproval(_Base):
    def test_approval_posts_the_prose_as_an_ENGINEER_comment(self):
        req = self._req()
        a = self._approved(req)
        c = req.comments.get()
        self.assertEqual(c.author_kind, org_requests.AUTHOR_ENGINEER)
        self.assertEqual(c.body, a.body)
        self.assertEqual(c.visibility, org_requests.VISIBILITY_SHARED)
        self.assertFalse(c.awaiting_reply, 'an analysis is a statement, not a question')
        self.assertEqual(a.posted_comment_id, c.id)

    def test_the_posted_comment_is_attributed_to_NOBODY(self):
        # The owner approved it; the engineer wrote it. Stamping the approver's name beside an
        # "Engineer" badge would be a lie about authorship. The AI's questions do the same.
        req = self._req()
        self._approved(req)
        self.assertIsNone(req.comments.get().author_admin)

    def test_the_approval_itself_IS_attributed(self):
        req = self._req()
        a = self._approved(req)
        self.assertEqual(a.approved_by, self.super)
        self.assertTrue(a.approved_at)

    def test_only_a_super_may_approve(self):
        req = self._req()
        a = self._draft(req)
        with self.assertRaises(org_requests.OrgRequestError) as e:
            org_requests.approve_analysis(a, self.oa)
        self.assertEqual(e.exception.code, 'forbidden')
        self.assertEqual(req.comments.count(), 0)

    def test_approving_twice_posts_once(self):
        req = self._req()
        a = self._draft(req)
        org_requests.approve_analysis(a, self.super)
        org_requests.approve_analysis(a, self.super)
        self.assertEqual(req.comments.count(), 1)

    def test_a_declined_request_leaves_NO_approved_but_unposted_row(self):
        # The atomicity claim. If approval stamped the row and then failed to post, the quote gate
        # would pass on an analysis the requester never received.
        req = self._req()
        a = self._draft(req)
        req.status = 'declined'
        req.save(update_fields=['status'])
        with self.assertRaises(org_requests.OrgRequestError) as e:
            org_requests.approve_analysis(a, self.super)
        self.assertEqual(e.exception.code, 'bad_transition')
        a.refresh_from_db()
        self.assertIsNone(a.approved_at)
        self.assertEqual(req.comments.count(), 0)

    def test_a_superseded_analysis_cannot_be_approved(self):
        req = self._req()
        a = self._draft(req)
        a.superseded_at = timezone.now()
        a.save(update_fields=['superseded_at'])
        with self.assertRaises(org_requests.OrgRequestError) as e:
            org_requests.approve_analysis(a, self.super)
        self.assertEqual(e.exception.code, 'analysis_superseded')


class TestWhatTheOrganisationSees(_Base):
    """The load-bearing privacy claim, asserted on VALUES rather than key names."""

    def test_the_prose_reaches_them_and_the_evidence_does_not(self):
        req = self._req()
        self._approved(req, body='We would reuse the existing invite engine.',
                       hours='4.0', files=['apps/scholarship/referrals.py'])
        data = OrgRequestOrgSerializer(req).data
        blob = str(data)
        self.assertIn('We would reuse the existing invite engine.', blob)
        self.assertNotIn('referrals.py', blob)
        self.assertNotIn('apps/scholarship', blob)
        self.assertNotIn('analyses', data)

    def test_the_ENDPOINT_carries_no_path_and_no_engineer_hours(self):
        # The serializer is half the answer; this is what the requester's browser receives.
        req = self._req()
        self._approved(req, hours='7.5', files=['apps/scholarship/referrals.py'])
        self._auth('an-oa')
        body = self.client.get(f'{BASE}{req.id}/').json()
        blob = str(body)
        self.assertNotIn('referrals.py', blob)
        self.assertNotIn('7.5', blob)
        self.assertNotIn('analyses', body)

    def test_the_owner_sees_the_whole_working_paper(self):
        req = self._req()
        self._approved(req, files=['apps/scholarship/referrals.py'])
        data = OrgRequestOwnerSerializer(req).data
        a = data['analyses'][0]
        self.assertEqual(a['cited_files'], ['apps/scholarship/referrals.py'])
        self.assertEqual(a['estimated_hours'], '4.0')
        self.assertEqual(a['authored_by'], 'claude-opus-5')
        self.assertTrue(a['is_current'])

    def test_an_org_admin_cannot_stage_or_approve(self):
        req = self._req()
        a = self._draft(req)
        self._auth('an-oa')
        r1 = self.client.post(f'{BASE}{req.id}/analysis/',
                              {'body': 'x', 'cited_files': ['a.py']}, format='json')
        r2 = self.client.post(f'{BASE}{req.id}/analysis/{a.id}/approve/', {}, format='json')
        self.assertEqual(r1.status_code, 403)
        self.assertEqual(r2.status_code, 403)
        self.assertEqual(req.analyses.count(), 1)

    def test_a_cross_org_super_side_lookup_is_404(self):
        req = self._req()
        self._auth('an-oa-x')
        r = self.client.post(f'{BASE}{req.id}/analysis/',
                             {'body': 'x', 'cited_files': ['a.py']}, format='json')
        self.assertIn(r.status_code, (403, 404))
        self.assertEqual(req.analyses.count(), 0)

    def test_an_analysis_id_from_ANOTHER_request_is_404(self):
        # The fence is the request lookup, so an id that exists but belongs elsewhere must not
        # resolve — `req.analyses` is what makes that true.
        mine, theirs = self._req(), self._req()
        a = self._draft(theirs)
        self._auth('an-su')
        r = self.client.post(f'{BASE}{mine.id}/analysis/{a.id}/approve/', {}, format='json')
        self.assertEqual(r.status_code, 404)
        a.refresh_from_db()
        self.assertIsNone(a.approved_at)


class TestTheQuoteGate(_Base):
    """`analysis_required` — and it must hold on BOTH twins."""

    def _quote(self, req):
        return org_requests.quote(req, self.super, hours='6', note='n')

    def _requote(self, req):
        return org_requests.requote(req, self.super, hours='6', note='n')

    def test_no_analysis_no_quote(self):
        req = self._req()
        with self.assertRaises(org_requests.OrgRequestError) as e:
            self._quote(req)
        self.assertEqual(e.exception.code, 'analysis_required')
        req.refresh_from_db()
        self.assertEqual(req.status, 'triaged')

    def test_a_DRAFT_is_not_enough(self):
        # The owner has not approved it, so the requester has not seen it.
        req = self._req()
        self._draft(req)
        with self.assertRaises(org_requests.OrgRequestError) as e:
            self._quote(req)
        self.assertEqual(e.exception.code, 'analysis_required')

    def test_a_superseded_analysis_is_not_enough(self):
        req = self._req()
        a = self._approved(req)
        a.superseded_at = timezone.now()
        a.save(update_fields=['superseded_at'])
        with self.assertRaises(org_requests.OrgRequestError) as e:
            self._quote(req)
        self.assertEqual(e.exception.code, 'analysis_required')

    def test_an_approved_analysis_lets_the_quote_through(self):
        req = self._req()
        self._approved(req)
        self._quote(req)
        req.refresh_from_db()
        self.assertEqual(req.status, 'quoted')
        self.assertEqual(req.quote_hours, Decimal('6.0'))

    def test_REQUOTE_refuses_and_passes_on_exactly_the_same_rule(self):
        # The anti-drift assertion. A gate on one of two byte-identical twins is the shape of the
        # award_amount defect.
        req = self._req(status='deferred')
        with self.assertRaises(org_requests.OrgRequestError) as e:
            self._requote(req)
        self.assertEqual(e.exception.code, 'analysis_required')
        self._approved(req)
        self._requote(req)
        req.refresh_from_db()
        self.assertEqual(req.status, 'quoted')

    def test_bug_is_free_still_fires_FIRST(self):
        # Ordering is deliberate: a bug is never quoted, so telling the owner "analyse it first"
        # would be the wrong message and would imply the rule covers bugs.
        req = self._req(kind='bug', triaged_kind='bug')
        with self.assertRaises(org_requests.OrgRequestError) as e:
            self._quote(req)
        self.assertEqual(e.exception.code, 'bug_is_free')

    def test_a_BUG_still_schedules_with_no_analysis_at_all(self):
        # The free lane is untouched. Somebody will eventually try to "complete" the gate by
        # adding it to schedule(); this is what stops that.
        req = self._req(kind='bug', triaged_kind='bug')
        org_requests.schedule(req, self.super)
        req.refresh_from_db()
        self.assertEqual(req.status, 'scheduled')

    def test_the_endpoint_refuses_with_the_code_the_UI_renders(self):
        req = self._req()
        self._auth('an-su')
        r = self.client.post(f'{BASE}{req.id}/quote/', {'hours': 6}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'analysis_required')


class TestSupersession(_Base):
    def test_a_MODIFIED_request_cannot_be_quoted_on_the_old_analysis(self):
        # The silent-mispricing case: without this the gate passes on an analysis of a description
        # that no longer exists.
        req = self._req(status='quoted')
        self._approved(req)
        org_requests.modify(req, self.oa, description='completely different scope now')
        org_requests.triage(req, self.super, triaged_kind='feature', lane='sprint')
        with self.assertRaises(org_requests.OrgRequestError) as e:
            org_requests.quote(req, self.super, hours='6')
        self.assertEqual(e.exception.code, 'analysis_required')

    def test_a_DRAFT_survives_a_modify(self):
        # Only APPROVED analyses are superseded — a draft has made no claim to the requester, and
        # the engineer may still be mid-revision.
        req = self._req(status='quoted')
        a = self._draft(req)
        org_requests.modify(req, self.oa, description='new scope')
        a.refresh_from_db()
        self.assertIsNone(a.superseded_at)

    def test_an_ANSWER_does_not_supersede(self):
        # Deliberate: answers are frequent, and superseding on each would be a treadmill. The
        # cockpit shows an amber "predates the last comment" note instead.
        req = self._req()
        a = self._approved(req)
        org_requests.post_comment(req, None, 'Which report?', author_kind=org_requests.AUTHOR_AI,
                                  awaiting_reply=True)
        org_requests.answer_clarification(req, 'The monthly one.', admin=self.oa)
        a.refresh_from_db()
        self.assertIsNone(a.superseded_at)
        self.assertIsNotNone(org_requests.approved_analysis(req))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   REQUESTS_ENABLED=True, GEMINI_API_KEY='k')
class TestTheReviewerReadsTheAnalysis(_Base):
    def test_the_prompt_attributes_the_engineer(self):
        # The point of the steer: a re-run reasons WITH the analysis instead of re-deriving it.
        # Without the _SPEAKER entry the prompt would print the raw key.
        req = self._req()
        self._approved(req, body='The invite engine already exists.')
        prompt = org_requests._build_review_prompt(req)
        self.assertIn('the engineer', prompt)
        self.assertIn('The invite engine already exists.', prompt)


class TestNobodyCanForgeAnEngineerComment(_Base):
    def test_an_org_admin_posting_author_kind_engineer_is_still_org(self):
        # Widening post_comment's allowlist is safe ONLY because the comment endpoint derives
        # author_kind from the caller's role and never reads it from the body. This is that claim.
        req = self._req()
        self._auth('an-oa')
        r = self.client.post(f'{BASE}{req.id}/comments/',
                             {'body': 'not the engineer', 'author_kind': 'engineer'},
                             format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(req.comments.get().author_kind, org_requests.AUTHOR_ORG)
