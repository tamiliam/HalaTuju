"""Owner ruling D16 (2026-10-27) — whether a gift asks for STPM-level results is a PER-GIFT setting,
`Programme.asks_higher_results`, read through ONE helper, `results_route.gift_asks_higher`.

BrightPath flagship (`brightpath-flagship`) is a POST-SPM programme; BrightPath Sabah is where
STPM-level results matter. Pinned here, on the SHAPES of live rows (never their data):

1. **Default ON** — a new gift, an existing one, and an application with no gift at all.
2. **OFF (flagship-shaped)** — a tertiary-held, degree-bound applicant: the SPM slip stays required
   as the programme set it, no higher-results card (D12 / D14 mapping not applied), no
   "Move it to STPM results"; once submitted, no `higher_owed` slot, cap or Check-2 ask.
3. **ON** — the same applicant gets today's behaviour, unchanged.
4. **Frozen snapshots are never rewritten** — a submitted application keeps what it froze.
5. **Configuration** — the gift's toggle is served, saved through the existing PUT, audited only on
   a change, a non-boolean is refused writing nothing, and the org fence is unchanged.
"""
from django.test import TestCase, override_settings

from apps.scholarship import higher_owed, requirements, results_route
from apps.scholarship.academic_engine import student_slip_check
from apps.scholarship.check2_queries import sync_check2_queries
from apps.scholarship.models import Programme, ResolutionItem
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_cohort, make_org, make_programme,
)
from apps.scholarship.tests.test_third_route_higher_owed import GENUINE_SPM
from apps.scholarship.tests.test_third_route_s4 import (
    DEGREE, SPM_HELD, SPM_READ, STPM_CERT_READ, STPM_HELD, _academic, _app, _doc, _fresh,
)

CONFIG = '/api/v1/admin/scholarship/programme/configuration/'
AUDIT_LOGGER = 'apps.scholarship.views_admin'


def _gift(asks):
    return make_cohort(programme=make_programme(asks_higher_results=asks))


def _live(profile=STPM_HELD, asks=False):
    """An application NOT yet submitted, on a gift that does (True) or does not (False) ask."""
    return _fresh(_app(profile, DEGREE, cohort=_gift(asks)))


def _submitted(asks=False):
    """#388's shape (submitted with the pre-S3 "SPM slip required" snapshot, an SPM slip on file)."""
    app = _app(STPM_HELD, DEGREE, stage='profile_complete', cohort=_gift(asks))
    _doc(app, 'results_slip', SPM_READ, authenticity=GENUINE_SPM)
    return _fresh(app)


class TestDefaultOn(TestCase):
    def test_a_new_gift_asks(self):
        gift = Programme.objects.create(organisation=make_org('d16-new'), code='d16-new', name_en='N')
        gift.refresh_from_db()
        self.assertTrue(gift.asks_higher_results)

    def test_the_helper_reads_true_by_default_and_with_no_gift(self):
        self.assertTrue(results_route.gift_asks_higher(_live(asks=True)))
        self.assertTrue(results_route.gift_asks_higher(None))
        self.assertFalse(results_route.gift_asks_higher(_live(asks=False)))


class TestAnSpmOnlyGift(TestCase):
    """The flagship shape: `asks_higher_results` False."""

    def test_the_spm_slip_stays_required_and_no_higher_card(self):
        docs = requirements.resolve(_live(), 'document')
        self.assertEqual(docs.get('results_slip'), 'required')
        self.assertNotIn('higher_results', docs)

    def test_d14_is_not_applied_to_an_spm_holder_bound_for_a_degree(self):
        docs = requirements.resolve(_live(profile=SPM_HELD), 'document')
        self.assertEqual(docs.get('results_slip'), 'required')
        self.assertNotIn('higher_results', docs)

    def test_map_documents_returns_the_programmes_answer_untouched(self):
        app = _live()
        resolved = {'ic': 'required', 'results_slip': 'required'}
        self.assertEqual(results_route.map_documents(app, resolved), resolved)

    def test_the_reverse_move_is_not_offered(self):
        app = _live()
        chk = student_slip_check(_doc(app, 'results_slip', STPM_CERT_READ))
        self.assertEqual(chk['higher_kind'], 'stpm')      # the reviewer-facing wrong-slip note stays
        self.assertFalse(chk['move_offered'])

    @override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_the_move_endpoint_refuses_it(self):
        app = _live()
        doc = _doc(app, 'results_slip', STPM_CERT_READ)
        r = authed_client(app.profile).post('/api/v1/scholarship/results/refile-to-higher/',
                                            {'document_id': doc.id}, format='json')
        self.assertEqual((r.status_code, r.json().get('code')), (400, 'higher_card_not_shown'))
        doc.refresh_from_db()
        self.assertEqual(doc.doc_type, 'results_slip')

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
    def test_submitted_no_missing_slot_no_cap_no_ask(self):
        app = _submitted()
        self.assertEqual(higher_owed.owed_kind(app), '')
        self.assertEqual(higher_owed.ask_codes(app), set())
        f = _academic(app)
        self.assertEqual(f['status'], 'verified')                  # not capped at Probable
        self.assertNotIn(higher_owed.NOTE_CODE, [i['code'] for i in f['unresolved']])
        sync_check2_queries(app)
        self.assertFalse(ResolutionItem.objects.filter(
            application=app, source='check2', code=higher_owed.ASK_CODE).exists())


class TestAGiftThatAsks(TestCase):
    """The same shapes on a gift that asks (`asks_higher_results` True): today's behaviour."""

    def test_the_higher_card_is_required_and_the_spm_slip_optional(self):
        docs = requirements.resolve(_live(asks=True), 'document')
        self.assertEqual((docs.get('higher_results'), docs.get('results_slip')), ('required', 'optional'))

    def test_d14_still_requires_both_for_an_spm_holder(self):
        docs = requirements.resolve(_live(profile=SPM_HELD, asks=True), 'document')
        self.assertEqual((docs.get('higher_results'), docs.get('results_slip')), ('required', 'required'))

    def test_the_reverse_move_is_offered(self):
        app = _live(asks=True)
        self.assertTrue(student_slip_check(_doc(app, 'results_slip', STPM_CERT_READ))['move_offered'])

    @override_settings(DOC_GENUINENESS_CHECK_ENABLED=True)
    def test_submitted_slot_cap_and_ask(self):
        app = _submitted(asks=True)
        self.assertEqual(higher_owed.owed_kind(app), 'stpm')
        self.assertEqual(higher_owed.ask_codes(app), {higher_owed.ASK_CODE})
        self.assertEqual(_academic(app)['status'], 'review')


class TestFrozenSnapshotsAreKept(TestCase):
    def test_a_snapshot_requiring_the_higher_results_is_not_rewritten(self):
        app = _submitted()
        frozen = {**app.requirements_snapshot, 'documents': {
            'ic': 'required', 'results_slip': 'optional', 'higher_results': 'required'}}
        app.requirements_snapshot = frozen
        app.save(update_fields=['requirements_snapshot'])
        app = _fresh(app)
        self.assertEqual(requirements.resolve(app, 'document').get('higher_results'), 'required')
        self.assertEqual(app.requirements_snapshot, frozen)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheConfigurationToggle(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_application_catalogue', verbosity=0)
        cls.org = make_org('d16-org')
        cls.gift = make_programme(organisation=cls.org, code='d16-a', is_active=True)
        cls.other = make_programme(organisation=cls.org, code='d16-b', is_active=True)
        cls.foreign = make_programme(organisation=make_org('d16-foreign'), code='d16-x')
        cls.oa = make_admin('org_admin', owning_org=cls.org)

    def _put(self, body, gift='d16-a', who=None):
        return authed_client(who or self.oa).put(f'{CONFIG}?programme={gift}', body, format='json')

    def test_served_on_by_default(self):
        resp = authed_client(self.oa).get(f'{CONFIG}?programme=d16-a')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIs(resp.json()['asks_higher_results'], True)

    def test_switching_off_saves_that_gift_only_and_audits(self):
        with self.assertLogs(AUDIT_LOGGER, 'INFO') as logs:
            resp = self._put({'asks_higher_results': False})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIs(resp.json()['asks_higher_results'], False)
        self.gift.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual((self.gift.asks_higher_results, self.other.asks_higher_results), (False, True))
        self.assertIn('AUDIT programme_setting_set programme=d16-a setting=asks_higher_results '
                      f'was=on now=off by={self.oa.email}', ' | '.join(r.getMessage() for r in logs.records))

    def test_a_no_op_is_not_audited(self):
        with self.assertLogs(AUDIT_LOGGER, 'INFO') as logs:
            self._put({'asks_higher_results': True, 'sources': {'social': False}})
        self.assertFalse([r for r in logs.records if 'programme_setting_set' in r.getMessage()])

    def test_a_non_boolean_is_refused_and_nothing_is_written(self):
        resp = self._put({'asks_higher_results': 'off', 'sources': {'social': False}})
        self.assertEqual((resp.status_code, resp.json()['code']), (400, 'bad_asks_higher_results'))
        self.gift.refresh_from_db()
        self.assertEqual((self.gift.asks_higher_results, self.gift.offers_social), (True, True))

    def test_the_org_fence_and_the_role_are_unchanged(self):
        self.assertEqual(self._put({'asks_higher_results': False}, gift='d16-x').status_code, 404)
        self.foreign.refresh_from_db()
        self.assertTrue(self.foreign.asks_higher_results)
        plain = make_admin('admin', owning_org=self.org)
        self.assertEqual(self._put({'asks_higher_results': False}, who=plain).status_code, 403)
