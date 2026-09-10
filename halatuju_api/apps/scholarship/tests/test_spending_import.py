"""Vircle spending import — S1 (docs/plans/2026-09-10-sponsor-spending-roadmap.md).

Fixtures use INVENTED merchants, wallets and names. The real corpus lives outside the repo and
carries student names and wallet ids; the one test that reads it SKIPS when it is absent, so CI
never depends on it.

Each test names the measured fact it protects. The corpus figures quoted throughout are from
`docs/plans/2026-09-09-sponsor-spending-reports-brief.md` §0b.
"""
import os
from datetime import date, datetime
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from apps.courses.models import PartnerOrganisation, StudentProfile
from apps.scholarship import spending_import as si
from apps.scholarship.models import (
    BursarySpendTxn, Programme, ScholarshipApplication, ScholarshipCohort,
)

D = Decimal
_SEQ = {'n': 0}

#: The real corpus, if this machine has it. Never committed.
CORPUS_DIR = r'C:\Users\tamil\Downloads\spending'

# The three header rows Vircle has actually shipped, in the order they appeared.
HEADER_A = ['transaction_date', 'wallet_id', 'BrightPath name', 'transaction_id', 'Sender',
            'Receiver', 'duitnow_type', 'Entry Type', 'TX Type', 'amount', 'Status']
HEADER_B = ['transaction_date', 'wallet_id', 'transaction_id', 'Wallet User', 'Child User',
            'Receiver', 'duitnow_type', 'Entry Type', 'TX Type', 'amount', 'Status']
HEADER_C = ['transaction_date', 'wallet_id', 'transaction_id', 'Wallet User', 'Child User',
            'Merchant Name', 'duitnow_type', 'Entry Type', 'TX Type', 'amount', 'Status']

MERCHANT_QR = 'STATIC_MERCHANT_QR_CODE_DUITNOW'


def row_c(txn_id, wallet, *, merchant='TEST CAFE', amount=5, when='30 Aug 2026',
          child='null', duitnow=MERCHANT_QR, tx='Spend', status='00', entry='CREDIT'):
    return [when, wallet, txn_id, 'Test Holder', child, merchant, duitnow, entry, tx,
            amount, status]


def make_org(code='spend-bp'):
    return PartnerOrganisation.objects.create(code=code, name='BrightPath')


def make_cohort(org):
    programme, _ = Programme.objects.get_or_create(
        organisation=org, code=f'{org.code}-prog', defaults={'name_en': 'Bursary'})
    return ScholarshipCohort.objects.create(
        code=f'{org.code}-c', name='B40', year=2026, owning_organisation=org,
        programme=programme)


def make_app(cohort, org, wallet, *, status='awarded'):
    _SEQ['n'] += 1
    i = _SEQ['n']
    prof = StudentProfile.objects.create(
        supabase_user_id=f'spend-stud-{i}', nric=f'{i:06d}-14-{i:04d}',
        name=f'Student {i}', contact_phone=f'01{i:08d}')
    return ScholarshipApplication.objects.create(
        cohort=cohort, profile=prof, owning_organisation=org, status=status,
        chosen_pathway='matric', award_amount=D('2000'), vircle_id=wallet)


# ── the parser ────────────────────────────────────────────────────────────────

class TestColumnResolution(TestCase):
    """The layout has drifted four times in eight weeks. Every past shape must still load."""

    def test_all_three_real_header_variants_resolve(self):
        for header in (HEADER_A, HEADER_B, HEADER_C):
            indexes, _ = si.resolve_columns(header)
            self.assertIn('merchant', indexes)
            self.assertIn('holder_name', indexes)

    def test_merchant_reads_from_either_name(self):
        a, _ = si.resolve_columns(HEADER_B)      # 'Receiver'
        c, _ = si.resolve_columns(HEADER_C)      # 'Merchant Name'
        self.assertEqual(HEADER_B[a['merchant']], 'Receiver')
        self.assertEqual(HEADER_C[c['merchant']], 'Merchant Name')

    def test_header_matching_ignores_case_and_spacing(self):
        header = list(HEADER_C)
        header[5] = '  MERCHANT   name '
        indexes, _ = si.resolve_columns(header)
        self.assertEqual(indexes['merchant'], 5)

    def test_a_missing_required_column_refuses_the_file_and_names_it(self):
        """⚠ THE ONE FAILURE THAT CAN MISATTRIBUTE MONEY. It must stop, not guess."""
        header = [h for h in HEADER_C if h != 'wallet_id']
        with self.assertRaises(si.UnreadableReport) as ctx:
            si.resolve_columns(header)
        self.assertIn('wallet_id', str(ctx.exception))

    def test_a_renamed_column_is_refused_not_silently_dropped(self):
        header = ['Merchant' if h == 'Merchant Name' else h for h in HEADER_C]
        with self.assertRaises(si.UnreadableReport):
            si.resolve_columns(header)

    def test_an_unknown_extra_column_is_reported_but_the_file_still_loads(self):
        header = HEADER_C + ['some_new_vircle_column']
        _, unknown = si.resolve_columns(header)
        self.assertEqual(unknown, ['some_new_vircle_column'])

    def test_sender_is_known_and_not_reported(self):
        """It existed in the two oldest reports and was dropped. Reporting it every run is noise."""
        _, unknown = si.resolve_columns(HEADER_A)
        self.assertEqual(unknown, [])


class TestAmountParsing(TestCase):
    """⚠ 1,280 real amounts are numbers and 88 are the string 'RM26.90'. Both, or 88 vanish."""

    def test_numbers_and_currency_strings_both_parse(self):
        self.assertEqual(si.parse_amount(2), D('2.00'))
        self.assertEqual(si.parse_amount(12.4), D('12.40'))
        self.assertEqual(si.parse_amount('RM26.90'), D('26.90'))
        self.assertEqual(si.parse_amount('RM1,234.50'), D('1234.50'))
        self.assertEqual(si.parse_amount(' rm 3.00 '), D('3.00'))

    def test_it_returns_decimal_never_float(self):
        """Money is summed and shown to a sponsor; float drift is not acceptable here."""
        self.assertIsInstance(si.parse_amount(0.1), Decimal)

    def test_unparseable_returns_none_so_the_caller_can_COUNT_it(self):
        for bad in (None, '', 'n/a', 'RM', True):
            self.assertIsNone(si.parse_amount(bad), bad)


class TestDateParsing(TestCase):
    """⚠ The two oldest reports carry a time of day; the rest do not."""

    def test_both_real_formats_parse_and_the_time_is_dropped(self):
        self.assertEqual(si.parse_txn_date('30 Aug 2026'), date(2026, 8, 30))
        self.assertEqual(si.parse_txn_date('5 Jul 2026, 15:14:59'), date(2026, 7, 5))
        self.assertEqual(si.parse_txn_date(datetime(2026, 7, 5, 15, 14)), date(2026, 7, 5))

    def test_unparseable_returns_none(self):
        self.assertIsNone(si.parse_txn_date('sometime last week'))


class TestRowFacts(TestCase):
    def test_child_user_null_is_not_a_child_but_a_name_is(self):
        """⚠ Vircle writes an absent Child User as the literal string 'null'."""
        rows, _ = si.rows_from_values(
            HEADER_C, [row_c('t1', '8000400170001'), row_c('t2', '8000400170001', child='A Child')],
            'f.xlsx')
        self.assertFalse(rows[0].spender_is_child)
        self.assertTrue(rows[1].spender_is_child)

    def test_person_transfer_comes_from_duitnow_type_never_from_the_name(self):
        """⚠ Half the real merchants are people's names. Name-shape matching would file a
        student's daily meals as money sent to a friend."""
        rows, _ = si.rows_from_values(HEADER_C, [
            row_c('t1', '8000400170001', merchant='AZMI BIN BAKAR'),
            row_c('t2', '8000400170001', merchant='99 SPEEDMART',
                  duitnow=si.DUITNOW_P2P),
        ], 'f.xlsx')
        self.assertFalse(rows[0].is_person_transfer)   # a person's NAME, but a shop
        self.assertTrue(rows[1].is_person_transfer)    # a shop's name, but a person

    def test_a_spend_is_read_from_tx_type_not_entry_type(self):
        """⚠ Entry Type reads CREDIT on a spend — it is the counterparty's view."""
        rows, _ = si.rows_from_values(
            HEADER_C, [row_c('t1', '8000400170001', tx='Spend', entry='CREDIT')], 'f.xlsx')
        self.assertTrue(rows[0].is_spend)

    def test_merchant_and_wallet_are_normalised(self):
        rows, _ = si.rows_from_values(
            HEADER_C, [row_c('t1', ' 8000-4001 70001 ', merchant='99  Speedmart ')], 'f.xlsx')
        self.assertEqual(rows[0].merchant, '99 SPEEDMART')
        self.assertEqual(rows[0].wallet_id, '8000400170001')

    def test_blank_rows_are_skipped_but_nothing_else_is(self):
        rows, _ = si.rows_from_values(
            HEADER_C, [row_c('t1', '8000400170001'), [None] * 11], 'f.xlsx')
        self.assertEqual(len(rows), 1)


# ── the ingest ────────────────────────────────────────────────────────────────

class TestIngest(TestCase):
    def setUp(self):
        self.org = make_org()
        self.cohort = make_cohort(self.org)
        self.wallet = '8000400170001'
        self.app = make_app(self.cohort, self.org, self.wallet)

    def _ingest(self, value_rows, *, apply=False, header=None):
        rows, unknown = si.rows_from_values(header or HEADER_C, value_rows, 'f.xlsx')
        return si.ingest([('f.xlsx', rows, unknown)], apply=apply)

    def test_report_mode_writes_NOTHING(self):
        """⚠ Read-only BY CONSTRUCTION, not by intent."""
        report = self._ingest([row_c('t1', self.wallet)])
        self.assertEqual(report.rows_stored, 1)          # it would have stored one
        self.assertEqual(BursarySpendTxn.objects.count(), 0)   # and it stored none

    def test_apply_stores_and_joins_to_the_student(self):
        self._ingest([row_c('t1', self.wallet, amount='RM26.90')], apply=True)
        txn = BursarySpendTxn.objects.get(txn_id='t1')
        self.assertEqual(txn.application_id, self.app.id)
        self.assertEqual(txn.amount, D('26.90'))
        self.assertEqual(txn.category, '')               # the sorter has not run
        self.assertEqual(txn.decided_by, '')

    def test_running_twice_stores_nothing_the_second_time(self):
        self._ingest([row_c('t1', self.wallet)], apply=True)
        report = self._ingest([row_c('t1', self.wallet)], apply=True)
        self.assertEqual(BursarySpendTxn.objects.count(), 1)
        self.assertEqual(report.rows_stored, 0)
        self.assertEqual(report.rows_already_stored, 1)

    def test_an_identical_repeat_across_files_is_counted_and_stored_once(self):
        """⚠ 186 real rows repeated when the 2 Aug export ran a week early."""
        report = self._ingest([row_c('t1', self.wallet), row_c('t1', self.wallet)], apply=True)
        self.assertEqual(BursarySpendTxn.objects.count(), 1)
        self.assertEqual(report.repeats_identical, 1)
        self.assertFalse(report.repeats_conflicting)

    def test_a_repeat_that_DISAGREES_is_reported_and_not_stored(self):
        """⚠ A restated figure is a correction. Keeping the first copy silently freezes the
        wrong number into a sponsor's chart."""
        report = self._ingest(
            [row_c('t1', self.wallet, amount=5), row_c('t1', self.wallet, amount=50)], apply=True)
        self.assertEqual(BursarySpendTxn.objects.count(), 1)
        self.assertEqual(len(report.repeats_conflicting), 1)
        self.assertTrue(report.needs_attention)

    def test_an_unknown_wallet_is_skipped_and_named(self):
        report = self._ingest([row_c('t1', '8000400179999')], apply=True)
        self.assertEqual(BursarySpendTxn.objects.count(), 0)
        self.assertEqual(report.unknown_wallets, {'8000400179999': 1})
        self.assertTrue(report.needs_attention)

    def test_a_wallet_claimed_by_two_students_is_skipped_not_guessed(self):
        """⚠ Two siblings on one parent-held account. Picking either files one student's
        spending against the other."""
        make_app(self.cohort, self.org, self.wallet)
        report = self._ingest([row_c('t1', self.wallet)], apply=True)
        self.assertEqual(BursarySpendTxn.objects.count(), 0)
        self.assertIn(self.wallet, report.ambiguous_wallets)
        self.assertTrue(report.needs_attention)

    def test_an_unparseable_amount_is_counted_never_silently_dropped(self):
        """⚠ The fault this whole module was written against: a silent skip under-reported the
        real corpus by RM621 and nothing looked wrong."""
        report = self._ingest([row_c('t1', self.wallet, amount='n/a')], apply=True)
        self.assertEqual(BursarySpendTxn.objects.count(), 0)
        self.assertEqual(len(report.unparsed_amount), 1)
        self.assertTrue(report.needs_attention)

    def test_a_funded_student_with_no_wallet_is_a_separate_finding(self):
        """⚠ 'We do not know this wallet' and 'we hold no wallet for this student' are opposite
        faults with different fixes."""
        make_app(self.cohort, self.org, '')
        report = self._ingest([row_c('t1', self.wallet)])
        self.assertEqual(len(report.students_without_wallet), 1)
        self.assertFalse(report.unknown_wallets)

    def test_a_closed_student_with_no_wallet_is_not_a_finding(self):
        make_app(self.cohort, self.org, '', status='closed')
        report = self._ingest([row_c('t1', self.wallet)])
        self.assertFalse(report.students_without_wallet)

    def test_non_spend_rows_are_stored_and_excluded_from_the_spend_total(self):
        """⚠ Two real rows are RECEIVED. Dropping them at import would make the table unable to
        answer a question we were handed the data for."""
        report = self._ingest([
            row_c('t1', self.wallet, amount=5, tx='Spend'),
            row_c('t2', self.wallet, amount=7, tx='Received', entry='DEBIT'),
        ], apply=True)
        self.assertEqual(BursarySpendTxn.objects.count(), 2)
        self.assertEqual(report.spend_rows, 1)
        self.assertEqual(report.spend_total, D('5.00'))

    def test_coverage_comes_from_the_dates_inside_not_the_file_name(self):
        """⚠ The 26 July report covers FOURTEEN days. A missing file is not a missing week."""
        report = self._ingest([
            row_c('t1', self.wallet, when='13 Jul 2026'),
            row_c('t2', self.wallet, when='26 Jul 2026'),
        ])
        self.assertEqual(report.coverage_from, date(2026, 7, 13))
        self.assertEqual(report.coverage_to, date(2026, 7, 26))

    def test_a_clean_run_needs_no_attention(self):
        report = self._ingest([row_c('t1', self.wallet)], apply=True)
        self.assertFalse(report.needs_attention)


class TestCommandWiring(TestCase):
    """⚠ A unit test on a helper does not prove the helper is CALLED. This drives the real
    command over a real file, which is the test that would actually have failed."""

    def setUp(self):
        self.org = make_org()
        self.cohort = make_cohort(self.org)
        self.app = make_app(self.cohort, self.org, '8000400170001')

    def _write_xlsx(self, path, header, rows):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(header)
        for row in rows:
            ws.append(row)
        wb.save(path)

    def test_the_command_reads_a_file_and_report_mode_writes_nothing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'report.xlsx')
            self._write_xlsx(path, HEADER_C, [row_c('t1', '8000400170001', amount='RM9.60')])
            call_command('ingest_spending', file=[path])
            self.assertEqual(BursarySpendTxn.objects.count(), 0)
            call_command('ingest_spending', file=[path], apply=True)
            self.assertEqual(BursarySpendTxn.objects.get().amount, D('9.60'))


class TestRealCorpus(TestCase):
    """The acceptance criterion, run against the eight real exports when this machine has them.

    ⚠ SKIPS when the folder is absent — the corpus carries student names and wallet ids and is
    never committed, so CI must not depend on it. Applications are built FROM the wallets found
    in the files, so no real identity is needed to prove the whole path.
    """

    def test_the_eight_real_reports_reproduce_the_measured_figures(self):
        if not os.path.isdir(CORPUS_DIR):
            self.skipTest('real corpus not present on this machine')
        import glob
        paths = sorted(p for p in glob.glob(os.path.join(CORPUS_DIR, '*.xlsx'))
                       if not os.path.basename(p).startswith('~$'))
        if not paths:
            self.skipTest('no .xlsx in the corpus folder')

        sources = []
        wallets = set()
        for path in paths:
            rows, unknown = si.rows_from_xlsx(path)
            sources.append((os.path.basename(path), rows, unknown))
            wallets |= {r.wallet_id for r in rows if r.wallet_id}

        org = make_org(code='corpus-bp')
        cohort = make_cohort(org)
        for wallet in sorted(wallets):
            make_app(cohort, org, wallet)

        report = si.ingest(sources, apply=True)

        self.assertEqual(report.rows_stored, 1368, 'unique transactions')
        self.assertEqual(report.spend_rows, 1366, 'SPEND rows')
        self.assertEqual(report.spend_total, D('10650.22'), 'SPEND total')
        self.assertEqual(report.unparsed_amount, [], 'every amount must parse')
        self.assertEqual(report.unparsed_date, [], 'every date must parse')
        self.assertEqual(report.unknown_headers, set(), 'no unknown columns')
        self.assertEqual(report.coverage_from, date(2026, 7, 1))
        self.assertEqual(report.coverage_to, date(2026, 8, 30))
        self.assertEqual(
            BursarySpendTxn.objects.filter(spender_is_child=True).count(), 28,
            'parent-held wallets')
        self.assertEqual(
            BursarySpendTxn.objects.filter(is_person_transfer=True).count(), 2,
            'person-to-person rows')
