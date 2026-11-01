"""The offer-letter exact-read scorer (`eval/offer_read_check.py`), the held-out split maker
(`eval/offer_split.py`) and the paged corpus fetch (`eval/fetch_corpus.rest`) — offer exact-read
S1, 2026-11-01. Synthetic twins only: every letter here is invented and built in a temp folder;
nothing reads the gitignored corpus (`test_no_gitignored_corpus.py`)."""
import contextlib
import io
import json
import os
import re
import tempfile

from django.test import SimpleTestCase

from apps.scholarship.eval import fetch_corpus
from apps.scholarship.eval import offer_read_check as orc
from apps.scholarship.eval import offer_split

#: Invented values. Each must never appear in the scorer's output.
SECRET_NAME = 'QUENTARO VELLISHAM A/L ZORBEX'
SECRET_NRIC = '010203-14-5678'
SECRET_INST = 'Kolej Zantharion Perlak'
SECRET_PROG = 'Diploma Kejuruteraan Qorvane'
SECRET_INTAKE = 'Sesi 2031/2032'
SECRET_DATE = '17 Ogos 2031'


def _answer(**over):
    base = {f: None for f in orc.ANSWER_FIELDS}
    base.update({'candidate_name': SECRET_NAME, 'candidate_nric': SECRET_NRIC,
                 'institution_as_printed': SECRET_INST, 'programme': SECRET_PROG,
                 'intake': SECRET_INTAKE, 'reporting_date': SECRET_DATE,
                 'is_offer_letter': 'yes', 'pages': 1, 'unsure_fields': [], 'labeller_note': None})
    base.update(over)
    return base


def _read(**over):
    base = {'candidate_name': SECRET_NAME.lower(), 'candidate_nric': '010203145678',
            'institution': SECRET_INST.upper(), 'programme': SECRET_PROG, 'intake': '2031/2032',
            'reporting_date': '17/08/2031', 'offer_date': '', 'issuer': '', 'stream': '',
            'bidang_pengkhususan': ''}
    base.update(over)
    return base


class TestTidying(SimpleTestCase):
    def test_text_ignores_case_spacing_punctuation_and_accents(self):
        self.assertEqual(orc.tidy_text('  Kolej   Matrikulasi, Perak. '), 'KOLEJ MATRIKULASI PERAK')
        self.assertEqual(orc.tidy_text('ALI A/L ABU'), orc.tidy_text('ali a/l  abu'))
        self.assertEqual(orc.tidy_text("D'Cruz"), 'DCRUZ')
        self.assertEqual(orc.tidy_text('Café'), 'CAFE')
        self.assertEqual(orc.tidy_text(None), '')
        self.assertEqual(orc.tidy_text(' - '), '')

    def test_no_fuzzy_matching_beyond_tidying(self):
        self.assertNotEqual(orc.tidy_text('Diploma Kejuruteraan Mekanikal'),
                            orc.tidy_text('Diploma Kejuruteraan Mekanikal (DKM)'))
        self.assertNotEqual(orc.tidy_text('MUHAMAD'), orc.tidy_text('MUHAMMAD'))

    def test_nric_digits_only(self):
        self.assertEqual(orc.tidy_nric('010203-14-5678'), '010203145678')
        self.assertEqual(orc.tidy_nric(' 010203 14 5678 '), '010203145678')
        self.assertEqual(orc.tidy_nric(None), '')

    def test_dates_become_d_mon_yyyy(self):
        for raw in ('17/08/2031', '17-8-31', '17.08.2031', '2031-08-17', '17 Ogos 2031',
                    '17 AUGUST 2031', 'Ahad, 17 Ogos 2031', '17 OGOS 2031 (AHAD)',
                    '17hb Ogos 2031', 'August 17, 2031', '17 Ogos 2031 8.00 pagi',
                    '17 HINGGA 18 OGOS 2031'):
            with self.subTest(raw=raw):
                self.assertEqual(orc.tidy_date(raw), '17 Aug 2031')

    def test_malay_and_english_months_agree(self):
        pairs = [('1 Januari 2030', '1 Jan 2030'), ('3 Mac 2030', '3 March 2030'),
                 ('5 Mei 2030', '5 May 2030'), ('7 Julai 2030', '7 Jul 2030'),
                 ('9 Oktober 2030', '9 Oct 2030'), ('11 Disember 2030', '11 Dec 2030')]
        for a, b in pairs:
            with self.subTest(a=a):
                self.assertEqual(orc.tidy_date(a), orc.tidy_date(b))

    def test_an_unparseable_date_is_compared_as_text(self):
        self.assertEqual(orc.tidy_date('akan dimaklumkan'), 'AKAN DIMAKLUMKAN')
        self.assertEqual(orc.tidy_date(''), '')

    def test_intake_drops_its_label_and_reads_months_one_way(self):
        self.assertEqual(orc.tidy_intake('Sesi 2031/2032'), orc.tidy_intake('2031/2032'))
        self.assertEqual(orc.tidy_intake('SESI AKADEMIK 2031/2032'), '2031 2032')
        self.assertEqual(orc.tidy_intake('Ambilan Julai 2031'), orc.tidy_intake('jul 2031'))
        self.assertNotEqual(orc.tidy_intake('2031/2032'), orc.tidy_intake('2031/32'))

    def test_intake_tahun_before_a_year_is_part_of_the_label(self):
        self.assertEqual(orc.tidy_intake('Ambilan Tahun 2031'), '2031')
        self.assertEqual(orc.tidy_intake('TAHUN 2031'), '2031')
        self.assertEqual(orc.tidy_intake('Sesi Tahun 2031/2032'), orc.tidy_intake('2031/2032'))

    def test_intake_tahun_without_a_following_year_stays(self):
        self.assertEqual(orc.tidy_intake('Tahun Satu'), 'TAHUN SATU')
        self.assertEqual(orc.tidy_intake('Tahun 1'), 'TAHUN 1')
        self.assertEqual(orc.tidy_intake('Tahun'), 'TAHUN')
        self.assertEqual(orc.tidy_intake('2031 Tahun'), '2031 TAHUN')
        self.assertNotEqual(orc.tidy_intake('Tahun Akademik 2031'), '2031')

    def test_institution_trailing_bracketed_acronym_is_optional(self):
        for raw in ('Universiti Zantharion Perlak (UniZP)', 'Universiti Zantharion Perlak (UZP)',
                    'UNIVERSITI ZANTHARION PERLAK  (UZP) ',
                    'Universiti Zantharion Perlak(U-Z.P&2)', 'universiti zantharion perlak'):
            with self.subTest(raw=raw):
                self.assertEqual(orc.tidy_institution(raw), 'UNIVERSITI ZANTHARION PERLAK')
        self.assertEqual(orc.tidy_institution(None), '')
        out = orc.score_letter(_answer(institution_as_printed='Universiti Zantharion Perlak (UZP)'),
                               _read(institution='Universiti Zantharion Perlak'), 'other_university')
        self.assertEqual(out['institution'], 'exact')
        out = orc.score_letter(_answer(institution_as_printed='Universiti Zantharion Perlak'),
                               _read(institution='UNIVERSITI ZANTHARION PERLAK (UZP)'), 'uitm')
        self.assertEqual(out['institution'], 'exact')

    def test_institution_other_brackets_stay(self):
        mid = 'Universiti Zantharion Perlak (UZP) Kampus Qorvane'
        self.assertEqual(orc.tidy_institution(mid),
                         'UNIVERSITI ZANTHARION PERLAK UZP KAMPUS QORVANE')
        self.assertNotEqual(orc.tidy_institution(mid),
                            orc.tidy_institution('Universiti Zantharion Perlak Kampus Qorvane'))
        # only ONE trailing token goes; too short, too long or spaced inside is not an acronym
        self.assertEqual(orc.tidy_institution('Kolej Qorvane (KQ) (UZP)'), 'KOLEJ QORVANE KQ')
        self.assertEqual(orc.tidy_institution('Kolej Qorvane (K)'), 'KOLEJ QORVANE K')
        self.assertEqual(orc.tidy_institution('Kolej Qorvane (ABCDEFGHIJKLM)'),
                         'KOLEJ QORVANE ABCDEFGHIJKLM')
        self.assertEqual(orc.tidy_institution('Kolej Qorvane (Kampus Utara)'),
                         'KOLEJ QORVANE KAMPUS UTARA')
        self.assertEqual(orc.tidy_institution('(UZP)'), 'UZP')
        # the rule is the institution's only: programme still differs with an acronym
        out = orc.score_letter(_answer(programme='Diploma Qorvane (DQ)'),
                               _read(programme='Diploma Qorvane'), 'polytechnic')
        self.assertEqual(out['programme'], 'wrong')


class TestOutcomes(SimpleTestCase):
    def test_each_outcome_kind(self):
        t = orc.tidy_text
        self.assertEqual(orc.field_outcome('Abc', 'ABC ', t), 'exact')
        self.assertEqual(orc.field_outcome(None, '', t), 'blank_correct')
        self.assertEqual(orc.field_outcome(None, None, t), 'blank_correct')
        self.assertEqual(orc.field_outcome('Abc', '', t), 'missing')
        self.assertEqual(orc.field_outcome('Abc', 'Abd', t), 'wrong')
        self.assertEqual(orc.field_outcome(None, 'Abc', t), 'extra')

    def test_blank_correct_needs_the_letter_to_print_nothing(self):
        out = orc.score_letter(_answer(reporting_date=None), _read(reporting_date=''), 'polytechnic')
        self.assertEqual(out['reporting_date'], 'blank_correct')
        out = orc.score_letter(_answer(), _read(reporting_date=''), 'polytechnic')
        self.assertEqual(out['reporting_date'], 'missing')

    def test_a_tidied_read_of_every_core_field_is_fully_exact(self):
        out = orc.score_letter(_answer(), _read(), 'polytechnic')
        self.assertEqual({f: out[f] for f in orc.CORE}, {f: 'exact' for f in orc.CORE})
        self.assertTrue(orc.fully_exact(out))

    def test_fully_exact_allows_blank_correct_and_ignores_not_core(self):
        out = orc.score_letter(_answer(intake=None, offer_date='1 Jan 2031', issuer='X'),
                               _read(intake='', offer_date='', issuer='Y'), 'polytechnic')
        self.assertEqual(out['intake'], 'blank_correct')
        self.assertEqual((out['offer_date'], out['issuer']), ('missing', 'wrong'))
        self.assertTrue(orc.fully_exact(out))

    def test_one_core_field_not_right_breaks_fully_exact(self):
        for read in (_read(candidate_nric='010203145679'), _read(institution=''),
                     _read(intake='2031')):
            with self.subTest(read=sorted(read.items())):
                self.assertFalse(orc.fully_exact(orc.score_letter(_answer(), read, 'polytechnic')))
        extra = orc.score_letter(_answer(intake=None), _read(), 'polytechnic')
        self.assertEqual(extra['intake'], 'extra')
        self.assertFalse(orc.fully_exact(extra))

    def test_programme_is_the_stream_for_stpm_and_matric_and_the_programme_elsewhere(self):
        ans = _answer(programme='Tingkatan Enam', stream='Sains Sosial')
        for fam in ('stpm', 'matriculation'):
            self.assertEqual(orc.score_letter(ans, _read(programme='', stream='SAINS SOSIAL'),
                                              fam)['programme'], 'exact')
            self.assertEqual(orc.score_letter(ans, _read(programme='Tingkatan Enam', stream=''),
                                              fam)['programme'], 'missing')
        self.assertEqual(orc.score_letter(_answer(), _read(), 'uitm')['programme'], 'exact')

    def test_pismp_programme_is_the_degree_title_not_the_specialisation(self):
        # owner 2026-11-01: PISMP's programme is the degree title, like any university course
        ans = _answer(programme='Ijazah Sarjana Muda Qorvane', specialisation='Pendidikan Qorvane')
        out = orc.score_letter(ans, _read(programme='IJAZAH SARJANA MUDA QORVANE',
                                          bidang_pengkhususan='pendidikan qorvane'), 'pismp')
        self.assertEqual((out['programme'], out['specialisation']), ('exact', 'exact'))
        out = orc.score_letter(ans, _read(programme='Program Ijazah Sarjana Muda Qorvane (PISMQ)',
                                          bidang_pengkhususan='pendidikan qorvane'), 'pismp')
        self.assertEqual((out['programme'], out['specialisation']), ('wrong', 'exact'))
        # the specialisation read right no longer rescues a programme read wrong
        out = orc.score_letter(ans, _read(programme='Pendidikan Qorvane',
                                          bidang_pengkhususan='pendidikan qorvane'), 'pismp')
        self.assertEqual(out['programme'], 'wrong')
        self.assertFalse(orc.fully_exact(out))

    def test_specialisation_is_scored_not_core_wherever_the_answer_has_one(self):
        ans = _answer(specialisation='Pendidikan Qorvane')
        for fam in ('pismp', 'other_university', 'polytechnic'):
            with self.subTest(fam=fam):
                out = orc.score_letter(ans, _read(bidang_pengkhususan=''), fam)
                self.assertEqual(out['specialisation'], 'missing')
                self.assertTrue(orc.fully_exact(out))        # not core
                out = orc.score_letter(ans, _read(bidang_pengkhususan='Pendidikan Zorbex'), fam)
                self.assertEqual(out['specialisation'], 'wrong')
        # no specialisation in the answer: not scored at all (no blank_correct, no extra)
        self.assertNotIn('specialisation',
                         orc.score_letter(_answer(), _read(bidang_pengkhususan='X'), 'pismp'))

    def test_specialisation_percent_is_over_the_letters_scored_on_it(self):
        scored = [{'outcomes': orc.score_letter(_answer(specialisation='Pendidikan Qorvane'),
                                                _read(bidang_pengkhususan='Pendidikan Qorvane'),
                                                'pismp'), 'fully_exact': True},
                  {'outcomes': orc.score_letter(_answer(), _read(), 'uitm'), 'fully_exact': True}]
        tally = orc._tally(scored)
        self.assertEqual(sum(tally['fields']['specialisation'].values()), 1)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            orc._print_fields(tally, ('issuer', 'specialisation'))
        self.assertRegex(out.getvalue(), r'specialisation\s+1\s+0\s+0\s+0\s+0\s+100\.0%\s+1')
        self.assertRegex(out.getvalue(), r'issuer\s+0\s+2\s+0\s+0\s+0\s+100\.0%\s+2')


class TestAnswerFormatAndFamily(SimpleTestCase):
    def test_a_complete_answer_has_no_problems(self):
        self.assertEqual(orc.answer_problems(_answer()), [])
        self.assertEqual(orc.answer_problems(_answer(family='pismp', unsure_fields=['intake'])), [])

    def test_every_field_must_be_present_even_when_null(self):
        ans = _answer()
        del ans['fees']
        self.assertEqual(orc.answer_problems(ans), ['absent:fees'])

    def test_bad_values_are_named_by_field(self):
        bad = _answer(is_offer_letter='maybe', pages=True, unsure_fields=['nope'], family='x')
        self.assertEqual(orc.answer_problems(bad),
                         ['family', 'is_offer_letter', 'pages', 'unsure_fields'])
        self.assertEqual(orc.answer_problems([]), ['not_an_object'])

    def test_family_from_the_stored_read(self):
        def vf(seen, inst=''):
            return {'authenticity': {'doc_seen': seen}, 'fields': {'institution': inst}}
        self.assertEqual(orc.offer_family(vf('stpm')), 'stpm')
        self.assertEqual(orc.offer_family(vf('ua_offer', 'Universiti Teknologi MARA')), 'uitm')
        self.assertEqual(orc.offer_family(vf('ua_offer', 'UiTM Cawangan X')), 'uitm')
        self.assertEqual(orc.offer_family(vf('ua_offer', 'Universiti Qorvane')), 'other_university')
        self.assertEqual(orc.offer_family(vf('tvet_belia_sukan')), 'tvet')
        self.assertEqual(orc.offer_family(vf(None)), 'other')
        self.assertEqual(orc.offer_family({}), 'other')
        self.assertEqual(orc.offer_family({'authenticity': 'not a dict'}), 'other')
        self.assertEqual(orc.offer_family(vf('stpm'), {'family': 'pismp'}), 'pismp')


class _Corpus:
    """A synthetic corpus folder shaped like the real one."""

    def __init__(self, tmp):
        self.dir = tmp
        os.makedirs(os.path.join(tmp, 'snapshots'))
        os.makedirs(os.path.join(tmp, 'fixtures', 'offer_letter'))
        self.programmes = []

    def letter(self, key, read, capture='ai', seen='polytechnic', ext='pdf', answer=None,
               programme='prog-a', raw_answer=None):
        snap = {'vision_fields': {'fields': read, 'capture': capture,
                                  'authenticity': {'doc_seen': seen}}}
        self._write(os.path.join('snapshots', key + '.json'), json.dumps(snap))
        self._write(os.path.join('fixtures', 'offer_letter', f'{key}.{ext}'), 'x')
        if answer is not None:
            self._write(os.path.join('snapshots', key + orc.ANSWER_SUFFIX), json.dumps(answer))
        if raw_answer is not None:
            self._write(os.path.join('snapshots', key + orc.ANSWER_SUFFIX), raw_answer)
        self.programmes.append((key, programme))

    def finish(self, heldout=()):
        rows = 'key,app_id,programme\n' + ''.join(f'{k},1,{p}\n' for k, p in self.programmes)
        self._write('programme_by_key.csv', rows)
        split = os.path.join(self.dir, 'split.json')
        with open(split, 'w', encoding='utf-8') as fh:
            json.dump({'heldout': sorted(heldout)}, fh)
        return split

    def _write(self, rel, text):
        with open(os.path.join(self.dir, rel), 'w', encoding='utf-8') as fh:
            fh.write(text)


def _run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = orc.main(argv)
    return rc, out.getvalue()


class TestScorerRun(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.c = _Corpus(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _three_letters(self):
        self.c.letter('offer_letter__a1__d11', _read(), answer=_answer())
        self.c.letter('offer_letter__a2__d12', _read(candidate_nric=''), answer=_answer(),
                      ext='jpg', programme='prog-b')
        self.c.letter('offer_letter__a3__d13', _read(), capture='deterministic', seen='stpm')
        return self.c.finish(heldout=['offer_letter__a1__d11', 'offer_letter__a2__d12'])

    def test_scores_counts_and_lists_keys_with_field_names(self):
        split = self._three_letters()
        rc, out = _run(['--eval-dir', self.c.dir, '--split-file', split, '--split', 'heldout'])
        self.assertEqual(rc, 0)
        self.assertIn('with answers: 2', out)
        self.assertIn('FULLY EXACT (every core field exact or blank_correct): 1 of 2 (50.0%)', out)
        self.assertRegex(out, r'offer_letter__a2__d12\s+nric')
        self.assertNotRegex(out, r'offer_letter__a1__d11\s+\w')

    def test_no_value_is_ever_printed(self):
        split = self._three_letters()
        tidied = [orc.tidy_text(v) for v in (SECRET_NAME, SECRET_INST, SECRET_PROG)]
        for argv in (['--split', 'all'], ['--split', 'heldout'], ['--split', 'all', '--json']):
            _, out = _run(['--eval-dir', self.c.dir, '--split-file', split, *argv])
            up = out.upper()
            for value in (SECRET_NAME, SECRET_NRIC, SECRET_INST, SECRET_PROG, SECRET_INTAKE,
                          SECRET_DATE, *tidied):
                self.assertNotIn(value.upper(), up, argv)
            for token in ('QUENTARO', 'VELLISHAM', 'ZORBEX', 'ZANTHARION', 'QORVANE', '2031',
                          '010203', '145678', 'OGOS'):
                self.assertNotIn(token, up, (argv, token))

    def test_output_is_identical_on_rerun(self):
        split = self._three_letters()
        argv = ['--eval-dir', self.c.dir, '--split-file', split, '--split', 'all']
        self.assertEqual(_run(argv), _run(argv))

    def test_groups_by_family_input_kind_capture_programme_and_split(self):
        split = self._three_letters()
        _, out = _run(['--eval-dir', self.c.dir, '--split-file', split, '--split', 'all',
                       '--json'])
        groups = json.loads(out)['groups']
        self.assertEqual(sorted(groups['input_kind']), ['pdf', 'photo'])
        self.assertEqual(sorted(groups['programme']), ['prog-a', 'prog-b'])
        self.assertEqual(sorted(groups['capture']), ['ai'])
        self.assertEqual(sorted(groups['split']), ['heldout'])
        self.assertEqual(sorted(groups['family']), ['polytechnic'])

    def test_no_answers_says_so_cleanly(self):
        self.c.letter('offer_letter__a1__d11', _read())
        split = self.c.finish()
        rc, out = _run(['--eval-dir', self.c.dir, '--split-file', split, '--split', 'all'])
        self.assertEqual(rc, 0)
        self.assertIn('0 letters with answers - nothing to score.', out)

    def test_an_empty_folder_exits_2(self):
        rc, out = _run(['--eval-dir', os.path.join(self.c.dir, 'nothing-here')])
        self.assertEqual(rc, 2)

    def test_a_broken_answer_is_reported_not_scored(self):
        self.c.letter('offer_letter__a1__d11', _read(), raw_answer='{not json')
        bad = _answer()
        del bad['pages']
        self.c.letter('offer_letter__a2__d12', _read(), answer=bad)
        split = self.c.finish()
        rc, out = _run(['--eval-dir', self.c.dir, '--split-file', split, '--split', 'all'])
        self.assertEqual(rc, 1)
        self.assertRegex(out, r'FORMAT offer_letter__a1__d11\s+not_json')
        self.assertRegex(out, r'FORMAT offer_letter__a2__d12\s+absent:pages,pages')
        self.assertIn('0 letters with answers - nothing to score.', out)

    def test_another_read_source_is_scored_the_same_way(self):
        self.c.letter('offer_letter__a1__d11', _read(candidate_nric=''), answer=_answer())
        with open(os.path.join(self.c.dir, 'snapshots', 'offer_letter__a1__d11.fresh.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump({'fields': _read(), 'capture': 'fresh'}, fh)
        split = self.c.finish()
        base = ['--eval-dir', self.c.dir, '--split-file', split, '--split', 'all', '--json']
        stored = json.loads(_run(base)[1])
        fresh = json.loads(_run(base + ['--read', 'file:.fresh.json'])[1])
        self.assertEqual((stored['total']['fully_exact'], fresh['total']['fully_exact']), (0, 1))
        self.assertEqual(sorted(fresh['groups']['capture']), ['fresh'])
        with self.assertRaises(ValueError):
            orc.read_source('gemini')

    def test_known_format_ai_count_covers_the_whole_corpus(self):
        self.c.letter('offer_letter__a1__d11', _read(), seen='stpm', ext='jpg')
        self.c.letter('offer_letter__a2__d12', _read(), seen='matriculation', programme='prog-b')
        self.c.letter('offer_letter__a3__d13', _read(), seen='polytechnic', capture='deterministic')
        self.c.letter('offer_letter__a4__d14', _read(), seen='ua_offer')
        split = self.c.finish(heldout=['offer_letter__a4__d14'])
        _, out = _run(['--eval-dir', self.c.dir, '--split-file', split, '--json'])
        self.assertEqual(json.loads(out)['known_format_ai'], {
            'total': 2, 'by_family': {'matriculation': 1, 'stpm': 1},
            'by_input_kind': {'pdf': 1, 'photo': 1}, 'by_programme': {'prog-a': 1, 'prog-b': 1}})


def _split_rows(n_unseen=40, n_seen=10, n_det=6):
    rows = []
    fams = ('stpm', 'polytechnic', 'other_university', 'pismp')
    for i in range(n_unseen):
        rows.append({'key': f'offer_letter__a{i}__d{1000 + i}', 'family': fams[i % 4],
                     'programme': 'p1' if i % 3 else 'p2', 'capture': 'ai', 'seen_before': False})
    for i in range(n_seen):
        rows.append({'key': f'offer_letter__a{100 + i}__d{2000 + i}', 'family': 'stpm',
                     'programme': 'p1', 'capture': 'ai', 'seen_before': True})
    for i in range(n_det):
        rows.append({'key': f'offer_letter__a{200 + i}__d{3000 + i}', 'family': 'polytechnic',
                     'programme': 'p1', 'capture': 'deterministic', 'seen_before': False})
    return rows


class TestHeldOutSplit(SimpleTestCase):
    def test_the_same_rows_give_the_same_split(self):
        self.assertEqual(offer_split.build_split(_split_rows(), target=20),
                         offer_split.build_split(list(reversed(_split_rows())), target=20))

    def test_the_seed_drives_the_draw(self):
        a = offer_split.build_split(_split_rows(), seed=1, target=20)['heldout']
        b = offer_split.build_split(_split_rows(), seed=2, target=20)['heldout']
        self.assertNotEqual(a, b)
        self.assertEqual(len(a), len(b))

    def test_only_unseen_ai_reads_are_drawn(self):
        split = offer_split.build_split(_split_rows(), target=20)
        self.assertEqual((split['pool'], split['heldout_count']), (40, 20))
        self.assertTrue(all(int(re.search(r'__d(\d+)', k).group(1)) < 2000
                            for k in split['heldout']))
        self.assertEqual((split['seen_before'], split['deterministic_unseen']), (10, 6))

    def test_a_small_pool_is_all_held_out(self):
        split = offer_split.build_split(_split_rows(n_unseen=7), target=90)
        self.assertEqual(split['heldout_count'], 7)

    def test_allocation_is_proportional_with_a_floor_of_one(self):
        quota = offer_split.allocate({'big': 50, 'mid': 20, 'pair': 2, 'one': 1}, 20)
        self.assertEqual(sum(quota.values()), 20)
        self.assertGreaterEqual(quota['pair'], 1)
        self.assertGreater(quota['big'], quota['mid'])
        self.assertTrue(all(quota[s] <= n for s, n in {'big': 50, 'mid': 20, 'pair': 2,
                                                       'one': 1}.items()))
        self.assertEqual(offer_split.allocate({}, 5), {})

    def test_the_committed_split_is_keys_only_and_self_consistent(self):
        path = os.path.join(os.path.dirname(orc.__file__), 'offer_split.json')
        with open(path, encoding='utf-8') as fh:
            split = json.load(fh)
        keys = split['heldout']
        self.assertEqual(keys, sorted(set(keys)))
        self.assertTrue(all(re.fullmatch(r'offer_letter__a\d+__d\d+', k) for k in keys))
        self.assertEqual(len(keys), split['heldout_count'])
        self.assertEqual(sum(s['heldout'] for s in split['strata'].values()), len(keys))
        self.assertEqual((split['seed'], split['target']), (offer_split.SEED, offer_split.TARGET))
        self.assertEqual(split['rule'], offer_split.RULE)
        self.assertLessEqual(len(keys), split['pool'])


class TestFetchCorpusPaging(SimpleTestCase):
    """PostgREST caps a response at its max-rows whatever `limit` says; the fetch must page."""

    def _server(self, rows, cap):
        calls = []

        def get_page(base, key, table, query):
            calls.append(dict(query))
            off, lim = int(query['offset']), int(query['limit'])
            return rows[off:off + min(lim, cap)]
        return get_page, calls

    def test_every_row_comes_back_past_the_server_cap(self):
        rows = [{'id': i} for i in range(2500)]
        for cap in (1000, 300):
            with self.subTest(cap=cap):
                get_page, calls = self._server(rows, cap)
                got = fetch_corpus.rest('b', 'k', 't', 'id', get_page=get_page)
                self.assertEqual(got, rows)
                self.assertEqual(calls[-1]['offset'], '2500')   # stops on an EMPTY page

    def test_filters_and_a_stable_order_go_on_every_page(self):
        get_page, calls = self._server([{'id': i} for i in range(1500)], 1000)
        fetch_corpus.rest('b', 'k', 'applicant_documents', 'id,doc_type',
                          {'doc_type': 'in.(offer_letter)'}, get_page=get_page)
        self.assertEqual(len(calls), 3)
        for q in calls:
            self.assertEqual((q['doc_type'], q['order'], q['select']),
                             ('in.(offer_letter)', 'id', 'id,doc_type'))
        get_page, calls = self._server([], 1000)
        self.assertEqual(fetch_corpus.rest('b', 'k', 'api_student_profiles', 'supabase_user_id',
                                           order='supabase_user_id', get_page=get_page), [])
        self.assertEqual([q['order'] for q in calls], ['supabase_user_id'])
