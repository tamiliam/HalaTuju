"""The apply page's public copy belongs to the GIFT (2026-09-09).

Two defects are proven here, and both are silent — which is why the tests are the deliverable:

1. **One advertisement for the whole platform.** The heading, intro and criteria were fixed
   strings, so a second gift's own apply link advertised BrightPath's B40 criteria. Sabah is
   ~2 weeks out.
2. **The open/closed gate answered platform-wide.** `getScholarshipIntake()` sent no programme
   code, so with Sabah open and BrightPath closed a student on an old BrightPath poster would be
   shown the WHOLE form and refused at submit — PF-1's "right refusal, wrong moment" again.

⚠ THE ADVERTISED BAR IS DELIBERATELY STRICTER THAN THE ENGINE (Sprint 8, 2026-05-24; reaffirmed
by the owner 2026-09-09). Nothing here derives copy from a round's thresholds, and no test should
ever assert that it does.
"""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.scholarship import apply_copy
from apps.scholarship.models import Programme, ProgrammeCodeAlias, ScholarshipCohort
from apps.scholarship.tests.test_api import TEST_JWT_SECRET
from apps.scholarship.tests.test_sabah_programme_screens import _Case, _org

INTAKE = '/api/v1/scholarship/intake/'
PROGRAMMES = '/api/v1/admin/scholarship/programmes/'

CARD = {'en': {'title': 'Apply for the Sabah Bursary',
               'intro': 'Support for Sabahan school leavers.',
               'criteria': ['Resident in Sabah.', 'Continuing to tertiary study.']}}


def _cohort(org, programme, code, *, is_open=True):
    return ScholarshipCohort.objects.create(
        code=code, name=f'Round {code}', year=2026, programme=programme,
        owning_organisation=org, is_open=is_open, is_active=True)


# ── The pure module ──────────────────────────────────────────────────────────────────────────

class TestTheCopyIsAllOrNothing(TestCase):
    """A gift writes its whole card or uses the platform's — never half of each."""

    def test_a_blank_payload_means_the_platform_default(self):
        self.assertEqual(apply_copy.normalise(None), {})
        self.assertEqual(apply_copy.normalise({}), {})

    def test_a_title_with_no_intro_is_refused(self):
        """Per-FIELD fallback would put the platform's B40 heading over Sabah's own bullets."""
        with self.assertRaises(apply_copy.ApplyCopyError) as ctx:
            apply_copy.normalise({'en': {'title': 'Hello', 'intro': '', 'criteria': []}})
        self.assertEqual(ctx.exception.code, 'incomplete')

    def test_malay_alone_is_refused_because_english_is_the_fallback(self):
        with self.assertRaises(apply_copy.ApplyCopyError) as ctx:
            apply_copy.normalise({'ms': dict(CARD['en'])})
        self.assertEqual(ctx.exception.code, 'english_required')

    def test_blank_bullets_are_dropped_not_refused(self):
        out = apply_copy.normalise({'en': {**CARD['en'], 'criteria': ['One.', '  ', 'Two.']}})
        self.assertEqual(out['en']['criteria'], ['One.', 'Two.'])

    def test_an_over_long_title_names_its_own_field(self):
        with self.assertRaises(apply_copy.ApplyCopyError) as ctx:
            apply_copy.normalise({'en': {**CARD['en'], 'title': 'x' * 121}})
        self.assertEqual((ctx.exception.code, ctx.exception.field), ('too_long', 'en.title'))

    def test_nine_bullets_are_refused(self):
        with self.assertRaises(apply_copy.ApplyCopyError) as ctx:
            apply_copy.normalise({'en': {**CARD['en'], 'criteria': ['a'] * 9}})
        self.assertEqual(ctx.exception.code, 'too_many')

    def test_angle_brackets_are_refused_because_this_is_not_markup(self):
        with self.assertRaises(apply_copy.ApplyCopyError) as ctx:
            apply_copy.normalise({'en': {**CARD['en'], 'intro': '<script>x</script>'}})
        self.assertEqual(ctx.exception.code, 'markup')


class TestMalayFallsBackToTheGiftsOwnEnglish(TestCase):
    """⚠ NEVER to the platform's Malay — that would advertise another gift's criteria."""

    def test_a_gift_with_english_only_serves_english_in_every_locale(self):
        p = Programme.objects.create(
            organisation=_org('fb-org'), code='fb', name_en='FB', apply_copy=CARD)
        wire = apply_copy.for_wire(p)
        self.assertEqual(wire['ms'], CARD['en'])
        self.assertEqual(wire['ta'], CARD['en'])

    def test_a_gift_with_no_copy_serves_nothing_so_the_browser_uses_the_platform_default(self):
        p = Programme.objects.create(
            organisation=_org('fb-org2'), code='fb2', name_en='FB2')
        self.assertEqual(apply_copy.for_wire(p), {})


class TestTheEthnicityWarning(TestCase):
    """Owner ruling 2026-09-09 (option A): WARN, never refuse. MyNadi's s44(6) is the reason."""

    def test_it_flags_a_descent_criterion(self):
        self.assertIn('indian', apply_copy.sensitive_terms('Open to students of Indian descent'))

    def test_a_language_subject_is_not_an_ethnicity_claim(self):
        """"Bahasa Melayu" is the most ordinary bullet anybody writes. It must not cry wolf."""
        self.assertEqual(apply_copy.sensitive_terms('A credit in Bahasa Melayu.'), ())
        self.assertEqual(apply_copy.sensitive_terms('Kredit dalam Bahasa Tamil.'), ())

    def test_normalise_still_SAVES_flagged_copy(self):
        """The ruling is a warning. A refusal here would bind a tenant to our funder's terms."""
        out = apply_copy.normalise(
            {'en': {**CARD['en'], 'criteria': ['Open to students of Indian descent.']}})
        self.assertTrue(out['en']['criteria'])


# ── The public endpoint ──────────────────────────────────────────────────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheIntakeEndpointAnswersPerGift(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = _org('ac-org')
        cls.open_gift = Programme.objects.create(
            organisation=cls.org, code='ac-open', name_en='Open Gift', apply_copy=CARD)
        cls.shut_gift = Programme.objects.create(
            organisation=cls.org, code='ac-shut', name_en='Shut Gift', apply_copy=CARD)
        _cohort(cls.org, cls.open_gift, 'ac-open-2026', is_open=True)
        _cohort(cls.org, cls.shut_gift, 'ac-shut-2026', is_open=False)
        ProgrammeCodeAlias.objects.create(programme=cls.shut_gift, code='ac-shut-old')

    def setUp(self):
        self.client = APIClient()

    def _get(self, code=None):
        url = INTAKE if code is None else f'{INTAKE}?programme={code}'
        return self.client.get(url).json()

    def test_THE_GATE_ANSWERS_PER_GIFT_not_platform_wide(self):
        """⚠ THE SABAH DEFECT. One gift open, another closed — the closed one reads closed.

        Pre-fix the browser asked "is anything open anywhere?", so this student was shown the
        whole form and refused only at submit.
        """
        self.assertTrue(self._get('ac-open')['open'])
        self.assertFalse(self._get('ac-shut')['open'])

    def test_a_closed_gift_is_still_IDENTIFIED_so_the_answer_is_about_the_right_gift(self):
        body = self._get('ac-shut')
        self.assertFalse(body['open'])
        self.assertEqual(body['apply_copy']['en']['title'], CARD['en']['title'])

    def test_a_retired_code_reaches_its_gifts_copy(self):
        """The alias path. A printed poster keeps working after a rename."""
        body = self._get('ac-shut-old')
        self.assertEqual(body['apply_copy']['en']['title'], CARD['en']['title'])

    def test_a_gift_with_no_copy_serves_an_empty_map(self):
        bare = Programme.objects.create(
            organisation=self.org, code='ac-bare', name_en='Bare')
        _cohort(self.org, bare, 'ac-bare-2026', is_open=False)
        self.assertEqual(self._get('ac-bare')['apply_copy'], {})

    def test_an_unknown_code_reads_closed_with_no_copy_and_is_NOT_a_404(self):
        """Public + unauthenticated: a 404 would let anyone enumerate the platform's tenants."""
        body = self._get('no-such-gift')
        self.assertFalse(body['open'])
        self.assertEqual(body['apply_copy'], {})

    def test_no_code_and_one_open_round_serves_that_gifts_copy(self):
        ScholarshipCohort.objects.filter(code='ac-shut-2026').delete()
        body = self._get()
        self.assertTrue(body['open'])
        self.assertEqual(body['apply_copy']['en']['title'], CARD['en']['title'])


# ── The editor ───────────────────────────────────────────────────────────────────────────────

class TestOnlyTheGiftsOwnOrganisationMayWriteIt(_Case):
    def _url(self, p):
        return f'{PROGRAMMES}{p.id}/'

    def _row(self, admin, p):
        """Read the row back off the LIST — the detail route is write-only (no GET), and the
        list is what the tab actually loads, so this is the reload the claim is about."""
        body = self._get(admin, PROGRAMMES).json()
        rows = body['programmes'] if isinstance(body, dict) else body
        return next(r for r in rows if r['id'] == p.id)

    def test_an_org_admin_saves_its_own_gifts_copy(self):
        r = self._patch(self.admin_a, self._url(self.prog_a), {'apply_copy': CARD})
        self.assertEqual(r.status_code, 200)
        self.prog_a.refresh_from_db()
        self.assertEqual(self.prog_a.apply_copy['en']['title'], CARD['en']['title'])

    def test_the_row_carries_the_stored_map_VERBATIM_so_a_blank_box_stays_blank(self):
        """`for_wire` folds ms onto English for a READER; an EDITOR must not see that."""
        self._patch(self.admin_a, self._url(self.prog_a), {'apply_copy': CARD})
        self.assertNotIn('ms', self._row(self.admin_a, self.prog_a)['apply_copy'])

    def test_a_refusal_names_the_field_the_reader_is_looking_at(self):
        r = self._patch(self.admin_a, self._url(self.prog_a),
                        {'apply_copy': {'en': {**CARD['en'], 'title': 'x' * 200}}})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['field'], 'en.title')

    def test_another_tenants_gift_is_404_never_403(self):
        r = self._patch(self.admin_a, self._url(self.prog_b), {'apply_copy': CARD})
        self.assertEqual(r.status_code, 404)

    def test_a_reviewer_may_not_write_it(self):
        r = self._patch(self.reviewer_a, self._url(self.prog_a), {'apply_copy': CARD})
        self.assertIn(r.status_code, (403, 404))

    def test_flagged_wording_is_reported_on_the_row_so_the_caution_survives_a_reload(self):
        self._patch(self.admin_a, self._url(self.prog_a),
                    {'apply_copy': {'en': {**CARD['en'],
                                           'criteria': ['Open to students of Indian descent.']}}})
        self.assertIn('indian', self._row(self.admin_a, self.prog_a)['apply_copy_sensitive'])

    def test_clearing_it_returns_the_gift_to_the_platform_default(self):
        self._patch(self.admin_a, self._url(self.prog_a), {'apply_copy': CARD})
        r = self._patch(self.admin_a, self._url(self.prog_a), {'apply_copy': {}})
        self.assertEqual(r.status_code, 200)
        self.prog_a.refresh_from_db()
        self.assertEqual(self.prog_a.apply_copy, {})
