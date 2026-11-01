"""Link an offer-sourced, labels-only pick to its catalogue course (owner, 2026-11-01, #243).

#243's record held only the letter's labels — "Sarjana Muda Seni Halus (Kepujian)" at "KOLEJ SEROJA,
UNIVERSITI TEKNOLOGI MARA", ``source=offer_letter_confirmed``, no ``course_id`` — because she
confirmed before the matcher could read a degree. The cockpit showed no course link and a hostel line
as her institution. Every rule of ``services.offer_link.plan_offer_link`` has its test here, the
forward path (a NEW confirm, a NEW autofill) included.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import FieldTaxonomy, Institution, StpmCourse, StpmRequirement
from apps.scholarship.models import InterviewSession
from apps.scholarship.pathway_engine import student_offer_check
from apps.scholarship.services import autofill_pathway_from_offer
from apps.scholarship.services.confirmation import confirm_pathway
from apps.scholarship.services.offer_link import link_offer_course, plan_offer_link
from apps.scholarship.tests.factories import TEST_JWT_SECRET, make_application, make_student
from apps.scholarship.tests.test_offer_course_match import seed_realign_catalogue
from apps.scholarship.tests.test_offer_realign import _offer

#: #243's own strings.
SENI_HALUS = ('Sarjana Muda Seni Halus (Kepujian)', 'KOLEJ SEROJA, UNIVERSITI TEKNOLOGI MARA',
              'UNIVERSITI TEKNOLOGI MARA')
LABELS = {'course_name': 'Sarjana Muda Seni Halus (Kepujian)',
          'institution': 'KOLEJ SEROJA, UNIVERSITI TEKNOLOGI MARA', 'source': 'offer_letter_confirmed'}


def _plan(app, offer):
    return plan_offer_link(app, offer, student_offer_check(offer))


@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_realign_catalogue()
        uitm = Institution.objects.get(institution_id='RA-UITM')
        sc = StpmCourse.objects.create(course_id='UE6211001', course_name='Sarjana Muda Seni Halus (Kepujian) #',
                                       university='Universiti Teknologi MARA', institution=uitm,
                                       field_key=FieldTaxonomy.objects.get(key='realign'))
        StpmRequirement.objects.create(course=sc, req_bumiputera=True)

    def _app(self, stage='profile_complete', pathway='degree', pick=None, **over):
        return make_application(stage, chosen_pathway=pathway,
                                chosen_programme=dict(LABELS if pick is None else pick), **over)


class Link243Test(_Base):
    def test_243_is_linked_to_the_uitm_degree_and_keeps_its_source(self):
        app = self._app()
        offer = _offer(app, SENI_HALUS)
        with self.assertLogs('apps.scholarship.services', level='INFO') as logs:
            self.assertTrue(link_offer_course(app, offer, student_offer_check(offer)))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme, {
            'course_id': 'UE6211001', 'course_name': 'Sarjana Muda Seni Halus (Kepujian) #',
            'institution': 'Universiti Teknologi MARA', 'source': 'offer_letter_confirmed'})
        self.assertEqual(app.chosen_pathway, 'university')     # 'degree' is no picker value
        self.assertTrue(any(f'AUDIT offer_course_link app_id={app.id} course_id=UE6211001' in line
                            for line in logs.output))
        self.assertEqual(_plan(app, offer)[0], 'has_course_id')   # idempotent

    def test_an_institution_id_follows_the_new_campus(self):
        app = self._app(pick={**LABELS, 'institution_id': 'SOMEWHERE'})
        offer = _offer(app, SENI_HALUS)
        link_offer_course(app, offer, student_offer_check(offer))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution_id'], 'RA-UITM')

    def test_a_picker_pathway_is_kept(self):
        # A CONFIRMED pick (round-3 review: an automatic one the realignment would also take gets the
        # realignment's pathway — see OrderIndependenceTest).
        app = self._app(pathway='poly')
        offer = _offer(app, SENI_HALUS)
        self.assertEqual(_plan(app, offer)[2], '')
        link_offer_course(app, offer, student_offer_check(offer))
        app.refresh_from_db()
        self.assertEqual((app.chosen_pathway, app.chosen_programme['course_id']), ('poly', 'UE6211001'))
        self.assertEqual(app.chosen_programme['source'], 'offer_letter_confirmed')

    def test_a_suspect_or_unscored_letter_links_a_fake_never(self):
        for status, reason in (('suspect', ''), ('', ''), ('not_offer_letter', 'not_offer_letter')):
            with self.subTest(status=status):
                app = self._app()
                self.assertEqual(_plan(app, _offer(app, SENI_HALUS, status=status))[0], reason)

    def test_the_profile_follows(self):
        student = make_student(chosen_pathway='degree', chosen_programme=dict(LABELS))
        app = self._app(student=student)
        offer = _offer(app, SENI_HALUS)
        link_offer_course(app, offer, student_offer_check(offer))
        student.refresh_from_db()
        self.assertEqual((student.chosen_programme['course_id'], student.chosen_pathway),
                         ('UE6211001', 'university'))


class SkipTest(_Base):
    def _skip(self, app, offer, reason):
        before = dict(app.chosen_programme)
        self.assertEqual(_plan(app, offer)[0], reason)
        self.assertFalse(link_offer_course(app, offer, student_offer_check(offer)))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme, before)

    def test_picks_that_are_not_the_letters_reading_are_never_touched(self):
        for source in ('', 'repair_chosen_programme', 'officer_interview'):
            with self.subTest(source=source):
                app = self._app(pick={**LABELS, 'source': source})
                self._skip(app, _offer(app, SENI_HALUS), 'not_offer_sourced')

    def test_a_linked_pick(self):
        app = self._app(pick={**LABELS, 'course_id': 'UM6343002'})
        self._skip(app, _offer(app, SENI_HALUS), 'has_course_id')

    def test_labels_from_another_letter(self):
        app = self._app(pick={**LABELS, 'course_name': 'Sarjana Muda Perakaunan (Kepujian)'})
        self._skip(app, _offer(app, SENI_HALUS), 'labels_disagree')
        # Labels that name NO course are an empty pick since 2026-11-01 (owner: the letter's course is
        # a fact to record) — filled, keeping its source; this used to skip as `no_course_name`.
        app = self._app(pick={**LABELS, 'course_name': ''})
        offer = _offer(app, SENI_HALUS)
        self.assertEqual(_plan(app, offer)[1]['source'], 'offer_letter_confirmed')

    def test_decided_and_the_open_interview_ruling(self):
        app = self._app(stage='interviewing')
        InterviewSession.objects.create(application=app, status='submitted')
        self._skip(app, _offer(app, SENI_HALUS), 'decided')
        app = self._app(verdict_decided_at=timezone.now())
        self._skip(app, _offer(app, SENI_HALUS), 'decided')
        # Interviewing with NO submitted interview is still open (owner ruling, 2026-10-31).
        app = self._app(stage='interviewing')
        self.assertEqual(_plan(app, _offer(app, SENI_HALUS))[0], '')

    def test_another_persons_letter_and_a_pre_u_pathway(self):
        app = self._app()
        self._skip(app, _offer(app, SENI_HALUS, nric='990101-01-9999'), 'not_own_letter')
        app = self._app(pathway='stpm')
        self._skip(app, _offer(app, SENI_HALUS), 'pre_u')

    def test_a_campus_the_letter_cannot_pin(self):
        app = self._app(pick={**LABELS, 'course_name': 'Diploma Pelancongan'})
        self._skip(app, _offer(app, ('DIPLOMA PELANCONGAN', 'KOLEJ KOMUNITI ARAU DAN KOLEJ KOMUNITI KANGAR', '')),
                   'unresolved')


class ForwardPathTest(_Base):
    def test_a_new_confirm_of_a_labels_only_pick_pins_the_course(self):
        app = self._app(pathway='university', pick={'course_name': 'Seni Halus', 'source': ''})
        _offer(app, SENI_HALUS)
        self.assertTrue(confirm_pathway(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_id'], 'UE6211001')
        self.assertEqual(app.chosen_programme['institution'], 'Universiti Teknologi MARA')
        self.assertEqual(app.chosen_programme['source'], 'offer_letter_confirmed')

    def test_a_new_autofill_of_a_degree_letter_pins_the_course(self):
        app = self._app(pathway='', pick={}, pathway_certainty='uncertain')
        _offer(app, ('SARJANA MUDA PENGURUSAN MUAMALAT', 'Universiti Malaya', 'Universiti Malaya'))
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_id'], 'UM6343002')


class CommandTest(_Base):
    def test_report_then_apply_then_idempotent(self):
        app = self._app()
        _offer(app, SENI_HALUS)
        student_pick = self._app(pick={'course_id': 'UM6343002', 'course_name': 'x'})
        _offer(student_pick, SENI_HALUS)
        out = StringIO()
        call_command('link_offer_courses', stdout=out)
        text = out.getvalue()
        self.assertIn(f'#{app.id} [profile_complete] (offer_letter_confirmed) LINK (would): -', text)
        self.assertIn('->  UE6211001 | Sarjana Muda Seni Halus (Kepujian) # | Universiti Teknologi MARA', text)
        self.assertIn(f'PATHWAY CHANGES (1):\n  #{app.id}: degree -> university', text)
        self.assertNotIn(f'#{student_pick.id} ', text)          # a student's own pick is not listed
        app.refresh_from_db()
        self.assertNotIn('course_id', app.chosen_programme)
        call_command('link_offer_courses', '--apply', stdout=StringIO())
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_id'], 'UE6211001')
        out = StringIO()
        call_command('link_offer_courses', '--apply', stdout=out)
        self.assertIn(f'#{app.id} [profile_complete] (offer_letter_confirmed) SKIP has_course_id', out.getvalue())


class Round3LinkTest(_Base):
    """Round-3 review (2026-11-01): the link checks the PLACE, and its outcome does not depend on
    whether the realignment ran first."""

    def test_a_label_naming_another_place_is_not_linked(self):
        app = self._app(pick={**LABELS, 'institution': 'UNIVERSITI MALAYA'})
        offer = _offer(app, SENI_HALUS, status='suspect')
        self.assertEqual(_plan(app, offer)[0], 'place_disagrees')
        app = self._app(pick={**LABELS, 'institution': ''})
        self.assertEqual(_plan(app, _offer(app, SENI_HALUS))[0], 'place_disagrees')

    def _both_apply(self):
        # An automatic labels-only pick (not settled) and a genuine Bumi-only letter: both the link and
        # the realignment take it.
        return self._app(pathway='poly', pathway_certainty='uncertain',
                         pick={**LABELS, 'source': 'offer_letter_auto'})

    def _row(self, app):
        app.refresh_from_db()
        return app.chosen_programme, app.chosen_pathway, app.pathway_certainty

    def test_link_then_realign_equals_realign_then_link(self):
        from apps.scholarship.services.offer_sync import realign_bumi_only_pick
        a, b = self._both_apply(), self._both_apply()
        oa, ob = _offer(a, SENI_HALUS), _offer(b, SENI_HALUS)
        link_offer_course(a, oa, student_offer_check(oa))
        realign_bumi_only_pick(a, oa, student_offer_check(oa))
        realign_bumi_only_pick(b, ob, student_offer_check(ob))
        link_offer_course(b, ob, student_offer_check(ob))
        self.assertEqual(self._row(a), self._row(b))
        self.assertEqual(self._row(a)[1:], ('university', 'sure'))

    def test_the_link_command_runs_the_realignment_first(self):
        app = self._both_apply()
        _offer(app, SENI_HALUS)
        out = StringIO()
        call_command('link_offer_courses', stdout=out)
        self.assertIn(f'#{app.id} [profile_complete] (offer_letter_auto) REALIGN-FIRST bumi_only (would)',
                      out.getvalue())
