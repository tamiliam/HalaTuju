"""Student maintenance Sprint 2 — the officer's Scholars list, maintenance file and activity log.

Pinned here, through the real endpoints (factory-built):
  * WHO IS LISTED — the maintenance predicate only; `?closed=1` the closed students with a file;
  * THE FENCE — the Applications rule (`_b40_scope`): see_all reads the organisation, a reviewer
    only their assigned scholars, finance 403; another organisation is 404, never 403;
  * the gift narrowing (`?programme=`, TD-334 for an organisation-less super);
  * filters, search, sort, pagination and the summary tiles;
  * the file payload (money from the ledger, no invented standing) and the activity log (manual
    entries with the staff-only flag, the actor, newest first; validation).
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import activity, maintenance
from apps.scholarship.models import Disbursement, SemesterResult, StudentActivity
from apps.scholarship.models.activity import EVENT_SUBSTATE_CHANGED
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_programme,
    make_student,
)

API = '/api/v1/admin/scholarship/scholars/'


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class _Scholars(TestCase):
    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        cls.cohort = make_cohort()
        cls.org = cls.cohort.owning_organisation
        cls.gift = cls.cohort.programme
        cls.reviewer = make_admin('reviewer', owning_org=cls.org)
        cls.org_admin = make_admin('org_admin', owning_org=cls.org)
        cls.officer = make_admin('admin', owning_org=cls.org)
        cls.finance = make_admin('finance', owning_org=cls.org)
        cls.qc = make_admin('qc', owning_org=cls.org)
        cls.super = make_admin('super', super_admin=True)

        def app(stage, name, **kw):
            return make_application(stage, cohort=cls.cohort, student=make_student(name=name), **kw)
        cls.aisyah = app('awarded', 'AISYAH', vircle_activated_at=now, reviewer=cls.reviewer,
                         chosen_programme={'course_name': 'Diploma in Accounting',
                                           'institution': 'Politeknik Ungku Omar'})
        cls.bala = make_application('active', cohort=cls.cohort, maintenance_substate='probation',
                                    student=make_student(name='BALA', nric='880312-10-5555'))
        cls.chen = app('maintenance', 'CHEN', maintenance_substate='on_hold')
        cls.dina = app('awarded', 'DINA')                               # no wallet: not in it
        cls.ezra = app('closed', 'EZRA')                                # funded, closed: a file
        other = make_cohort()
        cls.other_org_admin = make_admin('org_admin', owning_org=other.owning_organisation)
        cls.other_gift = other.programme
        cls.stranger = make_application('maintenance', cohort=other,
                                        student=make_student(name='STRANGER'))
        SemesterResult.objects.create(application=cls.bala, semester='Sem 1', cgpa=Decimal('3.40'),
                                      review_status='accepted')
        SemesterResult.objects.create(application=cls.chen, semester='Sem 1', cgpa=Decimal('2.10'),
                                      review_status='accepted')

    def _get(self, admin, url=API, **params):
        return authed_client(admin).get(url, params)

    def _names(self, r):
        self.assertEqual(r.status_code, 200, r.content[:300])
        return [row['name'] for row in r.json()['results']]


class TestWhoIsListed(_Scholars):
    def test_the_organisation_sees_its_in_maintenance_scholars(self):
        r = self._get(self.org_admin)
        self.assertEqual(self._names(r), ['AISYAH', 'BALA', 'CHEN'])
        self.assertEqual(r.json()['summary'], {
            'in_programme': 3, 'on_hold': 1, 'probation': 1, 'ready_to_close': 0, 'closed': 1,
            'below_minimum': 1})                     # S4a: Chen's accepted 2.10 is under 3.00

    def test_closed_lists_only_the_closed_files(self):
        self.assertEqual(self._names(self._get(self.org_admin, closed='1')), ['EZRA'])

    def test_a_row_says_what_it_knows_and_invents_nothing(self):
        rows = {row['name']: row for row in self._get(self.org_admin).json()['results']}
        a, b = rows['AISYAH'], rows['BALA']
        self.assertEqual((a['course'], a['institution'], a['status'], a['standing'], a['mentor']),
                         ('Diploma in Accounting', 'Politeknik Ungku Omar', 'awarded',
                          'no_result_yet', None))
        self.assertIsNone(a['latest_result'])
        self.assertEqual((b['standing'], b['latest_result']['cgpa'], b['latest_result']['semester']),
                         ('performing', '3.40', 'Sem 1'))
        self.assertEqual(rows['CHEN']['standing'], 'underperforming')
        self.assertTrue(rows['CHEN']['is_on_hold'])
        self.assertEqual(a['gift']['code'], self.gift.code)

    def test_last_activity_is_the_newest_row(self):
        activity.add_entry(self.aisyah, 'note', 'Called her.', actor_email='x@example.test')
        rows = {row['name']: row for row in self._get(self.org_admin).json()['results']}
        self.assertIsNotNone(rows['AISYAH']['last_activity_at'])
        self.assertIsNone(rows['BALA']['last_activity_at'])


class TestFence(_Scholars):
    def test_see_all_presets_read_the_organisation(self):
        for admin in (self.officer, self.org_admin, self.qc):
            self.assertEqual(self._names(self._get(admin)), ['AISYAH', 'BALA', 'CHEN'])

    def test_a_reviewer_reads_only_their_assigned_scholars(self):
        self.assertEqual(self._names(self._get(self.reviewer)), ['AISYAH'])
        self.assertEqual(self._get(self.reviewer).json()['summary']['in_programme'], 1)

    def test_finance_is_refused(self):
        self.assertEqual(self._get(self.finance).status_code, 403)
        self.assertEqual(self._get(self.finance, f'{API}{self.aisyah.id}/').status_code, 403)
        self.assertEqual(self._get(self.finance, f'{API}{self.aisyah.id}/activity/').status_code, 403)

    def test_another_organisation_is_404_never_403(self):
        self.assertNotIn('STRANGER', self._names(self._get(self.org_admin)))
        for url in (f'{API}{self.stranger.id}/', f'{API}{self.stranger.id}/activity/'):
            self.assertEqual(self._get(self.org_admin, url).status_code, 404)
        self.assertEqual(self._get(self.other_org_admin, f'{API}{self.aisyah.id}/').status_code, 404)

    def test_a_case_with_no_file_is_404(self):
        self.assertEqual(self._get(self.org_admin, f'{API}{self.dina.id}/').status_code, 404)

    def test_a_reviewer_is_refused_a_file_not_assigned_to_them(self):
        self.assertEqual(self._get(self.reviewer, f'{API}{self.bala.id}/').status_code, 403)
        self.assertEqual(self._get(self.reviewer, f'{API}{self.aisyah.id}/').status_code, 200)

    def test_the_gift_narrows_inside_the_fence(self):
        self.assertEqual(self._names(self._get(self.org_admin, programme=self.gift.code)),
                         ['AISYAH', 'BALA', 'CHEN'])
        self.assertEqual(self._get(self.org_admin, programme='no-such-gift').status_code, 404)
        # Another organisation's REAL gift code reads exactly like an unknown one.
        self.assertEqual(self._get(self.org_admin, programme=self.other_gift.code).status_code, 404)

    def test_a_moved_round_lists_its_scholars_under_its_new_gift(self):
        cohort = make_cohort(programme=make_programme(organisation=self.org))
        moved = make_application('maintenance', cohort=cohort, student=make_student(name='MIRA'))
        new_gift = make_programme(organisation=self.org)
        cohort.programme = new_gift
        cohort.save(update_fields=['programme'])
        moved.refresh_from_db()
        self.assertNotEqual(moved.programme_id, new_gift.id)          # the column stayed behind
        self.assertEqual(self._names(self._get(self.org_admin, programme=new_gift.code)), ['MIRA'])

    def test_a_reviewer_sees_no_closed_or_unassigned_scholar(self):
        self.assertEqual(self._names(self._get(self.reviewer, closed='1')), [])
        self.assertEqual(self._names(self._get(self.reviewer, search=f'#{self.bala.id}')), [])

    def test_no_ic_is_served(self):
        row = self._get(self.org_admin).json()['results'][0]
        self.assertNotIn('nric', row)
        self.assertNotIn('nric', self._get(self.org_admin, f'{API}{self.bala.id}/').json())

    def test_an_organisation_less_super_names_a_gift(self):
        r = self._get(self.super)
        self.assertEqual((r.status_code, r.json()['code']), (400, 'programme_required'))
        self.assertEqual(self._names(self._get(self.super, programme=self.gift.code)),
                         ['AISYAH', 'BALA', 'CHEN'])


class TestFiltersAndPages(_Scholars):
    def test_substate_and_on_hold(self):
        self.assertEqual(self._names(self._get(self.org_admin, substate='probation')), ['BALA'])
        self.assertEqual(self._names(self._get(self.org_admin, on_hold='1')), ['CHEN'])

    def test_search_by_name_ic_and_application_number(self):
        self.assertEqual(self._names(self._get(self.org_admin, search='aisy')), ['AISYAH'])
        self.assertEqual(self._names(self._get(self.org_admin, search=f'#{self.chen.id}')), ['CHEN'])
        for ic in ('880312-10-5555', '880312105555', '880312'):      # dashed, undashed, a prefix
            with self.subTest(ic=ic):
                self.assertEqual(self._names(self._get(self.org_admin, search=ic)), ['BALA'])

    def test_sort(self):
        self.assertEqual(self._names(self._get(self.org_admin, sort='-name')),
                         ['CHEN', 'BALA', 'AISYAH'])

    def test_a_student_with_nothing_sorts_last_both_ways(self):
        # Aisyah has no result; only Chen has activity. NULL last in BOTH directions (Postgres
        # would otherwise put the NULLs FIRST on a descending sort).
        self.assertEqual(self._names(self._get(self.org_admin, sort='-cgpa')), ['BALA', 'CHEN', 'AISYAH'])
        self.assertEqual(self._names(self._get(self.org_admin, sort='cgpa')), ['CHEN', 'BALA', 'AISYAH'])
        activity.add_entry(self.chen, 'note', 'x', actor_email='a@example.test')
        for sort in ('activity', '-activity'):
            with self.subTest(sort=sort):
                self.assertEqual(self._names(self._get(self.org_admin, sort=sort))[0], 'CHEN')

    def test_pagination(self):
        r = self._get(self.org_admin, page_size='1', page='2')
        self.assertEqual((self._names(r), r.json()['count'], r.json()['page']), (['BALA'], 3, 2))
        r = self._get(self.org_admin, page_size='1', page='99')          # clamps to the last page
        self.assertEqual((self._names(r), r.json()['page']), (['CHEN'], 3))


class TestFile(_Scholars):
    def test_the_file_payload(self):
        Disbursement.objects.create(application=self.chen, amount=Decimal('200'), status='released',
                                    sequence=1, released_at=timezone.now() - timedelta(days=3))
        r = self._get(self.org_admin, f'{API}{self.chen.id}/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        body = r.json()
        self.assertEqual((body['name'], body['status'], body['maintenance_substate'], body['is_on_hold']),
                         ('CHEN', 'maintenance', 'on_hold', True))
        money = body['money']
        self.assertEqual((money['award_amount'], money['paid_to_date'], money['remaining']),
                         ('2000.00', '200.00', '1800.00'))
        self.assertEqual(money['last_payment']['amount'], '200.00')
        self.assertEqual(body['contract'], {'exists': False, 'status': None})
        self.assertEqual((body['mentor'], body['letters'], body['standing']),
                         (None, [], 'underperforming'))
        self.assertEqual(body['latest_result']['cgpa'], '2.10')
        self.assertNotIn('spending', body)

    def test_no_award_reads_what_the_funding_summary_reads(self):
        from apps.scholarship import payments
        self.bala.award_amount = None
        self.bala.save(update_fields=['award_amount'])
        money = self._get(self.org_admin, f'{API}{self.bala.id}/').json()['money']
        self.assertEqual((money['award_amount'], money['remaining']),
                         (None, f'{payments._remaining(self.bala):.2f}'))

    def test_a_closed_file_still_opens(self):
        body = self._get(self.org_admin, f'{API}{self.ezra.id}/').json()
        self.assertEqual((body['status'], body['in_maintenance'], body['has_file']),
                         ('closed', False, True))


class TestCockpitLink(_Scholars):
    def test_the_cockpit_payload_says_whether_a_file_exists(self):
        url = '/api/v1/admin/scholarship/applications/{}/'
        self.assertTrue(self._get(self.org_admin, url.format(self.aisyah.id)).json()['has_file'])
        self.assertFalse(self._get(self.org_admin, url.format(self.dina.id)).json()['has_file'])


class TestActivity(_Scholars):
    def _url(self, app):
        return f'{API}{app.id}/activity/'

    def test_an_officer_adds_a_staff_only_note(self):
        r = authed_client(self.officer).post(self._url(self.bala), {
            'kind': 'call', 'body': '  Rang her mother about the slip.  ', 'internal': True},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()['kind'], r.json()['body'], r.json()['internal'],
                          r.json()['actor_email']),
                         ('call', 'Rang her mother about the slip.', True, self.officer.email))

    def test_the_timeline_is_newest_first_with_system_rows(self):
        maintenance.set_substate(self.bala, 'on_track', by_email='x@example.test')
        activity.add_entry(self.bala, 'note', 'Later note.', actor_email='y@example.test')
        rows = self._get(self.org_admin, self._url(self.bala)).json()['results']
        self.assertEqual([r['kind'] for r in rows], ['note', 'system'])
        self.assertEqual(rows[1]['event'], EVENT_SUBSTATE_CHANGED)

    def test_internal_is_only_true_when_sent_true(self):
        r = authed_client(self.officer).post(self._url(self.bala), {
            'kind': 'note', 'body': 'x', 'internal': 'yes'}, format='json')
        self.assertFalse(r.json()['internal'])

    def test_validation(self):
        client = authed_client(self.officer)
        for payload, code in (({'kind': 'system', 'body': 'x'}, 'bad_kind'),
                              ({'kind': 'note', 'body': '   '}, 'empty_body'),
                              ({'kind': 'note', 'body': 5}, 'empty_body'),
                              ({'kind': 'note', 'body': 'x' * 5001}, 'too_long')):
            with self.subTest(code=code):
                r = client.post(self._url(self.bala), payload, format='json')
                self.assertEqual((r.status_code, r.json()['code']), (400, code))
        self.assertFalse(StudentActivity.objects.filter(application=self.bala).exists())

    def test_a_closed_file_is_read_only(self):
        r = authed_client(self.officer).post(self._url(self.ezra), {'kind': 'note', 'body': 'x'},
                                             format='json')
        self.assertEqual((r.status_code, r.json()['code']), (409, 'file_closed'))
        self.assertEqual(self._get(self.org_admin, self._url(self.ezra)).status_code, 200)

    def test_another_organisations_file_is_404_to_write(self):
        r = authed_client(self.org_admin).post(self._url(self.stranger), {'kind': 'note', 'body': 'x'},
                                               format='json')
        self.assertEqual(r.status_code, 404)

    def test_a_reviewer_writes_only_on_their_own_scholar(self):
        client = authed_client(self.reviewer)
        ok = client.post(self._url(self.aisyah), {'kind': 'note', 'body': 'Met her.'}, format='json')
        self.assertEqual(ok.status_code, 201)
        no = client.post(self._url(self.bala), {'kind': 'note', 'body': 'x'}, format='json')
        self.assertEqual(no.status_code, 403)


class TestBatchedCatalogueNames(TestCase):
    """`card_display.catalogue_course_names` (two queries for a page) answers exactly what
    `catalogue_course_name` (two per course) answers — the list must not read a course differently
    from the cockpit and the sponsor card."""

    def test_the_batch_agrees_with_the_one_at_a_time_reader(self):
        from apps.courses.models import Course, FieldTaxonomy, Institution, StpmCourse
        from apps.scholarship import card_display
        tax = FieldTaxonomy.objects.create(key='zz_sch', name_en='X', name_ms='X', name_ta='X',
                                           image_slug='x')
        Course.objects.create(course_id='ZZS1', course='Diploma Perakaunan', level='Diploma',
                              department='X', field='Acc', field_key=tax)
        Institution.objects.get_or_create(
            institution_id='ZZ-UUM', defaults={'institution_name': 'Universiti Utara Malaysia',
                                               'type': 'Universiti', 'state': 'Kedah',
                                               'acronym': 'UUM'})
        StpmCourse.objects.create(course_id='ZZS2', course_name='Sarjana Muda Undang-Undang',
                                  university='UUM', institution_id='ZZ-UUM', field_key=tax)
        ids = ['ZZS1', 'ZZS2', 'ZZS-NONE', '']
        names = card_display.catalogue_course_names(ids)
        self.assertEqual({i: names.get(i, '') for i in ids},
                         {i: card_display.catalogue_course_name(i) for i in ids})
        app = make_application('maintenance', chosen_programme={'course_id': 'ZZS1',
                                                                'course_name': 'junk'})
        self.assertEqual(card_display.resolve_course(app, names=names),
                         card_display.resolve_course(app))


class TestFileControls(_Scholars):
    """Maintenance S3: the header OFFERS the sub-state and Close (moved from the cockpit). An offer,
    never the gate — the cockpit doors judge every request again."""

    def _controls(self, admin, app):
        return self._get(admin, f'{API}{app.id}/').json()['controls']

    def test_the_org_admin_may_hold_and_close_a_funded_case(self):
        c = self._controls(self.org_admin, self.bala)                    # active
        self.assertEqual((c['can_set_substate'], c['can_hold'], c['close_refusal']), (True, True, ''))
        self.assertIn('graduated', c['close_reasons'])

    def test_an_awarded_case_holding_the_offer_says_why_it_cannot_close(self):
        from apps.scholarship.models import Sponsor, Sponsorship
        sponsor = Sponsor.objects.create(supabase_user_id='spn-x', name='S', email='s@example.test',
                                         status='approved')
        Sponsorship.objects.create(sponsor=sponsor, application=self.aisyah, amount=Decimal('2000'),
                                   status='active')
        c = self._controls(self.org_admin, self.aisyah)
        self.assertEqual((c['close_reasons'], c['close_refusal']), ([], 'sponsorship_open'))
        self.assertTrue(c['can_set_substate'])

    def test_a_reviewer_may_not_hold(self):
        c = self._controls(self.reviewer, self.aisyah)                   # assigned to them
        self.assertEqual((c['can_set_substate'], c['can_hold']), (True, False))

    def test_a_reader_who_cannot_write_is_offered_nothing(self):
        c = self._controls(self.officer, self.bala)                      # see_all, not assigned
        self.assertEqual((c['can_set_substate'], c['close_reasons']), (False, []))

    def test_a_closed_file_offers_nothing(self):
        c = self._controls(self.org_admin, self.ezra)
        self.assertEqual((c['can_set_substate'], c['close_reasons'], c['close_refusal']),
                         (False, [], ''))


class TestControlsReviewGaps(_Scholars):
    """S3 adversarial review: an awarded case with NO live money is offered Close; a payable student
    with NO file is held from the cockpit (`maintenance_controls`)."""

    def test_an_awarded_case_with_no_live_money_is_offered_close(self):
        c = self._get(self.org_admin, f'{API}{self.aisyah.id}/').json()['controls']
        self.assertEqual(c['close_refusal'], '')
        self.assertIn('withdrawn', c['close_reasons'])

    def test_a_payable_student_with_no_file_is_held_from_the_cockpit(self):
        pending = make_application('awarded', cohort=self.cohort, reviewer=self.reviewer,
                                   vircle_id='8000400179999')
        url = f'/api/v1/admin/scholarship/applications/{pending.id}/'
        body = self._get(self.org_admin, url).json()
        self.assertEqual((body['has_file'], body['maintenance_controls']),
                         (False, {'can_set_substate': True, 'can_hold': True}))
        self.assertEqual(self._get(self.reviewer, url).json()['maintenance_controls']['can_hold'], False)
        self.assertEqual(self._get(self.org_admin, f'{API}{pending.id}/').status_code, 404)  # no file
        r = authed_client(self.org_admin).post(f'/api/v1/admin/scholarship/applications/{pending.id}/maintenance/',
                                               {'substate': 'on_hold'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['maintenance_controls']['can_hold'], True)

    def test_an_awarded_student_with_no_wallet_takes_no_substate_anywhere(self):
        url = f'/api/v1/admin/scholarship/applications/{self.dina.id}/'
        self.assertFalse(self._get(self.org_admin, url).json()['maintenance_controls']['can_set_substate'])
