"""Contract module — authoring immutability, quiz generation (mocked Gemini),
the deployment lifecycle, and the reader seams.

Gemini is mocked exactly like the reports tests (``@patch('google.genai.Client')``
+ overridden ``GEMINI_API_KEY``) — never a live call in CI.
"""
import datetime
import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.courses.models import StudentProfile
from apps.scholarship import contracts
from apps.scholarship.contracts import ContractsError
from apps.scholarship.models import (
    BursaryAgreement, ContractTemplate, ScholarshipApplication, ScholarshipCohort,
)

from apps.scholarship.tests.contract_helpers import (
    brightpath_org, make_deployable, seed_draft,
)

VALID_QUIZ = {'tag': 't', 'plain': 'p', 'question': 'q',
              'options': ['a', 'b', 'c'], 'correct': 1, 'why': 'w'}


def _deploy(template, **kw):
    contracts.submit_for_deployment(template)
    return contracts.deploy(template, is_super=True, **kw)


# ─────────────────────────────────────────────────────────────────────────────
# Authoring
# ─────────────────────────────────────────────────────────────────────────────
class TestCreateTemplate(TestCase):
    def test_creates_a_draft(self):
        t = contracts.create_template(brightpath_org(), '2027-v1', created_by_email='a@b.c')
        self.assertEqual(t.status, 'draft')
        self.assertEqual(t.version, '2027-v1')
        self.assertEqual(t.created_by_email, 'a@b.c')

    def test_blank_version_refused(self):
        with self.assertRaises(ContractsError) as cm:
            contracts.create_template(brightpath_org(), '   ')
        self.assertEqual(cm.exception.code, 'version_required')

    def test_duplicate_version_refused(self):
        contracts.create_template(brightpath_org(), 'dup')
        with self.assertRaises(ContractsError) as cm:
            contracts.create_template(brightpath_org(), 'dup')
        self.assertEqual(cm.exception.code, 'version_exists')

    def test_copy_from_clones_content(self):
        src = seed_draft('2026-v1')
        clone = contracts.create_template(brightpath_org(), '2027-v1', copy_from=src)
        self.assertEqual(clone.clauses.count(), src.clauses.count())
        self.assertEqual(clone.schedule_rows.count(), src.schedule_rows.count())
        self.assertEqual(clone.status, 'draft')
        # Clone starts unvetted/undeployed regardless of the source's stamps.
        self.assertEqual(clone.deployed_by_at, None)


class TestAuthoringIsDraftOnly(TestCase):
    """The immutability guarantee: no authoring call touches a non-draft template."""

    def setUp(self):
        self.t = _deploy(make_deployable())  # now 'active'

    def test_update_config_refused(self):
        with self.assertRaises(ContractsError) as cm:
            contracts.update_config(self.t, counterparty_title='x')
        self.assertEqual(cm.exception.code, 'not_draft')

    def test_replace_clauses_refused(self):
        with self.assertRaises(ContractsError) as cm:
            contracts.replace_clauses(self.t, [])
        self.assertEqual(cm.exception.code, 'not_draft')

    def test_replace_schedule_refused(self):
        with self.assertRaises(ContractsError) as cm:
            contracts.replace_schedule(self.t, [])
        self.assertEqual(cm.exception.code, 'not_draft')

    def test_record_vetting_refused(self):
        with self.assertRaises(ContractsError) as cm:
            contracts.record_vetting(self.t, vetted_by_name='x',
                                     vetted_on=datetime.date(2026, 1, 1),
                                     attested_by_email='a@b.c')
        self.assertEqual(cm.exception.code, 'not_draft')


class TestUpdateConfig(TestCase):
    def test_sets_whitelisted_fields(self):
        t = seed_draft()
        contracts.update_config(t, counterparty_name='ACME', parent_pin_required=False)
        t.refresh_from_db()
        self.assertEqual(t.counterparty_name, 'ACME')
        self.assertFalse(t.parent_pin_required)

    def test_unknown_field_refused(self):
        t = seed_draft()
        with self.assertRaises(ContractsError) as cm:
            contracts.update_config(t, not_a_field='x')
        self.assertEqual(cm.exception.code, 'unknown_config_field')


class TestReplaceSchedule(TestCase):
    def test_duplicate_pathway_variant_refused(self):
        t = seed_draft()
        rows = [
            {'pathway': 'stpm', 'variant': '', 'monthly_amount': '200', 'start_month': 7,
             'paid_offsets': [0]},
            {'pathway': 'stpm', 'variant': '', 'monthly_amount': '200', 'start_month': 7,
             'paid_offsets': [0]},
        ]
        with self.assertRaises(ContractsError) as cm:
            contracts.replace_schedule(t, rows)
        self.assertEqual(cm.exception.code, 'duplicate_schedule_row')


# ─────────────────────────────────────────────────────────────────────────────
# Quiz generation (mocked Gemini)
# ─────────────────────────────────────────────────────────────────────────────
def _mock_genai(text):
    response = MagicMock()
    response.text = text
    client = MagicMock()
    client.models.generate_content.return_value = response
    cls = MagicMock(return_value=client)
    return cls, client


@override_settings(GEMINI_API_KEY='test-key', CONTRACT_QUIZ_MODEL='gemini-2.5-pro')
class TestGenerateQuiz(TestCase):
    def setUp(self):
        self.t = seed_draft()
        self.clause = self.t.clauses.get(order=2)  # a non-candidate to (re)generate

    def _payload(self):
        return json.dumps({'en': VALID_QUIZ, 'ms': VALID_QUIZ, 'ta': VALID_QUIZ})

    @patch('google.genai.Client')
    def test_success_saves_quiz_and_stamps_model(self, mock_cls):
        cls, client = _mock_genai(self._payload())
        mock_cls.side_effect = cls
        contracts.generate_quiz(self.clause)
        self.clause.refresh_from_db()
        self.assertTrue(self.clause.is_quiz_candidate)
        self.assertEqual(self.clause.quiz_en['question'], 'q')
        self.assertEqual(self.clause.quiz_generated_model, 'gemini-2.5-pro')

    @patch('google.genai.Client')
    def test_uses_single_configured_model_no_downgrade(self, mock_cls):
        cls, client = _mock_genai(self._payload())
        mock_cls.side_effect = cls
        contracts.generate_quiz(self.clause)
        # Exactly ONE model call, with the configured model (no cascade).
        self.assertEqual(client.models.generate_content.call_count, 1)
        _, kwargs = client.models.generate_content.call_args
        self.assertEqual(kwargs['model'], 'gemini-2.5-pro')

    @patch('google.genai.Client')
    def test_bad_json_raises(self, mock_cls):
        cls, _ = _mock_genai('not json at all')
        mock_cls.side_effect = cls
        with self.assertRaises(ContractsError) as cm:
            contracts.generate_quiz(self.clause)
        self.assertEqual(cm.exception.code, 'quiz_bad_json')

    @patch('google.genai.Client')
    def test_structurally_invalid_output_raises(self, mock_cls):
        bad = json.dumps({'en': {'options': ['a', 'b'], 'correct': 0}})
        cls, _ = _mock_genai(bad)
        mock_cls.side_effect = cls
        with self.assertRaises(ContractsError) as cm:
            contracts.generate_quiz(self.clause)
        self.assertEqual(cm.exception.code, 'quiz_invalid')

    @patch('google.genai.Client')
    def test_fenced_json_is_tolerated(self, mock_cls):
        cls, _ = _mock_genai('```json\n' + self._payload() + '\n```')
        mock_cls.side_effect = cls
        contracts.generate_quiz(self.clause)
        self.clause.refresh_from_db()
        self.assertEqual(self.clause.quiz_en['correct'], 1)

    def test_missing_api_key_raises(self):
        with override_settings(GEMINI_API_KEY=''):
            with self.assertRaises(ContractsError) as cm:
                contracts.generate_quiz(self.clause)
        self.assertEqual(cm.exception.code, 'quiz_ai_unconfigured')

    def test_generate_on_non_draft_refused(self):
        active = _deploy(make_deployable('2027-x'))
        clause = active.clauses.get(order=2)
        with self.assertRaises(ContractsError) as cm:
            contracts.generate_quiz(clause)
        self.assertEqual(cm.exception.code, 'not_draft')


# ─────────────────────────────────────────────────────────────────────────────
# Lifecycle
# ─────────────────────────────────────────────────────────────────────────────
class TestLifecycle(TestCase):
    def test_submit_moves_draft_to_pending(self):
        t = make_deployable()
        contracts.submit_for_deployment(t, submitted_by_email='a@b.c')
        t.refresh_from_db()
        self.assertEqual(t.status, 'pending_deployment')
        self.assertEqual(t.submitted_by_email, 'a@b.c')

    def test_submit_refuses_when_invalid(self):
        t = seed_draft()  # no counterparty, no attestation → invalid
        with self.assertRaises(ContractsError) as cm:
            contracts.submit_for_deployment(t)
        self.assertEqual(cm.exception.code, 'not_deployable')
        self.assertIn('T1', cm.exception.errors)
        t.refresh_from_db()
        self.assertEqual(t.status, 'draft')

    def test_revert_returns_pending_to_draft(self):
        t = make_deployable()
        contracts.submit_for_deployment(t)
        contracts.revert_to_draft(t)
        t.refresh_from_db()
        self.assertEqual(t.status, 'draft')
        self.assertIsNone(t.submitted_by_at)

    def test_deploy_is_super_only(self):
        t = make_deployable()
        contracts.submit_for_deployment(t)
        with self.assertRaises(ContractsError) as cm:
            contracts.deploy(t, is_super=False)
        self.assertEqual(cm.exception.code, 'deploy_forbidden')

    def test_deploy_requires_pending(self):
        t = make_deployable()  # still draft
        with self.assertRaises(ContractsError) as cm:
            contracts.deploy(t, is_super=True)
        self.assertEqual(cm.exception.code, 'not_pending')

    def test_deploy_activates_and_stamps(self):
        t = _deploy(make_deployable(), deployed_by_email='super@x.c')
        t.refresh_from_db()
        self.assertEqual(t.status, 'active')
        self.assertEqual(t.deployed_by_email, 'super@x.c')
        self.assertIsNotNone(t.deployed_by_at)

    def test_deploy_atomically_archives_previous_active(self):
        first = _deploy(make_deployable('2026-v1'))
        self.assertEqual(first.status, 'active')
        second = _deploy(make_deployable('2026-v2'))
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(second.status, 'active')
        self.assertEqual(first.status, 'archived')
        self.assertIsNotNone(first.archived_at)
        # Exactly one active template for the org.
        self.assertEqual(
            ContractTemplate.objects.filter(
                organisation=brightpath_org(), status='active').count(), 1)


# ─────────────────────────────────────────────────────────────────────────────
# Readers
# ─────────────────────────────────────────────────────────────────────────────
class TestReaders(TestCase):
    def test_active_template_for(self):
        self.assertIsNone(contracts.active_template_for(brightpath_org()))
        t = _deploy(make_deployable())
        self.assertEqual(contracts.active_template_for(brightpath_org()), t)

    def test_template_for_application_prefers_pinned(self):
        active = _deploy(make_deployable('2026-v1'))
        pinned = ContractTemplate.objects.create(
            organisation=brightpath_org(), version='pinned', status='archived')
        cohort = ScholarshipCohort.objects.create(code='rd', name='B40', year=2026)
        profile = StudentProfile.objects.create(supabase_user_id='rd-1', grades={}, exam_type='spm')
        app = ScholarshipApplication.objects.create(
            cohort=cohort, profile=profile, status='awarded', chosen_pathway='matric')
        BursaryAgreement.objects.create(application=app, version='pinned', template=pinned)
        # The signed agreement's pinned template wins over the org's active one.
        self.assertEqual(contracts.template_for_application(app), pinned)

    def test_quiz_checkpoints_in_order_with_en_fallback(self):
        t = seed_draft()
        cps_en = contracts.quiz_checkpoints(t, 'en')
        self.assertEqual(len(cps_en), 8)
        # ta clause bodies are blank but the quiz has ta content → ta returned.
        cps_ta = contracts.quiz_checkpoints(t, 'ta')
        self.assertEqual(len(cps_ta), 8)
        self.assertTrue(all('question' in cp for cp in cps_ta))

    def test_resolve_locale_clamps_to_available(self):
        t = seed_draft()
        # ms/ta aren't fully translated at template level → clamp to en.
        self.assertEqual(contracts.resolve_locale('ms', t), 'en')
        self.assertEqual(contracts.resolve_locale('en', t), 'en')
        self.assertEqual(contracts.resolve_locale('ta', None), 'en')

    def test_languages_available_is_english_only_for_seed(self):
        t = seed_draft()
        self.assertEqual(t.languages_available, ['en'])

    def test_render_preview_html_has_banner_and_notice(self):
        t = seed_draft()
        html = contracts.render_preview_html(t, 'en')
        self.assertIn('PREVIEW', html)
        self.assertIn('authoritative', html)
        self.assertIn(t.title_en, html)
