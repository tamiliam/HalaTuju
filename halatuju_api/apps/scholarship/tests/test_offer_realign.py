"""Offer realignment, Parts B–D (2026-10-31): the issuer fills a hostel-line institution, and a
genuine Bumiputera-only offer replaces a pick the student made before those courses were shown.

Owner: *"we may realign the course and institutions based on the offer letter, and not treat the
previous selection as real selection. This should apply to all courses that are open only to
bumiputra."* The rule is a MONEY door (the pathway feeds the payment calendar and the funding
estimate), so every skip has its own test, and the writes are pinned field by field.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import check2_queries
from apps.scholarship.family import copy_pathway
from apps.scholarship.models import ApplicantDocument, ResolutionItem
from apps.scholarship.pathway_engine import student_offer_check
from apps.scholarship.services import autofill_pathway_from_offer, sync_institution_from_catalogue
from apps.scholarship.services.offer_sync import plan_bumi_realign, realign_bumi_only_pick
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_application, make_student)
from apps.scholarship.tests.test_offer_course_match import seed_realign_catalogue

UITM_LETTER = ('BA272 SARJANA MUDA PERNIAGAAN KEWANGAN (KEPUJIAN)',
               'UiTM CAWANGAN SABAH, KAMPUS KOTA KINABALU', 'UNIVERSITI TEKNOLOGI MARA')
UM_PICK = {'course_id': 'UM6343002', 'course_name': 'Sarjana Muda Pengurusan Muamalat',
           'institution': 'Universiti Malaya', 'institution_id': 'RA-UM'}
UITM_COURSE = {'course_id': 'UE6343001', 'course_name': 'Sarjana Muda Perniagaan Kewangan (Kepujian)',
               'institution': 'Universiti Teknologi MARA', 'source': 'offer_letter_auto'}


def _offer(app, letter, *, status='genuine', nric=None):
    programme, institution, issuer = letter
    prof = app.profile
    return ApplicantDocument.objects.create(
        application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/x',
        vision_fields={'fields': {
            'candidate_name': prof.name, 'candidate_nric': (nric or prof.nric).replace('-', ''),
            'programme': programme, 'institution': institution, 'issuer': issuer},
            'authenticity': {'status': status}, 'student_verdict': 'ok', 'warnings': [], 'error': ''},
        vision_run_at=timezone.now())


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_realign_catalogue()

    def _app(self, stage='profile_complete', pathway='university', pick=None, **over):
        over.setdefault('pathway_certainty', 'sure')
        return make_application(stage, chosen_pathway=pathway,
                                chosen_programme=dict(UM_PICK if pick is None else pick), **over)


class RealignTest(_Base):
    def test_a_locked_student_pick_gives_way_to_a_genuine_bumi_only_offer(self):
        app = self._app()
        offer = _offer(app, UITM_LETTER)
        self.assertEqual(student_offer_check(offer)['pathway'], 'mismatch')   # the clash it settles
        with self.assertLogs('apps.scholarship.services', level='INFO') as logs:
            self.assertTrue(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme, {**UITM_COURSE, 'institution_id': 'RA-UITM'})
        self.assertEqual(app.chosen_pathway, 'university')
        self.assertEqual(app.pathway_certainty, 'sure')
        self.assertTrue(any(f'AUDIT bumi_offer_realign app_id={app.id} old_course_id=UM6343002 '
                            f'new_course_id=UE6343001' in line for line in logs.output))
        self.assertEqual(student_offer_check(offer)['pathway'], 'match')
        # Idempotent: the written pick is now a settled source.
        self.assertEqual(plan_bumi_realign(app, offer, student_offer_check(offer))[0], 'same_course')

    def test_a_pick_without_an_institution_id_gains_none(self):
        app = self._app(pick={'course_id': 'UM6343002', 'course_name': 'Sarjana Muda Pengurusan Muamalat'})
        offer = _offer(app, UITM_LETTER)
        self.assertTrue(realign_bumi_only_pick(app, offer, student_offer_check(offer)))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme, UITM_COURSE)

    def test_a_poly_pick_moves_to_the_courses_own_pathway(self):
        # The payment calendar keys on chosen_pathway: a UiTM degree must not keep `poly`'s.
        app = self._app(pathway='poly', pick={'course_id': 'RA-POLY-DPM',
                                              'course_name': 'Diploma Pengurusan Muamalat'})
        offer = _offer(app, ('SARJANA MUDA PERAKAUNAN (KEPUJIAN)', 'UiTM KAMPUS SEGAMAT',
                             'Bahagian Pengambilan Pelajar'))
        self.assertTrue(realign_bumi_only_pick(app, offer, student_offer_check(offer)))
        app.refresh_from_db()
        self.assertEqual((app.chosen_pathway, app.chosen_programme['course_id']), ('university', 'UE6314001'))

    def test_an_asasi_offer_sets_asasi(self):
        app = self._app(pathway='university')
        offer = _offer(app, ('Asasi Sains', 'Pusat Persediaan Sains dan Teknologi', 'Universiti Malaysia Sabah'))
        self.assertTrue(realign_bumi_only_pick(app, offer, student_offer_check(offer)))
        app.refresh_from_db()
        self.assertEqual((app.chosen_pathway, app.chosen_programme['course_id']), ('asasi', 'UH0010001'))

    def test_labels_left_by_an_earlier_unresolved_offer_are_not_a_settled_pick(self):
        app = self._app(pathway='', pick={'course_name': 'SARJANA MUDA PERNIAGAAN KEWANGAN',
                                          'institution': 'UiTM', 'source': 'offer_letter_auto'})
        offer = _offer(app, UITM_LETTER)
        self.assertTrue(realign_bumi_only_pick(app, offer, student_offer_check(offer)))


class SkipTest(_Base):
    def _assert_skip(self, app, offer, reason):
        before = (app.chosen_programme, app.chosen_pathway)
        self.assertEqual(plan_bumi_realign(app, offer, student_offer_check(offer))[0], reason)
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme.get('course_id'), before[0].get('course_id'))
        self.assertEqual(app.chosen_pathway, before[1])

    def test_confirmed_sources_are_kept(self):
        for source in ('offer_letter_confirmed', 'repair_chosen_programme', 'officer_interview',
                       'offer_letter_auto'):
            with self.subTest(source=source):
                app = self._app(pick={**UM_PICK, 'source': source})
                self._assert_skip(app, _offer(app, UITM_LETTER), 'confirmed_source')

    def test_a_letter_not_scored_genuine(self):
        for status in ('suspect', 'not_offer_letter', ''):
            with self.subTest(status=status):
                app = self._app()
                self._assert_skip(app, _offer(app, UITM_LETTER, status=status), 'not_genuine')

    def test_another_persons_letter(self):
        app = self._app()
        self._assert_skip(app, _offer(app, UITM_LETTER, nric='990101-01-9999'), 'not_own_letter')

    def test_a_course_open_to_all(self):
        app = self._app(pick={'course_id': 'UE6343002', 'course_name': 'x', 'institution': 'Universiti Teknologi MARA'})
        self._assert_skip(app, _offer(app, ('SARJANA MUDA PENGURUSAN MUAMALAT', 'Universiti Malaya',
                                            'Universiti Malaya')), 'not_bumi_only')

    def test_a_pre_u_pathway_is_for_a_human(self):
        app = self._app(pathway='stpm')
        self._assert_skip(app, _offer(app, UITM_LETTER), 'pre_u')

    def test_an_unresolved_letter(self):
        app = self._app()
        self._assert_skip(app, _offer(app, ('SARJANA MUDA SESUATU', 'Kolej Entah', 'Entah')), 'unresolved')

    def test_decided_applications(self):
        app = make_application('recommended', chosen_pathway='university', chosen_programme=dict(UM_PICK))
        self._assert_skip(app, _offer(app, UITM_LETTER), 'decided')
        app = self._app(status='interviewed')
        self._assert_skip(app, _offer(app, UITM_LETTER), 'decided')
        app = self._app(stage='interviewing', officer_verdict={'overall': 'accept'})
        self._assert_skip(app, _offer(app, UITM_LETTER), 'decided')


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class ProfileAndQueryTest(_Base):
    def test_the_profile_follows_and_a_profile_save_keeps_the_offers_course(self):
        student = make_student(chosen_pathway='poly', chosen_programme={
            'course_id': 'RA-POLY-DPM', 'course_name': 'Diploma Pengurusan Muamalat'})
        app = self._app(student=student, pathway='poly',
                        pick={'course_id': 'RA-POLY-DPM', 'course_name': 'Diploma Pengurusan Muamalat'})
        offer = _offer(app, UITM_LETTER)
        self.assertTrue(realign_bumi_only_pick(app, offer, student_offer_check(offer)))
        student.refresh_from_db()
        self.assertEqual(student.chosen_programme['course_id'], 'UE6343001')
        self.assertEqual(student.chosen_pathway, 'university')
        # A /profile save through the real endpoint (copy_pathway) leaves the realigned pick.
        r = authed_client(student).put('/api/v1/profile/', {'pre_u_track': ''}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual((app.chosen_programme['course_id'], app.chosen_pathway), ('UE6343001', 'university'))

    def test_copy_pathway_never_lets_a_student_pick_overwrite_the_realigned_one(self):
        app = self._app()
        offer = _offer(app, UITM_LETTER)
        realign_bumi_only_pick(app, offer, student_offer_check(offer))
        stale_profile = make_student(chosen_programme=dict(UM_PICK))
        copy_pathway(stale_profile, app)
        self.assertEqual(app.chosen_programme['course_id'], 'UE6343001')

    def test_an_open_pathway_confirm_query_is_closed_by_the_next_sync(self):
        app = self._app()
        offer = _offer(app, UITM_LETTER)
        item = ResolutionItem.objects.create(application=app, source='check2', code='pathway_confirm',
                                             fact='pathway', kind='confirm', params={})
        realign_bumi_only_pick(app, offer, student_offer_check(offer))
        check2_queries._sync_pathway_confirm(app, {'pathway_confirm': item}, timezone.now())
        item.refresh_from_db()
        self.assertEqual((item.status, item.resolved_by), ('resolved', 'system'))


class HostelInstitutionFillTest(_Base):
    """Part B on the writer: #175's shape fills, a polytechnic line against a university course does
    not (the #11 / #64 private-or-other-place guard)."""

    def _picked(self):
        return self._app(pathway='university', pick={'course_id': 'UP4310001',
                                                     'course_name': 'Diploma Pembangunan Manusia'})

    def test_the_175_shape_fills_from_the_issuer(self):
        app = self._picked()
        _offer(app, ('DIPLOMA PEMBANGUNAN MANUSIA', 'KOLEJ SRI RAJANG', 'Universiti Putra Malaysia'))
        self.assertTrue(sync_institution_from_catalogue(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'], 'Universiti Putra Malaysia')

    def test_a_polytechnic_line_against_a_university_course_does_not_fill(self):
        app = self._picked()
        _offer(app, ('DIPLOMA PEMBANGUNAN MANUSIA', 'Politeknik Ungku Omar', 'Universiti Putra Malaysia'))
        self.assertFalse(sync_institution_from_catalogue(app))
        app.refresh_from_db()
        self.assertNotIn('institution', app.chosen_programme)


class RepairCommandTest(_Base):
    def test_report_then_apply_then_idempotent(self):
        app = self._app()
        _offer(app, UITM_LETTER)
        other = self._app(pick={**UM_PICK, 'source': 'offer_letter_confirmed'})
        _offer(other, UITM_LETTER)

        out = StringIO()
        call_command('realign_bumi_offers', stdout=out)
        text = out.getvalue()
        self.assertIn(f'#{app.id} [profile_complete] REALIGN (would): UM6343002', text)
        self.assertIn('->  UE6343001 | Sarjana Muda Perniagaan Kewangan (Kepujian) | Universiti Teknologi MARA', text)
        self.assertIn(f'#{other.id} [profile_complete] SKIP confirmed_source', text)
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_id'], 'UM6343002')     # report only

        call_command('realign_bumi_offers', '--apply', stdout=StringIO())
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_id'], 'UE6343001')

        out = StringIO()
        call_command('realign_bumi_offers', '--apply', stdout=out)
        self.assertIn(f'#{app.id} [profile_complete] SKIP same_course', out.getvalue())

    def test_the_report_names_an_institution_fill_without_writing_it(self):
        app = self._app(pick={'course_id': 'UP4310001', 'course_name': 'Diploma Pembangunan Manusia'})
        _offer(app, ('DIPLOMA PEMBANGUNAN MANUSIA', 'KOLEJ SRI RAJANG', 'Universiti Putra Malaysia'))
        out = StringIO()
        call_command('realign_bumi_offers', stdout=out)
        self.assertIn('institution would fill: Universiti Putra Malaysia', out.getvalue())
        app.refresh_from_db()
        self.assertNotIn('institution', app.chosen_programme)
        call_command('realign_bumi_offers', '--apply', stdout=StringIO())
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'], 'Universiti Putra Malaysia')



class ReviewFindingsRealignTest(_Base):
    """The adversarial review of 851b7cb9 (2026-10-31) — the writer's side of each finding."""

    def test_1_a_correct_uitm_pick_survives_a_uitm_letter(self):
        pick = {'course_id': 'UE4481001', 'course_name': 'Diploma Sains Komputer'}
        app = self._app(pick=pick)
        offer = _offer(app, ('DIPLOMA IN COMPUTER SCIENCE', 'UNIVERSITI TEKNOLOGI MARA', 'UNIVERSITI TEKNOLOGI MARA'))
        self.assertEqual(plan_bumi_realign(app, offer, student_offer_check(offer))[0], 'unresolved')
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_id'], 'UE4481001')

    def test_2_a_utm_pick_survives_a_utm_letter(self):
        app = self._app(pick={'course_id': 'UT6481003', 'course_name': 'Sarjana Muda Sains Komputer dengan Kepujian'})
        offer = _offer(app, ('SARJANA MUDA SAINS KOMPUTER DENGAN KEPUJIAN', 'UNIVERSITI TEKNOLOGI MALAYSIA',
                             'UNIVERSITI TEKNOLOGI MALAYSIA'))
        self.assertEqual(plan_bumi_realign(app, offer, student_offer_check(offer))[0], 'same_course')
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_id'], 'UT6481003')

    def test_3_a_campus_the_letter_cannot_pin_is_never_written(self):
        app = self._app()
        offer = _offer(app, ('DIPLOMA PELANCONGAN', 'KOMUNITI ARAU KANGAR', ''))   # names both campuses
        self.assertEqual(plan_bumi_realign(app, offer, student_offer_check(offer))[0], 'campus_unpinned')
        app2 = self._app()
        offer2 = _offer(app2, ('DIPLOMA TEKNOLOGI KEJURUTERAAN MEKANIKAL', 'IKM BESERI', ''))
        self.assertNotEqual(plan_bumi_realign(app2, offer2, student_offer_check(offer2))[0], '')

    def test_4_a_contradicting_code_never_realigns(self):
        app = self._app()
        offer = _offer(app, ('Sarjana Muda Ukur Bahan dengan Kepujian - UW6526002', 'Universiti Malaysia Sarawak', ''))
        self.assertEqual(plan_bumi_realign(app, offer, student_offer_check(offer))[0], 'unresolved')

    def test_5_a_state_word_never_realigns_to_that_states_university(self):
        app = self._app(pick={'course_id': 'UE6481001', 'course_name': 'Sarjana Muda Sains Komputer (Kepujian)'})
        offer = _offer(app, ('SARJANA MUDA KEJURUTERAAN KOMPUTER', 'UiTM CAWANGAN PERLIS, KAMPUS ARAU',
                             'Bahagian Pengambilan Pelajar'))
        self.assertEqual(plan_bumi_realign(app, offer, student_offer_check(offer))[0], 'unresolved')

    def test_6_the_offer_confirm_reads_the_issuer_too(self):
        from apps.courses.models import Course, CourseInstitution, Institution
        from apps.scholarship.services.confirmation import _settle_stale_course_id
        letter = ('DIPLOMA PEMBANGUNAN MANUSIA', 'KOLEJ SRI RAJANG', 'Universiti Putra Malaysia')
        # A correct pick with the hostel line on file is kept.
        app = self._app(pick={'course_id': 'UP4310001', 'course_name': 'Diploma Pembangunan Manusia',
                              'institution': 'KOLEJ SRI RAJANG'})
        offer = _offer(app, letter)
        _settle_stale_course_id(app, offer, letter[0], 'diploma')
        self.assertEqual(app.chosen_programme['course_id'], 'UP4310001')
        # A stale pick at the same university is re-pinned to the letter's course — which needs the
        # issuer: without it the hostel line resolves nothing and the stale id was kept.
        c = Course.objects.create(course_id='RA-UPM-DIP2', course='Diploma Pertanian', level='Diploma',
                                  department='x', field='x', field_key_id='realign')
        CourseInstitution.objects.create(course=c, institution=Institution.objects.get(institution_id='RA-UPM'))
        app = self._app(pick={'course_id': 'RA-UPM-DIP2', 'course_name': 'Diploma Pertanian',
                              'institution': 'KOLEJ SRI RAJANG'})
        offer = _offer(app, letter)
        _settle_stale_course_id(app, offer, letter[0], 'diploma')
        self.assertEqual(app.chosen_programme['course_id'], 'UP4310001')

    def test_8_decided_reads_querying_locked_and_the_verdict_stamp(self):
        from apps.scholarship.models import InterviewSession
        app = self._app(stage='interviewing')
        InterviewSession.objects.create(application=app, status='submitted')
        offer = _offer(app, UITM_LETTER)
        self.assertEqual(plan_bumi_realign(app, offer, student_offer_check(offer))[0], 'decided')
        app = self._app(verdict_decided_at=timezone.now())
        offer = _offer(app, UITM_LETTER)
        self.assertEqual(plan_bumi_realign(app, offer, student_offer_check(offer))[0], 'decided')

    def test_10_the_backfill_dry_run_plans_on_the_live_offer(self):
        app = self._app()
        _offer(app, UITM_LETTER)                                       # live, Bumi-only
        newer = _offer(app, UITM_LETTER, nric='990101-01-9999')       # someone else's letter…
        newer.superseded_at = timezone.now()                          # …newest, but replaced
        newer.save(update_fields=['superseded_at'])
        out = StringIO()
        call_command('backfill_offer_pathways', stdout=out)
        self.assertIn(f'app #{app.id}: would settle', out.getvalue())

    def test_11_the_report_never_runs_a_writer(self):
        from unittest import mock
        app = self._app(pick={'course_id': 'UP4310001', 'course_name': 'Diploma Pembangunan Manusia'})
        _offer(app, ('DIPLOMA PEMBANGUNAN MANUSIA', 'KOLEJ SRI RAJANG', 'Universiti Putra Malaysia'))
        target = 'apps.scholarship.management.commands.realign_bumi_offers'
        with mock.patch(f'{target}.sync_institution_from_catalogue', side_effect=AssertionError('writer ran')), \
                mock.patch(f'{target}.realign_bumi_only_pick', side_effect=AssertionError('writer ran')):
            out = StringIO()
            call_command('realign_bumi_offers', stdout=out)
        self.assertIn('institution would fill: Universiti Putra Malaysia', out.getvalue())


class ConfirmStoresTheCampusNotTheHostelTest(_Base):
    """Round-2 review (2026-10-31): the offer confirm stored the raw line, so a hostel became the
    sponsor-facing institution and the blank-only fill never corrected it."""

    def test_confirm_with_a_hostel_line_stores_the_catalogue_campus(self):
        from apps.scholarship.services.confirmation import confirm_pathway
        app = self._app(pick={'course_id': 'UP4310001', 'course_name': 'Diploma Pembangunan Manusia'})
        offer = _offer(app, ('DIPLOMA PEMBANGUNAN MANUSIA', 'KOLEJ SRI RAJANG', 'Universiti Putra Malaysia'))
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'], 'Universiti Putra Malaysia')
        self.assertEqual(app.chosen_programme['course_id'], 'UP4310001')
        self.assertEqual(student_offer_check(offer)['pathway'], 'match')

    def test_a_line_naming_the_campus_is_stored_as_before(self):
        from apps.scholarship.services.confirmation import confirm_pathway
        app = self._app(pick={'course_id': 'UP4310001', 'course_name': 'Diploma Pembangunan Manusia'})
        _offer(app, ('DIPLOMA PEMBANGUNAN MANUSIA', 'Universiti Putra Malaysia', 'Universiti Putra Malaysia'))
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'], 'Universiti Putra Malaysia')
