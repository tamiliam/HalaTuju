"""Today's free offer readers replayed on cached OCR text (`eval/offer_replay.py`) and the
failure map (`eval/offer_failure_map.py`) — offer exact-read S2, 2026-11-01. Synthetic twins only:
every letter is invented and built in a temp folder; nothing reads the gitignored corpus
(`test_no_gitignored_corpus.py`)."""
import contextlib
import io
import json
import os
import tempfile

from django.test import SimpleTestCase

from apps.scholarship import offer_parse
from apps.scholarship.eval import offer_failure_map as fm
from apps.scholarship.eval import offer_read_check as orc
from apps.scholarship.eval import offer_replay as rp
from apps.scholarship.genuineness.results_doc import MODEL_VERSION
from apps.scholarship.tests.test_offer_reader import text_pdf

#: Invented values. None may appear in any printed output.
SECRET_NAME = 'ZORBEX A/L QUENTARO'
SECRET_NRIC = '010203-14-5678'
SECRET_COLLEGE = 'KOLEJ MATRIKULASI ZANTHARION'

MATRIC_TWIN = f"""KEMENTERIAN PENDIDIKAN
Bahagian Matrikulasi
Tarikh: 3 MAC 2031
{SECRET_NAME}
K/P: {SECRET_NRIC}
TAWARAN KEMASUKAN PROGRAM MATRIKULASI KEMENTERIAN PENDIDIKAN SESI 2031/2032
Jurusan:
Tempoh Pengajian:
Kolej:
Pendaftaran dalam talian:
Tarikh Kemasukan ke kolej:
Yuran Pendaftaran:
SAINS
DUA SEMESTER (10 BULAN)
{SECRET_COLLEGE}
1 OGOS HINGGA 9 OGOS 2031
17 OGOS 2031
RM499.00
"""
UNIVERSITY_TWIN = ('SURAT TAWARAN KEMASUKAN KE PROGRAM IJAZAH SARJANA MUDA\n'
                   'UNIVERSITI QORVANE PERLAK\nTarikh Pendaftaran: 17 Ogos 2031\n')


def _stored(**over):
    base = {'candidate_name': SECRET_NAME, 'candidate_nric': SECRET_NRIC,
            'institution': 'DEWAN QORVANE', 'programme': 'Program Matrikulasi',
            'stream': 'SAINS', 'intake': '2031/2032', 'reporting_date': '17 Ogos 2031',
            'offer_date': '', 'issuer': '', 'candidate_address': 'kept from the stored read'}
    base.update(over)
    return base


class TestProductionText(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.snap = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _cache(self, key, meta, text=None, pages=None):
        with open(os.path.join(self.snap, key + '.ocr.meta.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f)
        if text is not None:
            with open(os.path.join(self.snap, key + '.ocr.txt'), 'w', encoding='utf-8') as f:
                f.write(text)
        if pages is not None:
            with open(os.path.join(self.snap, key + '.ocr.words.json'), 'w', encoding='utf-8') as f:
                json.dump({'pages': pages}, f)

    def test_vision_reads_page_one_only_as_production_does(self):
        self._cache('k', {'path': 'vision'}, text='page one\npage two',
                    pages=[{'page': 1, 'text': 'page one'}, {'page': 2, 'text': 'page two'}])
        self.assertEqual(rp.production_text(self.snap, 'k'), ('page one', 'vision'))

    def test_a_text_layer_and_an_earlier_capture_read_the_whole_cache(self):
        self._cache('t', {'path': 'text_layer'}, text='all pages')
        self._cache('e', {'path': 'earlier_vision'}, text='page one only')
        self.assertEqual(rp.production_text(self.snap, 't'), ('all pages', 'text_layer'))
        self.assertEqual(rp.production_text(self.snap, 'e'), ('page one only', 'earlier_vision'))

    def test_no_cache_is_no_text(self):
        self.assertEqual(rp.production_text(self.snap, 'missing'), ('', 'none'))


class TestReplayLetter(SimpleTestCase):
    def test_a_lock_is_merged_over_the_stored_read(self):
        rec = rp.replay_letter(MATRIC_TWIN, 'text_layer', _stored(), page1_layer=MATRIC_TWIN)
        self.assertEqual(rec['capture'], 'deterministic')
        self.assertEqual(rec['replay']['outcome'], 'locked')
        self.assertEqual(rec['fields']['institution'], SECRET_COLLEGE)          # the parser wins
        self.assertEqual(rec['fields']['candidate_address'], '')          # S5 review L2: an AI-only key, blank
        self.assertEqual(rec['fields']['offer_date'], '3 MAC 2031')        # read by the parser
        self.assertEqual(rec['replay']['parser_fields']['institution'], SECRET_COLLEGE)
        self.assertNotIn('_family', rec['fields'])
        self.assertEqual(rec['replay']['offer_parser_version'], offer_parse.PARSER_VERSION)
        self.assertEqual(rec['replay']['genuineness_model_version'], MODEL_VERSION)

    def test_a_fallback_keeps_the_stored_read_as_the_stand_in(self):
        rec = rp.replay_letter(UNIVERSITY_TWIN, 'vision', _stored())
        self.assertEqual((rec['capture'], rec['replay']['outcome']), ('ai_stand_in', 'fallback'))
        self.assertEqual(rec['fields'], _stored())
        self.assertEqual(rec['replay']['fields_source'], 'stored_stand_in')
        self.assertIsNone(rec['replay']['parser_fields'])

    def test_blank_text_is_no_text_and_no_genuineness_signal(self):
        rec = rp.replay_letter('  ', 'none', _stored())
        self.assertEqual((rec['capture'], rec['replay']['outcome']), ('no_text', 'no_text'))
        self.assertIsNone(rec['authenticity'])

    def test_genuineness_is_stored_in_production_s_shape(self):
        auth = rp.authenticity_of(MATRIC_TWIN)
        self.assertTrue({'status', 'reason', 'doc_seen'} <= set(auth))
        self.assertNotEqual(auth['status'], 'unrecognised')

    def test_the_merge_rule_is_production_s(self):
        # S5: `offer_exact.merge_over` — the parser's own keys whole (a stale AI campus is cleared),
        # the reporting date merge-preserve (the stored one stays when the parser read none).
        rec = rp.replay_letter(MATRIC_TWIN.replace('17 OGOS 2031\n', ''), 'vision',
                               _stored(campus='STALE CAMPUS', programme_code='X1'))
        self.assertEqual(rec['capture'], 'deterministic')
        self.assertEqual((rec['fields']['campus'], rec['fields']['programme_code']), ('', ''))
        self.assertEqual(rec['fields']['reporting_date'], '17 Ogos 2031')


class TestMissReason(SimpleTestCase):
    def _reason(self, text, kind='photo', family='matriculation'):
        return rp.miss_reason(family, text, rp.replay_letter(text, 'vision', {}), kind)

    def test_no_text(self):
        self.assertEqual(self._reason('short'), 'no_text')

    def test_a_text_that_never_names_the_family_is_other(self):
        self.assertEqual(self._reason(UNIVERSITY_TWIN), 'other')

    def test_family_named_without_the_issuer_marker_is_a_layout_variant(self):
        text = MATRIC_TWIN.replace('Bahagian Matrikulasi', 'Bahagian X').replace('PROGRAM MATRIKULASI', 'PROGRAM')
        self.assertIn('MATRIKULASI', text.upper())
        self.assertEqual(self._reason(text), 'layout_variant')

    def test_clean_text_that_does_not_lock_is_a_layout_variant(self):
        noisy = MATRIC_TWIN.replace(SECRET_NRIC, '0I02O3-l4-S678')
        self.assertEqual(self._reason(noisy, kind='text_pdf'), 'layout_variant')

    def test_vision_text_with_the_label_but_a_garbled_value_is_photo_ocr_noise(self):
        noisy = MATRIC_TWIN.replace(SECRET_NRIC, '0I02O3-l4-S678')
        self.assertEqual(self._reason(noisy), 'photo_ocr_noise')

    def test_a_missing_anchor_label_is_a_layout_variant_even_on_a_photo(self):
        no_label = MATRIC_TWIN.replace(f'K/P: {SECRET_NRIC}\n', '')
        self.assertEqual(self._reason(no_label), 'layout_variant')

    def test_a_shifted_block_on_vision_text_is_photo_ocr_noise(self):
        # S5: the shape reader leaves the Jurusan EMPTY rather than shifting a ringgit amount into it.
        shifted = MATRIC_TWIN.replace('SAINS\n', 'RM499.00\n', 1)
        diag = rp.parser_diagnosis(shifted)
        self.assertEqual(diag['empty_required'], ['programme', 'stream'])   # the bracket needs a Jurusan
        self.assertFalse(diag['locked'])
        self.assertEqual(self._reason(shifted), 'photo_ocr_noise')

    def test_an_ic_the_guard_refuses_is_guard_ic_guard(self):
        # A labelled IC that is malformed (no real birth date) and is not the profile's: blanked → no lock.
        bad = MATRIC_TWIN.replace(SECRET_NRIC, '019999-14-5678')
        diag = rp.parser_diagnosis(bad, profile_nric='020304-14-5678')
        self.assertEqual((diag['guard'], diag['locked']), ('ic_guard', False))


class _Corpus:
    """A synthetic corpus folder shaped like the real one, with OCR caches."""

    def __init__(self, tmp):
        self.dir = tmp
        self.snap = os.path.join(tmp, 'snapshots')
        os.makedirs(self.snap)
        os.makedirs(os.path.join(tmp, 'fixtures', 'offer_letter'))

    def letter(self, key, read, seen='matriculation', ext='jpg', route=None, text='', answer=None):
        self._json(key + '.json', {'vision_fields': {'fields': read, 'capture': 'ai',
                                                     'authenticity': {'doc_seen': seen,
                                                                      'status': 'genuine'}}})
        # A text-layer PDF is a real PDF carrying the text (S5: the replay reads its page-1 layer).
        with open(os.path.join(self.dir, 'fixtures', 'offer_letter', f'{key}.{ext}'), 'wb') as f:
            f.write(text_pdf([text]) if ext == 'pdf' and route == 'text_layer' and text else b'x')
        if route:
            self._json(key + '.ocr.meta.json', {'path': route})
            with open(os.path.join(self.snap, key + '.ocr.txt'), 'w', encoding='utf-8') as f:
                f.write(text)
            if route == 'vision':
                self._json(key + '.ocr.words.json', {'pages': [{'page': 1, 'text': text}]})
        if answer is not None:
            self._json(key + orc.ANSWER_SUFFIX, answer)

    def _json(self, name, data):
        with open(os.path.join(self.snap, name), 'w', encoding='utf-8') as f:
            json.dump(data, f)


def _answer(**over):
    base = {f: None for f in orc.ANSWER_FIELDS}
    base.update({'candidate_name': SECRET_NAME, 'candidate_nric': SECRET_NRIC,
                 'institution_as_printed': SECRET_COLLEGE, 'programme': 'Program Matrikulasi',
                 'stream': 'SAINS', 'intake': 'Sesi 2031/2032', 'reporting_date': '17 Ogos 2031',
                 'offer_date': '3 Mac 2031', 'is_offer_letter': 'yes', 'pages': 1,
                 'unsure_fields': [], 'labeller_note': None})
    base.update(over)
    return base


def _assert_no_value(test, out):
    up = out.upper()
    for token in ('ZORBEX', 'QUENTARO', 'ZANTHARION', 'QORVANE', '010203', '5678', 'OGOS'):
        test.assertNotIn(token, up)


class TestReplayCorpus(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.c = _Corpus(self._tmp.name)
        self.c.letter('offer_letter__a1__d11', _stored(), ext='pdf', route='text_layer', text=MATRIC_TWIN)
        self.c.letter('offer_letter__a2__d12', _stored(), seen='ua_offer', route='vision',
                      text=UNIVERSITY_TWIN)
        self.c.letter('offer_letter__a3__d13', _stored())                     # no OCR cache

    def tearDown(self):
        self._tmp.cleanup()

    def test_writes_a_cache_the_scorer_can_load(self):
        rows = rp.replay_corpus(self.c.dir, write=True)
        self.assertEqual([r['record']['replay']['outcome'] for r in rows], ['locked', 'fallback', 'no_text'])
        read = orc.read_source('file:' + rp.REPLAY_SUFFIX)
        fields, capture = read(self.c.dir, 'offer_letter__a1__d11')
        self.assertEqual((fields['institution'], capture), (SECRET_COLLEGE, 'deterministic'))
        self.assertEqual(read(self.c.dir, 'offer_letter__a2__d12')[1], 'ai_stand_in')

    def test_without_write_nothing_is_written(self):
        rp.replay_corpus(self.c.dir, write=False)
        self.assertFalse([n for n in os.listdir(self.c.snap) if n.endswith(rp.REPLAY_SUFFIX)])

    def test_summary_counts_by_family_and_kind_and_prints_no_value(self):
        s = rp.replay_summary(rp.replay_corpus(self.c.dir))
        self.assertEqual(s['outcome'], {'fallback': 1, 'locked': 1, 'no_text': 1})
        self.assertEqual(s['by_input_kind']['text_pdf'], {'locked': 1})
        self.assertEqual(s['known_format_ai']['total'], 2)          # two matriculation, stored AI
        self.assertEqual(s['known_format_ai']['not_locked_reason'], {'no_text': 1})
        for argv in ([], ['--json'], ['--write']):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(rp.main(['--eval-dir', self.c.dir, *argv]), 0)
            _assert_no_value(self, out.getvalue())


class TestFailureKinds(SimpleTestCase):
    def _kind(self, field, outcome, read, answer=None, family='other_university', **kw):
        return fm.field_kind(field, outcome, answer or _answer(), read, family, **kw)

    def test_institution_kinds(self):
        self.assertEqual(self._kind('institution', 'wrong', {'institution': 'Dewan Qorvane'}),
                         'institution = reporting venue')
        self.assertEqual(self._kind('institution', 'wrong', {'institution': 'Bahagian Matrikulasi'},
                                    _answer(issuer='Bahagian Matrikulasi')), 'institution = issuer')
        self.assertEqual(self._kind('institution', 'wrong', {'institution': 'Kolej Matrikulasi'}),
                         'institution keeps part of the name')
        self.assertEqual(self._kind('institution', 'wrong', {'institution': SECRET_COLLEGE + ' Perlak'}),
                         'institution adds to the name')
        self.assertEqual(self._kind('institution', 'wrong', {'institution': 'Kampus Perlak'},
                                    _answer(institution_as_printed='Universiti Qorvane')),
                         'institution names a campus / branch / college the answer does not')
        self.assertEqual(self._kind('institution', 'wrong', {'institution': 'Universiti Qorvane'},
                                    _answer(institution_as_printed='Kolej Qorvane Perlak')),
                         'institution = a university, the name is not')

    def test_institution_kinds_with_the_campus_a_field_of_its_own(self):
        # owner 2026-11-01: the name and the campus are two answer fields
        ans = _answer(institution_as_printed='UQP', institution_campus='Kampus Kota Perlak')
        self.assertEqual(self._kind('institution', 'wrong', {'institution': 'UQP Kampus Kota Perlak'}, ans),
                         'institution joins the campus')
        self.assertEqual(self._kind('institution', 'wrong', {'institution': 'Kampus Kota Perlak, UQP'}, ans),
                         'institution joins the campus')
        self.assertEqual(self._kind('institution', 'wrong', {'institution': 'KAMPUS KOTA PERLAK'}, ans),
                         'institution = the campus')
        # another campus than the answer's: not "joins", a campus the answer does not have
        self.assertEqual(self._kind('institution', 'wrong', {'institution': 'UQP Kampus Lain'}, ans),
                         'institution adds to the name')
        self.assertEqual(self._kind('institution', 'wrong', {'institution': 'Kolej Lain'}, ans),
                         'institution names a campus / branch / college the answer does not')
        # the campus's words already in the name: containing them is not joining
        ans = _answer(institution_as_printed='Universiti Qorvane Perlak', institution_campus='Perlak')
        self.assertEqual(self._kind('institution', 'wrong', {'institution': 'Universiti Qorvane Perlak Utara'},
                                    ans), 'institution adds to the name')
        # a campus word the answer's campus has is not counted against the read: no rule fits
        ans = _answer(institution_as_printed='Universiti Qorvane', institution_campus='Kampus Utara')
        self.assertEqual(self._kind('institution', 'wrong', {'institution': 'Kampus Selatan'}, ans),
                         'institution wrong')

    def test_programme_kinds(self):
        ans = _answer(programme='Diploma Qorvane')
        self.assertEqual(self._kind('programme', 'wrong', {'programme': 'DQ123 Diploma Qorvane'}, ans),
                         'programme keeps a code')
        self.assertEqual(self._kind('programme', 'wrong', {'programme': 'Program Ijazah (PISMP)'},
                                    _answer(programme='Ijazah Sarjana Muda Perguruan'), family='pismp'),
                         'programme = PISMP wrapper')
        self.assertEqual(self._kind('programme', 'wrong', {'programme': 'Diploma Qorvane Lanjutan'}, ans),
                         'programme adds words')

    def test_intake_kinds(self):
        ans = _answer(intake='Semester 1 Sesi 2031/2032')
        self.assertEqual(self._kind('intake', 'wrong', {'intake': 'Sesi 2031/2032'}, ans),
                         'intake drops Semester')
        self.assertEqual(self._kind('intake', 'wrong', {'intake': '2031'}, _answer(intake='Ogos 2031')),
                         'intake keeps only a year')

    def test_reporting_date_kinds_read_the_page_texts(self):
        missing = {'reporting_date': ''}
        self.assertEqual(self._kind('reporting_date', 'missing', missing, pages=2,
                                    texts=['no date here', 'Lapor diri: 17/08/2031']),
                         'reporting date only on page 2+')
        self.assertEqual(self._kind('reporting_date', 'missing', missing, pages=2,
                                    texts=['no date here'], complete=False),
                         'reporting date on page 2+ (not captured)')
        self.assertEqual(self._kind('reporting_date', 'missing', missing, pages=1,
                                    texts=['Daftar 17 hingga 19 Ogos 2031']),
                         'reporting date on page 1 (missing)')
        self.assertEqual(self._kind('reporting_date', 'missing', missing, pages=1, texts=['none']),
                         'reporting date not in the OCR text (missing)')
        self.assertEqual(self._kind('reporting_date', 'wrong', {'reporting_date': '3 Mac 2031'}),
                         'reporting date = offer date')

    def test_nric_and_fallback_kinds(self):
        self.assertEqual(self._kind('nric', 'missing', {}, texts=[f'K/P {SECRET_NRIC}']),
                         'nric on page 1 (missing)')
        self.assertEqual(self._kind('nric', 'missing', {}, texts=['nothing']),
                         'nric not in the page-1 OCR text (missing)')
        self.assertEqual(self._kind('name', 'wrong', {'candidate_name': 'X'}), 'name wrong')
        self.assertEqual(self._kind('intake', 'extra', {'intake': '2031'}), 'intake extra')

    def test_dates_in_a_text(self):
        self.assertEqual(fm.dates_in('Tarikh 17/08/2031 dan 2031-09-01, daftar 3 HINGGA 5 OGOS 2031'),
                         {'17 Aug 2031', '1 Sep 2031', '3 Aug 2031'})

    def test_genuineness_kinds(self):
        self.assertEqual(fm.genuineness_kind(_answer(), 'not_offer_letter'), 'real offer judged not genuine')
        self.assertIsNone(fm.genuineness_kind(_answer(), 'unchecked'))
        self.assertEqual(fm.genuineness_kind(_answer(is_offer_letter='portal_page'), 'genuine'),
                         'not an offer judged genuine')
        self.assertIsNone(fm.genuineness_kind(_answer(is_offer_letter='unsure'), 'suspect'))

    def test_tags(self):
        ans = _answer()
        self.assertEqual(fm.field_tag('institution', ans, 'matriculation', None), 'untagged')
        self.assertEqual(fm.field_tag('institution', ans, 'matriculation',
                                      {'replay': {'outcome': 'fallback'}}), 'ai, S3')
        locked = {'replay': {'outcome': 'locked'}, 'fields': {'institution': SECRET_COLLEGE}}
        self.assertEqual(fm.field_tag('institution', ans, 'matriculation', locked), 'old read')
        locked['fields']['institution'] = 'Kolej Lain'
        self.assertEqual(fm.field_tag('institution', ans, 'matriculation', locked), 'today too')

    def test_pages_bucket(self):
        self.assertEqual([fm.pages_bucket(p) for p in (1, 2, 3, 7, None, 0)],
                         ['1', '2', '3+', '3+', 'unknown', 'unknown'])


class TestFailureMapRun(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.c = _Corpus(self._tmp.name)
        # a1: stored AI read names the reporting venue; today's parser locks it right → old read.
        self.c.letter('offer_letter__a1__d11', _stored(), ext='pdf', route='text_layer',
                      text=MATRIC_TWIN, answer=_answer())
        # a2: a university letter, institution wrong, still Gemini today → ai, S3; judged not genuine.
        self.c.letter('offer_letter__a2__d12', _stored(institution='Kampus Perlak', stream=''),
                      seen='ua_offer', route='vision', text=UNIVERSITY_TWIN,
                      answer=_answer(institution_as_printed='Universiti Qorvane Perlak', stream=None,
                                     programme='Program Matrikulasi', family='other_university'))
        rp.replay_corpus(self.c.dir, write=True)
        self.split = os.path.join(self.c.dir, 'split.json')
        with open(self.split, 'w', encoding='utf-8') as f:
            json.dump({'heldout': []}, f)

    def tearDown(self):
        self._tmp.cleanup()

    def test_grid_kinds_and_tags(self):
        m = fm.failure_map(self.c.dir, 'dev', split_file=self.split)
        self.assertEqual(m['letters'], 2)
        self.assertEqual(m['grid']['institution'], {'wrong': 2, 'missing': 0, 'extra': 0})
        kinds = {k['kind']: k for k in m['kinds']}
        self.assertEqual(kinds['institution = reporting venue']['tags'], {'old read': 1})
        self.assertEqual(kinds['institution names a campus / branch / college the answer does not']['tags'],
                         {'ai, S3': 1})
        self.assertEqual(m['by']['input_kind']['text_pdf']['institution']['wrong'], 1)
        self.assertEqual(m['by']['stored_reader_version']['ai unversioned']['letters'], 2)

    def test_the_replay_read_can_be_mapped_and_nothing_prints_a_value(self):
        for argv in ([], ['--keys'], ['--json'], ['--read', 'file:' + rp.REPLAY_SUFFIX]):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = fm.main(['--eval-dir', self.c.dir, '--split-file', self.split, *argv])
            self.assertEqual(rc, 0)
            _assert_no_value(self, out.getvalue())
        m = fm.failure_map(self.c.dir, 'dev', 'file:' + rp.REPLAY_SUFFIX, self.split)
        self.assertEqual(m['grid']['institution']['wrong'], 1)    # the lock fixed a1

    def test_identical_on_rerun(self):
        a = fm.failure_map(self.c.dir, 'all', split_file=self.split)
        b = fm.failure_map(self.c.dir, 'all', split_file=self.split)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
