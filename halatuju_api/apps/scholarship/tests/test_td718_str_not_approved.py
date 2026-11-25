"""TD-718 — an STR page that says the application was received is not an approval (owner 2026-11-24).

Owner ruling: "To me this is a fail. Anyone can apply; so received application is a failed STR route.
The student must submit salary route."

As built:
  * a status reading "Permohonan Diterima" or "Dalam Proses Rayuan" (any case or spacing), with no
    approved word, is the new currency state 'not_approved' — red, as strong as a SALINAN
    ('wrong_type'): `str_not_breached` is False, the salary route applies, the gate asks with its own
    plain code `str_not_approved`.
  * it is reached only where the ladder said 'unreadable' before: another year still reads
    stale / future first, a rejection still wins, a non-STR stays wrong_type, an approved word wins.
  * a blank status stays 'unreadable' (amber).
  * the keep-better judge never lets such a page displace a live approved copy, and does not treat
    it as news like a rejection.
  * the parser keeps the words ONLY from the label-anchored status value, never from a body scan.

All data is invented.
"""
from django.test import SimpleTestCase, TestCase

from apps.scholarship.doc_parse import parse_by_labels
from apps.scholarship.tests.test_doc_parse import _BOTH_ORDERS, _currency, _semakan_page
from apps.scholarship.tests.test_td403_str_this_year import (
    ROUTES, _family, _income_fact, _income_gate, _payslip, _promotes, _upload_str)

PENDING = ('Permohonan Diterima', 'Dalam Proses', 'Dalam Proses Rayuan', 'PERMOHONAN  DITERIMA',
           'dalam proses\trayuan')

# Synthetic MySTR Semakan Status pages in the three real layouts (invented person, no real values).
_NAME, _NRIC = 'MEENA A/P TESTKUMAR', '850505105432'
_TAIL = ['Maklumat Pembayaran', 'Alasan Permohonan', 'Maklumat Anak', 'Kembali']


def _value(status, year):
    """The real two-line value: the status, then a planning line under it (only for 'received')."""
    if status.lower().startswith('permohonan'):
        return [status, f'- Permohonan akan diproses pada Disember {year}']
    return [status]


def _mobile(status, year='2026', icon='i', pedalaman='Ya (Sabah)'):
    label = ['Status Permohonan Semasa', icon] if icon else ['Status Permohonan Semasa']
    return '\n'.join(['Semakan Status', 'Maklumat Pemohon', 'Nama', _NAME, 'No. MyKad', _NRIC,
                      'Status Pedalaman', pedalaman] + label + _value(status, year) + _TAIL) + '\n'


def _desktop_rows(status, year='2026', icon='ⓘ'):
    first, *rest = _value(status, year)
    return '\n'.join(['Semakan Status', 'Maklumat Pemohon', f'Nama {_NAME}', f'No. MyKad {_NRIC}',
                      'Status Pedalaman Tidak', f'Status Permohonan Semasa {icon} {first}'] + rest + _TAIL) + '\n'


def _desktop_columns(status, year='2026'):
    """#104: all labels first, then all values."""
    return '\n'.join(['Semakan Status', 'Maklumat Pemohon', 'Nama', 'No. MyKad', 'Status Pedalaman',
                      'Status Permohonan Semasa ⓘ', _NAME, _NRIC, 'Tidak'] + _value(status, year) + _TAIL) + '\n'


class TheLadder(SimpleTestCase):
    def test_the_pending_words_read_not_approved_only_where_unreadable_was(self):
        from apps.scholarship.income_engine import _str_currency
        rows = []
        for word in PENDING:
            rows += [
                (word, '2026', 'semakan_status', 'not_approved'),
                (word, '', 'semakan_status', 'not_approved'),
                (word, '2026', 'dashboard', 'not_approved'),
                (word, '', 'letter', 'not_approved'),
                (word, '2025', 'semakan_status', 'stale'),      # another year is decided first
                (word, '2027', 'semakan_status', 'future'),
                (word, '2026', 'unknown', 'wrong_type'),        # not an STR at all, as before
            ]
        rows += [
            # An approved word anywhere in the status wins over a pending word.
            ('Lulus - Permohonan Diterima', '2026', 'semakan_status', 'current'),
            ('Dalam Proses Rayuan / Lulus Rayuan', '', 'dashboard', 'unconfirmed'),
            # A rejection still wins.
            ('Permohonan Diterima - Ditolak', '2026', 'semakan_status', 'rejected'),
            # TD-718 R3: the approved test is strict (whole-word Lulus), so "Dalam Proses KeLULUSan"
            # is no longer approved; it is in process, so not_approved. "Menunggu" is not a pending
            # word: amber. "Tidak Lulus" is a rejection. A Lulus still wins over "Dalam Proses".
            ('Dalam Proses Kelulusan', '2026', 'semakan_status', 'not_approved'),
            ('Menunggu Kelulusan', '2026', 'semakan_status', 'unreadable'),
            ('Tidak Lulus', '2026', 'semakan_status', 'rejected'),
            ('Lulus (Dalam Proses Bayaran)', '2026', 'semakan_status', 'current'),
            ('Lulus Rayuan', '2026', 'semakan_status', 'current'),
            # Blank stays amber.
            ('', '2026', 'semakan_status', 'unreadable'),
        ]
        for status, year, source, want in rows:
            with self.subTest(status=status, year=year, source=source):
                self.assertEqual(_str_currency(status, year, 2026, source), want)

    def test_it_is_red_failed_and_coached(self):
        from apps.scholarship.income_engine import STR_COACH_STATES, STR_FAILED_STATES, STR_RED_STATES
        self.assertIn('not_approved', STR_RED_STATES)
        self.assertIn('not_approved', STR_FAILED_STATES)
        self.assertIn('not_approved', STR_COACH_STATES)


class AReceivedPageIsAFailedStr(TestCase):
    def test_both_routes_block_and_ask_for_salary_papers(self):
        from apps.scholarship.income_engine import (has_valid_str, household_str_status,
                                                    member_income_evidenced, salary_income_satisfied,
                                                    str_confirmed_current, str_not_breached,
                                                    student_str_check)
        from apps.scholarship.resolution import doc_match_verdict
        from apps.scholarship.serializers import ApplicantDocumentSerializer
        from apps.scholarship.services import consent_blockers
        for status in ('Permohonan Diterima', 'Dalam Proses', 'Dalam Proses Rayuan'):
            for route in ROUTES:
                with self.subTest(status=status, route=route):
                    app, str_doc = _family(route, year='2026', status=status)
                    self.assertEqual(student_str_check(str_doc)['current_status'], 'not_approved')
                    self.assertIs(str_not_breached(app), False)
                    self.assertIs(member_income_evidenced(app, 'father'), False)
                    self.assertEqual(household_str_status(app), (None, None))
                    self.assertIs(has_valid_str(app), False)
                    self.assertIs(str_confirmed_current(app), False)
                    self.assertIs(salary_income_satisfied(app), False)
                    gate = _income_gate(app)
                    self.assertIn('str_not_approved', gate)
                    self.assertNotIn('str_person_mismatch', gate)   # never "doesn't match"
                    self.assertIn('str_not_approved', consent_blockers(app))
                    self.assertEqual(doc_match_verdict(str_doc), 'mismatch')   # closes no request
                    chip = ApplicantDocumentSerializer(str_doc).data['str_check']
                    self.assertEqual(chip['current_status'], 'not_approved')

    def test_the_salary_route_also_asks_for_the_earners_income(self):
        app, _ = _family('salary', year='2026', status='Permohonan Diterima')
        self.assertIn('income_evidence_missing:father', _income_gate(app))

    def test_real_salary_proof_carries_the_household(self):
        from apps.scholarship.income_engine import member_income_evidenced
        for route in ROUTES:
            with self.subTest(route=route):
                app, _ = _family(route, year='2026', status='Permohonan Diterima')
                _payslip(app)
                self.assertIs(member_income_evidenced(app, 'father'), True)
                self.assertNotIn('str_person_mismatch', _income_gate(app))

    def test_a_blank_status_stays_amber_and_passes_as_before(self):
        from apps.scholarship.income_engine import str_not_breached, student_str_check
        app, str_doc = _family('str', year='2026', status='')
        self.assertEqual(student_str_check(str_doc)['current_status'], 'unreadable')
        self.assertIs(str_not_breached(app), True)

    def test_the_verdict_fails_the_str_and_names_the_state(self):
        app, _ = _family('str', year='2026', status='Permohonan Diterima')
        fact = _income_fact(app)
        self.assertNotEqual(fact['status'], 'verified')
        items = [i for i in fact['unresolved'] if i['code'] == 'str_not_current']
        self.assertEqual([i['params'].get('status') for i in items], ['not_approved'])
        self.assertNotIn('str_verified', [i['code'] for i in fact['evidence']])

    def test_the_officer_gloss_names_it(self):
        from apps.scholarship.verdict_narrative import _CODE_GLOSS
        self.assertIn('not an approval', _CODE_GLOSS['str_not_current']['not_approved'])


class TheKeepBetterJudge(TestCase):
    def test_a_received_page_never_replaces_a_live_approved_copy(self):
        for live_status, live_year, live_src in (('Lulus', '2026', 'semakan_status'),
                                                 ('Lulus', '', 'dashboard')):
            with self.subTest(live=(live_status, live_year, live_src)):
                app, live = _family('str', year=live_year, status=live_status, source_type=live_src)
                new = _upload_str(app, year='2026', status='Permohonan Diterima')
                self.assertIs(_promotes(new, live), False)

    def test_it_is_not_news_like_a_rejection(self):
        from apps.scholarship.income_engine import str_proof_quality
        app, _live = _family('str', year='2026', status='Lulus')
        pending = _upload_str(app, year='2026', status='Dalam Proses Rayuan')
        rejected = _upload_str(app, year='2026', status='Ditolak')
        self.assertIsNotNone(str_proof_quality(pending))
        self.assertIsNone(str_proof_quality(rejected))

    def test_an_approved_copy_replaces_it(self):
        app, live = _family('str', year='2026', status='Permohonan Diterima')
        new = _upload_str(app, year='2026', status='Lulus')
        self.assertIs(_promotes(new, live), True)


class TheParserKeepsOnlyTheLabelledStatus(SimpleTestCase):
    def test_the_label_anchored_value_is_kept(self):
        for word, stored in (('Permohonan Diterima', 'Permohonan Diterima'),
                             ('Dalam Proses Rayuan', 'Dalam Proses Rayuan'),
                             ('PERMOHONAN   DITERIMA', 'PERMOHONAN DITERIMA'),
                             ('dalam proses rayuan.', 'dalam proses rayuan')):
            with self.subTest(word=word):
                r = parse_by_labels('str', _semakan_page(word))
                self.assertEqual(r['status'], stored)
                self.assertEqual(_currency(r), 'not_approved')

    def test_the_real_layouts_end_red(self):
        pages = []
        for icon in ('i', 'ⓘ', '(i)', ''):
            pages += [('mobile', icon, _mobile('Permohonan Diterima', icon=icon)),
                      ('mobile', icon, _mobile('Dalam Proses', icon=icon, pedalaman='Tidak'))]
        for icon in ('i', 'ⓘ', '(i)'):
            pages += [('mobile icon on the label line', icon,
                       _mobile('Permohonan Diterima', icon='').replace(
                           'Status Permohonan Semasa\n', f'Status Permohonan Semasa {icon}\n'))]
        for icon in ('i', 'ⓘ', '(i)', ''):
            pages += [('desktop rows', icon, _desktop_rows('Permohonan Diterima', icon=icon)),
                      ('desktop rows', icon, _desktop_rows('Dalam Proses', icon=icon))]
        pages += [('desktop columns (#104)', 'ⓘ', _desktop_columns('Permohonan Diterima'))]
        for layout, icon, page in pages:
            with self.subTest(layout=layout, icon=icon, page=page[60:120]):
                r = parse_by_labels('str', page)
                self.assertEqual(r['source_type'], 'semakan_status')
                self.assertIn(r['status'].lower(), ('permohonan diterima', 'dalam proses'))
                self.assertEqual(r['year'] or '2026', '2026')
                self.assertEqual(r['recipient_nric'].replace('-', ''), _NRIC)
                self.assertEqual(_currency(r), 'not_approved')

    def test_the_planning_line_gives_the_year_and_never_confuses_the_status(self):
        for year, want in (('2026', 'not_approved'), ('2025', 'stale'), ('2027', 'future')):
            for build in (_mobile, _desktop_rows, _desktop_columns):
                with self.subTest(year=year, layout=build.__name__):
                    r = parse_by_labels('str', build('Permohonan Diterima', year=year))
                    self.assertEqual(r['status'], 'Permohonan Diterima')   # never "akan diproses"
                    self.assertEqual(r['year'], year)
                    self.assertEqual(_currency(r), want)

    def test_a_bare_dalam_proses_in_the_columns_layout_stays_amber(self):
        # Decided, not missed: the #104 rescue takes ONLY the full phrase "Permohonan Diterima".
        r = parse_by_labels('str', _desktop_columns('Dalam Proses'))
        self.assertEqual(r['status'], '')
        self.assertEqual(_currency(r), 'unreadable')

    def test_the_rescue_never_fires_with_a_payment_row_or_a_status_token(self):
        with_payment = _desktop_columns('Permohonan Diterima').replace(
            'Maklumat Pembayaran\n', 'Maklumat Pembayaran\n15/03/2026\nRM 150\n')
        self.assertEqual(parse_by_labels('str', with_payment)['status'], '')
        approved = _desktop_columns('Lulus') + 'Sejarah\nPermohonan Diterima\n'
        r = parse_by_labels('str', approved)
        self.assertEqual((r['status'], _currency(r)), ('Lulus', 'unconfirmed'))   # no year on it: as before

    def test_a_body_only_mention_is_not_stored(self):
        page = _semakan_page('Menunggu Kelulusan') + 'Sejarah Permohonan\nPermohonan Diterima\n'
        r = parse_by_labels('str', page)
        self.assertEqual(r['status'], '')
        self.assertEqual(_currency(r), 'unreadable')
        page = _semakan_page('Menunggu Kelulusan') + 'Sejarah Permohonan\nDalam Proses\n'
        self.assertEqual(parse_by_labels('str', page)['status'], '')

    def test_label_debris_is_not_a_status(self):
        r = parse_by_labels('str', _semakan_page('Tarikh Permohonan Diterima 01/02/2026'))
        self.assertEqual(r['status'], '')

    def test_an_approved_page_with_a_history_line_stays_approved(self):
        for columns in _BOTH_ORDERS:
            with self.subTest(columns=columns):
                page = _semakan_page('Lulus', columns=columns) + 'Sejarah\nPermohonan Diterima\n'
                r = parse_by_labels('str', page)
                self.assertEqual(r['status'], 'Lulus')
                self.assertEqual(_currency(r), 'current')

    def test_the_older_columns_fixture_with_payment_rows_stays_amber(self):
        # The test_doc_parse page carries RM payment rows, so the #104 rescue must not fire there.
        r = parse_by_labels('str', _semakan_page('Permohonan Diterima', columns=True))
        self.assertEqual(r['status'], '')
        self.assertEqual(_currency(r), 'unreadable')
