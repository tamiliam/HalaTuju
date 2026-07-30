"""The deliberation half of the Requests module (2026-07-30).

Before this, the clarification thread ran one way: the AI asked, the requester answered, and the
owner watched by email. So a judgement about the SHAPE of a request — *"adding a sponsor directly
would bypass the terms and consent; would an invite do?"* — had nowhere to go, because
``triage_note`` is private and the AI never read it either. A re-run rebuilt its prompt from the
same inputs and could only re-derive the same answer.

Three things are pinned here:
  * the owner can ask, and an owner question does NOT consume the AI's question budget;
  * the owner's reasoning REACHES the reviewer (the steer), and still never reaches the org;
  * the reviewer is now sent the screenshots, while every other caller of the shared Gemini seam
    keeps its old text-only call exactly.
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import contracts, org_requests
from apps.scholarship.models import OrgRequest, OrgRequestAttachment
from apps.scholarship.serializers_admin import OrgRequestOrgSerializer


def _org_and_admins():
    org = PartnerOrganisation.objects.create(code='delib-org', name='Delib')
    owner = PartnerAdmin.objects.create(
        supabase_user_id='d-sup', is_super_admin=True, is_active=True,
        name='Owner', email='owner@x.com')
    oa = PartnerAdmin.objects.create(
        supabase_user_id='d-oa', role='org_admin', is_active=True,
        owning_organisation=org, name='Suresh', email='suresh@x.com')
    return org, owner, oa


class TestTheOwnerCanAsk(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org, cls.owner, cls.oa = _org_and_admins()

    def _req(self, status='submitted', **kw):
        return OrgRequest.objects.create(
            organisation=self.org, submitted_by=self.oa, kind='feature',
            title='a link to add sponsors', description='a link here to add sponsors will help',
            status=status, **kw)

    def test_the_owner_question_lands_tagged(self):
        req = self._req()
        org_requests.ask_question(req, self.owner, 'Would an invite work instead?')
        req.refresh_from_db()
        self.assertEqual(len(req.clarifications), 1)
        entry = req.clarifications[0]
        self.assertEqual(entry['question'], 'Would an invite work instead?')
        self.assertEqual(org_requests.asked_by(entry), 'owner')
        self.assertEqual(entry['asked_by_email'], 'owner@x.com')
        self.assertIsNone(entry['answer'])

    def test_only_a_super_may_ask(self):
        req = self._req()
        with self.assertRaises(org_requests.OrgRequestError) as ctx:
            org_requests.ask_question(req, self.oa, 'can I ask?')
        self.assertEqual(ctx.exception.code, 'forbidden')
        req.refresh_from_db()
        self.assertEqual(req.clarifications, [])

    def test_an_empty_question_is_refused(self):
        req = self._req()
        for bad in ('', '   ', None):
            with self.subTest(q=bad):
                with self.assertRaises(org_requests.OrgRequestError) as ctx:
                    org_requests.ask_question(req, self.owner, bad)
                self.assertEqual(ctx.exception.code, 'question_required')

    def test_asking_the_same_thing_twice_is_refused(self):
        req = self._req()
        org_requests.ask_question(req, self.owner, 'Would an invite work?')
        with self.assertRaises(org_requests.OrgRequestError) as ctx:
            org_requests.ask_question(req, self.owner, '  would an INVITE work?  ')
        self.assertEqual(ctx.exception.code, 'duplicate_question')

    def test_a_quoted_request_cannot_grow_new_questions(self):
        """The quote was priced against what was known when it was sent."""
        req = self._req(status='quoted', quote_hours=Decimal('4.0'))
        with self.assertRaises(org_requests.OrgRequestError) as ctx:
            org_requests.ask_question(req, self.owner, 'one more thing?')
        self.assertEqual(ctx.exception.code, 'bad_transition')

    def test_the_requester_answers_an_owner_question_through_the_existing_path(self):
        req = self._req()
        org_requests.ask_question(req, self.owner, 'Would an invite work instead?')
        org_requests.answer_clarification(req, 'Yes, an invite is fine.')
        req.refresh_from_db()
        self.assertEqual(req.clarifications[0]['answer'], 'Yes, an invite is fine.')


class TestOwnerQuestionsDoNotCostTheAiItsBudget(TestCase):
    """``MAX_OPEN_QUESTIONS`` caps the AI so it cannot bury the requester. It was never meant to
    stop the owner asking — so asking by hand must not silently spend a reviewer slot."""

    @classmethod
    def setUpTestData(cls):
        cls.org, cls.owner, cls.oa = _org_and_admins()

    def _req(self):
        return OrgRequest.objects.create(
            organisation=self.org, submitted_by=self.oa, kind='feature',
            title='t', description='d', status='submitted')

    def test_the_ai_still_gets_its_full_allowance_after_owner_questions(self):
        req = self._req()
        for i in range(org_requests.MAX_OPEN_QUESTIONS):
            org_requests.ask_question(req, self.owner, f'owner question {i}')
        added = org_requests._append_questions(req, ['ai a', 'ai b', 'ai c'])
        self.assertEqual(len(added), org_requests.MAX_OPEN_QUESTIONS,
                         'owner questions consumed the AI question budget')

    def test_the_ai_is_still_capped_by_its_own_open_questions(self):
        # The negative half: the cap must still BITE on the AI, or this "fix" would remove it.
        req = self._req()
        org_requests._append_questions(req, ['q1', 'q2', 'q3'])
        req.save(update_fields=['clarifications'])
        self.assertEqual(org_requests._append_questions(req, ['q4']), [])


class TestTheOwnersReasoningReachesTheReviewerAndNotTheOrg(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org, cls.owner, cls.oa = _org_and_admins()

    def _req(self):
        return OrgRequest.objects.create(
            organisation=self.org, submitted_by=self.oa, kind='feature',
            title='a link to add sponsors', description='a link here to add sponsors will help',
            status='triaged', triage_note='Adding a sponsor directly bypasses terms and consent.')

    def test_the_triage_note_is_in_the_prompt(self):
        prompt = org_requests._build_review_prompt(self._req())
        self.assertIn('bypasses terms and consent', prompt)
        self.assertIn("OWNER'S OWN ASSESSMENT", prompt)

    def test_an_unanswered_owner_question_is_a_steer_too(self):
        req = self._req()
        org_requests.ask_question(req, self.owner, 'Would an invite work instead?')
        prompt = org_requests._build_review_prompt(req)
        self.assertIn('STILL UNANSWERED', prompt)
        self.assertIn('Would an invite work instead?', prompt)

    def test_the_thread_is_attributed_in_the_prompt(self):
        req = self._req()
        org_requests.ask_question(req, self.owner, 'Would an invite work instead?')
        org_requests.answer_clarification(req, 'Yes.')
        prompt = org_requests._build_review_prompt(req)
        self.assertIn('Q (the owner)', prompt)

    def test_the_org_NEVER_sees_the_STEER(self):
        """The reason the steer is safe to send to the reviewer: it cannot come back out.

        ⚠ NARROWED 2026-07-30 (TD-202), and narrowed DELIBERATELY rather than deleted. This
        originally asserted that NO `ai_draft_*` field reached the org. The owner has since ruled
        that the reviewer's REASONING is exactly what the org should see — they filed request #4 as
        an org_admin, saw silence, and the reviewer had answered accurately 21 seconds in.

        What must still never travel is the OWNER'S PRIVATE JUDGEMENT (`triage_note`, and the
        triaged kind/lane) and the model's HOURS — the first because the owner has to stay free to
        be blunt, the second because the number is unreliable and would read as the real price.
        `ai_draft_note` and `ai_draft_model` moving from this list to the allowed one is the whole
        of the change; `test_the_ai_split_is_exact` in test_org_requests_endpoints.py states the
        positive half.
        """
        req = self._req()
        req.triage_note = 'the owner being blunt'
        req.ai_draft_note = 'reasoning the org SHOULD read'
        req.ai_draft_hours = Decimal('4.0')
        req.save()
        keys = set(OrgRequestOrgSerializer(req).data.keys())
        for leaked in ('triage_note', 'triaged_kind', 'lane',
                       'ai_draft_hours', 'ai_draft_kind', 'ai_draft_lane'):
            self.assertNotIn(leaked, keys, leaked)
        # And the steer's VALUE is not smuggled through some other field.
        self.assertNotIn('the owner being blunt', str(OrgRequestOrgSerializer(req).data))


@override_settings(GEMINI_API_KEY='k')
class TestTheReviewerSeesTheScreenshots(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org, cls.owner, cls.oa = _org_and_admins()

    def _req_with_shots(self, n=2):
        req = OrgRequest.objects.create(
            organisation=self.org, submitted_by=self.oa, kind='feature',
            title='t', description='d', status='submitted')
        for i in range(n):
            OrgRequestAttachment.objects.create(
                org_request=req, storage_path=f'{self.org.id}/requests/{req.id}/{i}.png',
                original_filename=f'shot{i}.png', content_type='image/png', size=100,
                uploaded_by=self.oa)
        return req

    def test_the_images_are_passed_to_the_seam(self):
        req = self._req_with_shots(2)
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=b'PNGDATA'), \
             patch('apps.scholarship.contracts._gemini_generate',
                   return_value='{"classification":"feature","lane":"sprint",'
                                '"estimated_hours":4,"clarifying_questions":[],"rationale":"r"}'
                   ) as gen:
            org_requests.run_ai_review(req)
        _prompt, _model = gen.call_args.args
        self.assertEqual(gen.call_args.kwargs['images'], [(b'PNGDATA', 'image/png')] * 2)

    def test_an_unfetchable_screenshot_is_skipped_not_fatal(self):
        """A broken blob must not cost the owner their triage."""
        req = self._req_with_shots(2)
        with patch('apps.scholarship.vision._fetch_image_bytes', return_value=None):
            self.assertEqual(org_requests._review_images(req), [])

    def test_the_prompt_stops_merely_COUNTING_them(self):
        req = self._req_with_shots(2)
        prompt = org_requests._build_review_prompt(req)
        self.assertNotIn('2 image(s) attached', prompt)
        self.assertIn('screenshots', prompt)

    def test_the_shared_seam_is_unchanged_for_every_other_caller(self):
        """`_gemini_generate` is shared with contract generation and mocked everywhere. Passing no
        images must take the SAME `contents=prompt` path it always did."""
        sent = {}

        class _Resp:
            text = 'ok'

        class _Models:
            def generate_content(self, model, contents):
                sent['contents'] = contents
                return _Resp()

        class _Client:
            models = _Models()

        with patch('google.genai.Client', return_value=_Client()):
            contracts._gemini_generate('just text', 'gemini-2.5-pro')
        self.assertEqual(sent['contents'], 'just text',
                         'a text-only call must not become a parts list')
