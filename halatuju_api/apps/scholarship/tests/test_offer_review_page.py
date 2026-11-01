"""The owner's offer-letter spot-check page (`eval/offer_review_page.py`) — offer exact-read S1,
2026-11-01. Synthetic twins only: every letter here is invented and built in a temp folder;
nothing reads the gitignored corpus (`test_no_gitignored_corpus.py`)."""
import contextlib
import io
import json
import os
import random
import re
import tempfile

from django.test import SimpleTestCase

from apps.scholarship.eval import offer_read_check as orc
from apps.scholarship.eval import offer_review_page as orp

#: Invented values. Each may appear in the PAGE (that is its job) but never in printed output.
SECRET_NAME = 'QUENTARO VELLISHAM A/L ZORBEX'
SECRET_NRIC = '010203-14-5678'
SECRET_INST = 'Kolej Zantharion <Perlak> & "Co"'
SECRET_STREAM = 'Sains Qorvane'


def _answer(**over):
    base = {f: None for f in orc.ANSWER_FIELDS}
    base.update({'candidate_name': SECRET_NAME, 'candidate_nric': SECRET_NRIC,
                 'institution_as_printed': SECRET_INST, 'programme': 'Diploma Qorvane',
                 'intake': 'Sesi 2031/2032', 'reporting_date': '17 Ogos 2031',
                 'is_offer_letter': 'yes', 'pages': 1, 'unsure_fields': [],
                 'labeller_note': None})
    base.update(over)
    return base


def _key(i):
    return f'offer_letter__a{1000 + i}__d{5000 + i}'


class _Corpus:
    """A tiny invented eval dir: `snapshots/`, `fixtures/offer_letter/`, and a split file."""

    def __init__(self, tmp):
        self.dir = os.path.join(tmp, 'corpus')
        os.makedirs(os.path.join(self.dir, 'snapshots'))
        os.makedirs(os.path.join(self.dir, 'fixtures', 'offer_letter'))
        self.split = os.path.join(tmp, 'split.json')
        self.heldout = []

    def letter(self, key, answer=None, ext='pdf', body=b'%PDF-1.4 invented', heldout=True,
               raw_answer=None):
        if answer is not None:
            self._write(os.path.join('snapshots', key + orc.ANSWER_SUFFIX), json.dumps(answer))
        if raw_answer is not None:
            self._write(os.path.join('snapshots', key + orc.ANSWER_SUFFIX), raw_answer)
        if ext:
            with open(os.path.join(self.dir, 'fixtures', 'offer_letter', f'{key}.{ext}'),
                      'wb') as fh:
                fh.write(body)
        if heldout:
            self.heldout.append(key)
        with open(self.split, 'w', encoding='utf-8') as fh:
            json.dump({'heldout': sorted(self.heldout)}, fh)

    def _write(self, rel, text):
        with open(os.path.join(self.dir, rel), 'w', encoding='utf-8') as fh:
            fh.write(text)

    def page(self):
        return _text(os.path.join(self.dir, orp.PAGE_NAME))


def _text(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = orp.main(argv)
    return rc, out.getvalue()


class _Base(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.c = _Corpus(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def argv(self, *extra):
        return ['--eval-dir', self.c.dir, '--split-file', self.c.split, *extra]


class TestSample(_Base):
    def _many(self, n_plain=30, unsure=(3, 7, 11)):
        for i in range(n_plain):
            fields = ['intake'] if i in unsure else []
            self.c.letter(_key(i), _answer(unsure_fields=fields))

    def test_every_unsure_letter_is_in_plus_a_seeded_random_20(self):
        self._many()
        keys, _, counts = orp.select_sample(self.c.dir, orc.load_heldout(self.c.split))
        for i in (3, 7, 11):
            self.assertIn(_key(i), keys)
        self.assertEqual(counts, {'unsure': 3, 'random': 20, 'skipped': 0, 'total': 23})
        self.assertEqual(keys, sorted(keys))
        rest = sorted(_key(i) for i in range(30) if i not in (3, 7, 11))
        expected = set(random.Random(orp.SEED).sample(rest, 20)) | {_key(3), _key(7), _key(11)}
        self.assertEqual(set(keys), expected)

    def test_the_draw_is_stable_and_follows_seed_and_n(self):
        self._many()
        heldout = orc.load_heldout(self.c.split)
        a, _, _ = orp.select_sample(self.c.dir, heldout)
        b, _, _ = orp.select_sample(self.c.dir, heldout)
        self.assertEqual(a, b)
        other, _, _ = orp.select_sample(self.c.dir, heldout, seed=1)
        self.assertNotEqual(a, other)
        only_unsure, _, counts = orp.select_sample(self.c.dir, heldout, n_random=0)
        self.assertEqual(only_unsure, [_key(3), _key(7), _key(11)])
        everything, _, counts = orp.select_sample(self.c.dir, heldout, n_random=500)
        self.assertEqual(counts['total'], 30)

    def test_dev_letters_and_unusable_answers_are_left_out(self):
        self.c.letter(_key(1), _answer())
        self.c.letter(_key(2), _answer(), heldout=False)               # dev
        self.c.letter(_key(3))                                        # held out, no answer
        self.c.letter(_key(4), raw_answer='{not json')                # malformed
        self.c.letter(_key(5), _answer(pages=0))                      # format problem
        keys, _, counts = orp.select_sample(self.c.dir, orc.load_heldout(self.c.split))
        self.assertEqual(keys, [_key(1)])
        self.assertEqual(counts['skipped'], 3)


class TestPage(_Base):
    def _build(self, *extra):
        self.c.letter(_key(1), _answer(unsure_fields=['candidate_nric']))
        self.c.letter(_key(2), _answer(stream=SECRET_STREAM, offer_date=None), ext='jpg',
                      body=b'\xff\xd8\xff invented')
        self.c.letter(_key(3), _answer(), ext='png', body=b'')        # empty file
        self.c.letter(_key(4), _answer(), ext=None)                   # no file at all
        self.c.letter(_key(5), _answer(), ext='pdf', body=b'garbage')  # damaged
        rc, out = _run(self.argv(*extra))
        self.assertEqual(rc, 0, out)
        return out, self.c.page()

    def test_one_card_per_sampled_key_and_the_save_button(self):
        _, page = self._build()
        self.assertEqual(len(re.findall(r'<section class="card"', page)), 5)
        for i in range(1, 6):
            self.assertEqual(page.count(f'data-key="{_key(i)}"'), 1)
        self.assertIn('<button type="button" id="save">Save my answers</button>', page)
        self.assertIn(orp.RESULTS_NAME, page)
        self.assertIn('localStorage', page)
        self.assertIn('new Blob', page)

    def test_every_line_starts_right_by_default(self):
        _, page = self._build()
        self.assertIn(orp.INSTRUCTION, page)
        self.assertIn('Every line is already marked Right.', page)
        self.assertIn('0 of 5 letters looked at or changed', page)
        self.assertIn('var MODE = "prefilled"', page)
        rights = page.count('value="right"')
        self.assertGreater(rights, 0)
        self.assertEqual(page.count('value="right" checked'), rights)
        self.assertNotIn('value="wrong" checked', page)
        self.assertIn('looked_at', page)                              # saved per letter

    def test_blank_flag_keeps_the_old_page(self):
        _, page = self._build('--blank')
        self.assertIn(orp.INSTRUCTION_BLANK, page)
        self.assertNotIn(orp.INSTRUCTION, page)
        self.assertIn('0 of 5 done', page)
        self.assertIn('var MODE = "blank"', page)
        self.assertNotIn(' checked>', page)

    def test_an_earlier_saved_tick_wins_over_the_default(self):
        """restore() runs after the defaults are in the HTML and sets the saved verdict;
        an untouched (not_checked) saved line leaves the default alone."""
        _, page = self._build()
        restore = page[page.index('function restore()'):page.index('restore();\n  refresh();')]
        self.assertIn('r.checked = (r.value === f.verdict)', restore)
        self.assertIn('f.verdict !== "right" && f.verdict !== "wrong"', restore)
        self.assertLess(page.index('value="right" checked'), page.index('function restore()'))

    def test_documents_load_by_relative_path_and_problems_are_plain_words(self):
        _, page = self._build()
        self.assertIn(f'<iframe class="doc" src="fixtures/offer_letter/{_key(1)}.pdf"', page)
        self.assertIn(f'<img src="fixtures/offer_letter/{_key(2)}.jpg"', page)
        self.assertIn('The document file is empty', page)
        self.assertIn('The document file is missing', page)
        self.assertIn('The document file looks damaged', page)
        self.assertNotIn(f'{_key(3)}.png"', page)                    # empty file not embedded

    def test_fields_labels_unsure_and_not_printed(self):
        _, page = self._build()
        for _, label in orp.PAGE_FIELDS:
            if label.startswith('Course —'):
                continue
            self.assertIn(f'<legend>{label}', page.replace('&#x27;', "'"))
        self.assertIn('Course — stream', page)                        # set on letter 2
        self.assertNotIn('Course — specialisation', page)             # never set
        self.assertIn('<legend>IC number <span class="unsure">unsure</span>', page)
        self.assertIn(orp.NOT_PRINTED, page)
        self.assertIn('>Yes<', page)                                  # is_offer_letter in words
        self.assertEqual(page.count('value="right"'), page.count('value="wrong"'))
        self.assertIn('What the letter really says', page)

    def test_values_are_escaped_and_nothing_external_is_loaded(self):
        _, page = self._build()
        self.assertNotIn('<Perlak>', page)
        self.assertIn('&lt;Perlak&gt; &amp; &quot;Co&quot;', page)
        self.assertIsNone(re.search(r'(src|href)="(https?:)?//', page))
        self.assertNotIn('<link', page)

    def test_printed_output_is_counts_and_path_only(self):
        out, _ = self._build()
        for secret in (SECRET_NAME, SECRET_NRIC, 'Zantharion', SECRET_STREAM, _key(1)):
            self.assertNotIn(secret, out)
        self.assertIn('sample: 5 letters (1 unsure + 4 random; skipped 0)', out)
        self.assertIn(orp.PAGE_NAME, out)

    def test_no_held_out_answers_writes_nothing(self):
        self.c.letter(_key(1), _answer(), heldout=False)
        rc, _ = _run(self.argv())
        self.assertEqual(rc, 2)
        self.assertFalse(os.path.exists(os.path.join(self.c.dir, orp.PAGE_NAME)))

    def test_refuses_a_tracked_folder_of_this_checkout(self):
        tracked = os.path.dirname(os.path.abspath(orp.__file__))
        self.assertFalse(orp.page_location_ok(tracked))
        self.assertTrue(orp.page_location_ok(orp._IGNORED_ROOT + os.sep + 'x'))
        self.assertTrue(orp.page_location_ok(self.c.dir))
        rc, out = _run(['--eval-dir', tracked, '--split-file', self.c.split])
        self.assertEqual(rc, 2)
        self.assertIn('Refused', out)


class TestApply(_Base):
    def _results(self):
        def f(verdict, correction=''):
            return {'verdict': verdict, 'correction': correction}
        letters = {
            _key(1): {'fields': {n: f('right') for n in orp.FIELD_NAMES}, 'note': ''},
            _key(2): {'fields': {'candidate_name': f('wrong', SECRET_NAME),
                                 'intake': f('wrong'), 'issuer': f('right'),
                                 'offer_date': f('not_checked')}, 'note': 'see page 2'},
            _key(3): {'fields': {'candidate_name': f('not_checked')}, 'note': ''},
            _key(4): {'fields': {'candidate_nric': f('wrong', SECRET_NRIC),
                                 'mystery_field': f('right'), 'intake': f('maybe')}, 'note': ''},
            _key(5): 'not a dict',
        }
        path = os.path.join(self._tmp.name, orp.RESULTS_NAME)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump({'page': 'review_s1', 'letters': letters}, fh)
        return path

    def test_counts(self):
        c = orp.apply_counts(json.loads(_text(self._results())))
        self.assertEqual(c['letters'], 5)
        self.assertEqual(c['fully_checked'], 2)                      # key 1, key 4 (its 1 valid)
        self.assertEqual(c['partly_checked'], 1)                     # key 2
        self.assertEqual(c['not_started'], 1)                        # key 3
        self.assertEqual(c['letters_with_any_wrong'], 2)
        self.assertEqual(c['wrong_by_field']['candidate_name'], 1)
        self.assertEqual(c['wrong_by_field']['intake'], 1)
        self.assertEqual(c['wrong_by_field']['candidate_nric'], 1)
        self.assertEqual(c['wrong_by_field']['issuer'], 0)
        self.assertEqual(c['corrections_typed'], 2)
        self.assertEqual(c['notes_typed'], 1)
        self.assertEqual(c['unreadable_entries'], 3)                 # 2 bad lines + 1 bad letter

    def test_apply_prints_counts_only_and_changes_no_answer_file(self):
        self.c.letter(_key(1), _answer())
        answer_path = os.path.join(self.c.dir, 'snapshots', _key(1) + orc.ANSWER_SUFFIX)
        before = _text(answer_path)
        rc, out = _run(['--apply', self._results()])
        self.assertEqual(rc, 0)
        for secret in (SECRET_NAME, SECRET_NRIC, 'see page 2', 'mystery_field', _key(2)):
            self.assertNotIn(secret, out)
        self.assertIn('letters with any line marked wrong: 2', out)
        self.assertIn('No answer file was changed.', out)
        self.assertEqual(_text(answer_path), before)
        self.assertFalse(os.path.exists(os.path.join(self.c.dir, orp.PAGE_NAME)))

    def test_apply_bad_file(self):
        bad = os.path.join(self._tmp.name, 'bad.json')
        with open(bad, 'w', encoding='utf-8') as fh:
            fh.write('{nope')
        self.assertEqual(_run(['--apply', bad])[0], 1)
        self.assertEqual(_run(['--apply', os.path.join(self._tmp.name, 'absent.json')])[0], 2)
