"""Requests space — service-layer tests (Sprint 15, Phase 1).

Covers the OrgRequest transition/actor matrix (derived from the TRANSITIONS source so it can't
drift), terminal refusals, bug_is_free, the withdraw/defer/modify paths, the AI-run cap, the
defensive draft parser (good / fenced / garbage / bad-enum JSON), and the ContractsError mapping —
the AI seam mocked, never a live call.
"""
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from apps.courses.models import PartnerAdmin, PartnerOrganisation
from apps.scholarship import org_requests as svc
from apps.scholarship.models import OrgRequest


def _org(code='br'):
    return PartnerOrganisation.objects.create(code=code, name=code)


def _admin(org, role='org_admin', **kw):
    n = kw.pop('name', role)
    return PartnerAdmin.objects.create(
        supabase_user_id=kw.pop('uid', f'{code_of(org)}-{role}'), role=role,
        is_active=True, owning_organisation=org, name=n,
        email=kw.pop('email', f'{role}@{code_of(org)}.test'), **kw)


def code_of(org):
    return org.code


def _super():
    return PartnerAdmin.objects.create(
        supabase_user_id='super', is_super_admin=True, is_active=True,
        name='Super', email='super@x.test')


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = _org()
        cls.org_admin = _admin(cls.org, 'org_admin')
        cls.super = _super()

    def _req(self, kind='feature', status='submitted', **kw):
        r = OrgRequest.objects.create(
            organisation=self.org, submitted_by=self.org_admin,
            kind=kind, title='X', description='desc', status=status, **kw)
        return r


class TestCreate(_Base):
    def test_create_ok(self):
        r = svc.create_request(self.org, self.org_admin, kind='bug', title='Broken',
                               description='It crashes')
        self.assertEqual(r.status, 'submitted')
        self.assertEqual(r.kind, 'bug')
        self.assertEqual(r.ai_run_count, 0)

    def test_bad_kind(self):
        with self.assertRaises(svc.OrgRequestError) as e:
            svc.create_request(self.org, self.org_admin, kind='nope', title='X', description='y')
        self.assertEqual(e.exception.code, 'bad_kind')

    def test_missing_title_description(self):
        for kw in ({'title': '', 'description': 'y'}, {'title': 'x', 'description': ''}):
            with self.assertRaises(svc.OrgRequestError):
                svc.create_request(self.org, self.org_admin, kind='bug', **kw)


class TestTransitionMatrix(_Base):
    """Every action refuses (`bad_transition`) from any status NOT in its TRANSITIONS from-set —
    derived from the source table so a future edit can't silently loosen a gate."""

    ALL_STATUSES = [s for s, _ in OrgRequest.STATUS_CHOICES]

    def _call(self, action, req):
        """Invoke each action with the minimum valid args; the super/kind guards fire AFTER the
        transition check, so a feature at the right kind avoids masking bad_transition."""
        s, oa = self.super, self.org_admin
        return {
            'triage':   lambda: svc.triage(req, s, triaged_kind='feature', lane='sprint'),
            'quote':    lambda: svc.quote(req, s, hours=5),
            'requote':  lambda: svc.requote(req, s, hours=5),
            'approve':  lambda: svc.approve(req, oa, by_role='org_admin'),
            'defer':    lambda: svc.defer(req, oa),
            'modify':   lambda: svc.modify(req, oa, description='new'),
            'schedule': lambda: svc.schedule(req, s),
            'done':     lambda: svc.done(req, s),
            'decline':  lambda: svc.decline(req, s, by_role='super', reason='r'),
            'answer':   lambda: svc.answer_clarification(req, 'a'),
            'ai_rerun': lambda: svc.run_ai_review(req),
        }[action]()

    def test_refuses_from_invalid_statuses(self):
        for action, (valid_from, _to) in svc.TRANSITIONS.items():
            for status in self.ALL_STATUSES:
                if status in valid_from:
                    continue
                req = self._req(kind='feature', status=status)
                with self.assertRaises(svc.OrgRequestError) as e:
                    self._call(action, req)
                # answer/ai_rerun may hit not_answerable/ai_limit only from a VALID status; from an
                # invalid one it must be bad_transition.
                self.assertEqual(e.exception.code, 'bad_transition',
                                 f'{action} from {status} should be bad_transition')


class TestOwnerFlow(_Base):
    def test_triage_sets_authoritative_kind_lane(self):
        r = self._req(kind='bug')
        svc.triage(r, self.super, triaged_kind='feature', lane='sprint', note='reclassified')
        r.refresh_from_db()
        self.assertEqual(r.status, 'triaged')
        self.assertEqual(r.triaged_kind, 'feature')
        self.assertEqual(r.lane, 'sprint')
        self.assertEqual(r.triage_note, 'reclassified')

    def test_triage_requires_super(self):
        r = self._req()
        with self.assertRaises(svc.OrgRequestError) as e:
            svc.triage(r, self.org_admin, triaged_kind='feature', lane='sprint')
        self.assertEqual(e.exception.code, 'wrong_role')

    def test_triage_bad_lane(self):
        r = self._req()
        with self.assertRaises(svc.OrgRequestError) as e:
            svc.triage(r, self.super, triaged_kind='feature', lane='nope')
        self.assertEqual(e.exception.code, 'bad_lane')

    def test_quote_feature_ok(self):
        r = self._req(kind='feature', status='triaged', triaged_kind='feature', lane='sprint')
        svc.quote(r, self.super, hours='8.5', note='estimate')
        r.refresh_from_db()
        self.assertEqual(r.status, 'quoted')
        self.assertEqual(r.quote_hours, Decimal('8.5'))
        self.assertEqual(r.quote_margin_pct, 50)   # default from settings

    def test_quote_bug_is_free(self):
        r = self._req(kind='bug', status='triaged', triaged_kind='bug', lane='small_change')
        with self.assertRaises(svc.OrgRequestError) as e:
            svc.quote(r, self.super, hours=3)
        self.assertEqual(e.exception.code, 'bug_is_free')

    def test_quote_bad_hours(self):
        r = self._req(status='triaged', triaged_kind='feature', lane='sprint')
        for bad in (0, -1, 'abc'):
            r.status = 'triaged'
            with self.assertRaises(svc.OrgRequestError) as e:
                svc.quote(r, self.super, hours=bad)
            self.assertEqual(e.exception.code, 'bad_hours')

    def test_schedule_bug_from_triaged(self):
        r = self._req(kind='bug', status='triaged', triaged_kind='bug', lane='small_change')
        svc.schedule(r, self.super)
        r.refresh_from_db()
        self.assertEqual(r.status, 'scheduled')

    def test_schedule_feature_from_triaged_refused(self):
        r = self._req(kind='feature', status='triaged', triaged_kind='feature', lane='sprint')
        with self.assertRaises(svc.OrgRequestError) as e:
            svc.schedule(r, self.super)
        self.assertEqual(e.exception.code, 'bad_transition')

    def test_full_feature_path_to_done(self):
        r = self._req(kind='feature')
        svc.triage(r, self.super, triaged_kind='feature', lane='sprint')
        svc.quote(r, self.super, hours=5)
        svc.approve(r, self.org_admin, by_role='org_admin')
        self.assertEqual(r.status, 'approved')
        svc.schedule(r, self.super)
        svc.done(r, self.super)
        r.refresh_from_db()
        self.assertEqual(r.status, 'done')


class TestRequesteeResponses(_Base):
    def _quoted(self):
        r = self._req(kind='feature')
        svc.triage(r, self.super, triaged_kind='feature', lane='sprint')
        svc.quote(r, self.super, hours=5)
        return r

    def test_defer_then_requote_then_approve(self):
        r = self._quoted()
        svc.defer(r, self.org_admin)
        self.assertEqual(r.status, 'deferred')
        svc.requote(r, self.super, hours=6)
        self.assertEqual(r.status, 'quoted')
        svc.approve(r, self.org_admin, by_role='org_admin')
        self.assertEqual(r.status, 'approved')

    def test_modify_returns_to_submitted_and_keeps_history(self):
        r = self._quoted()
        old = r.description
        svc.modify(r, self.org_admin, description='amended text')
        r.refresh_from_db()
        self.assertEqual(r.status, 'submitted')
        self.assertEqual(r.description, 'amended text')
        hist = [c for c in r.clarifications if c.get('history') == 'description_modified']
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]['previous_description'], old)

    def test_withdraw_no_reason_needed(self):
        r = self._quoted()
        svc.decline(r, self.org_admin, by_role='org_admin')
        r.refresh_from_db()
        self.assertEqual(r.status, 'declined')
        self.assertEqual(r.declined_by_role, 'org_admin')

    def test_super_decline_needs_reason(self):
        r = self._quoted()
        with self.assertRaises(svc.OrgRequestError) as e:
            svc.decline(r, self.super, by_role='super')
        self.assertEqual(e.exception.code, 'reason_required')
        svc.decline(r, self.super, by_role='super', reason='out of scope')
        r.refresh_from_db()
        self.assertEqual(r.status, 'declined')
        self.assertEqual(r.decline_reason, 'out of scope')


class TestClarifications(_Base):
    def test_answer_first_unanswered(self):
        r = self._req(clarifications=[
            {'question': 'Which page?', 'asked_at': 't', 'answer': None, 'answered_at': None}])
        svc.answer_clarification(r, 'The dashboard')
        r.refresh_from_db()
        self.assertEqual(r.clarifications[0]['answer'], 'The dashboard')
        self.assertTrue(r.clarifications[0]['answered_at'])

    def test_answer_nothing_to_answer(self):
        r = self._req(clarifications=[
            {'question': 'Q', 'asked_at': 't', 'answer': 'done', 'answered_at': 't'}])
        with self.assertRaises(svc.OrgRequestError) as e:
            svc.answer_clarification(r, 'again')
        self.assertEqual(e.exception.code, 'not_answerable')


# ── AI reviewer ───────────────────────────────────────────────────────────────

_GOOD = ('{"classification": "feature", "lane": "sprint", "estimated_hours": 12, '
         '"clarifying_questions": ["Which report?"], "rationale": "New page."}')
_FENCED = '```json\n' + _GOOD + '\n```'
_BAD_ENUM = ('{"classification": "wishlist", "lane": "epic", "estimated_hours": "lots", '
             '"clarifying_questions": [], "rationale": "hmm"}')
_GARBAGE = 'I think this is a feature, roughly 3 days.'


class TestParseDraft(_Base):
    def test_good(self):
        d = svc._parse_draft(_GOOD)
        self.assertTrue(d['ok'])
        self.assertEqual(d['kind'], 'feature')
        self.assertEqual(d['lane'], 'sprint')
        self.assertEqual(d['hours'], Decimal('12.0'))
        self.assertEqual(d['questions'], ['Which report?'])

    def test_fenced(self):
        d = svc._parse_draft(_FENCED)
        self.assertTrue(d['ok'])
        self.assertEqual(d['kind'], 'feature')
        self.assertEqual(d['hours'], Decimal('12.0'))

    def test_bad_enum_clamped(self):
        d = svc._parse_draft(_BAD_ENUM)
        self.assertTrue(d['ok'])            # parsed, but enums cleared
        self.assertEqual(d['kind'], '')
        self.assertEqual(d['lane'], '')
        self.assertIsNone(d['hours'])       # non-numeric hours → None

    def test_garbage(self):
        d = svc._parse_draft(_GARBAGE)
        self.assertFalse(d['ok'])
        self.assertEqual(d['raw'], _GARBAGE)

    def test_prose_wrapped_json_recovered(self):
        d = svc._parse_draft('Sure! ' + _GOOD + ' Hope that helps.')
        self.assertTrue(d['ok'])
        self.assertEqual(d['kind'], 'feature')


class TestRunAiReview(_Base):
    def test_good_review_writes_draft_and_questions(self):
        r = self._req()
        with mock.patch('apps.scholarship.contracts._gemini_generate', return_value=_GOOD):
            out = svc.run_ai_review(r)
        r.refresh_from_db()
        self.assertEqual(r.ai_run_count, 1)
        self.assertEqual(r.ai_draft_kind, 'feature')
        self.assertEqual(r.ai_draft_hours, Decimal('12.0'))
        self.assertTrue(r.ai_draft_model)
        self.assertEqual(out['new_questions'], ['Which report?'])
        open_q = [c for c in r.clarifications if not c.get('answer')]
        self.assertEqual(len(open_q), 1)

    def test_garbage_stored_no_500(self):
        r = self._req()
        with mock.patch('apps.scholarship.contracts._gemini_generate', return_value=_GARBAGE):
            svc.run_ai_review(r)
        r.refresh_from_db()
        self.assertEqual(r.ai_run_count, 1)
        self.assertEqual(r.ai_draft_note, _GARBAGE)
        self.assertEqual(r.ai_draft_kind, '')       # nothing structured written

    def test_ai_cap(self):
        r = self._req(ai_run_count=svc.AI_RUN_CAP)
        with self.assertRaises(svc.OrgRequestError) as e:
            svc.run_ai_review(r)
        self.assertEqual(e.exception.code, 'ai_limit_reached')

    def test_contracts_error_unconfigured_mapped(self):
        from apps.scholarship import contracts
        r = self._req()
        with mock.patch('apps.scholarship.contracts._gemini_generate',
                        side_effect=contracts.ContractsError('quiz_ai_unconfigured')):
            with self.assertRaises(svc.OrgRequestError) as e:
                svc.run_ai_review(r)
        self.assertEqual(e.exception.code, 'triage_ai_unconfigured')

    def test_contracts_error_unavailable_mapped(self):
        from apps.scholarship import contracts
        r = self._req()
        with mock.patch('apps.scholarship.contracts._gemini_generate',
                        side_effect=contracts.ContractsError('quiz_ai_unavailable')):
            with self.assertRaises(svc.OrgRequestError) as e:
                svc.run_ai_review(r)
        self.assertEqual(e.exception.code, 'triage_ai_unavailable')

    def test_live_call_error_is_unavailable(self):
        r = self._req()
        with mock.patch('apps.scholarship.contracts._gemini_generate',
                        side_effect=RuntimeError('network')):
            with self.assertRaises(svc.OrgRequestError) as e:
                svc.run_ai_review(r)
        self.assertEqual(e.exception.code, 'triage_ai_unavailable')

    def test_auto_run_swallows_failure(self):
        r = self._req()
        with mock.patch('apps.scholarship.contracts._gemini_generate',
                        side_effect=RuntimeError('boom')):
            self.assertFalse(svc.auto_run_ai_review(r))
        r.refresh_from_db()
        self.assertEqual(r.ai_run_count, 0)

    def test_auto_run_dedupes_questions_across_reruns(self):
        r = self._req()
        with mock.patch('apps.scholarship.contracts._gemini_generate', return_value=_GOOD):
            self.assertTrue(svc.auto_run_ai_review(r))
            self.assertTrue(svc.auto_run_ai_review(r))
        r.refresh_from_db()
        # Same question both runs → appended once, not twice.
        qs = [c for c in r.clarifications if c.get('question')]
        self.assertEqual(len(qs), 1)
        self.assertEqual(r.ai_run_count, 2)
