"""Request #31 (BrightPath, 2026-10-08) — an intake year can accept only students BORN in chosen
states: `ScholarshipCohort.allowed_birth_states`, read against the IC's place-of-birth code.

THIS DECIDES WHO QUALIFIES FOR MONEY, so the rulings are pinned here as tests:

  * The test is BORN IN — the MyKad's place-of-birth code, digits 7-8 of YYMMDD-PB-###G. Not
    "Sabahan": family roots and where the student lives now do not count.
  * The full JPN code list (owner + BrightPath), every state's codes, old and new.
  * FAIL CLOSED: born outside Malaysia (60-99 except 82), "state unknown" (82), or an IC that
    cannot be read (not 12 digits; 00; 17-20) does NOT pass a state rule.
  * EMPTY = THE RULE IS OFF (the value is the switch, in list form). Off means the IC is not read.
  * A failure is a hard gate, category 'ineligible' — the generic decline email, no new one.
  * The admin endpoints refuse anything but a list of known keys, WHOLE, and save nothing.
  * The cockpit line is on the ADMIN serializer only — never a student or sponsor payload.
"""
from unittest import mock

from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings

from apps.scholarship import birth_state as bs
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import release_decision, rescore_pending_decisions, score_application
from apps.scholarship.shortlisting import evaluate
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_programme,
    make_student,
)

#: The owner's code list, restated here on purpose rather than imported: the module's table is
#: the thing under test, and a test that read its expectations from it would agree with any typo.
JPN = {
    'johor': ('01', '21', '22', '23', '24'),
    'kedah': ('02', '25', '26', '27'),
    'kelantan': ('03', '28', '29'),
    'melaka': ('04', '30'),
    'negeri_sembilan': ('05', '31', '59'),
    'pahang': ('06', '32', '33'),
    'pulau_pinang': ('07', '34', '35'),
    'perak': ('08', '36', '37', '38', '39'),
    'perlis': ('09', '40'),
    'selangor': ('10', '41', '42', '43', '44'),
    'terengganu': ('11', '45', '46'),
    'sabah': ('12', '47', '48', '49'),
    'sarawak': ('13', '50', '51', '52', '53'),
    'wp_kuala_lumpur': ('14', '54', '55', '56', '57'),
    'wp_labuan': ('15', '58'),
    'wp_putrajaya': ('16',),
}


def ic(code, stem='050505', tail='1234'):
    """A 12-digit IC with place-of-birth ``code``, in the dashed form the profile stores."""
    return f'{stem}-{code}-{tail}'


#: Every other requirement cleared, so a verdict can only turn on the birth-state rule.
ONLY_BIRTH = dict(min_spm_a_count=None, min_spm_bplus_count=None, min_spm_credit_count=None,
                  min_stpm_pngk=None, min_merit_score=None, income_ceiling=None,
                  per_capita_ceiling=None)


class TestTheCodeTable(SimpleTestCase):
    def test_every_state_code_on_the_owners_list_reads_as_that_state(self):
        for state, codes in JPN.items():
            for code in codes:
                with self.subTest(code=code):
                    self.assertEqual(bs.birth_state_from_nric(ic(code)),
                                     (bs.STATE, state, code))

    def test_all_four_sabah_codes(self):
        for code in ('12', '47', '48', '49'):
            with self.subTest(code=code):
                self.assertEqual(bs.birth_state_from_nric(ic(code)).state, 'sabah')

    def test_the_module_table_is_exactly_the_owners_list(self):
        self.assertEqual(bs.CODE_TO_STATE, {c: s for s, cs in JPN.items() for c in cs})

    def test_EVERY_two_digit_code_has_exactly_one_answer(self):
        # 00-99, all of them: nothing falls through to an accidental pass.
        for n in range(100):
            code = f'{n:02d}'
            kind = bs.birth_state_from_nric(ic(code)).kind
            with self.subTest(code=code):
                if 1 <= n <= 16 or 21 <= n <= 59:
                    self.assertEqual(kind, bs.STATE)
                elif n == 82:
                    self.assertEqual(kind, bs.UNKNOWN)
                elif 60 <= n <= 99:
                    self.assertEqual(kind, bs.ABROAD)
                else:      # 00 and 17-20
                    self.assertEqual(kind, bs.UNREADABLE)

    def test_82_is_unknown_and_71_is_abroad_and_both_keep_their_code(self):
        self.assertEqual(bs.birth_state_from_nric(ic('82')), (bs.UNKNOWN, '', '82'))
        self.assertEqual(bs.birth_state_from_nric(ic('71')), (bs.ABROAD, '', '71'))

    def test_00_and_17_to_20_are_unreadable_with_no_code(self):
        for code in ('00', '17', '18', '19', '20'):
            with self.subTest(code=code):
                self.assertEqual(bs.birth_state_from_nric(ic(code)), (bs.UNREADABLE, '', ''))

    def test_dashes_spaces_and_bare_digits_read_the_same(self):
        for raw in ('050505-12-1234', '050505121234', '050505 12 1234', ' 050505-12-1234 '):
            with self.subTest(raw=raw):
                self.assertEqual(bs.birth_state_from_nric(raw), (bs.STATE, 'sabah', '12'))

    def test_garbage_short_long_and_empty_are_unreadable(self):
        for raw in ('', None, 'not an ic', 'XXXXXX-XX-XXXX', '050505-12-123', '05050512',
                    '050505-12-12345', 'A1234567', 1234):
            with self.subTest(raw=raw):
                self.assertEqual(bs.birth_state_from_nric(raw).kind, bs.UNREADABLE)

    def test_a_non_ascii_digit_is_unreadable_and_never_crashes(self):
        # '²' is a digit to `str.isdigit()` and `int('²1')` raises — review finding 5.
        for raw in ('080505-²1-1234', '080505-12-123٤', '０８０５０５-12-1234'):
            with self.subTest(raw=raw):
                self.assertEqual(bs.birth_state_from_nric(raw), (bs.UNREADABLE, '', ''))
                self.assertFalse(bs.check(raw, ['sabah'])[0])

    def test_sixteen_states_with_stable_keys(self):
        self.assertEqual(len(bs.STATE_KEYS), 16)
        self.assertEqual(set(bs.STATE_KEYS), set(JPN))
        self.assertEqual(bs.STATE_NAMES['wp_kuala_lumpur'], 'W.P. Kuala Lumpur')


class TestTheCheck(SimpleTestCase):
    def test_an_EMPTY_list_is_off_and_never_reads_the_ic(self):
        for nric in ('', 'garbage', ic('71'), ic('82'), ic('05')):
            with self.subTest(nric=nric):
                self.assertEqual(bs.check(nric, []), (True, ''))
                self.assertEqual(bs.check(nric, None), (True, ''))

    def test_reasons_name_what_the_ic_says_and_every_accepted_state(self):
        self.assertEqual(bs.check(ic('05'), ['sabah']),
                         (False, 'born in Negeri Sembilan (IC code 05); this intake accepts Sabah'))
        self.assertEqual(bs.check(ic('71'), ['sabah']),
                         (False, 'born outside Malaysia (IC code 71); this intake accepts Sabah'))
        self.assertEqual(bs.check(ic('82'), ['sabah']),
                         (False, 'place of birth unknown (IC code 82); this intake accepts Sabah'))
        self.assertEqual(bs.check('', ['sabah']),
                         (False, 'IC number not readable; this intake accepts Sabah'))

    def test_several_states_are_listed_readably_in_the_platform_order(self):
        _, why = bs.check(ic('10'), ['wp_labuan', 'sabah', 'sarawak'])
        self.assertEqual(why, 'born in Selangor (IC code 10); '
                              'this intake accepts Sabah, Sarawak and W.P. Labuan')
        _, why = bs.check(ic('10'), ['sarawak', 'sabah'])
        self.assertTrue(why.endswith('accepts Sabah and Sarawak'))

    def test_a_hand_edited_non_list_still_fails_closed(self):
        # Only a database edit can store one; it must not match a substring or crash.
        self.assertEqual(bs.check(ic('12'), 'sabah'), (True, ''))
        self.assertFalse(bs.check(ic('12'), 'sabahan')[0])
        self.assertFalse(bs.check(ic('12'), {'sabah': True})[0])


class TestNormalise(SimpleTestCase):
    def test_known_keys_are_deduplicated_and_put_in_platform_order(self):
        self.assertEqual(bs.normalise_states(['sarawak', 'sabah', 'sabah']),
                         (['sabah', 'sarawak'], True))

    def test_null_and_empty_clear_the_rule(self):
        self.assertEqual(bs.normalise_states(None), ([], True))
        self.assertEqual(bs.normalise_states([]), ([], True))

    def test_anything_else_is_refused_whole(self):
        for bad in ('sabah', '', 5, True, {'sabah': True}, ['sabah', 'atlantis'], ['Sabah'],
                    ['sabah', None], ['sabah', 12], [['sabah']]):
            with self.subTest(bad=bad):
                self.assertEqual(bs.normalise_states(bad), (None, False))


class _Engine(TestCase):
    def _run(self, nric, states, **app):
        c = make_cohort(**ONLY_BIRTH, allowed_birth_states=states)
        a = make_application(cohort=c, student=make_student(nric=nric), **app)
        return evaluate(a, c)


class TestTheGate(_Engine):
    def test_off_when_the_list_is_empty_whatever_the_ic_says(self):
        for nric in (ic('05'), ic('71'), ic('82'), '', 'garbage'):
            with self.subTest(nric=nric):
                self.assertEqual(self._run(nric, []).verdict, 'shortlisted')

    def test_born_in_an_accepted_state_passes_on_every_one_of_its_codes(self):
        for code in JPN['sabah']:
            with self.subTest(code=code):
                self.assertEqual(self._run(ic(code), ['sabah']).verdict, 'shortlisted')

    def test_born_elsewhere_is_rejected_ineligible_with_the_reason(self):
        r = self._run(ic('05'), ['sabah'])
        self.assertEqual((r.verdict, r.bucket, r.category), ('rejected', '', 'ineligible'))
        self.assertEqual(r.reason, 'born in Negeri Sembilan (IC code 05); this intake accepts Sabah')

    def test_abroad_unknown_and_unreadable_all_fail_closed(self):
        for nric in (ic('71'), ic('82'), ic('18'), '050505-12', ''):
            with self.subTest(nric=nric):
                r = self._run(nric, ['sabah'])
                self.assertEqual((r.verdict, r.category), ('rejected', 'ineligible'))

    def test_several_states_ticked(self):
        for code, verdict in (('12', 'shortlisted'), ('13', 'shortlisted'), ('58', 'shortlisted'),
                              ('14', 'rejected')):
            with self.subTest(code=code):
                r = self._run(ic(code), ['sabah', 'sarawak', 'wp_labuan'])
                self.assertEqual(r.verdict, verdict)

    def test_no_profile_fails_closed(self):
        c = make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah'])
        a = make_application(cohort=c, student=make_student(nric=ic('12')))
        ScholarshipApplication.objects.filter(pk=a.pk).update(profile=None)
        a.refresh_from_db()
        r = evaluate(a, c)
        self.assertEqual((r.verdict, r.category), ('rejected', 'ineligible'))
        self.assertTrue(r.reason.startswith('IC number not readable'))

    def test_it_runs_AFTER_the_three_existing_gates(self):
        r = self._run(ic('05'), ['sabah'], consent_to_contact=False)
        self.assertEqual(r.reason, 'no consent to contact')

    def test_it_runs_BEFORE_the_academic_test(self):
        c = make_cohort(**{**ONLY_BIRTH, 'min_spm_a_count': 4}, allowed_birth_states=['sabah'])
        a = make_application(cohort=c, student=make_student(nric=ic('05'), grades={}))
        r = evaluate(a, c)
        self.assertEqual(r.category, 'ineligible')
        self.assertTrue(r.reason.startswith('born in Negeri Sembilan'))

    def test_a_passing_student_is_still_tested_on_everything_else(self):
        c = make_cohort(**{**ONLY_BIRTH, 'min_spm_a_count': 4}, allowed_birth_states=['sabah'])
        a = make_application(cohort=c, student=make_student(nric=ic('12'), grades={}))
        self.assertEqual(evaluate(a, c).category, 'merit')

    def test_a_cohort_object_without_the_attribute_is_off(self):
        # The engine is called with stand-in cohorts in places; a missing attribute is "not set".
        class Bare:
            min_spm_a_count = min_spm_bplus_count = min_spm_credit_count = None
            min_stpm_pngk = min_merit_score = income_ceiling = per_capita_ceiling = None
        a = make_application(student=make_student(nric=ic('71')))
        self.assertEqual(evaluate(a, Bare()).verdict, 'shortlisted')


class TestItArrivesEmpty(TestCase):
    def test_the_field_defaults_to_an_empty_list_and_is_not_nullable(self):
        field = ScholarshipCohort._meta.get_field('allowed_birth_states')
        self.assertFalse(field.null)
        self.assertEqual(field.get_default(), [])
        self.assertEqual(make_cohort().allowed_birth_states, [])

    def test_two_new_cohorts_do_not_share_one_list(self):
        a, b = make_cohort(), make_cohort()
        a.allowed_birth_states.append('sabah')
        self.assertEqual(b.allowed_birth_states, [])


class TestWhatTheStudentIsSent(TestCase):
    def _scored(self, nric, states=('sabah',)):
        c = make_cohort(**ONLY_BIRTH, allowed_birth_states=list(states))
        app = make_application(cohort=c, student=make_student(nric=nric))
        score_application(app)
        app.refresh_from_db()
        return app

    def test_the_verdict_reason_and_category_are_stored(self):
        app = self._scored(ic('05'))
        self.assertEqual((app.verdict, app.rejection_category), ('rejected', 'ineligible'))
        self.assertEqual(app.shortlist_reason,
                         'born in Negeri Sembilan (IC code 05); this intake accepts Sabah')

    @override_settings(DECLINE_COOLOFF_DAYS=0)
    def test_the_decline_is_the_GENERIC_one(self):
        app = self._scored(ic('71'))
        self.assertTrue(release_decision(app))
        body = mail.outbox[-1].body.lower()
        self.assertIn('this particular scholarship', body)      # FAIL_BODIES (generic)
        self.assertNotIn('academic', body)                      # not the merit email
        self.assertNotIn('financial need', body)                # not the need email
        self.assertNotIn('ic code', body)                       # the staff reason is never mailed

    def test_a_rescore_applies_a_rule_set_after_submit(self):
        app = self._scored(ic('05'), states=())
        self.assertEqual(app.verdict, 'shortlisted')
        ScholarshipCohort.objects.filter(pk=app.cohort_id).update(allowed_birth_states=['sabah'])
        out = rescore_pending_decisions()
        app.refresh_from_db()
        self.assertEqual((app.verdict, app.rejection_category), ('rejected', 'ineligible'))
        self.assertIn(app.id, [row['id'] for row in out['changed']])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheAdminScreens(TestCase):
    """Read and write through the real intake-year endpoints, beside the numeric rules."""

    @classmethod
    def setUpTestData(cls):
        cls.programme = make_programme()
        cls.admin = make_admin('org_admin', owning_org=cls.programme.organisation)

    def setUp(self):
        self.client = authed_client(self.admin)

    def _years(self):
        return f'/api/v1/admin/scholarship/programmes/{self.programme.id}/years/'

    def _year(self, c):
        return f'/api/v1/admin/scholarship/intake-years/{c.id}/'

    def _cohort(self, **kw):
        return make_cohort(programme=self.programme, is_active=True, is_open=False, **kw)

    def _create(self, code, **body):
        return self.client.post(self._years(), {'code': code, 'name': code, 'year': 2027, **body},
                                format='json')

    def test_create_stores_and_serves_it_in_platform_order(self):
        r = self._create('bs-set', allowed_birth_states=['sarawak', 'sabah', 'sarawak'])
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['requirements']['allowed_birth_states'], ['sabah', 'sarawak'])
        self.assertEqual(ScholarshipCohort.objects.get(code='bs-set').allowed_birth_states,
                         ['sabah', 'sarawak'])

    def test_create_without_it_is_empty(self):
        r = self._create('bs-none')
        self.assertEqual(r.data['requirements']['allowed_birth_states'], [])
        self.assertEqual(ScholarshipCohort.objects.get(code='bs-none').allowed_birth_states, [])

    def test_the_list_serves_it(self):
        self._cohort(code='bs-list', allowed_birth_states=['sabah'])
        row = self.client.get(self._years()).data['years'][0]
        self.assertEqual(row['requirements']['allowed_birth_states'], ['sabah'])

    def test_patch_sets_then_empty_or_null_clears(self):
        c = self._cohort(code='bs-patch')
        for sent, stored in ((['sabah'], ['sabah']), ([], []), (['sarawak', 'sabah'],
                             ['sabah', 'sarawak']), (None, [])):
            with self.subTest(sent=sent):
                r = self.client.patch(self._year(c), {'allowed_birth_states': sent}, format='json')
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.data['requirements']['allowed_birth_states'], stored)
                c.refresh_from_db()
                self.assertEqual(c.allowed_birth_states, stored)

    def test_a_patch_that_does_not_mention_it_leaves_it_alone(self):
        c = self._cohort(code='bs-alone', allowed_birth_states=['sabah'])
        self.client.patch(self._year(c), {'name': 'Renamed', 'min_spm_a_count': 3}, format='json')
        c.refresh_from_db()
        self.assertEqual(c.allowed_birth_states, ['sabah'])

    def test_anything_but_a_list_of_known_keys_is_refused_and_NOTHING_is_saved(self):
        # ⚠ request #30's lesson: a bad value must never quietly become a different rule while
        # the screen says Saved. The rule stays as it was, and so does everything else sent.
        for bad in ('sabah', '', 5, True, {'sabah': True}, ['sabah', 'atlantis'], ['Sabah'],
                    ['sabah', None], ['sabah', 12]):
            with self.subTest(bad=bad):
                c = self._cohort(allowed_birth_states=['sarawak'], min_spm_a_count=4)
                r = self.client.patch(self._year(c), {'allowed_birth_states': bad,
                                                      'name': 'Renamed', 'min_spm_a_count': 2},
                                      format='json')
                self.assertEqual(r.status_code, 400)
                self.assertEqual((r.data['code'], r.data['field']),
                                 ('bad_requirement', 'allowed_birth_states'))
                c.refresh_from_db()
                self.assertEqual(c.allowed_birth_states, ['sarawak'])
                self.assertEqual((c.name, c.min_spm_a_count), ('Test Bursary Programme 2026', 4))

    def test_creating_a_year_refuses_the_same_values(self):
        for bad in ('sabah', ['atlantis'], 5):
            with self.subTest(bad=bad):
                r = self._create('bs-new-bad', allowed_birth_states=bad)
                self.assertEqual((r.status_code, r.data['field']), (400, 'allowed_birth_states'))
                self.assertFalse(ScholarshipCohort.objects.filter(code='bs-new-bad').exists())

    def test_moving_it_is_audited_from_what_to_what(self):
        c = self._cohort(code='bs-audit')
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            self.client.patch(self._year(c), {'allowed_birth_states': ['sabah']}, format='json')
        line = [m for m in logs.output if 'intake_year_requirements_set' in m]
        self.assertEqual(len(line), 1)
        self.assertIn("allowed_birth_states:[]->['sabah']", line[0])

    def test_the_org_fence_holds_as_for_every_other_rule(self):
        c = self._cohort(code='bs-fence')
        stranger = make_admin('org_admin', owning_org=make_programme().organisation)
        r = authed_client(stranger).patch(self._year(c), {'allowed_birth_states': ['sabah']},
                                          format='json')
        self.assertEqual(r.status_code, 404)
        c.refresh_from_db()
        self.assertEqual(c.allowed_birth_states, [])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestTheCockpitLine(TestCase):
    """What the IC says, on the ADMIN application payload — and nowhere a student or sponsor reads."""

    def _detail(self, nric, states=()):
        programme = make_programme()
        admin = make_admin('org_admin', owning_org=programme.organisation)
        app = make_application(cohort=make_cohort(programme=programme,
                                                  allowed_birth_states=list(states)),
                               student=make_student(nric=nric))
        r = authed_client(admin).get(f'/api/v1/admin/scholarship/applications/{app.pk}/')
        self.assertEqual(r.status_code, 200)
        return r.data['birth_state']

    def test_each_kind_is_served_with_its_line(self):
        off = {'meets_rule': None, 'warning': ''}      # this intake has no rule
        cases = (
            (ic('12'), {'kind': 'state', 'state': 'sabah', 'code': '12',
                        'label': 'Born in: Sabah (IC code 12)', **off}),
            (ic('71'), {'kind': 'abroad', 'state': None, 'code': '71',
                        'label': 'Born outside Malaysia (IC code 71)', **off}),
            (ic('82'), {'kind': 'unknown', 'state': None, 'code': '82',
                        'label': 'Place of birth unknown (IC code 82)', **off}),
            ('', {'kind': 'unreadable', 'state': None, 'code': '',
                  'label': 'IC number not readable', **off}),
        )
        for nric, want in cases:
            with self.subTest(nric=nric):
                self.assertEqual(self._detail(nric), want)

    def test_against_a_rule_it_says_whether_the_CURRENT_ic_meets_it(self):
        self.assertEqual(self._detail(ic('47'), ['sabah'])['meets_rule'], True)
        self.assertEqual(self._detail(ic('47'), ['sabah'])['warning'], '')
        got = self._detail(ic('10'), ['sabah', 'sarawak'])
        self.assertIs(got['meets_rule'], False)
        self.assertEqual(got['warning'], "Born in: Selangor (IC code 10) — does not meet this "
                                         "intake's rule (Sabah and Sarawak)")
        self.assertIs(self._detail('', ['sabah'])['meets_rule'], False)

    def test_it_is_served_whether_or_not_the_intake_has_the_rule(self):
        # The reviewer sees where the IC says the student was born on EVERY case: a doubt is for
        # a birth certificate, which the cockpit can already ask for.
        self.assertEqual(self._detail(ic('05'))['kind'], 'state')

    def test_it_is_ABSENT_from_the_students_own_payload(self):
        # ⚠ A REJECTED student on an intake WITH the rule — the case where the engine's staff note
        # ("born in Selangor (IC code 10); this intake accepts Sabah") exists to leak. Review
        # finding 3: `shortlist_reason` was served here, before the decision was even revealed.
        student = make_student(nric=ic('10'))
        app = make_application(cohort=make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah']),
                               student=student)
        score_application(app)
        app.refresh_from_db()
        self.assertTrue(app.shortlist_reason.startswith('born in Selangor'))   # it IS stored
        r = authed_client(student.supabase_user_id).get(
            f'/api/v1/scholarship/applications/{app.pk}/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertNotIn('birth_state', body)
        self.assertNotIn('shortlist_reason', body)
        for leak in ('IC code', 'Selangor', 'this intake accepts'):
            self.assertNotIn(leak, r.content.decode())
        # The list GET and the submit response (`views.py`) use the same serializer.
        from apps.scholarship.serializers import ApplicationReadSerializer
        self.assertNotIn('shortlist_reason', ApplicationReadSerializer.Meta.fields)
        listed = authed_client(student.supabase_user_id).get('/api/v1/scholarship/applications/')
        self.assertNotIn('this intake accepts', listed.content.decode())

    def test_the_admin_payload_still_carries_the_reason(self):
        programme = make_programme()
        admin = make_admin('org_admin', owning_org=programme.organisation)
        app = make_application(cohort=make_cohort(programme=programme, **ONLY_BIRTH,
                                                  allowed_birth_states=['sabah']),
                               student=make_student(nric=ic('10')))
        score_application(app)
        r = authed_client(admin).get(f'/api/v1/admin/scholarship/applications/{app.pk}/')
        self.assertTrue(r.data['shortlist_reason'].startswith('born in Selangor (IC code 10)'))

    def test_no_student_or_sponsor_serializer_declares_it(self):
        # `apps.scholarship.serializers` is the student- and sponsor-facing module. Every class in
        # it is read: a sponsor card or the student read growing the field would be a leak.
        import inspect

        from rest_framework import serializers as drf

        from apps.scholarship import serializers as public
        classes = [c for _, c in inspect.getmembers(public, inspect.isclass)
                   if issubclass(c, drf.BaseSerializer) and c.__module__ == public.__name__]
        self.assertGreater(len(classes), 15)       # the scan really found the module's classes
        for cls in classes:
            with self.subTest(cls=cls.__name__):
                self.assertNotIn('birth_state', cls().fields)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestAnIcChangedAfterTheGate(TestCase):
    """Review finding 1. The gate runs at SUBMIT. An unverified NRIC can be changed afterwards
    (`POST /profile/claim-nric/`, the "created" branch), and a MyKad matching the NEW number then
    locks it — so nothing re-ran the rule. The cockpit now re-reads it on every load, and the QC
    ACCEPT floor holds a case whose current IC fails the intake's current rule."""

    def setUp(self):
        self.cohort = make_cohort(**ONLY_BIRTH, allowed_birth_states=['sabah'])
        org = self.cohort.owning_organisation
        self.qc = make_admin('qc', owning_org=org, email='qc@example.test')
        self.org_admin = make_admin('org_admin', owning_org=org)
        # A clean AI verdict, so the floor can only turn on the birth-state fact (the factory
        # carries no documents; `test_qc_gate.py` patches the same seam for the same reason).
        patcher = mock.patch('apps.scholarship.views_admin.verdict.build_verdict', return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

    def _qc(self, app, **body):
        return authed_client(self.qc).post(
            f'/api/v1/admin/scholarship/applications/{app.pk}/qc-decision/',
            {'decision': 'accept', **body}, format='json')

    def _awaiting_qc(self, nric, outcome='recommend', cohort=None):
        return make_application('awaiting_qc', outcome=outcome, cohort=cohort or self.cohort,
                                student=make_student(nric=nric))

    def test_the_swap_is_seen_in_the_cockpit(self):
        from apps.courses.profile_claim import handle_claim
        student = make_student(nric=ic('12', stem='080505'))
        app = make_application(cohort=self.cohort, student=student)
        score_application(app)
        app.refresh_from_db()
        self.assertEqual(app.verdict, 'shortlisted')            # Sabah-born at submit
        uid = student.supabase_user_id
        self.assertEqual(handle_claim(uid, uid, {'nric': '080505-10-1234'}),
                         ({'status': 'created'}, 200))          # the number changes to Selangor
        got = authed_client(self.org_admin).get(
            f'/api/v1/admin/scholarship/applications/{app.pk}/').data['birth_state']
        self.assertIs(got['meets_rule'], False)
        self.assertEqual(got['warning'], "Born in: Selangor (IC code 10) — does not meet this "
                                         "intake's rule (Sabah)")

    def test_qc_accept_is_refused_on_the_floor(self):
        app = self._awaiting_qc(ic('10'))
        r = self._qc(app)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'verdict_gap_floor')
        self.assertEqual(r.json()['facts'], ['birth_state'])
        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewed')

    def test_qc_accept_with_a_reason_passes_and_the_override_is_recorded(self):
        app = self._awaiting_qc(ic('10'))
        with self.assertLogs('apps.scholarship.views_admin', level='INFO') as logs:
            r = self._qc(app, override_reason='Birth certificate shows Kota Kinabalu.')
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, 'recommended')
        self.assertEqual(app.qc_override_reason, 'Birth certificate shows Kota Kinabalu.')
        self.assertEqual(app.qc_override_by, 'qc@example.test')
        self.assertIsNotNone(app.qc_override_at)
        self.assertTrue(any('qc_gap_override' in m and 'facts=birth_state' in m
                            for m in logs.output))

    def test_an_ic_that_meets_the_rule_is_not_held(self):
        app = self._awaiting_qc(ic('49'))
        self.assertEqual(self._qc(app).status_code, 200)
        app.refresh_from_db()
        self.assertEqual((app.status, app.qc_override_reason), ('recommended', ''))

    def test_rule_off_adds_no_fact(self):
        off = make_cohort(**ONLY_BIRTH, owning_organisation=self.cohort.owning_organisation)
        app = self._awaiting_qc(ic('71'), cohort=off)
        self.assertEqual(self._qc(app).status_code, 200)
        app.refresh_from_db()
        self.assertEqual((app.status, app.qc_override_reason), ('recommended', ''))
        got = authed_client(self.org_admin).get(
            f'/api/v1/admin/scholarship/applications/{app.pk}/').data['birth_state']
        self.assertIsNone(got['meets_rule'])

    @override_settings(DECLINE_QC_COOLOFF_HOURS=24)
    def test_confirming_a_DECLINE_is_not_affected(self):
        app = self._awaiting_qc(ic('10'), outcome='decline')
        r = self._qc(app)
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual((app.status, app.rejection_category), ('rejected', 'interview'))
        self.assertEqual(app.qc_override_reason, '')


class TestTheProfileStepAcceptsEveryStateCode(TestCase):
    """Review finding 2. `profile_claim.VALID_STATE_CODES` stopped at 24, so an IC born in Sabah
    under 47/48/49 — or anywhere under 25-59 — was refused at the profile step and could never
    reach the gate. It is a literal in `apps.courses` (no courses -> scholarship import); this
    holds it to the birth-state table."""

    def test_it_is_every_state_code_plus_71_72_and_82(self):
        from apps.courses.profile_claim import VALID_STATE_CODES
        self.assertEqual(set(VALID_STATE_CODES), set(bs.CODE_TO_STATE) | {'71', '72', '82'})

    def test_the_later_codes_are_accepted_and_the_gaps_still_refused(self):
        from apps.courses.profile_claim import validate_nric
        for code in ('47', '48', '49', '58', '59', '12', '25'):
            with self.subTest(code=code):
                self.assertEqual(validate_nric(f'080505-{code}-1234'), '')
        for code in ('00', '17', '20', '60', '99'):
            with self.subTest(code=code):
                self.assertEqual(validate_nric(f'080505-{code}-1234'),
                                 'Invalid state code in IC number')

    def test_a_sabah_47_ic_can_be_saved_on_the_profile(self):
        from apps.courses.profile_claim import handle_claim
        student = make_student(nric='')
        uid = student.supabase_user_id
        self.assertEqual(handle_claim(uid, uid, {'nric': '080505-47-1234'}),
                         ({'status': 'created'}, 200))
        student.refresh_from_db()
        self.assertEqual(bs.birth_state_from_nric(student.nric), (bs.STATE, 'sabah', '47'))
