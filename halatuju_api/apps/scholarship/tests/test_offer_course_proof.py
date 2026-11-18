"""Offer course proof (owner 2026-11-18, #804): how the pathway hearing reads a TERTIARY student's
declared degree, and how an offer letter's course is matched to it.

R1 a tertiary student's own degree pick or named top choices count as declared;
R2 her pick IS the letter's one catalogue course -> no ask;
R3 her pick is another course -> the one-tap "is this your final pathway?" (kept);
R4 nothing declared and the letter names ONE catalogue course -> no ask (the autofill links it);
R5 a waiting student's top choices do not include the letter's course -> no ask;
R6 the letter names no ONE catalogue course -> pick your course (pathway_undeclared);
R7 a "[a / b / c]" in a catalogue name is an option list, not specialisation words;
R8 no offer yet -> the cockpit's context line names her degree(s).

Catalogue strings are the live UPU names; no student data.
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import FieldTaxonomy, Institution, StpmCourse, StpmRequirement
from apps.scholarship.models import ApplicantDocument, ResolutionItem
from apps.scholarship.offer_course_match import match_offer_course
from apps.scholarship.tests.factories import make_application, make_cohort, make_student
from apps.scholarship.verdict_engine import build_verdict

USM = 'Universiti Sains Malaysia'
SOCSCI = ('Sarjana Muda Sains Kemasyarakatan dengan Kepujian [antropologi dan Sosiologi / Ekonomi / '
          'Sains Politik / Pengajian Pembangunan]')
ARTS = ('Sarjana Muda Sastera [pengajian Bahasa Inggeris / Linguistik Bahasa Melayu / Geografi / Sejarah / '
        'Kesusasteraan] dengan Kepujian')
#: The #804 letter's own programme line (printed code included).
LETTER_804 = 'SARJANA MUDA SAINS KEMASYARAKATAN DENGAN KEPUJIAN - US6310001'
NAME, NRIC = 'TEST STUDENT A/P SAMPLE', '080101-01-0101'


def seed_usm():
    ft, _ = FieldTaxonomy.objects.get_or_create(key='proof', defaults={
        'name_en': 'x', 'name_ms': 'x', 'name_ta': 'x', 'image_slug': 'proof'})
    inst, _ = Institution.objects.get_or_create(institution_id='RA-USM', defaults={
        'institution_name': USM, 'acronym': 'USM', 'type': 'IPTA', 'state': 'Pulau Pinang'})
    for cid, name in (('US6310001', SOCSCI), ('US6220001', ARTS)):
        sc, _ = StpmCourse.objects.get_or_create(course_id=cid, defaults={
            'course_name': name, 'university': USM, 'institution': inst, 'field_key': ft})
        StpmRequirement.objects.get_or_create(course=sc, defaults={'req_bumiputera': False})


def _cid(programme, institution=USM, issuer=USM):
    return (match_offer_course(programme, institution, issuer) or {}).get('course_id')


class BracketOptionListTest(TestCase):
    """R7: a bracketed option list is options, not specialisation words."""

    @classmethod
    def setUpTestData(cls):
        seed_usm()

    def test_the_804_printed_code_matches(self):
        self.assertEqual(_cid(LETTER_804, ''), 'US6310001')

    def test_the_menu_opens_only_under_a_printed_code(self):
        # A name-only letter keeps TD-150: the options read as a specialisation it never states.
        self.assertIsNone(_cid('SARJANA MUDA SAINS KEMASYARAKATAN DENGAN KEPUJIAN'))
        self.assertIsNone(_cid('SARJANA MUDA SAINS KEMASYARAKATAN (EKONOMI) DENGAN KEPUJIAN'))

    def test_the_base_name_with_one_listed_option_matches(self):
        self.assertEqual(_cid('SARJANA MUDA SAINS KEMASYARAKATAN (EKONOMI) DENGAN KEPUJIAN - US6310001'),
                         'US6310001')
        self.assertEqual(_cid('SARJANA MUDA SAINS KEMASYARAKATAN DENGAN KEPUJIAN (SAINS POLITIK) - US6310001'),
                         'US6310001')

    def test_words_from_two_options_are_not_a_clean_match(self):
        self.assertIsNone(_cid('SARJANA MUDA SAINS KEMASYARAKATAN (EKONOMI DAN SAINS POLITIK) - US6310001'))
        self.assertIsNone(_cid('SARJANA MUDA SAINS KEMASYARAKATAN (EKONOMI, ANTROPOLOGI) - US6310001'))

    def test_an_option_not_in_the_list_is_not_a_clean_match(self):
        self.assertIsNone(_cid('SARJANA MUDA SAINS KEMASYARAKATAN (PSIKOLOGI) DENGAN KEPUJIAN'))
        self.assertIsNone(_cid('SARJANA MUDA SAINS KEMASYARAKATAN (PSIKOLOGI) - US6310001', ''))

    def test_a_bracket_mid_name(self):
        self.assertEqual(_cid('SARJANA MUDA SASTERA (SEJARAH) DENGAN KEPUJIAN - US6220001'), 'US6220001')
        self.assertEqual(_cid('SARJANA MUDA SASTERA DENGAN KEPUJIAN - US6220001'), 'US6220001')
        self.assertIsNone(_cid('SARJANA MUDA SASTERA DENGAN KEPUJIAN'))

    def test_the_core_name_is_still_required(self):
        self.assertIsNone(_cid('SARJANA MUDA EKONOMI DENGAN KEPUJIAN'))
        self.assertIsNone(_cid('SARJANA MUDA EKONOMI DENGAN KEPUJIAN - US6310001'))

    def test_labels_describe_reads_the_option_list(self):
        from apps.scholarship.services.offer_link import labels_describe
        self.assertTrue(labels_describe('SARJANA MUDA SAINS KEMASYARAKATAN DENGAN KEPUJIAN', SOCSCI))
        self.assertTrue(labels_describe('Sarjana Muda Sains Kemasyarakatan (Ekonomi)', SOCSCI))
        self.assertFalse(labels_describe('Sarjana Muda Sains Kemasyarakatan (Psikologi)', SOCSCI))


class _Tertiary(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_usm()
        cls.cohort = make_cohort(code='proof', name='B40', year=2026)

    def setUp(self):
        self.profile = make_student(supabase_user_id=f'proof-{self.id()}', name=NAME, nric=NRIC,
                                    exam_type='stpm', results_exam_type='stpm')
        self.app = make_application('shortlisted', cohort=self.cohort, student=self.profile,
                                    chosen_pathway='', pre_u_institution='SMK Contoh')
        self.app.chosen_programme = {}
        self.app.top_choices = []
        self.app.save()

    def offer(self, programme=LETTER_804, institution=USM, issuer=USM, status='genuine', **extra):
        fields = {'candidate_name': NAME, 'candidate_nric': NRIC, 'programme': programme,
                  'institution': institution, 'issuer': issuer, **extra}
        return ApplicantDocument.objects.create(
            application=self.app, doc_type='offer_letter', storage_path=f'{self.app.id}/offer_letter/x',
            vision_run_at=timezone.now(),
            vision_fields={'fields': fields, 'warnings': [], 'student_verdict': 'ok', 'error': '',
                           'authenticity': {'status': status, 'reason': 'x'}})

    def pathway(self):
        return next(f for f in build_verdict(self.app) if f['fact'] == 'pathway')

    def codes(self):
        return [i['code'] for i in self.pathway()['unresolved']]

    def pick(self, **cp):
        self.app.chosen_programme = cp
        self.app.chosen_pathway = 'university'
        self.app.save()


class HearingTest(_Tertiary):
    def test_804_shape_asks_nothing(self):
        # STPM, 'sure', the autofill's labels with no course id, no top choices, the letter with US6310001.
        self.app.pathway_certainty = 'sure'
        self.app.chosen_programme = {'course_name': 'SARJANA MUDA SAINS KEMASYARAKATAN DENGAN KEPUJIAN',
                                     'institution': 'UNIVERSITI SAINS MALAYSIA', 'source': 'offer_letter_auto'}
        self.app.save()
        self.offer()
        f = self.pathway()
        self.assertEqual(f['unresolved'], [])
        self.assertEqual(f['status'], 'verified')

    def test_r4_nothing_declared_and_a_clean_letter_asks_nothing(self):
        self.offer()
        self.assertEqual(self.codes(), [])

    def test_r2_her_own_pick_is_the_letters_course(self):
        self.pick(course_id='US6310001', course_name=SOCSCI, institution=USM, source='picker')
        self.offer()
        self.assertEqual(self.codes(), [])

    def test_r2_a_name_only_pick_of_the_same_course(self):
        self.pick(course_name='Sarjana Muda Sains Kemasyarakatan', institution=USM, source='picker')
        self.offer()
        self.assertEqual(self.codes(), [])

    def test_r3_her_own_pick_is_another_course(self):
        self.pick(course_id='US6220001', course_name=ARTS, institution=USM, source='picker')
        self.offer()
        self.assertEqual(self.codes(), ['pathway_confirm'])

    def test_r5_a_waiting_student_with_other_top_choices_is_not_asked(self):
        self.app.top_choices = [{'rank': 1, 'course_id': 'US6220001', 'course_name': ARTS, 'institution': USM}]
        self.app.save()
        self.offer()
        codes = self.codes()
        self.assertNotIn('pathway_confirm', codes)
        self.assertNotIn('pathway_undeclared', codes)

    def test_r6_a_letter_matching_no_one_course_asks_her_to_pick(self):
        self.offer(programme='SARJANA MUDA SAINS KEMASYARAKATAN (PSIKOLOGI) DENGAN KEPUJIAN')
        self.assertEqual(self.codes(), ['pathway_undeclared'])

    def test_r6_also_for_a_waiting_student_with_top_choices(self):
        self.app.top_choices = [{'rank': 1, 'course_id': 'US6220001', 'course_name': ARTS, 'institution': USM}]
        self.app.save()
        self.offer(programme='SARJANA MUDA PSIKOLOGI DENGAN KEPUJIAN')
        self.assertEqual(self.codes(), ['pathway_undeclared'])

    # Review 2026-11-18: "clean" is what the LINKER writes, not a loose name match. Her old pre-U school
    # makes the offer check a mismatch, so the autofill only fills an empty pick (fill_empty_pick: one
    # campus, the letter's own level, a GENUINE letter); anything it will not link asks her to pick.
    def _asks_and_stays_unlinked(self, programme, status='genuine'):
        from apps.scholarship.services.offer_sync import autofill_pathway_from_offer
        self.offer(programme=programme, status=status)
        f = self.pathway()
        codes = [i['code'] for i in f['unresolved']]       # a suspect letter adds its own red line too
        self.assertIn('pathway_undeclared', codes)
        self.assertNotIn('pathway_confirm', codes)
        self.assertNotEqual(f['status'], 'verified')
        autofill_pathway_from_offer(self.app)
        self.app.refresh_from_db()
        self.assertFalse((self.app.chosen_programme or {}).get('course_id'))

    def test_a_letter_with_no_level_word_is_not_clean(self):
        self._asks_and_stays_unlinked('SAINS KEMASYARAKATAN')

    def test_a_masters_letter_is_not_clean(self):
        self._asks_and_stays_unlinked('SARJANA SAINS KEMASYARAKATAN (EKONOMI)')

    def test_a_suspect_letter_is_not_clean_for_an_empty_pick(self):
        self._asks_and_stays_unlinked('SARJANA MUDA SAINS KEMASYARAKATAN DENGAN KEPUJIAN', status='suspect')

    def test_804_with_an_empty_pick_asks_nothing_and_is_linked(self):
        from apps.scholarship.services.offer_sync import autofill_pathway_from_offer
        self.offer()
        self.assertEqual(self.codes(), [])
        autofill_pathway_from_offer(self.app)
        self.app.refresh_from_db()
        self.assertEqual(self.app.chosen_programme.get('course_id'), 'US6310001')
        f = self.pathway()
        self.assertEqual((f['status'], f['unresolved']), ('verified', []))

    def test_an_unscored_letter_still_gets_no_hearing(self):
        self.offer(programme='SARJANA MUDA PSIKOLOGI DENGAN KEPUJIAN', status='')
        self.assertEqual(self.codes(), [])


class SpmUnchangedTest(_Tertiary):
    """SPM students keep the old Case 1 except R4/R6 (the ask follows the clean match)."""

    def setUp(self):
        super().setUp()
        self.profile.exam_type = 'spm'
        self.profile.results_exam_type = 'spm'
        self.profile.save()
        self.app.pre_u_institution = ''
        self.app.save()

    def test_pre_u_letter_keeps_the_one_tap_confirm(self):
        self.offer(programme='Tingkatan Enam (Sains Sosial)', institution='SMK Contoh', issuer='')
        self.assertEqual(self.codes(), ['pathway_confirm'])

    def test_a_declared_type_is_still_not_asked(self):
        self.app.chosen_pathway = 'university'
        self.app.save()
        self.offer(programme='SARJANA MUDA PSIKOLOGI DENGAN KEPUJIAN')
        self.assertEqual(self.codes(), [])

    def test_r4_a_clean_letter_asks_nothing(self):
        self.offer()
        self.assertEqual(self.codes(), [])

    def test_a_unique_pismp_letter_keeps_the_one_tap_confirm(self):
        # Review 2026-11-18: the PISMP one-tap confirm is checked BEFORE the clean match, so even a
        # letter the linker would link keeps it (CHANGELOG: "unique-bidang PISMP keep theirs").
        from unittest import mock
        course = {'course_id': 'PISMP-SJKT-BT', 'course_name': 'Bahasa Tamil (SJKT)', 'aliran': 'sjkt'}
        linked = ('', {'course_id': 'PISMP-SJKT-BT', 'course_name': 'Bahasa Tamil (SJKT)'}, 'pismp')
        self.offer(programme='PROGRAM IJAZAH SARJANA MUDA PERGURUAN', institution='IPG Kampus Contoh',
                   issuer='IPG Kampus Contoh', bidang_pengkhususan='Bahasa Tamil')
        with mock.patch('apps.scholarship.offer_pathway.resolve_pismp_course', return_value=course), \
                mock.patch('apps.scholarship.services.offer_link.plan_offer_link', return_value=linked):
            f = self.pathway()
        self.assertEqual([i['code'] for i in f['unresolved']], ['pathway_confirm'])
        self.assertEqual(f['unresolved'][0]['params']['course_id'], 'PISMP-SJKT-BT')

    def test_r8_no_context_line_change(self):
        from apps.scholarship.verdict_pathway import declared_degree
        self.pick(course_id='US6310001', course_name=SOCSCI, institution=USM, source='picker')
        self.assertEqual(declared_degree(self.app), '')


class NoOfferContextTest(_Tertiary):
    """R8: the no-offer line names her degree(s)."""

    def declared(self):
        items = self.pathway()['evidence']
        return [i['params']['pathway'] for i in items if i['code'] == 'pathway_declared']

    def test_her_own_pick(self):
        self.pick(course_id='US6310001', course_name=SOCSCI, institution=USM, source='picker')
        self.assertEqual(self.declared(), [f'{SOCSCI} — {USM}'])

    def test_her_top_choices(self):
        self.app.top_choices = [
            {'rank': 1, 'course_id': 'US6310001', 'course_name': 'Sains Kemasyarakatan', 'institution': USM},
            {'rank': 2, 'course_id': '', 'course_name': '', 'institution': ''},
            {'rank': 3, 'course_id': 'US6220001', 'course_name': 'Sastera', 'institution': USM}]
        self.app.save()
        self.assertEqual(self.declared(), [f'Sains Kemasyarakatan — {USM}; Sastera — {USM}'])

    def test_the_autofill_labels_are_not_her_pick(self):
        self.app.chosen_programme = {'course_name': 'X', 'institution': USM, 'source': 'offer_letter_auto'}
        self.app.chosen_pathway = 'university'
        self.app.save()
        self.assertEqual(self.declared(), ['university'])

    def test_nothing_declared_shows_nothing(self):
        self.assertEqual(self.declared(), [])


class DoorsTest(_Tertiary):
    def test_check2_sync_closes_a_stale_ask(self):
        from apps.scholarship.check2_confirms import _sync_pathway_confirm
        self.offer()
        item = ResolutionItem.objects.create(application=self.app, source='check2', code='pathway_undeclared',
                                             fact='pathway', kind='explanation', params={})
        now = timezone.now()
        _sync_pathway_confirm(self.app, {'pathway_undeclared': item}, now)
        item.refresh_from_db()
        self.assertEqual((item.status, item.resolved_by), ('resolved', 'system'))

    def test_check2_sync_raises_the_pick_ask(self):
        from apps.scholarship.check2_confirms import _sync_pathway_confirm
        self.offer(programme='SARJANA MUDA PSIKOLOGI DENGAN KEPUJIAN')
        self.assertTrue(_sync_pathway_confirm(self.app, {}, timezone.now()))
        item = ResolutionItem.objects.get(application=self.app, code='pathway_undeclared')
        self.assertEqual((item.source, item.kind, item.status), ('check2', 'explanation', 'open'))

    def test_autofill_links_the_804_course(self):
        from apps.scholarship.services.offer_sync import autofill_pathway_from_offer
        self.app.pathway_certainty = 'sure'
        self.app.chosen_programme = {'course_name': 'SARJANA MUDA SAINS KEMASYARAKATAN DENGAN KEPUJIAN',
                                     'institution': 'UNIVERSITI SAINS MALAYSIA', 'source': 'offer_letter_auto'}
        self.app.save()
        self.offer()
        autofill_pathway_from_offer(self.app)
        self.app.refresh_from_db()
        self.assertEqual(self.app.chosen_programme.get('course_id'), 'US6310001')
        self.assertEqual(self.codes(), [])

    def test_the_linker_takes_the_804_labels(self):
        from apps.scholarship.pathway_engine import student_offer_check
        from apps.scholarship.services.offer_link import plan_offer_link
        self.app.chosen_programme = {'course_name': 'SARJANA MUDA SAINS KEMASYARAKATAN DENGAN KEPUJIAN',
                                     'institution': 'UNIVERSITI SAINS MALAYSIA', 'source': 'offer_letter_auto'}
        self.app.save()
        offer = self.offer()
        reason, new_cp, _ = plan_offer_link(self.app, offer, student_offer_check(offer))
        self.assertEqual(reason, '')
        self.assertEqual(new_cp['course_id'], 'US6310001')

    def test_an_empty_pick_is_filled_from_a_clean_letter(self):
        from apps.scholarship.pathway_engine import student_offer_check
        from apps.scholarship.services.offer_link import fill_empty_pick
        offer = self.offer()
        self.assertTrue(fill_empty_pick(self.app, offer, student_offer_check(offer)))
        self.app.refresh_from_db()
        self.assertEqual(self.app.chosen_programme['course_id'], 'US6310001')
