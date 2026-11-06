"""The offer-field doors the S4 adversarial review added (2026-11-02, M2 + L4).

* MONEY — `pathway_engine.course_start_year` / `started_before_cohort` (read by
  `award.proposed_award_amount`, `award.course_start_unknown`, `epf_evidence`): EXACTLY main's behaviour.
  The not_offer_letter ruling was taken out of S4 and deferred to a money sprint (owner, 2026-11-02).
* `blockers.document_unreadable_blockers`, the reporting bonus (`offer_reporting_bonus`, read by
  `verdict_ladder` and `promotion._offer_quality`), the IC the student is shown (`serializers` →
  `checklistsPathway.tsx`), the cockpit intake-year chip.
* `offer_pathway_switch` across reader versions (an old hostel line vs a new name + campus), and
  `promotion.is_pathway_switch` across versions (L4).

Synthetic twins only (`test_no_gitignored_corpus.py`)."""
import datetime
from types import SimpleNamespace

from django.test import TestCase
from django.utils import timezone

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.offer_reader import clean_offer_fields
from apps.scholarship.pathway_engine import (
    course_start_year, offer_pathway_switch, offer_reporting_bonus, student_offer_check)
from apps.scholarship.promotion import is_pathway_switch
from apps.scholarship.services.blockers import document_unreadable_blockers
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.factories import create_document


def _offer(app, status='genuine', superseded=False, **fields):
    prof = app.profile
    base = {'candidate_name': prof.name, 'candidate_nric': prof.nric.replace('-', '')}
    return create_document(
        application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/{len(fields)}{superseded}',
        vision_fields={'fields': {**base, **fields}, 'authenticity': {'status': status, 'doc_seen': 'ua_offer'},
                       'student_verdict': 'ok', 'warnings': [], 'error': ''},
        vision_run_at=timezone.now(), superseded_at=timezone.now() if superseded else None)


class CourseStartYearIsMainsTest(TestCase):
    """MONEY: S4 ships the reader only and money behaves EXACTLY as on main (owner, 2026-11-02). The
    not_offer_letter money ruling is DEFERRED to its own money sprint (`docs/decisions.md`), so these pin
    main's behaviour: any scored letter's intake dates the course, and its reporting date is synced."""

    def _app(self):
        return make_application('submitted', chosen_pathway='stpm')

    def test_any_scored_letter_dates_the_course_as_on_main(self):
        for status in ('genuine', 'suspect', '', 'not_offer_letter'):
            app = self._app()
            _offer(app, status=status, intake='SESI 1-2025/2026')
            self.assertEqual(course_start_year(app), 2025, status)

    def test_the_reporting_date_sync_and_backfill_read_are_mains(self):
        from apps.scholarship.pathway_engine import offer_reporting_date
        from apps.scholarship.services.offer_sync import sync_reporting_date_from_offer
        app = self._app()
        doc = _offer(app, status='not_offer_letter', reporting_date='17 Aug 2025')
        self.assertTrue(sync_reporting_date_from_offer(app, offer=doc))
        app.refresh_from_db()
        self.assertEqual(app.reporting_date, datetime.date(2025, 8, 17))
        self.assertEqual(offer_reporting_date(app), datetime.date(2025, 8, 17))
        self.assertEqual(course_start_year(app), 2025)


class OtherDoorsTest(TestCase):
    def test_a_blank_name_still_raises_the_unreadable_blocker(self):
        app = make_application('submitted')
        _offer(app, candidate_name='')
        self.assertIn('offer_letter_unreadable', document_unreadable_blockers(app))

    def test_no_reporting_date_means_no_reporting_bonus(self):
        app = make_application('submitted')
        doc = _offer(app, reporting_date='', reporting_date_label='')     # a commencement-only letter
        self.assertFalse(offer_reporting_bonus(doc))

    def test_the_ic_the_student_is_shown_is_never_someone_elses_reference_line(self):
        app = make_application('submitted')
        read = {'candidate_nric': '991231-01-0001', 'candidate_nric_source': 'reference_line'}
        clean_offer_fields(read, profile_nric=app.profile.nric)
        chk = student_offer_check(_offer(app, **read))
        self.assertEqual(chk['candidate_nric'], '')               # serializers → checklistsPathway.tsx

    def test_the_intake_year_chip_reads_a_labelled_intake(self):
        app = make_application('submitted')
        for intake in ('SESI 1-2026/2027', 'SEMESTER 1 TAHUN 2026', 'SESI AKADEMIK 2026/2027'):
            self.assertEqual(student_offer_check(_offer(app, intake=intake))['intake_year'], '2026', intake)


class SwitchAcrossVersionsTest(TestCase):
    def test_an_old_hostel_line_against_the_new_name_and_campus_is_pinned(self):
        """`offer_pathway_switch` (the reviewer's "course switched" flag) compares the LIVE offer with
        the last SUPERSEDED one. A re-read of one document never supersedes it, so the flag can only
        fire when the student uploads a second letter. Pinned here: with the SAME programme, an old
        hostel-line read against the S4 name + campus — this is what the reviewer would see."""
        app = make_application('submitted')
        _offer(app, superseded=True, programme='DIPLOMA QORVANE', institution='KOLEJ DAHLIA, UNIVERSITI QORVANE')
        _offer(app, programme='DIPLOMA QORVANE', institution='UNIVERSITI QORVANE', campus='KAMPUS PERLAK')
        self.assertIsNone(offer_pathway_switch(app))      # the university's own words carry it: no false switch
        app2 = make_application('submitted')
        _offer(app2, superseded=True, programme='DIPLOMA QORVANE', institution='KOLEJ DAHLIA')   # hostel only
        _offer(app2, programme='DIPLOMA QORVANE', institution='UNIVERSITI QORVANE', campus='KAMPUS PERLAK')
        sw = offer_pathway_switch(app2)
        # A hostel-only old line shares no word with the university: the flag fires on the institution
        # alone, with the SAME programme on both sides — the reviewer sees "from DIPLOMA QORVANE to DIPLOMA
        # QORVANE". Documented, not fixed (the review's option): it needs a second upload to happen.
        self.assertIsNotNone(sw)
        self.assertEqual(sw['from_programme'], sw['to_programme'])

    def test_is_pathway_switch_reads_codes_across_versions(self):                      # review L4
        def doc(**f):
            return SimpleNamespace(doc_type='offer_letter', vision_fields={'fields': f})
        old = doc(programme='SARJANA MUDA QORVANE (KEPUJIAN) - UW6526001')             # pre-S4: code inline
        same = doc(programme='SARJANA MUDA QORVANE (KEPUJIAN)', programme_code='UW6526001')
        other = doc(programme='SARJANA MUDA QORVANE (KEPUJIAN)', programme_code='UW6526002')
        self.assertFalse(is_pathway_switch(same, old))
        self.assertTrue(is_pathway_switch(other, old))
        self.assertFalse(is_pathway_switch(doc(programme='BA272 SARJANA MUDA QORVANE'),
                                           doc(programme='SARJANA MUDA QORVANE', programme_code='BA272')))
