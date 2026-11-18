"""LL3: the model digest itself - what it reads, what it ignores, and what it refuses.

Split out of `test_model_versions.py` (the version guard) to keep both under the 600-line cap.
That file checks every registered model against its log; this one checks the fingerprint those
checks rely on: stable across Python versions and line endings, moved by any logic change, and
refusing source shapes that would let a logic change through with the same digest.
"""
import hashlib
import pathlib
import tempfile
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import model_registry as registry

#: `halatuju_api/`, three levels up from this file's own folder.
API_ROOT = pathlib.Path(__file__).resolve().parents[3]

#: A pinned sample: BOM, CRLF endings, comments, docstrings, a '#' inside an f-string, the version
#: line, and multi-line strings (one an f-string) holding a blank line and trailing spaces.
_SAMPLE = (
    '﻿"""Module docstring."""\r\n'
    "MODEL_VERSION = '9.9.9'  # bump me\r\n"
    'PROMPT = (\r\n'
    "    'Read the slip. '  # why\r\n"
    "    'Answer in JSON.')\r\n"
    'TEMPLATE = """first line\r\n'
    '\r\n'
    '  keep my trailing spaces   \r\n'
    'last"""\r\n'
    '\r\n'
    '\r\n'
    'def score(x):\r\n'
    '    """Docstring goes."""\r\n'
    "    label = f'{x} # not a comment'   \r\n"
    '    note = f"""{x}\r\n'
    '   \r\n'
    'done"""\r\n'
    '    return label  # a comment\r\n')

_SAMPLE_CLEAN = (
    'PROMPT = (\n'
    "    'Read the slip. '\n"
    "    'Answer in JSON.')\n"
    'TEMPLATE = """first line\n'
    '\n'
    '  keep my trailing spaces   \n'
    'last"""\n'
    'def score(x):\n'
    "    label = f'{x} # not a comment'\n"
    '    note = f"""{x}\n'
    '   \n'
    'done"""\n'
    '    return label')

#: sha256 of the sample as a one-file model. Hard-coded on purpose: if this moves, every seeded
#: digest in model_versions/ moves with it, and every model would demand a bump at once.
_SAMPLE_DIGEST = '20570bd6957328d0b8d28ce0826c43e5e8db92bd60351dbadfefa188ecc7efed'


def _sample_digest(source=_SAMPLE, extra=None, pins=()):
    """The digest of a throwaway one-file model `m.py` (plus `extra` files) in a temporary tree."""
    files = {'m.py': source.encode('utf-8'), **(extra or {})}
    with tempfile.TemporaryDirectory() as tmp:
        for rel, data in files.items():
            (pathlib.Path(tmp) / rel).write_bytes(data)
        spec = {'constant': ('m.py', 'MODEL_VERSION'), 'files': ['m.py'], 'pins': list(pins)}
        with mock.patch.dict(registry.MODELS, {'fake': spec}):
            return registry.model_digest(tmp, 'fake')


class TestTheDigestIsStable(SimpleTestCase):
    def test_the_cleaned_text_is_pinned(self):
        """The cleaning is the contract. It must not depend on the Python version (production
        runs 3.11), the line endings git happened to check out, or a BOM."""
        text = _SAMPLE.lstrip('﻿').replace('\r\n', '\n')
        self.assertEqual(registry.clean_model_source(text, drop_names=('MODEL_VERSION',)),
                         _SAMPLE_CLEAN)

    def test_the_digest_is_pinned(self):
        self.assertEqual(_sample_digest(), _SAMPLE_DIGEST)
        self.assertEqual(_sample_digest(), hashlib.sha256(
            b'4:m.py' + f'{len(_SAMPLE_CLEAN.encode())}:'.encode() + _SAMPLE_CLEAN.encode()).hexdigest())

    def test_line_endings_and_the_version_value_do_not_move_it(self):
        base = _sample_digest()
        self.assertEqual(_sample_digest(_SAMPLE.replace('\r\n', '\n')), base)
        self.assertEqual(_sample_digest(_SAMPLE.replace("'9.9.9'", "'10.0.0'")), base)

    def test_comments_docstrings_and_blank_lines_do_not_move_it(self):
        base = _sample_digest()
        for edited in (_SAMPLE.replace('# a comment', '# another comment'),
                       _SAMPLE.replace('Docstring goes.', 'Docstring says more now.'),
                       _SAMPLE.replace('def score', '\r\n\r\ndef score'),
                       _SAMPLE.replace('    return label', '    # new note\r\n    return label')):
            with self.subTest(edited=edited):
                self.assertEqual(_sample_digest(edited), base)

    def test_a_logic_change_moves_it(self):
        base = _sample_digest()
        for edited in (_SAMPLE.replace('return label', 'return label.upper()'),
                       _SAMPLE.replace('Answer in JSON.', 'Answer in YAML.'),
                       _SAMPLE.replace('# not a comment', '# still not a comment')):
            with self.subTest(edited=edited):
                self.assertNotEqual(_sample_digest(edited), base)

    def test_a_blank_line_or_trailing_space_inside_a_prompt_moves_it(self):
        """Inside a multi-line string the blank lines and spaces are part of what the model is
        sent, so stripping them there would hide a real prompt change."""
        base = _sample_digest()
        for edited in (_SAMPLE.replace('first line\r\n', 'first line\r\n\r\n'),
                       _SAMPLE.replace('spaces   \r\n', 'spaces\r\n'),
                       _SAMPLE.replace('   \r\ndone', '\r\ndone')):
            with self.subTest(edited=edited):
                self.assertNotEqual(_sample_digest(edited), base)

    def test_a_pinned_cascade_change_moves_it(self):
        """The model switch case: the cascade lives in another file, and the pin carries it (and
        the list it is built from) into the model's digest."""
        engine = ("BASE = ['model-a', 'model-b']\nCASCADE = ['model-z', *BASE]\n"
                  "OTHER = ['unrelated']\n")
        pins = [('engine.py', 'CASCADE')]
        base = _sample_digest(extra={'engine.py': engine.encode()}, pins=pins)
        for edited, moves in ((engine.replace('model-b', 'model-c'), True),
                              (engine.replace('model-z', 'model-y'), True),
                              (engine.replace('unrelated', 'changed'), False)):
            with self.subTest(edited=edited):
                digest = _sample_digest(extra={'engine.py': edited.encode()}, pins=pins)
                self.assertEqual(digest != base, moves)


def _pin_text(engine, name='CASCADE'):
    with tempfile.TemporaryDirectory() as tmp:
        (pathlib.Path(tmp) / 'engine.py').write_bytes(engine.encode())
        return registry.pinned_model_text(tmp, 'engine.py', name)


class TestTheDigestHidesNothing(SimpleTestCase):
    """LL3 review rounds: each case below gave the SAME digest for different logic before."""

    def test_the_version_line_must_stand_alone(self):
        """Dropping the version line must drop nothing else, and there must be one value only."""
        for source in ("MODEL_VERSION = '1.0.0'; THRESHOLD = 0.70\n",
                       "MODEL_VERSION = '1.0.0'\nX = 1\nMODEL_VERSION = '2.0.0'\n",
                       "THRESHOLD = MODEL_VERSION = '1.0.0'\n",
                       "MODEL_VERSION = '1.0.0' if True else '0'\n",
                       "MODEL_VERSION = '1.0.0'\nMODEL_VERSION += 'x'\n",
                       'X = 1\n'):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    registry.clean_model_source(source, drop_names=('MODEL_VERSION',))
                with self.assertRaises(ValueError):
                    _sample_digest(source)
        self.assertEqual(registry.clean_model_source(
            "MODEL_VERSION = (\n    '1.0.0')  # note\nX = 1\n", drop_names=('MODEL_VERSION',)), 'X = 1')

    def test_a_pin_leaves_out_its_modules_own_version(self):
        """school_leaving_doc pins results_doc.misfiled_as, which returns results_doc's version: a
        results_doc bump must not turn school_leaving_doc red. Its logic still counts."""
        engine = "MODEL_VERSION = '1.29.0'\nCASCADE = ['m', MODEL_VERSION]\n"
        base = _pin_text(engine)
        self.assertNotIn('1.29.0', base)
        self.assertEqual(_pin_text(engine.replace('1.29.0', '1.30.0')), base)
        self.assertNotEqual(_pin_text(engine.replace("'m'", "'n'")), base)
        with self.assertRaises(ValueError):
            _pin_text(engine.replace("'1.29.0'\n", "'1.29.0'; X = 2\n"))

    def test_a_pinned_name_changed_later_is_refused(self):
        """Import-time, module-level statements only: a change made inside a function that is then
        called, a `global` rebind, an alias or globals()/setattr is NOT seen (a recorded gap)."""
        engine = "CASCADE = ['a']\nBASE = {}\n"
        self.assertEqual(_pin_text(engine), "CASCADE = ['a']")
        for later in ("CASCADE += ['b']", "CASCADE.insert(0, 'b')", "CASCADE[0] = 'b'",
                      "CASCADE.extend(['b'])", "if True:\n    CASCADE.append('b')",
                      "del CASCADE[0]", "for CASCADE in [[]]:\n    pass"):
            with self.subTest(later=later):
                with self.assertRaises(ValueError):
                    _pin_text(engine + later + '\n')
        for harmless in ("BASE.update(x=1)", "OTHER = list(CASCADE)", "BASE[CASCADE[0]] = 1"):
            with self.subTest(harmless=harmless):
                self.assertEqual(_pin_text(engine + harmless + '\n'), "CASCADE = ['a']")

    def test_a_name_set_only_inside_a_block_is_refused(self):
        """Review round 2: `try: LIMIT = 0.7` then `CASCADE = [LIMIT]` - the pin read CASCADE but
        not LIMIT, so changing LIMIT kept the digest."""
        for block in ("try:\n    LIMIT = 0.7\nexcept ImportError:\n    pass\n",
                      "if True:\n    LIMIT = 0.7\n",
                      "try:\n    from x import LIMIT\nexcept ImportError:\n    LIMIT = 0.7\n",
                      "for LIMIT in [0.7]:\n    pass\n"):
            with self.subTest(block=block):
                with self.assertRaises(ValueError):
                    _pin_text(block + 'CASCADE = [LIMIT]\n')
        self.assertEqual(_pin_text("LIMIT = 0.7\nCASCADE = [LIMIT]\n"),
                         'LIMIT = 0.7\nCASCADE = [LIMIT]')
        self.assertEqual(_pin_text("if True:\n    OTHER = 1\nCASCADE = ['a']\n"), "CASCADE = ['a']")

    def test_a_pins_lazy_and_module_imports_are_its_dependencies(self):
        tree = {'apps/__init__.py': '', 'apps/x/__init__.py': '', 'apps/x/other.py': 'T = 1\nU = 2\n',
                'apps/x/engine.py': ('from apps.x.other import U\n'
                                     'def helper():\n    from .other import T\n    return T\n'
                                     'def unrelated():\n    return U\n')}
        with tempfile.TemporaryDirectory() as tmp:
            for rel, text in tree.items():
                (pathlib.Path(tmp) / rel).parent.mkdir(parents=True, exist_ok=True)
                (pathlib.Path(tmp) / rel).write_text(text)
            self.assertEqual(registry.pin_imports(tmp, 'apps/x/engine.py', 'helper'),
                             [('apps/x/other.py', 'T')])
            self.assertEqual(registry.pin_imports(tmp, 'apps/x/engine.py', 'unrelated'),
                             [('apps/x/other.py', 'U')])

    def test_the_supporting_doc_note_names_its_one_live_path(self):
        note = registry.load_version_log(API_ROOT, 'supporting_doc')['1.0.0']['note']
        self.assertIn('STR fallback', note)
        self.assertNotIn('(str / birth_certificate / epf)', note)
