"""The UMS rules read (OCR-first S1, 2026-11-19): `offer_parse_university.read_ums`, its hook in
`offer_parse.diagnose`, the lane name on the Exact read, and Gate 2's last checks
(`offer_exact.rules_lane_verdict`: the lane switch + one pinned catalogue course) in the vision offer branch.

Synthetic twins only — invented names, ICs and hostels (`test_no_gitignored_corpus.py`)."""
import os
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.scholarship import vision
from apps.scholarship.models import ApplicantDocument
from apps.scholarship import pdf_pages
from apps.scholarship.offer_course_match import letter_level
from apps.scholarship.offer_exact import exact_read, ocr_first_lanes, rules_lane_open, rules_lane_verdict
from apps.scholarship.offer_parse import diagnose, parse_govt_offer
from apps.scholarship.offer_parse_university import LANE, read_ums
from apps.scholarship.tests.factories import make_application
from apps.scholarship.tests.test_offer_reader import png

NAME, NRIC = 'ZORBEX A/L QUENTARO', '010203-14-5678'
PROG = 'Ijazah Sarjana Muda Sains Komputer Dengan Kepujian'
HOSTEL = 'Kolej Kediaman Zantharion'
MATCH = 'apps.scholarship.offer_course_match.match_offer_course'
PINNED = 'apps.scholarship.offer_course_match.pinned_match'
LEVEL = 'apps.scholarship.offer_course_match.course_level'
ONE = ('', {'course_id': 'uh6481001', 'institution': 'Universiti Malaysia Sabah'})


def ums(name=NAME, nric=NRIC, prog_line=PROG, said=PROG, report='28-29 September 2031', extra_head='',
        title='TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA SABAH SESI I-2031/2032', top='',
        kampus='Kampus :      Kota Kinabalu', code='Kod Program :      UH6481001'):
    """A synthetic UMS letter in the layout shape (label and value on one line, padded columns): the label
    block (Program / Kod Program / Fakulti / Kampus) sits between the title and the "untuk mendapat" sentence."""
    return f"""{top}UNIVERSITI MALAYSIA SABAH
Rujukan Kami :      UMS/PPA/100-1/2/3
Tarikh :      15 Ogos 2031
{name}
No. Kad Pengenalan :      {nric}
No. Pelajar :      BK31110410
{extra_head}Jalan Zantharion 7, 88000 Kota Kinabalu
{title}
Program :      {prog_line}
{code}
Fakulti :      Fakulti Komputeran dan Informatik
{kampus}
Dengan sukacitanya dimaklumkan bahawa saudara ditawarkan kemasukan untuk mendapat
{said} dan sebanyak 128 jam kredit diperlukan.
Tarikh Lapor Diri :      {report}
Tempat / Kolej :      {HOSTEL}
"""


class TestTheRulesRead(SimpleTestCase):
    def test_a_well_formed_letter_reads_every_field(self):
        f, reason = read_ums(ums())
        self.assertEqual(reason, '')
        self.assertEqual(f['candidate_name'], NAME)
        self.assertEqual(f['candidate_nric'], NRIC)
        self.assertEqual(f['candidate_nric_source'], 'label')
        self.assertEqual(f['programme'], PROG)
        self.assertEqual(f['programme_code'], 'UH6481001')
        self.assertEqual(f['intake'], 'SESI I-2031/2032')
        self.assertEqual(f['campus'], 'Kota Kinabalu')
        self.assertEqual(f['offer_date'], '15 Ogos 2031')

    def test_the_institution_is_the_title_and_the_hostel_is_only_the_venue(self):
        f, _r = read_ums(ums())
        self.assertEqual(f['institution'], 'Universiti Malaysia Sabah')
        self.assertEqual(f['issuer'], 'Universiti Malaysia Sabah')
        self.assertEqual(f['reporting_venue'], HOSTEL)

    def test_a_day_range_reports_on_its_first_day_and_a_full_range_too(self):
        self.assertTrue(read_ums(ums())[0]['reporting_date'].startswith('28'))
        f, reason = read_ums(ums(report='12 September 2031 - 13 September 2031'))
        self.assertEqual(reason, '')
        self.assertTrue(f['reporting_date'].startswith('12'))

    def test_a_scanned_letter_one_item_per_line_reads_the_same(self):
        text = ums().replace('Tarikh :      15 Ogos 2031', 'Tarikh :\n15 Ogos 2031')
        self.assertEqual(read_ums(text)[1], '')

    def test_a_status_letter_never_locks(self):
        self.assertEqual(read_ums(ums(top='SURAT PENGESAHAN PELAJAR\n'))[1], 'status_letter')

    def test_the_blank_template_does_not_lock(self):
        f, reason = read_ums(ums(name='', nric='', report=''))
        self.assertTrue(reason.startswith('empty:'))
        self.assertIn('candidate_name', reason)

    def test_an_ic_without_its_label_is_never_read(self):
        text = ums().replace('No. Kad Pengenalan :      ' + NRIC, 'No. Kad Pengenalan :') + NRIC + '\n'
        f, reason = read_ums(text)
        self.assertEqual(f['candidate_nric'], '')
        self.assertIn('candidate_nric', reason)

    def test_a_second_ic_in_the_head_refuses_the_ic(self):
        f, _r = read_ums(ums(extra_head='Waris : 750101-12-9999\n'))
        self.assertEqual(f['candidate_nric'], '')

    def test_a_programme_line_that_disagrees_with_the_sentence_is_not_read(self):
        f, reason = read_ums(ums(said='Ijazah Sarjana Muda Sains Marin Dengan Kepujian'))
        self.assertEqual(f['programme'], '')
        self.assertIn('programme', reason)

    def test_a_reporting_date_outside_the_intake_is_not_sane(self):
        self.assertEqual(read_ums(ums(report='28 September 2035'))[1], 'dates_not_sane')

    def test_a_certifier_stamp_line_is_never_the_name(self):
        f, _r = read_ums(ums(name='DISAHKAN SALINAN SEBENAR'))
        self.assertEqual(f['candidate_name'], '')


class TestTheDiagnoseHook(SimpleTestCase):
    def test_a_scanned_letter_locks_with_its_lane(self):
        lock = parse_govt_offer(ums())
        self.assertEqual(lock['rules_lane'], LANE)
        self.assertEqual(lock['_family'], 'ums')

    def test_a_text_layer_without_its_layout_never_locks(self):
        d = diagnose(ums(), page1_text=ums())
        self.assertEqual(d['guard'], 'no_layout')
        self.assertIsNone(d['locked'])

    def test_a_text_layer_reads_from_its_layout(self):
        glued = ums().replace('\n', ' ')
        self.assertIsNone(diagnose(glued, page1_text=glued)['locked'])
        self.assertEqual(diagnose(glued, page1_text=glued, page1_layout=ums())['locked']['candidate_name'], NAME)

    def test_the_exact_read_names_the_lane(self):
        ex = exact_read(ums())
        self.assertEqual(ex['rules_lane'], LANE)
        self.assertEqual(ex['offer_reader_inputs']['rules_lane'], LANE)
        self.assertNotIn('rules_lane', ex['fields'])


class TestGateTwo(SimpleTestCase):
    def test_the_switch_is_read_from_the_environment_and_is_off_by_default(self):
        with mock.patch.dict(os.environ, {'OCR_FIRST_LANES': ' ua:UMS , '}):
            self.assertEqual(ocr_first_lanes(), ('ua:UMS',))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(ocr_first_lanes(), ())

    def test_a_government_read_is_unaffected(self):
        self.assertTrue(rules_lane_open({'fields': {}, 'rules_lane': ''}))

    @override_settings(OCR_FIRST_LANES=())
    def test_a_lane_switched_off_goes_to_the_ai(self):
        self.assertFalse(rules_lane_open(exact_read(ums())))

    @override_settings(OCR_FIRST_LANES=(LANE,))
    def test_a_lane_switched_on_needs_one_pinned_course(self):
        ex = exact_read(ums())
        with mock.patch(PINNED, return_value=('unresolved', None)):
            self.assertEqual(rules_lane_verdict(ex), 'match_unresolved')
        with mock.patch(PINNED, return_value=ONE) as pinned:
            self.assertTrue(rules_lane_open(ex))
        self.assertEqual(pinned.call_args.args[2], 'Universiti Malaysia Sabah')

    @override_settings(OCR_FIRST_LANES=(LANE,))
    def test_a_course_with_no_pinned_campus_goes_to_the_ai(self):
        """Review round 1 #4: one catalogue course is not enough; it must be pinned to one campus."""
        ex = exact_read(ums())
        with mock.patch(MATCH, return_value={'course_id': 'uh6481001', 'institution': ''}),                 mock.patch(LEVEL, return_value=letter_level(PROG)):
            self.assertEqual(rules_lane_verdict(ex), 'match_campus_unpinned')

    @override_settings(OCR_FIRST_LANES=(LANE,))
    def test_a_course_of_another_level_goes_to_the_ai(self):
        ex = exact_read(ums())
        with mock.patch(MATCH, return_value={'course_id': 'dip-x', 'institution': 'Universiti Malaysia Sabah'}),                 mock.patch(LEVEL, return_value='diploma'):
            self.assertEqual(rules_lane_verdict(ex), 'match_unresolved')

    @override_settings(OCR_FIRST_LANES=(LANE,))
    def test_a_match_that_raises_goes_to_the_ai_and_is_logged(self):
        """Review round 1 #10."""
        ex = exact_read(ums())
        with mock.patch(MATCH, side_effect=RuntimeError('catalogue down')),                 self.assertLogs('apps.scholarship.offer_exact', level='ERROR'):
            self.assertEqual(rules_lane_verdict(ex), 'match_error')
            self.assertFalse(rules_lane_open(ex))


@override_settings(DOC_GENUINENESS_CHECK_ENABLED=False)
class TestTheVisionOfferBranch(TestCase):
    def _run(self, ai, text=None):
        app = make_application('submitted')
        app.profile.nric = NRIC.replace('-', '')
        app.profile.save(update_fields=['nric'])
        doc = ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/x', content_type='image/png',
            vision_fields={'fields': {}}, vision_run_at=timezone.now())
        vision._run_field_extraction_impl(doc, names=[app.profile.name], ocr={'text': text or ums(), 'error': '', 'image': png()})
        doc.refresh_from_db()
        return doc

    @override_settings(OCR_FIRST_LANES=())
    def test_lane_off_falls_through_to_the_ai_and_says_why(self):
        with mock.patch('apps.scholarship.vision.extract_document_fields',
                        return_value={'fields': {}, 'warnings': [], 'error': ''}) as ai:
            doc = self._run(ai)
        ai.assert_called_once()
        self.assertEqual(doc.vision_fields['offer_reader_inputs']['rules_fallback'],
                         {'lane': LANE, 'reason': 'lane_off'})

    @override_settings(OCR_FIRST_LANES=(LANE,))
    def test_lane_on_with_no_pinned_course_falls_through_to_the_ai_and_says_why(self):
        with mock.patch(PINNED, return_value=('unresolved', None)), mock.patch(
                'apps.scholarship.vision.extract_document_fields',
                return_value={'fields': {}, 'warnings': [], 'error': '', 'offer_reader_inputs': {'pages': 1}}) as ai:
            doc = self._run(ai)
        ai.assert_called_once()
        inputs = doc.vision_fields['offer_reader_inputs']
        self.assertEqual(inputs['rules_fallback'], {'lane': LANE, 'reason': 'match_unresolved'})
        self.assertEqual(inputs['pages'], 1)
        self.assertEqual(doc.vision_fields['capture'], 'ai')

    @override_settings(OCR_FIRST_LANES=(LANE,))
    def test_lane_on_with_a_pinned_course_is_the_rules_read(self):
        with mock.patch(PINNED, return_value=ONE), mock.patch.object(vision, '_call_gemini_json') as gemini:
            doc = self._run(None)
        gemini.assert_not_called()
        self.assertEqual(doc.vision_fields['capture'], 'deterministic')
        self.assertEqual(doc.vision_fields['offer_reader_inputs']['rules_lane'], LANE)
        self.assertEqual(doc.vision_fields['fields']['institution'], 'Universiti Malaysia Sabah')

    @override_settings(OCR_FIRST_LANES=(LANE,))
    def test_a_ums_letter_the_rules_refuse_says_why_on_the_ai_read(self):
        """Review round 2 LOW-3: the rules read's own refusal is recorded like the lane and match reasons."""
        with mock.patch('apps.scholarship.vision.extract_document_fields',
                        return_value={'fields': {}, 'warnings': [], 'error': ''}) as ai:
            doc = self._run(ai, text=ums(top='SURAT PENGESAHAN PELAJAR\n'))
        ai.assert_called_once()
        self.assertEqual(doc.vision_fields['offer_reader_inputs']['rules_fallback'],
                         {'lane': LANE, 'reason': 'read_status_letter'})


class TestReviewRoundOne(SimpleTestCase):
    """The S1 review's findings (2026-11-19): each rule refuses rather than guess."""

    def test_the_title_must_start_its_line(self):
        title = 'NOTIS TAWARAN KEMASUKAN KE UNIVERSITI MALAYSIA SABAH SESI I-2031/2032'
        self.assertEqual(read_ums(ums(title=title))[1], 'no_title')

    def test_a_withdrawal_deferral_refusal_or_reply_never_locks(self):
        for word in ('PEMBATALAN', 'PENANGGUHAN', 'PENOLAKAN', 'TARIK BALIK', 'RAYUAN', 'MAKLUMBALAS', 'MAKLUM BALAS'):
            with self.subTest(word=word):
                self.assertEqual(read_ums(ums(top=f'{word} TAWARAN KEMASUKAN\n'))[1], 'not_an_offer')
                self.assertEqual(read_ums(ums(extra_head=f'Perkara : {word.lower()}\n'))[1], 'not_an_offer')

    def test_a_wrapped_sentence_is_never_the_programme_source(self):
        wrapped = f'\n{PROG}\n'                  # the sentence's middle line alone equals the programme
        self.assertEqual(read_ums(ums(said=wrapped))[0]['programme'], PROG)
        for prog_line in ('', 'Diploma Sains Komputer'):
            with self.subTest(prog_line=prog_line):
                f, reason = read_ums(ums(said=wrapped, prog_line=prog_line))
                self.assertEqual(f['programme'], '')
                self.assertIn('programme', reason)

    def test_a_degree_line_in_the_label_block_that_disagrees_refuses(self):
        text = ums().replace('Fakulti :', 'Diploma Sains Komputer\nFakulti :')
        self.assertEqual(read_ums(text)[0]['programme'], '')

    def test_a_wrapped_program_value_and_a_scanned_label_block_read(self):
        head, tail = 'Ijazah Sarjana Muda Sains Komputer', 'Dengan Kepujian'
        self.assertEqual(read_ums(ums(prog_line=f'{head}\n{tail}'))[0]['programme'], PROG)
        scanned = ums().replace(f'Program :      {PROG}\nKod Program :      UH6481001',
                                f'Program\nKod Program\n:\n{head}\n{tail}\nUH6481001')
        f, reason = read_ums(scanned)
        self.assertEqual((reason, f['programme']), ('', PROG))

    def test_no_program_label_no_programme(self):
        text = ums().replace(f'Program :      {PROG}', PROG)
        self.assertEqual(read_ums(text)[0]['programme'], '')

    def test_a_range_across_two_months_reports_on_its_first_day(self):
        for report, want in (('28 September - 1 Oktober 2031', '28 Sep 2031'),
                             ('28 September hingga 1 Oktober 2031', '28 Sep 2031'),
                             ('30 Disember 2031 - 2 Januari 2032', '30 Dec 2031'),
                             ('28-29 September 2031', '28 Sep 2031')):
            with self.subTest(report=report):
                f, reason = read_ums(ums(report=report))
                self.assertEqual((reason, f['reporting_date']), ('', want))

    def test_a_range_whose_first_day_cannot_be_placed_is_no_date(self):
        for report in ('30 - 2 Oktober 2031', '30 Disember - 2 Januari 2032', '28 September 2031 - 8.00 pagi'):
            with self.subTest(report=report):
                f, reason = read_ums(ums(report=report))
                self.assertEqual(f['reporting_date'], '')
                self.assertIn('reporting_date', reason)

    def test_the_campus_is_read_only_by_its_label(self):
        self.assertEqual(read_ums(ums(extra_head='Labuan\n'))[0]['campus'], 'Kota Kinabalu')
        self.assertEqual(read_ums(ums(kampus='Kampus :\nSandakan'))[0]['campus'], 'Sandakan')
        f, reason = read_ums(ums(kampus='Labuan'))          # a bare campus line with no label
        self.assertEqual((reason, f['campus']), ('', ''))
        self.assertEqual(read_ums(ums(kampus='Kampus :      Labuan\nKampus :      Sandakan'))[0]['campus'], '')

    def test_an_officer_title_is_never_the_name(self):
        for name in ('PENDAFTAR', 'TIMBALAN NAIB CANSELOR', 'PEJABAT PENDAFTAR', 'CANSELOR'):
            with self.subTest(name=name):
                self.assertEqual(read_ums(ums(name=name))[0]['candidate_name'], '')

    def test_two_dated_lines_in_the_head_refuse_the_name_and_date(self):
        f, reason = read_ums(ums(top='Tarikh : 1 Ogos 2031\n'))
        self.assertEqual((f['candidate_name'], f['offer_date']), ('', ''))
        self.assertIn('candidate_name', reason)

    def test_a_wrapped_name_refuses_but_an_address_line_does_not(self):
        f, _r = read_ums(ums(name=f'{NAME}\nQUELLAN ZORB'))
        self.assertEqual(f['candidate_name'], '')
        f, reason = read_ums(ums(name=f'{NAME}\nKG ZANTHARION'))
        self.assertEqual((reason, f['candidate_name']), ('', NAME))

    def test_the_upu_code_needs_a_left_boundary(self):
        glued = read_ums(ums(code='Fakulti:UH6481001Bayaran'))[0]
        self.assertEqual(glued['programme_code'], 'UH6481001')
        for code in ('Kod Program : 1UH6481001', 'Kod Program : XUH6481001'):
            with self.subTest(code=code):
                self.assertEqual(read_ums(ums(code=code))[0]['programme_code'], '')


class TestTheLayoutRunsInTheChild(SimpleTestCase):
    """Review round 1 #11: page 1's layout text comes from the pdfium child, under its limits."""

    def setUp(self):
        pdf_pages._layer_memo_clear()

    def test_the_child_reads_the_layout(self):
        from apps.scholarship.tests.test_ocr_visible import _pdf, _show
        self.assertEqual(pdf_pages.pdf_page1_layout(_pdf([_show('Nama   ZORBEX QUENTARO')])), 'Nama   ZORBEX QUENTARO')

    def test_no_answer_from_the_child_is_no_layout(self):
        from apps.scholarship.tests.test_ocr_visible import _pdf, _show
        from apps.scholarship import pdfium_run
        real, asked = pdfium_run.ask, []

        def ask(data, ops):                     # the visibility check runs as before; the layout op gets nothing
            asked.append(ops)
            return None if ops == [{'op': 'layout'}] else real(data, ops)
        with mock.patch('apps.scholarship.pdfium_run.ask', side_effect=ask):
            self.assertEqual(pdf_pages.pdf_page1_layout(_pdf([_show('Nama   ZORBEX QUENTARO')])), '')
        self.assertIn([{'op': 'layout'}], asked)


class TestReviewRoundTwo(SimpleTestCase):
    """The S1 review's round-2 findings (2026-11-19): each trigger refuses; the forms already placed still read."""

    def test_a_reporting_date_after_another_day_number_is_no_date(self):
        """MED-1: any joiner or list the range rule does not place would give the LAST day: refuse it."""
        for report in ('28 \u2014 29 September 2031', '28 -- 29 September 2031', '28 29 September 2031',
                       '28 sampai 29 September 2031', '28 s/d 29 September 2031', '28 ke 29 September 2031',
                       '27, 28 dan 29 September 2031', '28 & 29 September 2031', '28/29 September 2031'):
            with self.subTest(report=report):
                f, reason = read_ums(ums(report=report))
                self.assertEqual(f['reporting_date'], '')
                self.assertIn('reporting_date', reason)

    def test_the_ranges_already_placed_still_read_their_first_day(self):
        for report in ('28 \u2013 29 September 2031', '28 September 2031 (Ahad) - 29 September 2031',
                       '28 September 2031'):
            with self.subTest(report=report):
                f, reason = read_ums(ums(report=report))
                self.assertEqual((reason, f['reporting_date']), ('', '28 Sep 2031'))

    def test_a_cut_name_refuses_when_the_next_line_may_be_its_tail(self):
        """MED-2: a name connector, or a name-like first column (state and town words no longer clear it)."""
        for nxt in ('HAKIM BIN BANDAR', 'SABAH BINTI ABDULLAH', 'HAKIM BIN ABDULLAH        KOTA KINABALU',
                    'HAKIM ABDULLAH      JALAN ZANTHARION', 'QUELLAN A/P ZORB'):
            with self.subTest(nxt=nxt):
                f, reason = read_ums(ums(name=f'{NAME}\n{nxt}'))
                self.assertEqual(f['candidate_name'], '')
                self.assertIn('candidate_name', reason)

    def test_an_address_line_under_the_name_still_locks(self):
        for nxt in ('JALAN ZANTHARION 7', 'LOT 9 KAMPUNG ZANTHARION', 'TAMAN ZANTHARION',
                    'PETI SURAT 99      88000 KOTA KINABALU', '88000 KOTA KINABALU'):
            with self.subTest(nxt=nxt):
                f, reason = read_ums(ums(name=f'{NAME}\n{nxt}'))
                self.assertEqual((reason, f['candidate_name']), ('', NAME))

    def test_a_withdrawal_said_only_in_the_body_never_locks(self):
        """LOW-1."""
        for tail in ('Tawaran ini DIBATALKAN.', 'Tawaran ini telah ditarik balik.', 'Tawaran BATAL.'):
            with self.subTest(tail=tail):
                self.assertEqual(read_ums(ums() + tail + '\n')[1], 'not_an_offer')
        self.assertEqual(read_ums(ums() + 'Kor Batalion\n')[1], '')

    def test_every_program_line_must_agree(self):
        """LOW-2: a Program line anywhere in the letter that disagrees refuses; one that agrees does not."""
        f, reason = read_ums(ums() + 'Program :      Diploma Sains Marin\n')
        self.assertEqual(f['programme'], '')
        self.assertIn('programme', reason)
        self.assertEqual(read_ums(ums() + f'Program :      {PROG}\n')[0]['programme'], PROG)

    def test_a_ums_refusal_is_recorded_with_its_lane(self):
        """LOW-3: the same shape as `rules_lane_verdict`'s reasons; a non-UMS letter records nothing."""
        cases = ((dict(text=ums(top='SURAT PENGESAHAN PELAJAR\n')), 'read_status_letter'),
                 (dict(text=ums(), from_text_layer=True, page1_layer=ums()), 'read_no_layout'),
                 (dict(text=ums(), from_text_layer=True, page1_layer=''), 'read_no_page1_layer'),
                 (dict(text=ums(name='')), 'read_empty:candidate_name'))
        for kw, want in cases:
            with self.subTest(want=want):
                why = {}
                self.assertIsNone(exact_read(why=why, **kw))
                self.assertEqual(why, {'lane': LANE, 'reason': want})
        why = {}
        self.assertIsNone(exact_read('SURAT BIASA\nTiada apa-apa\n', why=why))
        self.assertEqual(why, {})
        why = {}
        self.assertIsNotNone(exact_read(ums(), why=why))
        self.assertEqual(why, {})

    def test_a_blanked_ic_and_a_pdf_without_bytes_are_recorded(self):
        from apps.scholarship.offer_exact import exact_offer_read

        def blank(govt, **_kw):
            govt['candidate_nric'] = ''
            return {}
        why = {}
        with mock.patch('apps.scholarship.offer_ic.guard_nric', side_effect=blank):
            self.assertIsNone(exact_read(ums(), why=why))
        self.assertEqual(why, {'lane': LANE, 'reason': 'read_nric_guard'})
        why = {}
        self.assertIsNone(exact_offer_read(ums(), image=None, content_type='application/pdf', why=why))
        self.assertEqual(why, {'lane': LANE, 'reason': 'read_no_pdf_bytes'})


class TestTheMemoCountsText(SimpleTestCase):
    """Review round 2 LOW-4: the layout text and word boxes count against the memo's byte cap."""

    def setUp(self):
        from apps.scholarship import pdfium_run
        pdfium_run.memo_clear()
        self.addCleanup(pdfium_run.memo_clear)

    def test_text_and_words_are_counted(self):
        from apps.scholarship.pdfium_run import _WORD_BOX_BYTES, _result_bytes
        self.assertEqual(_result_bytes({'text': 'x' * 100}), 100)
        self.assertEqual(_result_bytes({'words': [{'text': 'ab'}, {'text': ''}, 'junk']}), 2 + 2 * _WORD_BOX_BYTES)
        self.assertEqual(_result_bytes({'png': b'12', 'pngs': [b'345'], 'text': 'xy'}), 7)
        self.assertEqual(_result_bytes(None), 0)

    def test_a_big_text_answer_is_evicted(self):
        from apps.scholarship import pdfium_run
        with mock.patch.object(pdfium_run, '_MEMO_MAX_BYTES', 1500), \
                mock.patch.object(pdfium_run, '_spawn', return_value=[{'text': 'x' * 1000}]):
            pdfium_run.ask(b'first', [{'op': 'layout'}])
            pdfium_run.ask(b'second', [{'op': 'layout'}])
            self.assertEqual(len(pdfium_run._MEMO), 1)
