"""The written summary filed back to Drive — S4b.

⚠ **THE THREE TESTS THAT CARRY THIS FILE ARE WRITTEN FROM THE HARM:**

  * `TestWeNeverReadOurOwnOutput` asserts the generated filename against **the reader's own
    regex**, imported from `sheets`, not against a copy of it. If somebody renames the summary to
    something date-led tomorrow, the next import would try to parse it as a Vircle export, fail on
    the header, refuse the file and email a fault every single day for ever.
  * `TestTheModelCannotInventAFigure` — the prompt says "never invent a number", and a prompt is a
    request. `_numbers_agree` is the rule, and these tests are what make it one: prose containing a
    total nobody supplied is DISCARDED, and the figures beneath it are unaffected.
  * `TestADriveHiccupBreaksNothing` — the import has already stored and sorted everything by the
    time the summary runs. A Drive failure must cost a document and nothing else.
"""
import datetime
import re
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile  # noqa: F401
from apps.scholarship import sheets, spend_summary as ss, spending_import as si
from apps.scholarship.models import (
    BursarySpendTxn, Programme, ScholarshipApplication, ScholarshipCohort,
)

D = Decimal
_SEQ = {'n': 0}
TEXT_SEAM = 'apps.scholarship.profile_engine._call_gemini_text'
TODAY = datetime.date(2026, 9, 10)


def make_app(wallet='8000400170001'):
    _SEQ['n'] += 1
    i = _SEQ['n']
    org = PartnerOrganisation.objects.create(code=f'sum{i}', name='BrightPath')
    programme, _ = Programme.objects.get_or_create(
        organisation=org, code=f'{org.code}-prog', defaults={'name_en': 'Bursary'})
    cohort = ScholarshipCohort.objects.create(
        code=f'{org.code}-c', name='B40', year=2026, owning_organisation=org, programme=programme)
    profile = StudentProfile.objects.create(
        supabase_user_id=f'sum-stud-{i}', nric=f'{i:06d}-17-{i:04d}',
        name=f'Student {i}', contact_phone=f'04{i:08d}')
    return ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, owning_organisation=org, status='awarded',
        chosen_pathway='matric', award_amount=D('2000'), vircle_id=wallet)


def txn(app, merchant, amount, *, source='r.xlsx', category='food', decided_by='rule'):
    _SEQ['n'] += 1
    return BursarySpendTxn.objects.create(
        application=app, txn_id=f'U{_SEQ["n"]:08d}', txn_date=datetime.date(2026, 8, 30),
        wallet_id=app.vircle_id, merchant=si.norm_text(merchant), amount=D(str(amount)),
        duitnow_type='STATIC_MERCHANT_QR_CODE_DUITNOW', entry_type='CREDIT', tx_type='SPEND',
        status='00', category=category, decided_by=decided_by, source_file=source)


def a_report(**over):
    """An `IngestReport` shaped like a real successful run."""
    r = si.IngestReport()
    r.files = [('r.xlsx', 200, 180)]
    r.rows_stored = 180
    r.rows_already_stored = 20
    r.coverage_from = datetime.date(2026, 8, 24)
    r.coverage_to = datetime.date(2026, 8, 30)
    r.spend_rows = 178
    r.spend_total = D('1234.50')
    for key, value in over.items():
        setattr(r, key, value)
    return r


def prose(text):
    return {'markdown': text, 'model_used': 'test'}


# ── the two locks ─────────────────────────────────────────────────────────────

class TestWeNeverReadOurOwnOutput(TestCase):
    """⚠⚠ A summary the next import tries to parse is a fault email every day for ever."""

    def test_the_filename_cannot_match_the_readers_own_pattern(self):
        # ⚠ The reader's REGEX, imported — not a copy. A copy drifts and this guard goes quiet.
        name = ss.summary_filename({'today': TODAY})
        self.assertIsNone(sheets._SPENDING_FILENAME_RE.match(name),
                          f'{name!r} would be read back in as a Vircle export')

    def test_a_real_vircle_export_name_still_matches_that_pattern(self):
        """The floor. If the regex stopped matching anything, the test above would pass while
        protecting nothing."""
        self.assertIsNotNone(sheets._SPENDING_FILENAME_RE.match(
            '2026-08-30 BrightPath Bursary_Bursary Usage Report_Table'))

    def test_the_filename_leads_with_words_not_a_date(self):
        name = ss.summary_filename({'today': TODAY})
        self.assertTrue(name.startswith(ss.FILENAME_STEM))
        self.assertNotRegex(name, r'^\d{4}-\d{2}-\d{2}')

    def test_the_stem_itself_is_a_word_and_cannot_be_emptied(self):
        """⚠ FOUND BY A SILENT BITE-CHECK, 2026-09-10.

        Emptying `FILENAME_STEM` failed nothing: the name became `' 2026-09-10.md'`, which still
        does not match the reader's pattern — by accident, on a leading space. The guard above was
        testing the COMBINATION and not the thing that has to hold. The stem is what keeps the
        date off the front, so pin the stem: a non-empty word, starting with a letter.
        """
        self.assertTrue(ss.FILENAME_STEM.strip(), 'the stem may never be empty')
        self.assertTrue(ss.FILENAME_STEM[0].isalpha(),
                        'the stem must start with a letter, so no date can lead the name')
        self.assertNotIn('usage report', ss.FILENAME_STEM.lower(),
                         "the reader's pattern also looks for these words")

    def test_no_date_in_the_year_produces_a_readable_name(self):
        """The pattern is date-shaped, so walk a year rather than trusting one example."""
        day = datetime.date(2026, 1, 1)
        while day.year == 2026:
            name = ss.summary_filename({'today': day})
            self.assertIsNone(sheets._SPENDING_FILENAME_RE.match(name), name)
            day += datetime.timedelta(days=17)

    def test_it_is_written_into_the_SUBFOLDER_not_beside_the_exports(self):
        """Lock one. The folder is a level below the one the reader walks."""
        with self.settings(VIRCLE_SPENDING_SUMMARY_FOLDER='A/B/06 Student Spending/Summaries'):
            with mock.patch(TEXT_SEAM, return_value=prose('All quiet.')), \
                 mock.patch('apps.scholarship.sheets.file_text_to_folder',
                            return_value='http://x') as write:
                ss.file_summary(a_report(), today=TODAY)
        folder = write.call_args[0][0]
        self.assertTrue(folder.endswith('/Summaries'), folder)


# ── the deterministic guard on the prose ──────────────────────────────────────

class TestTheModelCannotInventAFigure(TestCase):
    """⚠⚠ The prompt asks; `_numbers_agree` decides."""

    def setUp(self):
        self.facts = ss.build_facts(a_report(), today=TODAY)

    def test_prose_repeating_a_figure_we_gave_it_is_kept(self):
        with mock.patch(TEXT_SEAM, return_value=prose('A steady week: RM1234.50 across 178 '
                                                      'payments, nothing needing attention.')):
            self.assertNotEqual(ss.render_prose(self.facts), '')

    def test_prose_inventing_a_total_is_DISCARDED(self):
        with mock.patch(TEXT_SEAM, return_value=prose('Students spent RM9999.99 this week.')):
            self.assertEqual(ss.render_prose(self.facts), '')

    def test_prose_inventing_a_COUNT_is_discarded_too(self):
        with mock.patch(TEXT_SEAM, return_value=prose('There were 4321 payments.')):
            self.assertEqual(ss.render_prose(self.facts), '')

    def test_ordinary_small_numbers_and_words_are_fine(self):
        with mock.patch(TEXT_SEAM, return_value=prose('A quiet week, with 2 things worth a look '
                                                      'and nothing urgent.')):
            self.assertNotEqual(ss.render_prose(self.facts), '')

    def test_a_thousands_separator_is_not_treated_as_a_different_number(self):
        with mock.patch(TEXT_SEAM, return_value=prose('Spending came to RM1,234.50.')):
            self.assertNotEqual(ss.render_prose(self.facts), '')

    def test_the_figures_survive_the_prose_being_dropped(self):
        """⚠ Losing the prose must never lose the numbers — they are the point of the document."""
        with mock.patch(TEXT_SEAM, return_value=prose('Students spent RM9999.99 this week.')):
            with mock.patch('apps.scholarship.sheets.file_text_to_folder',
                            return_value='http://x') as write:
                out = ss.file_summary(a_report(), folder_path='A/Summaries', today=TODAY)
        self.assertFalse(out['prose'])
        self.assertTrue(out['filed'])
        body = write.call_args[0][2]
        self.assertIn('RM1234.50', body)
        self.assertNotIn('9999.99', body)

    def test_a_model_failure_files_the_figures_anyway(self):
        with mock.patch(TEXT_SEAM, return_value={'error': 'quota'}):
            self.assertEqual(ss.render_prose(self.facts), '')


# ── what the prompt is given ──────────────────────────────────────────────────

class TestThePrompt(TestCase):

    def test_it_is_told_todays_date(self):
        """⚠ A weekly summary reasons about dates constantly, and the model does not know what day
        it is (lesson, 2026-06-20)."""
        facts = ss.build_facts(a_report(), today=TODAY)
        self.assertIn('2026-09-10', ss._facts_for_prompt(facts))

    def test_it_carries_the_hard_rules(self):
        self.assertIn('NEVER invent', ss._PROMPT_HEAD)
        self.assertIn('Name no student', ss._PROMPT_HEAD)

    def test_it_goes_through_the_shared_text_seam_and_is_metered(self):
        facts = ss.build_facts(a_report(), today=TODAY)
        with mock.patch(TEXT_SEAM, return_value=prose('Quiet.')) as seam:
            ss.render_prose(facts)
        self.assertEqual(seam.call_count, 1)


# ── the document ──────────────────────────────────────────────────────────────

class TestTheDocument(TestCase):

    def setUp(self):
        self.app = make_app()
        txn(self.app, 'DELIMA MATANG CAFE', 30, category='food')
        txn(self.app, '99 SPEEDMART', 70, category='groceries')
        txn(self.app, 'EY VENTURE', 5, category='unsorted', decided_by='')

    def test_every_figure_is_computed_from_the_stored_rows(self):
        facts = ss.build_facts(a_report(), today=TODAY)
        by_code = {r['code']: r for r in facts['categories']}
        self.assertEqual(by_code['food']['total'], D('30.00'))
        self.assertEqual(by_code['groceries']['total'], D('70.00'))
        self.assertEqual(by_code['unsorted']['payments'], 1)

    def test_it_names_shops_because_it_is_internal(self):
        facts = ss.build_facts(a_report(), today=TODAY)
        self.assertIn('99 SPEEDMART', ss.figures_block(facts))

    def test_it_names_no_student(self):
        """⚠ We never stored one, and per-student lines would turn an operational note into a file
        about people. Wallets and application ids only, exactly as the alert email does."""
        facts = ss.build_facts(a_report(), today=TODAY)
        body = ss.summary_text(facts, 'A quiet week.')
        self.assertNotIn(self.app.profile.name, body)

    def test_it_says_it_must_not_reach_a_sponsor(self):
        facts = ss.build_facts(a_report(), today=TODAY)
        self.assertIn('sponsor', ss.summary_text(facts, '').lower())

    def test_it_stamps_the_prompt_version_into_the_DOCUMENT(self):
        """⚠ Into the document, not merely a field — a reader holding the file can tell which
        prompt produced it."""
        facts = ss.build_facts(a_report(), today=TODAY)
        self.assertIn(ss.PROMPT_VERSION, ss.summary_text(facts, 'Quiet.'))

    def test_a_run_that_needs_a_human_says_so_in_the_document(self):
        report = a_report(unknown_wallets={'8000400179999': 3},
                          students_without_wallet=[41, 42])
        facts = ss.build_facts(report, today=TODAY)
        block = ss.figures_block(facts)
        self.assertIn('Needs a human', block)
        self.assertIn('8000400179999', block)
        self.assertIn('41', block)

    def test_a_clean_run_has_no_needs_a_human_section(self):
        facts = ss.build_facts(a_report(), today=TODAY)
        self.assertNotIn('Needs a human', ss.figures_block(facts))


# ── best effort ───────────────────────────────────────────────────────────────

class TestADriveHiccupBreaksNothing(TestCase):
    """⚠ Everything is already stored and sorted by the time this runs. A Drive failure costs a
    document and nothing else — and is REPORTED, because a summary that silently never appears is
    indistinguishable from a week nobody opened the folder."""

    def test_a_failed_write_is_reported_not_raised(self):
        with mock.patch(TEXT_SEAM, return_value=prose('Quiet.')), \
             mock.patch('apps.scholarship.sheets.file_text_to_folder', return_value=None):
            out = ss.file_summary(a_report(), folder_path='A/Summaries', today=TODAY)
        self.assertFalse(out['filed'])
        self.assertIn('could not write', out['error'])

    def test_an_exception_inside_drive_is_swallowed_and_reported(self):
        with mock.patch(TEXT_SEAM, return_value=prose('Quiet.')), \
             mock.patch('apps.scholarship.sheets.file_text_to_folder',
                        side_effect=RuntimeError('boom')):
            out = ss.file_summary(a_report(), folder_path='A/Summaries', today=TODAY)
        self.assertFalse(out['filed'])
        self.assertIn('boom', out['error'])

    def test_no_folder_configured_is_reported_not_a_crash(self):
        with self.settings(VIRCLE_SPENDING_SUMMARY_FOLDER=''):
            with mock.patch(TEXT_SEAM, return_value=prose('Quiet.')):
                out = ss.file_summary(a_report(), today=TODAY)
        self.assertFalse(out['filed'])
        self.assertIn('no summary folder', out['error'])


class TestTheCsvWriterStillBehavesAsItDid(TestCase):
    """⚠ S4b GENERALISED `file_csv_to_folder` into `file_text_to_folder` and made the CSV helper
    delegate. Its one real caller — the Vircle activation-request archive — had **no test at all**,
    so the rewiring was unguarded until this bite-check went looking. What must not drift: the
    mimetype stays `text/csv`, and it must NOT create a missing folder (only an output folder we
    own may be created, and that archive folder is not one)."""

    def test_it_delegates_with_the_csv_mimetype(self):
        with mock.patch('apps.scholarship.sheets.file_text_to_folder',
                        return_value='http://x') as write:
            url = sheets.file_csv_to_folder('03 Vircle/01 Payment', 'run.csv', 'a,b\n1,2')
        self.assertEqual(url, 'http://x')
        self.assertEqual(write.call_args[0], ('03 Vircle/01 Payment', 'run.csv', 'a,b\n1,2'))
        self.assertEqual(write.call_args[1]['mimetype'], 'text/csv')

    def test_it_does_NOT_create_a_missing_folder(self):
        """A CSV lands in a folder somebody else maintains. Conjuring it when the name is wrong
        would hide a misconfiguration behind a new empty folder."""
        with mock.patch('apps.scholarship.sheets.file_text_to_folder',
                        return_value=None) as write:
            sheets.file_csv_to_folder('03 Vircle/01 Payment', 'run.csv', 'a,b')
        self.assertFalse(write.call_args[1].get('create_missing', False))

    def test_a_missing_folder_is_still_a_quiet_None(self):
        with mock.patch('apps.scholarship.sheets.file_text_to_folder', return_value=None):
            self.assertIsNone(sheets.file_csv_to_folder('nope', 'run.csv', 'a,b'))


class TestFilingTheSameNameTwice(TestCase):
    """⚠⚠ **FOUND ON THE OWNER'S REAL DRIVE, 2026-09-12.** The daily job filed
    `Spending summary 2026-09-12.md` at 07:00; the recovery run filed ANOTHER at 09:03. Drive keeps
    both — same folder, same name, **different figures**, because the 07:00 one was written before
    a month of missing spending was recovered.

    That is not clutter, it is two documents with one name disagreeing about a total, and a reader
    has no way to tell which is true. `_find_or_create_sheet` already carried this reasoning for
    the relay spreadsheet; the text path simply never got it.
    """

    def _drive(self, existing):
        """A fake Drive. `existing` is what `files().list` finds in the folder."""
        drive = mock.MagicMock()
        drive.files.return_value.list.return_value.execute.return_value = {'files': existing}
        drive.files.return_value.create.return_value.execute.return_value = {
            'id': 'new-id', 'webViewLink': 'http://new'}
        drive.files.return_value.update.return_value.execute.return_value = {
            'id': 'old-id', 'webViewLink': 'http://updated'}
        return drive

    def _write(self, drive):
        with mock.patch('apps.scholarship.sheets.sheets_enabled', return_value=True),              mock.patch('apps.scholarship.sheets._drive_for_upload', return_value=drive),              mock.patch('apps.scholarship.sheets._find_folder_path', return_value='parent'),              mock.patch('apps.scholarship.sheets._find_or_create_folder', return_value='folder'):
            return sheets.file_text_to_folder(
                'A/B/Summaries', 'Spending summary 2026-09-12.md', 'body',
                mimetype='text/markdown', create_missing=True)

    def test_filing_the_same_name_REPLACES_it_and_never_adds_a_second(self):
        drive = self._drive([{'id': 'old-id', 'name': 'Spending summary 2026-09-12.md'}])
        url = self._write(drive)
        drive.files.return_value.update.assert_called_once()
        drive.files.return_value.create.assert_not_called()
        self.assertEqual(drive.files.return_value.update.call_args[1]['fileId'], 'old-id')
        self.assertEqual(url, 'http://updated')

    def test_it_looks_ONLY_INSIDE_THIS_FOLDER_and_ignores_the_bin(self):
        """⚠⚠ FOUND BY A SILENT BITE. The tests above mock `files().list` and never read the QUERY,
        so a lookup that searched the whole Drive passed both of them — and that version would
        overwrite a same-named file in somebody else's folder, which is a far worse fault than the
        duplicate it was fixing. A trashed match matters too: silently updating a document in the
        bin means the summary is filed nowhere a person will look."""
        drive = self._drive([{'id': 'old-id', 'name': 'Spending summary 2026-09-12.md'}])
        self._write(drive)
        q = drive.files.return_value.list.call_args[1]['q']
        self.assertIn("'folder' in parents", q)
        self.assertIn('trashed=false', q)
        self.assertIn("name='Spending summary 2026-09-12.md'", q)

    def test_a_name_never_written_before_is_still_CREATED(self):
        drive = self._drive([])
        url = self._write(drive)
        drive.files.return_value.create.assert_called_once()
        drive.files.return_value.update.assert_not_called()
        self.assertEqual(url, 'http://new')


# ── the command wiring ────────────────────────────────────────────────────────

@override_settings(VIRCLE_SPENDING_SUMMARY_FOLDER='A/B/Summaries')
class TestIngestFilesTheSummary(TestCase):

    def setUp(self):
        self.app = make_app()

    def _values(self):
        header = ['transaction_date', 'wallet_id', 'transaction_id', 'Wallet User', 'Child User',
                  'Merchant Name', 'duitnow_type', 'Entry Type', 'TX Type', 'amount', 'Status']
        row = ['30 Aug 2026', self.app.vircle_id, 'TX-SUM-1', 'Holder', 'null',
               'DELIMA MATANG CAFE', 'STATIC_MERCHANT_QR_CODE_DUITNOW', 'CREDIT', 'SPEND', 5, '00']
        return [header, row]

    def _run(self, *flags):
        from django.core.management import call_command
        with mock.patch('apps.scholarship.sheets.spending_reports_in',
                        return_value=[('f1', 'r.xlsx', None)]), \
             mock.patch('apps.scholarship.sheets.read_spending_report',
                        return_value=self._values()), \
             mock.patch('apps.scholarship.vision._call_gemini_json'), \
             mock.patch(TEXT_SEAM, return_value=prose('A quiet week.')), \
             mock.patch('apps.scholarship.sheets.file_text_to_folder',
                        return_value='http://drive/x') as write:
            call_command('ingest_spending', '--drive', '--no-email', *flags)
        return write

    def test_an_apply_run_files_a_summary(self):
        write = self._run('--apply')
        self.assertEqual(write.call_count, 1)
        self.assertIn(ss.FILENAME_STEM, write.call_args[0][1])

    def test_no_summary_opts_out(self):
        self.assertEqual(self._run('--apply', '--no-summary').call_count, 0)

    def test_a_report_run_writes_nothing_to_drive_either(self):
        """⚠ Report mode must be unable to write ANYTHING, Drive included."""
        self.assertEqual(self._run().call_count, 0)

    def test_a_run_that_stored_nothing_files_nothing(self):
        BursarySpendTxn.objects.create(
            application=self.app, txn_id='TX-SUM-1', txn_date=datetime.date(2026, 8, 30),
            wallet_id=self.app.vircle_id, merchant='DELIMA MATANG CAFE', amount=D('5.00'),
            tx_type='SPEND', status='00', source_file='r.xlsx')
        self.assertEqual(self._run('--apply').call_count, 0)
