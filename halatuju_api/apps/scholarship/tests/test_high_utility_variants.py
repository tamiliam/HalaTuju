"""TD-306 — the high-utility clarify never asks the student to read "RM {income}".

`high_utility_expense`'s copy quotes "the household income of RM {income} a month you reported".
Before TD-306 it was raised for a household with NO income on file, the params carried no
`income`, and the web painted the placeholder literally. Now a third variant,
`high_utility_expense_noincome`, asks the same question without the figure, and the plain one is
raised only when there is a figure to quote (`high_utility_variant`).
"""
from django.utils import timezone

from django.test import TestCase

from apps.scholarship import check2_queries as c2q
from apps.scholarship import high_utility_variant as hu
from apps.scholarship.models import ApplicantDocument, ResolutionItem
from apps.scholarship.tests.factories import make_application, make_cohort, make_student

PLAIN, NOINCOME, STR = hu.PLAIN, hu.NOINCOME, hu.STR


class _Household(TestCase):
    """A submitted application whose only standing clarifies are device + transport (two of the
    three slots), so the lowest-priority high-utility ask has the third — the same shape as
    `test_check2_queries._Base`, built through the factory."""

    income = 1200

    def setUp(self):
        student = make_student(name='Priya Devi', household_income=self.income, household_size=3)
        self.app = make_application(
            'profile_complete', cohort=make_cohort(), student=student,
            aspirations='I want to teach.', field_of_study='Education',
            siblings_in_tertiary=0, siblings_in_school=0,
            chosen_pathway='stpm', pathway_certainty='sure',
            father_occupation='gov', mother_occupation='homemaker')
        ApplicantDocument.objects.create(
            application=self.app, doc_type='salary_slip', household_member='father',
            storage_path='x/slip')

    def add_high_bills(self):
        # RM200 each → 400 / household of 3 ≈ 133 a head, over the RM60 floor → 'high'.
        for dt in ('water_bill', 'electricity_bill'):
            ApplicantDocument.objects.create(
                application=self.app, doc_type=dt, storage_path=f'x/{dt}',
                vision_fields={'fields': {'amount': 'RM200', 'name': 'Priya Devi'},
                               'student_verdict': 'ok'})

    def add_valid_str(self):
        ApplicantDocument.objects.create(
            application=self.app, doc_type='str', storage_path='x/str',
            vision_fields={'fields': {'status': 'Lulus', 'source_type': ''}},
            vision_run_at=timezone.now())

    def open_codes(self):
        return set(self.app.resolution_items.filter(source='check2', status='open')
                   .values_list('code', flat=True))

    def high_items(self):
        return list(self.app.resolution_items.filter(code__in=hu.CODES))

    def assert_no_unquotable_copy(self):
        """THE invariant: a row on the plain variant always carries the figure its copy quotes."""
        for item in self.app.resolution_items.filter(code=PLAIN):
            self.assertIn('income', item.params,
                          f'{PLAIN} row {item.pk} has no income — the student would read "RM {{income}}"')


class TestNoIncomeOnFile(_Household):
    income = None

    def test_the_noincome_variant_is_raised_instead(self):
        self.add_high_bills()
        c2q.sync_check2_queries(self.app)
        codes = self.open_codes()
        self.assertIn(NOINCOME, codes)
        self.assertNotIn(PLAIN, codes)
        self.assertNotIn(STR, codes)
        item = self.app.resolution_items.get(code=NOINCOME)
        self.assertEqual((item.kind, item.fact), ('clarify', 'income'))
        self.assertEqual(item.params, {'amount': 400})
        self.assert_no_unquotable_copy()

    def test_a_zero_income_is_no_figure_either(self):
        self.app.profile.household_income = 0
        self.app.profile.save()
        self.add_high_bills()
        c2q.sync_check2_queries(self.app)
        self.assertEqual([i.code for i in self.high_items()], [NOINCOME])
        self.assert_no_unquotable_copy()

    def test_a_second_sync_changes_nothing(self):
        self.add_high_bills()
        c2q.sync_check2_queries(self.app)
        before = [(i.pk, i.code, i.params, i.status) for i in self.high_items()]
        c2q.sync_check2_queries(self.app)
        self.assertEqual([(i.pk, i.code, i.params, i.status) for i in self.high_items()], before)


class TestIncomeOnFile(_Household):
    def test_plain_variant_unchanged(self):
        self.add_high_bills()
        c2q.sync_check2_queries(self.app)
        item = self.app.resolution_items.get(code=PLAIN)
        self.assertEqual(item.params, {'amount': 400, 'income': 1200})
        self.assertNotIn(NOINCOME, self.open_codes())

    def test_str_route_unchanged(self):
        self.add_high_bills()
        self.add_valid_str()
        c2q.sync_check2_queries(self.app)
        self.assertEqual([(i.code, i.params) for i in self.high_items()], [(STR, {'amount': 400})])


class TestNoIncomeStrRouteUnchanged(_Household):
    income = None

    def test_an_str_household_with_no_income_still_gets_the_str_variant(self):
        self.add_high_bills()
        self.add_valid_str()
        c2q.sync_check2_queries(self.app)
        self.assertEqual([i.code for i in self.high_items()], [STR])


class TestSamePriorityAndSlot(TestCase):
    def test_registered_like_its_sibling(self):
        self.assertEqual(c2q.CLARIFY_SPECS[NOINCOME], c2q.CLARIFY_SPECS[PLAIN])
        self.assertEqual(c2q.GOVERNED_BY[NOINCOME], c2q.GOVERNED_BY[PLAIN])
        order = c2q._CLARIFY_ORDER
        self.assertEqual(order[-3:], [PLAIN, NOINCOME, STR])     # the lowest-priority block
        self.assertEqual(len(order), 22)                          # 21 before TD-306, +1
        self.assertEqual(c2q.MAX_CLARIFY, 3)                      # the cap did not move


class TestSlotsCounted(_Household):
    """Device + transport + the high-utility ask fill the 3 slots whichever variant it is; a
    higher-priority ask crowds it out the same way."""

    def _open_clarifies(self):
        return self.app.resolution_items.filter(source='check2', kind='clarify', status='open')

    def test_three_slots_with_and_without_income(self):
        self.add_high_bills()
        c2q.sync_check2_queries(self.app)
        with_income = sorted(self._open_clarifies().values_list('code', flat=True))
        self.assertEqual(with_income, ['device_status_unknown', PLAIN, 'transport_cost_unknown'])

        self.app.resolution_items.all().delete()
        self.app.profile.household_income = None
        self.app.profile.save()
        c2q.sync_check2_queries(self.app)
        without = sorted(self._open_clarifies().values_list('code', flat=True))
        self.assertEqual(without, ['device_status_unknown', NOINCOME, 'transport_cost_unknown'])

    def test_crowded_out_like_the_plain_one(self):
        self.app.profile.household_income = None
        self.app.profile.save()
        self.app.other_scholarships = ['MARA loan']   # a higher-priority clarify takes the 3rd slot
        self.app.save()
        self.add_high_bills()
        c2q.sync_check2_queries(self.app)
        self.assertNotIn(NOINCOME, self.open_codes())
        self.assertEqual(c2q.clarify_overflow_count(self.app), 1)


class TestExistingRowsAreSwappedInPlace(_Household):
    """The rows raised before TD-306: an OPEN plain item with no `income` is re-coded to the
    no-income variant on the next sync — same row, no second question, no new-item email."""

    income = None

    def _legacy(self, code=PLAIN, params=None, status='open'):
        return ResolutionItem.objects.create(
            application=self.app, source='check2', code=code, fact='income', kind='clarify',
            params={'amount': 400} if params is None else params, status=status)

    def test_a_literal_bearing_row_becomes_the_noincome_variant(self):
        self.add_high_bills()
        legacy = self._legacy()
        c2q.sync_check2_queries(self.app)
        legacy.refresh_from_db()
        self.assertEqual((legacy.code, legacy.status, legacy.params), (NOINCOME, 'open', {'amount': 400}))
        self.assertEqual([i.pk for i in self.high_items()], [legacy.pk])     # no second row
        self.assert_no_unquotable_copy()

    def test_the_swap_does_not_re_announce(self):
        self.add_high_bills()
        c2q.sync_check2_queries(self.app)                  # device + transport + the ask, all new
        self.app.resolution_items.filter(code=NOINCOME).update(code=PLAIN)   # the pre-TD-306 row
        self.app.query_raised_notified_at = timezone.now()
        self.app.save(update_fields=['query_raised_notified_at'])
        c2q.sync_check2_queries(self.app)
        self.app.refresh_from_db()
        self.assertIsNotNone(self.app.query_raised_notified_at)
        self.assertEqual([i.code for i in self.high_items()], [NOINCOME])

    def test_a_literal_bearing_row_is_filled_when_income_is_now_on_file(self):
        self.app.profile.household_income = 900
        self.app.profile.save()
        self.add_high_bills()
        legacy = self._legacy()
        c2q.sync_check2_queries(self.app)
        legacy.refresh_from_db()
        self.assertEqual((legacy.code, legacy.params), (PLAIN, {'amount': 400, 'income': 900}))

    def test_an_open_noincome_row_takes_the_figure_once_income_is_reported(self):
        self.add_high_bills()
        c2q.sync_check2_queries(self.app)
        row = self.app.resolution_items.get(code=NOINCOME)
        self.app.profile.household_income = 900
        self.app.profile.save()
        c2q.sync_check2_queries(self.app)
        row.refresh_from_db()
        self.assertEqual((row.code, row.status, row.params), (PLAIN, 'open', {'amount': 400, 'income': 900}))

    def test_an_answered_row_is_not_asked_again_under_the_other_code(self):
        self.add_high_bills()
        answered = self._legacy(status='resolved')
        c2q.sync_check2_queries(self.app)
        self.assertEqual([i.pk for i in self.high_items()], [answered.pk])
        answered.refresh_from_db()
        self.assertEqual(answered.code, PLAIN)          # an answer stays on the question it answered
        self.assertEqual(c2q.clarify_overflow_count(self.app), 0)   # and nothing is "waiting"

    def test_a_row_whose_bills_are_no_longer_high_still_auto_resolves(self):
        legacy = self._legacy()                          # no bills on file → no high signal
        c2q.sync_check2_queries(self.app)
        legacy.refresh_from_db()
        self.assertEqual((legacy.code, legacy.status, legacy.resolved_by), (PLAIN, 'resolved', 'system'))


class TestTheReCodeIsSafe(_Household):
    """Review F1 / F2: the in-place re-code must never raise out of the sync (a UNIQUE clash would
    break the Action Centre, the officer page and the hourly email sweep), must not run when the
    machine may not ask, and leaves one log line."""

    income = None

    def _row(self, code, params=None, status='open'):
        return ResolutionItem.objects.create(
            application=self.app, source='check2', code=code, fact='income', kind='clarify',
            params={'amount': 400} if params is None else params, status=status)

    def test_both_codes_already_on_file_the_duplicate_is_closed_not_clashed(self):
        self.add_high_bills()
        plain, live = self._row(PLAIN), self._row(NOINCOME)     # two syncs raced
        c2q.sync_check2_queries(self.app)                        # must not raise
        plain.refresh_from_db()
        live.refresh_from_db()
        self.assertEqual((plain.code, plain.status, plain.resolved_by), (PLAIN, 'resolved', 'system'))
        self.assertEqual((live.code, live.status), (NOINCOME, 'open'))

    def test_an_answered_live_row_also_closes_the_open_duplicate(self):
        self.add_high_bills()
        plain = self._row(PLAIN)
        self._row(NOINCOME, status='resolved')
        c2q.sync_check2_queries(self.app)
        plain.refresh_from_db()
        self.assertEqual((plain.status, plain.resolved_by), ('resolved', 'system'))

    def test_a_clash_the_caller_could_not_see_is_swallowed_and_undone(self):
        self.add_high_bills()
        plain = self._row(PLAIN)
        self._row(NOINCOME)                   # on file, but NOT in the caller's snapshot (a race)
        existing = {PLAIN: plain}
        hu.reconcile_open(self.app, existing, {NOINCOME}, may_ask=True)   # must not raise
        self.assertEqual((plain.code, plain.params), (PLAIN, {'amount': 400}))   # in memory too
        self.assertIs(existing[PLAIN], plain)
        plain.refresh_from_db()
        self.assertEqual(plain.code, PLAIN)
        c2q.sync_check2_queries(self.app)     # the next sync still runs clean

    def test_no_re_code_when_the_machine_may_not_ask(self):
        self.add_high_bills()
        plain = self._row(PLAIN)
        self.app.status = 'interviewing'
        self.app.save(update_fields=['status'])
        c2q.sync_check2_queries(self.app)
        plain.refresh_from_db()
        self.assertEqual((plain.code, plain.status, plain.params), (PLAIN, 'open', {'amount': 400}))
        self.assertFalse(self.app.resolution_items.filter(code=NOINCOME).exists())

    def test_the_re_code_is_logged(self):
        self.add_high_bills()
        plain = self._row(PLAIN)
        with self.assertLogs('apps.scholarship.check2_queries', level='INFO') as logs:
            c2q.sync_check2_queries(self.app)
        self.assertEqual(len(logs.output), 1)
        line = logs.output[0]
        for part in (f'application={self.app.pk}', f'item={plain.pk}', PLAIN, NOINCOME):
            self.assertIn(part, line)


class TestTheStrWordingIsTheSameQuestion(_Household):
    """TD-314. A valid STR arriving on a household with an OPEN plain / no-income bills clarify and
    a FULL cap used to close that clarify as `system` and raise the `_str` wording later, with a
    fresh "new query" email — the same question twice, the first closed unanswered. The three
    wordings are now one question: the open row is re-worded in place (TD-306's mechanism)."""

    def _ask_then_notify(self):
        self.add_high_bills()
        c2q.sync_check2_queries(self.app)              # device + transport + the bills ask: full
        self.assertEqual(self.app.resolution_items.filter(
            source='check2', kind='clarify', status='open').count(), c2q.MAX_CLARIFY)
        self.app.query_raised_notified_at = timezone.now()
        self.app.save(update_fields=['query_raised_notified_at'])

    def test_a_valid_str_arriving_re_words_the_open_ask_in_place(self):
        self._ask_then_notify()
        row = self.app.resolution_items.get(code=PLAIN)
        self.add_valid_str()
        c2q.sync_check2_queries(self.app)
        row.refresh_from_db()
        self.assertEqual((row.code, row.status, row.resolved_by, row.params),
                         (STR, 'open', '', {'amount': 400}))
        self.assertEqual([i.pk for i in self.high_items()], [row.pk])        # no second row
        self.app.refresh_from_db()
        self.assertIsNotNone(self.app.query_raised_notified_at)             # no new-item email

    def test_and_back_when_the_str_stops_vouching(self):
        self.add_high_bills()
        self.add_valid_str()
        c2q.sync_check2_queries(self.app)
        row = self.app.resolution_items.get(code=STR)
        self.app.documents.filter(doc_type='str').delete()
        c2q.sync_check2_queries(self.app)
        row.refresh_from_db()
        self.assertEqual((row.code, row.status, row.params),
                         (PLAIN, 'open', {'amount': 400, 'income': 1200}))
        self.assert_no_unquotable_copy()

    def test_an_ANSWERED_plain_ask_is_not_asked_again_in_str_words(self):
        self.add_high_bills()
        c2q.sync_check2_queries(self.app)
        self.app.resolution_items.filter(code=PLAIN).update(
            status='resolved', resolved_by='student', resolution_text='a big family')
        self.add_valid_str()
        c2q.sync_check2_queries(self.app)
        self.assertEqual([(i.code, i.status) for i in self.high_items()], [(PLAIN, 'resolved')])
        self.assertEqual(c2q.clarify_overflow_count(self.app), 0)

    def test_a_raced_duplicate_is_closed_not_clashed(self):
        self.add_high_bills()
        self.add_valid_str()
        plain = ResolutionItem.objects.create(application=self.app, source='check2', code=PLAIN,
                                              fact='income', kind='clarify', params={'amount': 400})
        live = ResolutionItem.objects.create(application=self.app, source='check2', code=STR,
                                             fact='income', kind='clarify', params={'amount': 400})
        c2q.sync_check2_queries(self.app)                                   # must not raise
        plain.refresh_from_db()
        live.refresh_from_db()
        self.assertEqual((plain.code, plain.status, plain.resolved_by), (PLAIN, 'resolved', 'system'))
        self.assertEqual((live.code, live.status), (STR, 'open'))

    def test_no_re_word_when_the_machine_may_not_ask_and_no_close_either(self):
        self.add_high_bills()
        c2q.sync_check2_queries(self.app)
        row = self.app.resolution_items.get(code=PLAIN)
        self.app.status = 'interviewing'
        self.app.save(update_fields=['status'])
        self.add_valid_str()
        c2q.sync_check2_queries(self.app)
        row.refresh_from_db()
        self.assertEqual((row.code, row.status), (PLAIN, 'open'))           # as asked
        self.assertFalse(self.app.resolution_items.filter(code=STR).exists())

    def test_stand_ins_maps_every_wording_to_the_one_row(self):
        row = object()
        for only in hu.CODES:
            with self.subTest(only=only):
                self.assertEqual(hu.stand_ins({only: row}), {c: row for c in hu.CODES})


class TestTheEmailCarriesNoItemText(TestCase):
    def test_the_query_email_takes_a_count_not_items(self):
        import inspect
        from apps.scholarship.emails.student_queries import send_query_raised_email
        self.assertEqual(list(inspect.signature(send_query_raised_email).parameters),
                         ['to_email', 'applicant_name', 'programme_name', 'n_queries', 'lang'])
