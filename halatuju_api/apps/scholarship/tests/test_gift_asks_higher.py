"""Owner rulings D16 + D16c (2026-10-27) — whether an application's gift asks for STPM-level
results is INFERRED from its INTAKE: `cohort.min_stpm_pngk` set → it asks; blank → SPM only. ONE
reader, `results_route.gift_asks_higher`. There is no per-gift switch any more (D16c superseded the
D16 Configuration toggle; `Programme.asks_higher_results` is left in place, unread, for a later drop).

BrightPath flagship (`brightpath-flagship`, intake b40-2026) is a POST-SPM programme with its STPM
floor cleared; BrightPath Sabah sets one. Pinned here, on the SHAPES of live rows (never their data):

1. **A floor asks** — the default intake (2.9), and an application with no intake at all.
2. **Blank floor (flagship-shaped)** — a tertiary-held, degree-bound applicant: the SPM slip stays
   required as the programme set it, no higher-results card (D12 / D14 mapping not applied), no
   "Move it to STPM results"; once submitted, no `higher_owed` slot, cap or Check-2 ask.
3. **A floor set** — the same applicant gets today's behaviour, unchanged.
4. **Frozen snapshots are never rewritten** — a submitted application keeps what it froze.
5. **No switch** — the gift's column is not read, and Configuration neither serves nor saves it.
"""
from django.test import TestCase, override_settings

from apps.scholarship import higher_owed, requirements, results_route
from apps.scholarship.academic_engine import student_slip_check
from apps.scholarship.check2_queries import sync_check2_queries
from apps.scholarship.models import ResolutionItem
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
    """An intake that sets an STPM floor (asks) or leaves it blank (SPM only)."""
    return make_cohort(min_stpm_pngk=2.9 if asks else None)


def _live(profile=STPM_HELD, asks=False):
    """An application NOT yet submitted, on a gift that does (True) or does not (False) ask."""
    return _fresh(_app(profile, DEGREE, cohort=_gift(asks)))


def _submitted(asks=False):
    """#388's shape (submitted with the pre-S3 "SPM slip required" snapshot, an SPM slip on file)."""
    app = _app(STPM_HELD, DEGREE, stage='profile_complete', cohort=_gift(asks))
    _doc(app, 'results_slip', SPM_READ, authenticity=GENUINE_SPM)
    return _fresh(app)


class TestInferredFromTheIntake(TestCase):
    def test_the_default_intake_asks(self):
        self.assertTrue(results_route.gift_asks_higher(_fresh(_app(STPM_HELD, DEGREE))))

    def test_the_helper_reads_the_intake_floor(self):
        self.assertTrue(results_route.gift_asks_higher(_live(asks=True)))
        self.assertTrue(results_route.gift_asks_higher(None))
        self.assertFalse(results_route.gift_asks_higher(_live(asks=False)))

    def test_the_gift_column_is_not_read(self):
        """D16c: the per-gift switch is gone. Its column says the opposite of the intake both
        ways round, and the intake wins both times."""
        on = make_cohort(programme=make_programme(asks_higher_results=False), min_stpm_pngk=2.5)
        off = make_cohort(programme=make_programme(asks_higher_results=True), min_stpm_pngk=None)
        self.assertTrue(results_route.gift_asks_higher(_fresh(_app(STPM_HELD, DEGREE, cohort=on))))
        self.assertFalse(results_route.gift_asks_higher(_fresh(_app(STPM_HELD, DEGREE, cohort=off))))


class TestAnSpmOnlyGift(TestCase):
    """The flagship shape: the intake leaves the STPM floor blank."""

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
    """The same shapes on an intake with an STPM floor: today's behaviour."""

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
class TestNoConfigurationSwitch(TestCase):
    """D16c: Configuration neither serves nor saves `asks_higher_results`."""

    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_application_catalogue', verbosity=0)
        cls.org = make_org('d16-org')
        cls.gift = make_programme(organisation=cls.org, code='d16-a', is_active=True)
        cls.oa = make_admin('org_admin', owning_org=cls.org)

    def test_not_served(self):
        resp = authed_client(self.oa).get(f'{CONFIG}?programme=d16-a')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertNotIn('asks_higher_results', resp.json())

    def test_not_saved_alone_and_ignored_beside_items(self):
        client = authed_client(self.oa)
        resp = client.put(f'{CONFIG}?programme=d16-a', {'asks_higher_results': False}, format='json')
        self.assertEqual((resp.status_code, resp.json()['code']), (400, 'bad_items'))
        with self.assertLogs(AUDIT_LOGGER, 'INFO') as logs:
            resp = client.put(f'{CONFIG}?programme=d16-a',
                              {'asks_higher_results': False, 'sources': {'social': False}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.gift.refresh_from_db()
        self.assertTrue(self.gift.asks_higher_results)
        self.assertFalse([r for r in logs.records if 'programme_setting_set' in r.getMessage()])
