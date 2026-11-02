"""Every reader of an offer letter's fields, fed the S4 reader's shape (offer exact-read S4, 2026-11-01).

S4 changes what `fields` CARRY: `institution` is the institution's name only, the campus is the new
`campus`, a hostel / venue goes to `reporting_venue`, a printed code leaves `programme` for
`programme_code`, a commencement date is no longer a reporting date, and the IC may come from the
reference line. The door list is in the roadmap's S4 section. Two kinds of test here:

* **Name / IC must not get worse** — one test per door that reads `name` / `ic` (all of them read the
  statuses `student_offer_check` builds, plus the extraction verdict `doc_student_verdict`).
* **What the new shape does to the matcher's doors.** The campus is rejoined for every reader by the
  matcher session's `offer_course_match.letter_institution` (live on main d08283f1), read inside
  `student_offer_check`; these tests show the pins survive through it. The printed-code tier
  is rejoined the same way by `programme_line` (main cddb4661).

Synthetic twins only (`test_no_gitignored_corpus.py`): invented people, and invented campuses
("Institut Qorvane ...") beside the shared realignment catalogue.
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import Course, CourseInstitution, CourseRequirement, FieldTaxonomy, Institution
from apps.scholarship import offer_pathway as op
from apps.scholarship import vision
from apps.scholarship.doc_red_keys import person_red
from apps.scholarship.models import ApplicantDocument
from apps.scholarship.offer_course_match import (
    letter_institution, letter_place, match_offer_course, pinned_match, programme_line)
from apps.scholarship.offer_reader import clean_offer_fields
from apps.scholarship.pathway_engine import offer_reporting_date_unknown, student_offer_check
from apps.scholarship.services.offer_sync import institution_fill
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.test_offer_course_match import BPP, UPM, seed_realign_catalogue

#: A course taught at TWO campuses of one invented institute — the shape of IPG / KKTM / a
#: multi-campus university diploma, where the catalogue holds one row per campus.
MULTI = 'RA-QV-DIP'
NORTH, SOUTH = 'Institut Qorvane Kampus Utara', 'Institut Qorvane Kampus Selatan'


def seed_multi_campus():
    ft, _ = FieldTaxonomy.objects.get_or_create(key='realign', defaults={
        'name_en': 'x', 'name_ms': 'x', 'name_ta': 'x', 'image_slug': 'realign'})
    c, _ = Course.objects.get_or_create(course_id=MULTI, defaults={
        'course': 'Diploma Zantharion Gunaan', 'level': 'Diploma', 'department': 'x', 'field': 'x',
        'field_key': ft})
    CourseRequirement.objects.get_or_create(course=c, defaults={'source_type': 'ua', 'req_bumiputera': False})
    for iid, name in (('RA-QV-N', NORTH), ('RA-QV-S', SOUTH)):
        inst, _ = Institution.objects.get_or_create(institution_id=iid, defaults={
            'institution_name': name, 'acronym': '', 'type': 'IPTA', 'state': 'Selangor'})
        CourseInstitution.objects.get_or_create(course=c, institution=inst)


def _offer(app, **fields):
    prof = app.profile
    base = {'candidate_name': prof.name, 'candidate_nric': prof.nric.replace('-', '')}
    return ApplicantDocument.objects.create(
        application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/x',
        vision_fields={'fields': {**base, **fields}, 'authenticity': {'status': 'genuine'},
                       'student_verdict': 'ok', 'warnings': [], 'error': '', 'offer_reader_version': '2.0.0'},
        vision_run_at=timezone.now())


class NameAndIcDoNotGetWorseTest(TestCase):
    """Doors: `student_offer_check` (read by the verdict, the ladder, the gate's `person_red`, the
    Action Centre's `resolution`, Cikgu Gopal's `help_engine`, `offer_sync`, `offer_link`, the
    confirm and the backfills — all through the `name` / `ic` statuses) and `doc_student_verdict`."""

    def setUp(self):
        self.app = make_application('submitted')

    def _chk(self, **fields):
        return student_offer_check(_offer(self.app, institution='UNIVERSITI QORVANE', campus='KAMPUS PERLAK',
                                          reporting_venue='KOLEJ KEDIAMAN ZORBEX', **fields))

    def test_the_new_shape_reads_the_same_name_and_ic(self):
        chk = self._chk()
        self.assertEqual((chk['name'], chk['ic']), ('match', 'match'))
        self.assertFalse(person_red('offer_letter', chk))
        # The matcher session's live join (`letter_institution`, main d08283f1): one line again.
        self.assertEqual(chk['institution'], 'UNIVERSITI QORVANE KAMPUS PERLAK')

    def test_an_ic_read_off_the_reference_line_matches(self):
        ref_line_read = clean_offer_fields({'candidate_nric': self.app.profile.nric.replace('-', '')})
        chk = self._chk(candidate_nric=ref_line_read['candidate_nric'])
        self.assertEqual(chk['ic'], 'match')

    def test_no_ic_printed_is_unread_never_a_wrong_person(self):
        chk = self._chk(candidate_nric='')
        self.assertEqual(chk['ic'], 'unreadable')
        self.assertFalse(person_red('offer_letter', chk))

    def test_a_reference_number_read_as_the_ic_is_blanked_not_red(self):
        before = self._chk(candidate_nric='UPM/BPA/S/3-1')            # what an unguarded read would store
        self.assertEqual(before['ic'], 'mismatch')
        after = self._chk(candidate_nric=clean_offer_fields({'candidate_nric': 'UPM/BPA/S/3-1'})['candidate_nric'])
        self.assertEqual(after['ic'], 'unreadable')

    def test_another_persons_ic_is_still_a_wrong_person(self):
        chk = self._chk(candidate_nric='991231-01-0001')
        self.assertEqual(chk['ic'], 'mismatch')
        self.assertTrue(person_red('offer_letter', chk))

    def test_the_extraction_verdict_reads_the_name_as_before(self):
        name = self.app.profile.name
        fields = {'candidate_name': name, 'institution': 'UNIVERSITI QORVANE', 'campus': 'KAMPUS PERLAK'}
        self.assertEqual(vision.doc_student_verdict('offer_letter', fields, names=[name]), 'ok')
        self.assertEqual(vision.doc_student_verdict('offer_letter', {**fields, 'candidate_name': 'QUENTARO BIN ZEM'},
                                                    names=[name]), 'name_mismatch')


class MatcherOnTheNewShapeTest(TestCase):
    """Doors: `match_offer_course` / `pinned_match` (realign, link, confirm), `letter_place` and
    `CampusReader` (the ticks, `institution_fill`), fed from `student_offer_check`."""

    @classmethod
    def setUpTestData(cls):
        seed_realign_catalogue()
        seed_multi_campus()

    def test_a_one_row_university_resolves_from_the_name_alone(self):
        # UiTM: "UiTM" + campus "KAMPUS KOTA KINABALU", the code moved to programme_code.
        read = clean_offer_fields({'programme': 'BA272 SARJANA MUDA PERNIAGAAN KEWANGAN (KEPUJIAN)'})
        self.assertEqual(read['programme_code'], 'BA272')
        m = match_offer_course(read['programme'], 'UiTM', 'UNIVERSITI TEKNOLOGI MARA')
        self.assertEqual(m['course_id'], 'UE6343001')

    def test_the_university_name_now_agrees_where_a_hostel_line_needed_the_issuer(self):
        self.assertEqual(letter_place('UP4310001', UPM, BPP), UPM)
        self.assertEqual(op.institution_agreement('UP4310001', '', UPM, BPP), 'match')
        # Before S4 the hostel line contradicted the course unless the issuer named it.
        self.assertTrue(op.offer_contradicts_course_institution('UP4310001', 'KOLEJ SRI RAJANG', BPP))
        self.assertFalse(op.offer_contradicts_course_institution('UP4310001', UPM, BPP))

    def test_a_multi_campus_pin_survives_through_the_live_join(self):
        prog = 'DIPLOMA ZANTHARION GUNAAN'
        self.assertEqual(pinned_match(prog, 'INSTITUT QORVANE KAMPUS UTARA')[1]['institution'], NORTH)  # old line
        self.assertIsNone(pinned_match(prog, 'INSTITUT QORVANE')[1])          # the S4 name alone pins nothing
        joined = letter_institution('INSTITUT QORVANE', 'KAMPUS UTARA')        # what every reader is fed
        self.assertEqual(pinned_match(prog, joined)[1]['institution'], NORTH)

    def test_the_printed_code_tier_survives_through_the_live_join(self):
        issuer = 'Pejabat Timbalan Naib Canselor (Akademik dan Antarabangsa)'
        old = 'Sarjana Muda Ukur Bahan dengan Kepujian - UW6526001'
        self.assertEqual(match_offer_course(old, '', issuer)['course_id'], 'UW6526001')
        read = clean_offer_fields({'programme': old})
        self.assertEqual((read['programme'], read['programme_code']),
                         ('Sarjana Muda Ukur Bahan dengan Kepujian', 'UW6526001'))
        self.assertIsNone(match_offer_course(read['programme'], '', issuer))      # the name alone
        line = programme_line(read['programme'], read['programme_code'])           # what readers are fed
        self.assertEqual(match_offer_course(line, '', issuer)['course_id'], 'UW6526001')

    def test_student_offer_check_feeds_both_joins(self):
        app = make_application('submitted')
        chk = student_offer_check(_offer(app, programme='Sarjana Muda Ukur Bahan dengan Kepujian',
                                         programme_code='UW6526001', institution='UNIVERSITI QORVANE',
                                         campus='KAMPUS PERLAK'))
        self.assertIn('UW6526001', chk['programme'])
        self.assertEqual(chk['institution'], 'UNIVERSITI QORVANE KAMPUS PERLAK')

    def test_a_private_arm_letterhead_still_refuses_with_the_tell_in_the_issuer(self):
        self.assertIsNone(match_offer_course('SARJANA MUDA SAINS KOMPUTER DENGAN KEPUJIAN',
                                             'UNIVERSITI TEKNOLOGI MALAYSIA', 'UTM SPACE'))


class SponsorFacingInstitutionTest(TestCase):
    """Door: `offer_sync.institution_fill` / `sync_institution_from_catalogue` — the must-fill,
    sponsor-facing `chosen_programme.institution` of a multi-campus pick."""

    @classmethod
    def setUpTestData(cls):
        seed_multi_campus()

    def _app(self):
        return make_application('submitted', chosen_pathway='university',
                                chosen_programme={'course_id': MULTI, 'course_name': 'Diploma Zantharion Gunaan'})

    def test_the_campus_fill_survives_the_split(self):
        app = self._app()
        old = _offer(app, programme='DIPLOMA ZANTHARION GUNAAN', institution='INSTITUT QORVANE KAMPUS UTARA')
        self.assertEqual(institution_fill(app, offer=old), NORTH)
        app2 = self._app()
        new = _offer(app2, programme='DIPLOMA ZANTHARION GUNAAN', institution='INSTITUT QORVANE',
                     campus='KAMPUS UTARA')
        self.assertEqual(institution_fill(app2, offer=new), NORTH)      # via student_offer_check's join


class CheckTwoReportingDateTest(TestCase):
    """Door: Check 2's "when do you report?" (`offer_reporting_date_unknown`) and the reporting-date
    sync. A letter printing only a COMMENCEMENT date now reads no reporting date (owner, a405) — so
    after a re-read Check 2 asks the student, and the stored date is never cleared by the blank."""

    def test_a_commencement_only_letter_asks_check_two(self):
        app = make_application('submitted')
        _offer(app, institution='UNIVERSITI QORVANE', reporting_date='')
        self.assertTrue(offer_reporting_date_unknown(app))

    def test_a_reporting_date_still_answers_it(self):
        app = make_application('submitted')
        _offer(app, institution='UNIVERSITI QORVANE', reporting_date='17 Aug 2031')
        self.assertFalse(offer_reporting_date_unknown(app))
