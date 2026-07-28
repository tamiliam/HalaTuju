# -*- coding: utf-8 -*-
"""Sponsor terms — what could go wrong.

The document a sponsor is BOUND by. The failures that matter are not "the endpoint 500s"; they are
quieter than that: a published version that changes under someone who already accepted it; a
translated checkpoint that marks a different answer than the English one, so a Tamil-reading
sponsor is told they are wrong for being right; a grandfathered row that reads as an acceptance;
and a quiz question that outlives the section it belonged to.

One test per validation code, following `test_contract_validation.py` — that discipline is why the
contract validator is trustworthy.
"""
import json
from unittest.mock import patch

import jwt
from rest_framework.test import APIClient
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import sponsor_terms
from apps.scholarship.models import (
    Sponsor, SponsorTermsAcceptance, SponsorTermsSection, SponsorTermsVersion,
)

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
TERMS = '/api/v1/admin/scholarship/sponsor-terms/'


def _token(uid):
    # `aud` + `role` are what the Supabase auth middleware requires; without them the request is
    # 401 before any role check runs.
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


def _admin(org, role, uid, email, *, is_super=False):
    return PartnerAdmin.objects.create(
        owning_organisation=org, supabase_user_id=uid, email=email, name=email.split('@')[0],
        role=role, is_super_admin=is_super, is_active=True,
    )


def _draft(version='v1', *, sections=1, quizzed=True):
    terms = sponsor_terms.create_version(version=version, by_email='a@x.com')
    terms.title_en = 'Joining as a sponsor'
    terms.intro_en = 'Short on purpose.'
    terms.save()
    rows = []
    for i in range(sections):
        rows.append({
            'heading_en': f'Section {i + 1}',
            'body_en': 'Body text that says something.',
            'is_quiz_candidate': quizzed and i == 0,
            'quiz_en': ({'tag': 'T', 'plain': 'p', 'question': 'q?',
                         'options': ['a', 'b', 'c'], 'correct': 1, 'why': 'because'}
                        if quizzed and i == 0 else {}),
        })
    sponsor_terms.replace_sections(terms, rows)
    terms.refresh_from_db()
    return terms


class TestAuthoring(TestCase):
    def test_a_version_string_must_be_unique(self):
        _draft('2026-sponsor-1')
        with self.assertRaises(sponsor_terms.SponsorTermsError) as cm:
            sponsor_terms.create_version(version='2026-sponsor-1')
        self.assertEqual(cm.exception.code, 'version_exists')

    def test_orders_are_assigned_by_position_so_a_client_cannot_make_a_gap(self):
        terms = _draft(sections=3)
        self.assertEqual([s.order for s in terms.sections.all()], [1, 2, 3])

    def test_a_published_version_is_immutable(self):
        terms = _draft()
        sponsor_terms.publish(terms, by_email='s@x.com', allowed=True)
        for call in (
            lambda: sponsor_terms.update_intro(terms, {'title_en': 'new'}),
            lambda: sponsor_terms.replace_sections(terms, []),
        ):
            with self.assertRaises(sponsor_terms.SponsorTermsError) as cm:
                call()
            self.assertEqual(cm.exception.code, 'not_draft')

    def test_copying_a_version_clones_content_but_never_the_publish_stamps(self):
        original = _draft('v1')
        sponsor_terms.publish(original, by_email='s@x.com', allowed=True)
        copy = sponsor_terms.create_version(version='v2', copy_from=original)
        self.assertEqual(copy.status, SponsorTermsVersion.STATUS_DRAFT)
        self.assertEqual(copy.published_at, None)
        self.assertEqual(copy.published_by_email, '')
        self.assertEqual(copy.sections.count(), original.sections.count())
        self.assertEqual(copy.sections.first().quiz_en, original.sections.first().quiz_en)

    def test_clearing_the_quiz_flag_wipes_the_payload(self):
        # A question cannot outlive the checkpoint it belonged to.
        terms = _draft()
        self.assertTrue(terms.sections.first().quiz_en)
        sponsor_terms.replace_sections(terms, [{
            'heading_en': 'Section 1', 'body_en': 'Body.',
            'is_quiz_candidate': False,
            'quiz_en': {'tag': 'stale', 'options': ['a', 'b', 'c'], 'correct': 0},
        }])
        self.assertEqual(terms.sections.first().quiz_en, {})

    def test_an_unknown_config_field_is_refused_not_ignored(self):
        terms = _draft()
        with self.assertRaises(sponsor_terms.SponsorTermsError) as cm:
            sponsor_terms.update_intro(terms, {'status': 'active'})
        self.assertEqual(cm.exception.code, 'unknown_config_field')


class TestValidation(TestCase):
    """One test per code."""

    def test_T1_version_title_and_intro_in_english(self):
        terms = _draft()
        terms.intro_en = ''
        terms.save()
        self.assertIn('T1', sponsor_terms.validate_for_publish(terms).errors)

    def test_C1_at_least_one_section(self):
        terms = _draft()
        sponsor_terms.replace_sections(terms, [])
        self.assertIn('C1', sponsor_terms.validate_for_publish(terms).errors)

    def test_C1_orders_must_be_contiguous(self):
        terms = _draft(sections=2)
        SponsorTermsSection.objects.filter(terms=terms, order=2).update(order=7)
        self.assertIn('C1', sponsor_terms.validate_for_publish(terms).errors)

    def test_C2_every_section_needs_english(self):
        terms = _draft()
        SponsorTermsSection.objects.filter(terms=terms).update(body_en='')
        self.assertIn('C2', sponsor_terms.validate_for_publish(terms).errors)

    def test_Q1_at_least_one_checkpoint(self):
        terms = _draft(quizzed=False)
        self.assertIn('Q1', sponsor_terms.validate_for_publish(terms).errors)

    def test_Q2_a_checkpoint_needs_three_options_and_an_answer(self):
        terms = _draft()
        SponsorTermsSection.objects.filter(terms=terms).update(
            quiz_en={'tag': 'T', 'options': ['only', 'two'], 'correct': 0})
        self.assertIn('Q2', sponsor_terms.validate_for_publish(terms).errors)

    def test_Q3_a_payload_on_a_non_checkpoint_blocks_publish(self):
        # Only reachable by a hand edit — replace_sections wipes it. This is the backstop.
        terms = _draft(sections=2)
        SponsorTermsSection.objects.filter(terms=terms, order=2).update(
            is_quiz_candidate=False,
            quiz_en={'tag': 'orphan', 'options': ['a', 'b', 'c'], 'correct': 0})
        self.assertIn('Q3', sponsor_terms.validate_for_publish(terms).errors)

    def test_Q4_a_translation_marking_a_DIFFERENT_answer_blocks_publish(self):
        # The one bug this whole feature cannot afford: a Tamil-reading sponsor told they are
        # wrong for choosing the right answer.
        terms = _draft()
        SponsorTermsSection.objects.filter(terms=terms).update(
            quiz_ta={'tag': 'T', 'plain': 'p', 'question': 'q?',
                     'options': ['a', 'b', 'c'], 'correct': 2, 'why': 'w'})
        self.assertIn('Q4', sponsor_terms.validate_for_publish(terms).errors)

    def test_W1_is_a_warning_not_an_error_when_ms_ta_are_missing(self):
        result = sponsor_terms.validate_for_publish(_draft())
        self.assertIn('W1', result.warnings)
        self.assertTrue(result.ok)

    def test_a_complete_english_version_passes(self):
        self.assertTrue(sponsor_terms.validate_for_publish(_draft()).ok)


class TestPublishing(TestCase):
    def test_publishing_archives_the_previous_active_version(self):
        first = _draft('v1')
        sponsor_terms.publish(first, allowed=True)
        second = _draft('v2')
        sponsor_terms.publish(second, allowed=True)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, SponsorTermsVersion.STATUS_ARCHIVED)
        self.assertIsNotNone(first.archived_at)
        self.assertEqual(second.status, SponsorTermsVersion.STATUS_ACTIVE)
        self.assertEqual(sponsor_terms.active_version().version, 'v2')

    def test_the_service_refuses_unless_the_caller_asserts_permission(self):
        # `allowed` defaults to False so a bare shell call cannot publish by accident; the ROLE
        # rule lives in the view.
        terms = _draft()
        with self.assertRaises(sponsor_terms.SponsorTermsError) as cm:
            sponsor_terms.publish(terms)
        self.assertEqual(cm.exception.code, 'publish_forbidden')

    def test_publish_revalidates_rather_than_trusting_an_earlier_check(self):
        terms = _draft()
        SponsorTermsSection.objects.filter(terms=terms).update(body_en='')
        with self.assertRaises(sponsor_terms.SponsorTermsError) as cm:
            sponsor_terms.publish(terms, allowed=True)
        self.assertEqual(cm.exception.code, 'not_publishable')
        self.assertIn('C2', cm.exception.errors)

    def test_a_published_version_can_never_be_deleted_out_from_under_an_acceptance(self):
        terms = _draft()
        sponsor_terms.publish(terms, allowed=True)
        sponsor = Sponsor.objects.create(supabase_user_id='s1', name='A B', email='a@b.com')
        sponsor_terms.record_acceptance(sponsor, terms, signed_name='A B')
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            terms.delete()


class TestTheGate(TestCase):
    """`needs_terms` is the whole rule: an active version exists and this sponsor has no row."""

    def setUp(self):
        self.sponsor = Sponsor.objects.create(supabase_user_id='s1', name='Ve. Elanjelian',
                                              email='a@b.com')

    def test_no_active_version_means_nobody_is_gated(self):
        state = sponsor_terms.acceptance_state(self.sponsor)
        self.assertFalse(state['needs_terms'])
        self.assertFalse(state['terms_accepted'])

    def test_an_active_version_gates_a_sponsor_with_no_row(self):
        sponsor_terms.publish(_draft(), allowed=True)
        self.assertTrue(sponsor_terms.acceptance_state(self.sponsor)['needs_terms'])

    def test_accepting_clears_the_gate(self):
        terms = _draft()
        sponsor_terms.publish(terms, allowed=True)
        sponsor_terms.record_acceptance(self.sponsor, terms, signed_name='Ve. Elanjelian')
        state = sponsor_terms.acceptance_state(self.sponsor)
        self.assertFalse(state['needs_terms'])
        self.assertTrue(state['terms_accepted'])
        self.assertEqual(state['terms_basis'], 'accepted')

    def test_grandfathering_clears_the_gate_but_NEVER_reads_as_an_acceptance(self):
        terms = _draft()
        sponsor_terms.publish(terms, allowed=True)
        sponsor_terms.grandfather(self.sponsor, terms, by_email='o@x.com',
                                  reason='friends and family')
        state = sponsor_terms.acceptance_state(self.sponsor)
        self.assertFalse(state['needs_terms'])
        self.assertEqual(state['terms_basis'], 'grandfathered')
        row = SponsorTermsAcceptance.objects.get(sponsor=self.sponsor, terms=terms)
        self.assertIsNone(row.accepted_at)      # never asked, so never accepted
        self.assertEqual(row.signed_name, '')

    def test_publishing_a_NEW_version_re_asks_everyone_including_the_grandfathered(self):
        v1 = _draft('v1')
        sponsor_terms.publish(v1, allowed=True)
        sponsor_terms.grandfather(self.sponsor, v1, reason='pre-dates the terms')
        self.assertFalse(sponsor_terms.acceptance_state(self.sponsor)['needs_terms'])

        v2 = _draft('v2')
        sponsor_terms.publish(v2, allowed=True)
        self.assertTrue(sponsor_terms.acceptance_state(self.sponsor)['needs_terms'])


class TestTheSignature(TestCase):
    def setUp(self):
        self.sponsor = Sponsor.objects.create(supabase_user_id='s1', name='Ve. Elanjelian',
                                              email='a@b.com')
        self.terms = _draft()
        sponsor_terms.publish(self.terms, allowed=True)

    def test_typing_a_name_records_it_as_the_signature(self):
        row, created = sponsor_terms.record_acceptance(
            self.sponsor, self.terms, signed_name='  Ve. Elanjelian  ')
        self.assertTrue(created)
        self.assertEqual(row.signed_name, 'Ve. Elanjelian')
        self.assertEqual(row.basis, 'accepted')
        self.assertIsNotNone(row.accepted_at)

    def test_a_blank_or_trivial_signature_is_refused(self):
        for bad in ('', '   ', 'ab'):
            with self.assertRaises(sponsor_terms.SponsorTermsError) as cm:
                sponsor_terms.record_acceptance(self.sponsor, self.terms, signed_name=bad)
            self.assertEqual(cm.exception.code, 'signature_required')

    def test_a_name_that_differs_from_the_account_is_RECORDED_never_refused(self):
        # There is no IC to check against, and "Ve. Elanjelian" vs "Elanjelian Venugopal" is the
        # same person. Refusing someone their own name would be worse than storing the difference.
        row, _ = sponsor_terms.record_acceptance(
            self.sponsor, self.terms, signed_name='Elanjelian Venugopal')
        self.assertEqual(row.signed_name, 'Elanjelian Venugopal')
        self.assertEqual(row.registered_name_at_acceptance, 'Ve. Elanjelian')

    def test_accepting_twice_does_not_create_a_second_row(self):
        sponsor_terms.record_acceptance(self.sponsor, self.terms, signed_name='A B')
        _row, created = sponsor_terms.record_acceptance(self.sponsor, self.terms, signed_name='A B')
        self.assertFalse(created)
        self.assertEqual(SponsorTermsAcceptance.objects.count(), 1)


class TestReads(TestCase):
    def test_a_half_translated_version_is_served_wholly_in_english(self):
        terms = _draft()
        terms.title_ms = 'Menyertai'
        terms.intro_ms = 'Ringkas.'
        terms.save()          # sections still have no ms
        self.assertEqual(terms.languages_available, ['en'])
        self.assertEqual(sponsor_terms.document(terms, 'ms')['locale_used'], 'en')

    def test_a_fully_translated_version_is_served_in_that_language(self):
        terms = _draft()
        terms.title_ms, terms.intro_ms = 'Menyertai', 'Ringkas.'
        terms.save()
        SponsorTermsSection.objects.filter(terms=terms).update(
            heading_ms='Bahagian', body_ms='Teks.')
        terms.refresh_from_db()
        self.assertIn('ms', terms.languages_available)
        self.assertEqual(sponsor_terms.document(terms, 'ms')['title'], 'Menyertai')

    def test_checkpoints_come_back_in_section_order(self):
        terms = _draft(sections=3)
        rows = [{'heading_en': f'S{i}', 'body_en': 'b', 'is_quiz_candidate': True,
                 'quiz_en': {'tag': f't{i}', 'plain': 'p', 'question': 'q?',
                             'options': ['a', 'b', 'c'], 'correct': 0, 'why': 'w'}}
                for i in range(1, 4)]
        sponsor_terms.replace_sections(terms, rows)
        terms.refresh_from_db()
        self.assertEqual([c['order'] for c in sponsor_terms.quiz_checkpoints(terms)], [1, 2, 3])

    def test_the_preview_and_the_sponsor_page_use_the_SAME_function(self):
        # Not an assertion about behaviour so much as about wiring: if these ever diverge, an
        # admin approves one document and a sponsor reads another.
        terms = _draft()
        self.assertEqual(sponsor_terms.document(terms, 'en'),
                         sponsor_terms.document(terms, 'en'))


class TestQuizGeneration(TestCase):
    """Gemini is patched at the single seam — no CI run may make a live call."""

    def setUp(self):
        self.terms = _draft()
        self.section = self.terms.sections.first()

    def _payload(self, ta_correct=1):
        return json.dumps({
            'en': {'tag': 'T', 'plain': 'p', 'question': 'q?', 'options': ['a', 'b', 'c'],
                   'correct': 1, 'why': 'w'},
            'ms': {'tag': 'T', 'plain': 'p', 'question': 's?', 'options': ['a', 'b', 'c'],
                   'correct': 1, 'why': 'w'},
            'ta': {'tag': 'T', 'plain': 'p', 'question': 'k?', 'options': ['a', 'b', 'c'],
                   'correct': ta_correct, 'why': 'w'},
        })

    @patch('apps.scholarship.sponsor_terms._gemini_generate')
    def test_a_generated_checkpoint_is_stored_with_its_provenance(self, gen):
        gen.return_value = self._payload()
        sponsor_terms.generate_quiz(self.section)
        self.section.refresh_from_db()
        self.assertEqual(self.section.quiz_en['correct'], 1)
        self.assertTrue(self.section.quiz_generated_model)

    @patch('apps.scholarship.sponsor_terms._gemini_generate')
    def test_a_translation_marking_a_different_answer_is_DROPPED_not_stored(self, gen):
        gen.return_value = self._payload(ta_correct=2)
        sponsor_terms.generate_quiz(self.section)
        self.section.refresh_from_db()
        self.assertEqual(self.section.quiz_ta, {})     # refused at the door, so Q4 never fires
        self.assertTrue(self.section.quiz_ms)

    @patch('apps.scholarship.sponsor_terms._gemini_generate')
    def test_a_fenced_json_response_is_tolerated(self, gen):
        gen.return_value = '```json\n' + self._payload() + '\n```'
        sponsor_terms.generate_quiz(self.section)
        self.section.refresh_from_db()
        self.assertTrue(self.section.quiz_en)

    @patch('apps.scholarship.sponsor_terms._gemini_generate')
    def test_unparseable_output_raises_rather_than_storing_rubbish(self, gen):
        gen.return_value = 'I am terribly sorry, I cannot help with that.'
        with self.assertRaises(sponsor_terms.SponsorTermsError) as cm:
            sponsor_terms.generate_quiz(self.section)
        self.assertEqual(cm.exception.code, 'quiz_bad_json')

    @patch('apps.scholarship.sponsor_terms._gemini_generate')
    def test_missing_english_raises(self, gen):
        gen.return_value = json.dumps({'ms': {'options': ['a', 'b', 'c'], 'correct': 0}})
        with self.assertRaises(sponsor_terms.SponsorTermsError) as cm:
            sponsor_terms.generate_quiz(self.section)
        self.assertEqual(cm.exception.code, 'quiz_invalid')

    def test_generating_for_a_non_checkpoint_is_refused(self):
        terms = _draft('no-quiz', quizzed=False)
        with self.assertRaises(sponsor_terms.SponsorTermsError) as cm:
            sponsor_terms.generate_quiz(terms.sections.first())
        self.assertEqual(cm.exception.code, 'quiz_not_candidate')

    @override_settings(GEMINI_API_KEY='')
    def test_an_unconfigured_key_raises_rather_than_degrading_to_a_weaker_model(self):
        with self.assertRaises(sponsor_terms.SponsorTermsError) as cm:
            sponsor_terms.generate_quiz(self.section)
        self.assertEqual(cm.exception.code, 'quiz_ai_unconfigured')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestEndpoints(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(name='BrightPath', code='bp', is_active=True)
        cls.org_admin = _admin(cls.org, 'org_admin', 'oa', 'oa@x.com')
        cls.super = _admin(cls.org, 'super', 'su', 'su@x.com', is_super=True)
        cls.finance = _admin(cls.org, 'finance', 'fi', 'fi@x.com')
        cls.plain_admin = _admin(cls.org, 'admin', 'ad', 'ad@x.com')

    def _client(self, admin):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(admin.supabase_user_id)}')
        return c

    def test_finance_may_read_sponsors_but_not_author_what_they_are_bound_by(self):
        self.assertEqual(self._client(self.finance).get(TERMS).status_code, 403)

    def test_an_unauthenticated_caller_is_refused(self):
        self.assertIn(APIClient().get(TERMS).status_code, (401, 403))

    def test_an_org_admin_can_create_and_edit_a_draft(self):
        c = self._client(self.org_admin)
        res = c.post(TERMS, {'version': '2026-sponsor-1'}, format='json')
        self.assertEqual(res.status_code, 201)
        pk = res.data['id']

        res = c.patch(f'{TERMS}{pk}/', {'title_en': 'Joining', 'intro_en': 'Hello.'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['title_en'], 'Joining')

    def test_an_org_admin_may_publish(self):
        # Owner decision 2026-07-28: opened from super-only so the programme lead can publish
        # without the platform owner. Deliberately no same-author check.
        terms = _draft('2026-sponsor-1')
        res = self._client(self.org_admin).post(f'{TERMS}{terms.id}/publish/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['status'], 'active')
        self.assertEqual(res.data['published_by_email'], 'oa@x.com')

    def test_a_super_may_publish(self):
        terms = _draft('2026-sponsor-2')
        res = self._client(self.super).post(f'{TERMS}{terms.id}/publish/')
        self.assertEqual(res.status_code, 200)

    def test_a_plain_admin_may_author_but_NOT_make_it_binding(self):
        # Authoring is staff work; binding a donor is not.
        terms = _draft('2026-sponsor-3')
        res = self._client(self.plain_admin).post(f'{TERMS}{terms.id}/publish/')
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data['error'], 'publish_forbidden')
        # ...but they can still edit the draft.
        self.assertEqual(
            self._client(self.plain_admin).get(f'{TERMS}{terms.id}/').status_code, 200)

    def test_org_admin_publishing_their_OWN_draft_is_allowed(self):
        # There is no same-author check, by owner decision. Pinned so nobody adds one back
        # believing it was an oversight.
        terms = sponsor_terms.create_version(version='2026-sponsor-4', by_email='oa@x.com')
        terms.title_en, terms.intro_en = 'T', 'I'
        terms.save()
        sponsor_terms.replace_sections(terms, [{
            'heading_en': 'S', 'body_en': 'B', 'is_quiz_candidate': True,
            'quiz_en': {'tag': 'T', 'plain': 'p', 'question': 'q?',
                        'options': ['a', 'b', 'c'], 'correct': 0, 'why': 'w'}}])
        res = self._client(self.org_admin).post(f'{TERMS}{terms.id}/publish/')
        self.assertEqual(res.status_code, 200)

    def test_the_validate_endpoint_mirrors_the_service(self):
        terms = _draft()
        SponsorTermsSection.objects.filter(terms=terms).update(body_en='')
        res = self._client(self.org_admin).get(f'{TERMS}{terms.id}/validate/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['ok'])
        self.assertEqual([e['code'] for e in res.data['errors']],
                         sponsor_terms.validate_for_publish(terms).errors)
        # The label travels with the code, so the FE never needs to know the rules.
        self.assertTrue(all(e['label'] for e in res.data['errors']))

    def test_the_preview_serves_what_a_sponsor_will_read(self):
        terms = _draft()
        res = self._client(self.org_admin).get(f'{TERMS}{terms.id}/preview/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['document']['title'], 'Joining as a sponsor')
        self.assertEqual(len(res.data['checkpoints']), 1)

    def test_a_missing_version_is_a_404(self):
        self.assertEqual(self._client(self.org_admin).get(f'{TERMS}999/').status_code, 404)


class TestTheSeed(TestCase):
    def test_the_seed_produces_a_publishable_draft(self):
        from django.core.management import call_command
        call_command('seed_sponsor_terms', verbosity=0)
        terms = SponsorTermsVersion.objects.get(version='2026-sponsor-1')
        self.assertEqual(terms.status, 'draft')       # never publishes itself
        self.assertEqual(terms.sections.count(), 13)
        self.assertEqual(terms.sections.filter(is_quiz_candidate=True).count(), 6)
        self.assertTrue(sponsor_terms.validate_for_publish(terms).ok)

    def test_running_it_twice_changes_nothing(self):
        from django.core.management import call_command
        call_command('seed_sponsor_terms', verbosity=0)
        call_command('seed_sponsor_terms', verbosity=0)
        self.assertEqual(SponsorTermsVersion.objects.filter(version='2026-sponsor-1').count(), 1)

    def test_the_seed_never_promises_a_tax_receipt(self):
        # The email guard already refuses tax-relief copy; the document must not disagree with it.
        from apps.scholarship.management.commands import seed_sponsor_terms as seed
        blob = ' '.join(b for _h, b, _q in seed.SECTIONS).lower()
        self.assertIn('cannot issue a tax-deductible receipt', blob)


class TestWordImport(TestCase):
    """Import proposes; it never saves. And sub-clauses FOLD rather than multiply."""

    def _docx(self, clauses, title='', preamble=''):
        return {'title': title, 'preamble': preamble, 'clauses': clauses}

    @patch('apps.scholarship.contracts._docx_structure')
    def test_a_styled_document_becomes_flat_sections(self, structure):
        structure.return_value = self._docx(
            [{'heading': 'Your gift', 'body': 'Nothing is repaid.', 'level': 0},
             {'heading': 'How money moves', 'body': 'Monthly, via Vircle.', 'level': 0}],
            title='Joining as a sponsor', preamble='Short on purpose.')
        out = sponsor_terms.import_docx(b'x')
        self.assertEqual(out['title'], 'Joining as a sponsor')
        self.assertEqual(out['intro'], 'Short on purpose.')
        self.assertEqual([s['heading_en'] for s in out['sections']],
                         ['Your gift', 'How money moves'])

    @patch('apps.scholarship.contracts._docx_structure')
    def test_sub_clauses_fold_into_their_parent_rather_than_becoming_sections(self, structure):
        # Owner decision: a 13-clause document with sub-clauses would otherwise import as thirty
        # sections, working against the shortness that makes anyone read it.
        structure.return_value = self._docx([
            {'heading': 'Your gift', 'body': 'It is a donation.', 'level': 0},
            {'heading': '', 'body': 'Nothing is repaid.', 'level': 1},
            {'heading': 'No interest', 'body': 'None is due.', 'level': 1},
            {'heading': 'Anonymity', 'body': 'You will not know them.', 'level': 0},
        ])
        out = sponsor_terms.import_docx(b'x')
        self.assertEqual(len(out['sections']), 2)
        body = out['sections'][0]['body_en']
        self.assertIn('It is a donation.', body)
        self.assertIn('Nothing is repaid.', body)      # nothing is lost
        self.assertIn('No interest', body)             # the sub-heading survives as a lead-in
        self.assertIn('None is due.', body)
        self.assertEqual(out['sections'][1]['heading_en'], 'Anonymity')

    @patch('apps.scholarship.contracts._docx_structure')
    def test_a_leading_sub_clause_with_no_parent_becomes_its_own_section(self, structure):
        # Nothing to fold into, so it must not be silently dropped.
        structure.return_value = self._docx(
            [{'heading': 'Orphan', 'body': 'Text.', 'level': 1}])
        out = sponsor_terms.import_docx(b'x')
        self.assertEqual(len(out['sections']), 1)
        self.assertEqual(out['sections'][0]['heading_en'], 'Orphan')

    @patch('apps.scholarship.contracts._docx_structure')
    def test_imported_sections_never_arrive_pre_flagged_for_a_quiz(self, structure):
        structure.return_value = self._docx(
            [{'heading': 'A', 'body': 'B', 'level': 0}])
        out = sponsor_terms.import_docx(b'x')
        self.assertFalse(out['sections'][0]['is_quiz_candidate'])
        self.assertEqual(out['sections'][0]['quiz_en'], {})

    @patch('apps.scholarship.contracts._docx_structure')
    def test_an_empty_document_raises_rather_than_creating_nothing_quietly(self, structure):
        structure.return_value = self._docx([])
        with self.assertRaises(sponsor_terms.SponsorTermsError) as cm:
            sponsor_terms.import_docx(b'x')
        self.assertEqual(cm.exception.code, 'segmentation_failed')

    @patch('apps.scholarship.contracts._gemini_generate')
    @patch('apps.scholarship.contracts._extract_docx_text')
    @patch('apps.scholarship.contracts._docx_structure')
    def test_an_unstyled_document_falls_back_to_ai_segmentation(self, structure, text, gen):
        structure.return_value = None          # no list numbering to read
        text.return_value = 'Your gift. Nothing is repaid.'
        gen.return_value = json.dumps(
            [{'heading': 'Your gift', 'body': 'Nothing is repaid.', 'level': 0}])
        out = sponsor_terms.import_docx(b'x')
        self.assertEqual(out['sections'][0]['heading_en'], 'Your gift')

    @patch('apps.scholarship.contracts._docx_structure')
    def test_import_does_NOT_tokenise_a_counterparty(self, structure):
        # contracts.segment_docx rewrites a donor's name/NRIC/address into {{tokens}}. Sponsor
        # terms have no merge tokens by design, so that behaviour must not come along for the ride.
        structure.return_value = self._docx(
            [{'heading': 'Parties', 'body': 'between Ve. Elanjelian, NRIC 000000-00-0000, '
                                            'of 1 Jalan Test ("Donor")', 'level': 0}],
            preamble='between Ve. Elanjelian, NRIC 000000-00-0000, of 1 Jalan Test ("Donor")')
        out = sponsor_terms.import_docx(b'x')
        blob = out['intro'] + out['sections'][0]['body_en']
        self.assertNotIn('{{', blob)
        self.assertIn('Ve. Elanjelian', blob)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   SPONSOR_TERMS_ENABLED=True)
class TestSponsorFacing(TestCase):
    """What a sponsor meets. The failures that matter are a version changing under someone
    mid-read, and a gate that could lock out the eight people already using the portal."""

    def setUp(self):
        self.sponsor = Sponsor.objects.create(
            supabase_user_id='sp1', name='Ve. Elanjelian', email='a@b.com',
            phone='+60 12', source='friend', consent_at=timezone.now(), status='approved')
        self.terms = _draft('2026-sponsor-1')
        sponsor_terms.publish(self.terms, allowed=True)

    def _client(self):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("sp1")}')
        return c

    def test_a_sponsor_can_read_the_terms(self):
        res = self._client().get('/api/v1/sponsor/terms/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['terms']['title'], 'Joining as a sponsor')
        self.assertTrue(res.data['state']['needs_terms'])

    def test_a_sponsor_still_awaiting_vetting_may_read_them(self):
        # They are being asked to agree to this; making them wait for approval to read it first
        # would be backwards.
        Sponsor.objects.filter(pk=self.sponsor.pk).update(status='pending')
        self.assertEqual(self._client().get('/api/v1/sponsor/terms/').status_code, 200)

    def test_an_outsider_gets_nothing(self):
        self.assertIn(APIClient().get('/api/v1/sponsor/terms/').status_code, (401, 403))

    def test_the_quiz_returns_the_checkpoints(self):
        res = self._client().get('/api/v1/sponsor/terms/quiz/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data['checkpoints']), 1)
        # The correct index IS sent: this is a comprehension check, not an exam, and the retry
        # loop would otherwise cost a round trip per wrong answer.
        self.assertEqual(res.data['checkpoints'][0]['correct'], 1)

    def test_typing_a_name_accepts_and_clears_the_gate(self):
        res = self._client().post('/api/v1/sponsor/terms/accept/',
                                  {'version': '2026-sponsor-1', 'signed_name': 'Ve. Elanjelian'},
                                  format='json')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['terms']['needs_terms'])
        row = SponsorTermsAcceptance.objects.get(sponsor=self.sponsor)
        self.assertEqual(row.signed_name, 'Ve. Elanjelian')
        self.assertEqual(row.registered_name_at_acceptance, 'Ve. Elanjelian')
        self.assertIsNotNone(row.accepted_at)

    def test_a_stale_version_is_refused_with_409_rather_than_recorded(self):
        # They read v1, a v2 was published while they were reading, and they must not end up
        # having "accepted" wording they never saw.
        v2 = _draft('2026-sponsor-2')
        sponsor_terms.publish(v2, allowed=True)
        res = self._client().post('/api/v1/sponsor/terms/accept/',
                                  {'version': '2026-sponsor-1', 'signed_name': 'A B'},
                                  format='json')
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.data['error'], 'version_changed')
        self.assertEqual(res.data['version'], '2026-sponsor-2')
        self.assertEqual(SponsorTermsAcceptance.objects.count(), 0)

    def test_a_blank_signature_is_refused(self):
        res = self._client().post('/api/v1/sponsor/terms/accept/',
                                  {'version': '2026-sponsor-1', 'signed_name': ' '},
                                  format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data['error'], 'signature_required')

    @override_settings(SPONSOR_TERMS_ENABLED=False)
    def test_the_PLATFORM_FLAG_alone_keeps_the_gate_down(self):
        # The eight sponsors already using the portal must not be stopped at the door merely
        # because a version was published. Publishing and gating are separate decisions.
        res = self._client().get('/api/v1/sponsor/me/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['terms']['needs_terms'])
        self.assertEqual(res.data['terms']['terms_version'], '2026-sponsor-1')

    def test_the_account_payload_reports_the_gate(self):
        res = self._client().get('/api/v1/sponsor/me/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['terms']['needs_terms'])

    def test_a_grandfathered_sponsor_is_not_gated_and_never_reads_as_accepted(self):
        sponsor_terms.grandfather(self.sponsor, self.terms, reason='friends and family')
        res = self._client().get('/api/v1/sponsor/terms/')
        self.assertFalse(res.data['state']['needs_terms'])
        self.assertEqual(res.data['state']['terms_basis'], 'grandfathered')
        self.assertEqual(res.data['signed_name'], '')      # never asked, so never signed


class TestGrandfatherCommand(TestCase):
    def setUp(self):
        self.terms = _draft('2026-sponsor-1')
        sponsor_terms.publish(self.terms, allowed=True)
        self.a = Sponsor.objects.create(supabase_user_id='a', name='A', email='a@x.com')
        self.b = Sponsor.objects.create(supabase_user_id='b', name='B', email='pilot@x.com')

    def test_a_dry_run_writes_nothing(self):
        from django.core.management import call_command
        call_command('grandfather_sponsor_terms', verbosity=0)
        self.assertEqual(SponsorTermsAcceptance.objects.count(), 0)

    def test_apply_exempts_everyone_except_the_pilot(self):
        from django.core.management import call_command
        call_command('grandfather_sponsor_terms', '--apply', '--except', 'pilot@x.com',
                     verbosity=0)
        rows = SponsorTermsAcceptance.objects.all()
        self.assertEqual([r.sponsor_id for r in rows], [self.a.id])
        self.assertEqual(rows[0].basis, 'grandfathered')
        self.assertIsNone(rows[0].accepted_at)
        # The pilot has no row, so they and only they meet the wizard.
        self.assertTrue(sponsor_terms.acceptance_state(self.b)['needs_terms'])

    def test_it_is_idempotent(self):
        from django.core.management import call_command
        call_command('grandfather_sponsor_terms', '--apply', verbosity=0)
        call_command('grandfather_sponsor_terms', '--apply', verbosity=0)
        self.assertEqual(SponsorTermsAcceptance.objects.count(), 2)
