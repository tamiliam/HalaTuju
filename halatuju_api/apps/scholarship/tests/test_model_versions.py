"""LL3: a model's version must move whenever its source can move its answers.

`apps/scholarship/model_registry.py` lists each scoring model, its version constant and the source
it depends on. `model_versions/<model>.json` logs every version with the fingerprint (digest) of
the source it was recorded against. This file is the guard: change a model's logic without
bumping its version and it goes red, with a message saying what to do.

Built like `test_ai_registry.TestTheRegistryCannotGoStale`: the load-bearing tests are not that
the register is right today, but that it cannot quietly go stale. A new dependency, a new version
constant or a moved file each fails here until somebody accounts for it, with a reason.
"""
import ast
import hashlib
import json
import pathlib
import re
import tempfile
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import model_registry as registry
from apps.scholarship.tests.source_walk import SKIP_PARTS, floor_count, read_source, walk_sources

#: `halatuju_api/`, three levels up from this file's own folder.
API_ROOT = pathlib.Path(__file__).resolve().parents[3]

# --- the reasoned exemptions -------------------------------------------------------------------
# A dependency is `<file>:<name>` (or `<file>:*` for the whole module). Every exemption says why it
# is here; a bare exclude list rots as quietly as the register would.

#: Imported by a model file, and cannot change any model's answers.
_NOT_LOGIC = {
    'apps/scholarship/usage.py:*':
        'Metering only: records which model ran and what it cost. Never touches an answer.',
    'apps/scholarship/models/__init__.py:*':
        'The ORM table classes: what is stored, not how it is judged. A field change comes with '
        'a migration and the rule that reads the field lives in a listed file.',
}

#: Listed files whose OWN imports the walk does not follow, each for a reason.
_WALK_SKIPS_SOURCE = {
    'halatuju/ai_registry.py':
        'Listed (roadmap) as the screen of which model each AI job uses. It stores no model '
        'names; its imports are the cascades it DISPLAYS. The cascades that actually choose a '
        "model are pinned on each AI model (see model_registry.MODELS 'pins').",
}

_SECOND_LEVEL = (
    'KNOWN GAP. A second-level helper of a listed file. Listing it would pull in its own imports '
    'too, and the full import closure is about 476 files, so LL3 phase 1 names it here instead. '
    "A change to it can move this model's answers without a version bump.")
_OWN_MODEL = (
    'A registered model of its own (see MODELS). Its own version moves when it changes; this '
    "model's does not.")
_TRANSPORT = (
    'KNOWN GAP. The shared Gemini call and image/PDF preparation used by every AI job. The prompt, '
    "schema and cascade are this model's own files and pins; a change to how the image is "
    "prepared or the call is made can still move answers without a bump.")
_COURSES = (
    'KNOWN GAP. The courses app catalogue API (labels, families, qualification rules): another '
    'app, much of it data that changes without a deploy at all.')

_VERDICT_SECOND_LEVEL = [f'apps/scholarship/{name}.py:*' for name in (
    'academic_compare', 'academic_engine', 'card_display', 'exam_years', 'family',
    'genuineness/offer_issuers', 'higher_owed', 'income_declaration', 'income_shown',
    'income_str_ownership', 'name_order', 'offer_course_match', 'offer_pathway', 'pathway_engine',
    'pathway_match', 'read_errors', 'results_kind', 'results_route', 'services/__init__',
    'services/offer_link', 'session_year', 'stpm_names', 'str_check_memo', 'vision/__init__',
    'wrong_slip')]
_VISION = 'apps/scholarship/vision/__init__.py'

#: Per model: dependencies that are logic but are not (yet) in the model's files.
_KNOWN_GAPS = {
    'verdict_engine': {
        **dict.fromkeys(_VERDICT_SECOND_LEVEL, _SECOND_LEVEL),
        'apps/courses/public.py:*': _COURSES,
        'apps/scholarship/stpm_parse.py:*': _OWN_MODEL,
        'apps/scholarship/matric_parse.py:*': _OWN_MODEL,
        'apps/scholarship/poly_diploma_parse.py:*': _OWN_MODEL,
    },
    'results_doc': {
        'apps/courses/public.py:*': _COURSES,
        f'{_VISION}:_call_gemini_json': _TRANSPORT,
        f'{_VISION}:_as_image_for_gemini': _TRANSPORT,
    },
    'ic': {
        f'{_VISION}:_call_gemini_json': _TRANSPORT,
        f'{_VISION}:_as_image_for_gemini': _TRANSPORT,
    },
    'supporting_doc': {
        f'{_VISION}:_call_gemini_json': _TRANSPORT,
        f'{_VISION}:_as_image_for_gemini': _TRANSPORT,
    },
    'sample_stamp': {
        f'{_VISION}:_call_gemini_json': _TRANSPORT,
        f'{_VISION}:_as_image_for_gemini': _TRANSPORT,
    },
    'offer_reader': {
        f'{_VISION}:_call_gemini_json': _TRANSPORT,
        f'{_VISION}:_as_image_for_gemini': _TRANSPORT,
        f'{_VISION}:_is_pdf': _TRANSPORT,
        'apps/scholarship/pdf_pages.py:*': _TRANSPORT,
    },
}

#: Module-level `*VERSION` constants under apps/scholarship that are NOT a scoring model's version.
_NOT_A_MODEL_VERSION = {
    'apps/scholarship/profile_engine.py:PROMPT_VERSION':
        'The student-profile writing prompt: prose for a reader, not a scored decision.',
    'apps/scholarship/spend_category.py:PROMPT_VERSION':
        'Sorts a sponsored student\'s spending into categories after the award; no decision.',
    'apps/scholarship/spend_summary.py:PROMPT_VERSION':
        'Writes a spending summary for sponsors after the award; no decision.',
    'apps/scholarship/verdict_narrative.py:CASE_SUMMARY_VERSION':
        'The plain-English case summary written FROM a verdict; the verdict engine decides.',
    'apps/scholarship/vision/gemini_read.py:IC_SECOND_OPINION_PROMPT_VERSION':
        'A hash of the IC second-opinion READ prompt (NRIC / name / address): it keys the reuse of '
        'a stored second reading. A field reader, not a scorer; IC genuineness is its own '
        "registered model ('ic', genuineness/ic.py MODEL_VERSION).",
    'apps/scholarship/vision/field_extraction.py:SLIP_READER_VERSION':
        'The SPM slip field read (OCR to fields). Not on the LL3 model list; a reader, not a '
        'scorer. To register it, add it to MODELS.',
    'apps/scholarship/services/consent.py:CONSENT_VERSION':
        'The version of the consent wording a student agreed to. Legal text, not a model.',
    'apps/scholarship/views_sponsor.py:SPONSOR_CONSENT_VERSION':
        'The version of the consent wording a sponsor agreed to. Legal text, not a model.',
    'apps/scholarship/management/commands/seed_sponsor_terms.py:VERSION':
        'The version of the sponsor terms text it seeds. Legal text, not a model.',
}

_VERSION_NAME = re.compile(r'(^|_)VERSION$')

_FIX = (
    '  What to do:\n'
    "  1. If this change CAN change the model's answers: bump {const} in {const_file}, then add an "
    'entry for the new version at the END of {log} with this digest and a one-line note. Never '
    'edit an old entry.\n'
    "  2. If it CANNOT (a rename, a refactor, a moved helper): add "
    '{{"digest": "{digest}", "note": "<why the answers are unchanged>"}} to "also_ok" under '
    '"{version}" in {log}.\n'
    '  Every model\'s current digest: run "python apps/scholarship/model_registry.py" in '
    'halatuju_api/.')


def _log_path(key):
    return API_ROOT / registry.VERSIONS_DIR / f'{key}.json'


def _registered_files(key):
    return registry.expand_model_files(API_ROOT, registry.MODELS[key]['files'])


def _pinned_by(spec, target, name):
    """A pin covers `target:name` when it names that definition in that file, or in a module of
    the package `target` is the `__init__.py` of (a re-export)."""
    package = target[:-len('__init__.py')] if target.endswith('/__init__.py') else None
    return any(pin_name == name and (pin_file == target or (package and pin_file.startswith(package)))
               for pin_file, pin_name in spec['pins'])


def _unmet_dependencies(key):
    """(dependency, importing file, exemption used or None) for every `apps.*` import of every
    listed file that is not itself a listed file or a pin."""
    spec, files = registry.MODELS[key], _registered_files(key)
    gaps = _KNOWN_GAPS.get(key, {})
    out = []
    for rel in files:
        if rel in _WALK_SKIPS_SOURCE:
            continue
        for target, name in registry.model_imports(API_ROOT, rel):
            if target in files or _pinned_by(spec, target, name):
                continue
            used = next((k for k in (f'{target}:{name}', f'{target}:*')
                         if k in _NOT_LOGIC or k in gaps), None)
            out.append((f'{target}:{name}', rel, used))
    return out


class TestEveryModelIsAtItsRecordedSource(SimpleTestCase):
    def test_the_current_version_is_logged_against_todays_source(self):
        """⚠ THE POINT OF LL3. A logic change with no version bump files two behaviours under one
        number, and the learning loop then scores the new behaviour as if it were the old one."""
        for key, spec in registry.MODELS.items():
            with self.subTest(model=key):
                const_file, const = spec['constant']
                version = registry.read_model_version(API_ROOT, key)
                log = registry.load_version_log(API_ROOT, key)
                digest = registry.model_digest(API_ROOT, key)
                log_name = f'{registry.VERSIONS_DIR}/{key}.json'
                fix = _FIX.format(const=const, const_file=const_file, log=log_name,
                                  digest=digest, version=version)
                self.assertIn(version, log, (
                    f'MODEL VERSION GUARD: {key} is at version {version} ({const} in '
                    f'{const_file}), but {log_name} has no entry for it. Add one at the END: '
                    f'{{"digest": "{digest}", "note": "<what changed>", "also_ok": []}}.'))
                self.assertEqual(list(log)[-1], version, (
                    f'MODEL VERSION GUARD: {log_name} is append-only and its LAST entry must be '
                    f'the current version {version}. Move the new entry to the end; never '
                    f'reorder or edit old ones.'))
                entry = log[version]
                accepted = [entry['digest']] + [ok['digest'] for ok in entry['also_ok']]
                self.assertIn(digest, accepted, (
                    f"MODEL VERSION GUARD: the source of model '{key}' changed, but its version "
                    f'did not.\n  Version {version} was recorded against digest '
                    f"{entry['digest']}; today's source gives {digest}.\n" + fix))

    def test_every_log_entry_is_well_formed(self):
        hex64 = re.compile(r'^[0-9a-f]{64}$')
        for key in registry.MODELS:
            for version, entry in registry.load_version_log(API_ROOT, key).items():
                with self.subTest(model=key, version=version):
                    self.assertEqual(set(entry), {'digest', 'note', 'also_ok'})
                    self.assertRegex(entry['digest'], hex64)
                    self.assertTrue(entry['note'].strip(), 'every version says what it was')
                    self.assertIsInstance(entry['also_ok'], list)
                    for ok in entry['also_ok']:
                        self.assertEqual(set(ok), {'digest', 'note'})
                        self.assertRegex(ok['digest'], hex64)
                        self.assertTrue(ok['note'].strip(),
                                        'an also_ok digest must say why the answers did not change')

    def test_every_log_belongs_to_a_registered_model_and_every_model_has_one(self):
        logs = walk_sources(API_ROOT / registry.VERSIONS_DIR, '*.json', 12,
                            'one append-only version log per registered model (LL3)')
        self.assertEqual(sorted(p.stem for p in logs), sorted(registry.MODELS))

    def test_a_repeated_version_in_a_log_is_refused(self):
        """JSON quietly keeps the last of two equal keys, which would let an old entry be
        "edited" by appending a second copy of it."""
        with self.assertRaises(ValueError):
            json.loads('{"1.0.0": {}, "1.0.0": {}}', object_pairs_hook=registry._refuse_duplicate_keys)


class TestTheRegisterCannotGoStale(SimpleTestCase):
    def test_every_registered_file_and_pin_is_there(self):
        for key, spec in registry.MODELS.items():
            with self.subTest(model=key):
                files = _registered_files(key)
                for rel in files:
                    read_source(API_ROOT / rel, f"model_registry.MODELS['{key}'] lists it")
                self.assertIn(spec['constant'][0], files, 'the version constant lives in a listed file')
                for rel, name in spec['pins']:
                    self.assertTrue(registry.pinned_model_text(API_ROOT, rel, name).strip())
        floor_count(_registered_files('verdict_engine'), 30, 'verdict engine files',
                    'the income_engine/*.py glob must still expand (about 33 files on 2026-11-18)')

    def test_the_verdict_engine_reaches_only_listed_files(self):
        """The roadmap's walk: every module `verdict_engine.py` imports, at module level or lazily
        inside a function, is one of its listed files (or cannot change an answer). No known
        gaps at this level."""
        files = _registered_files('verdict_engine')
        missing = sorted(
            f'{target}:{name}'
            for target, name in registry.model_imports(API_ROOT, 'apps/scholarship/verdict_engine.py')
            if target not in files and f'{target}:{name}' not in _NOT_LOGIC
            and f'{target}:*' not in _NOT_LOGIC)
        self.assertEqual(missing, [], (
            'verdict_engine.py now imports these, and they are not in '
            "model_registry.MODELS['verdict_engine']['files']. Add the file to the list (and bump "
            'VERDICT_ENGINE_VERSION if the change moves answers), or, if it cannot change an '
            'answer, add it to _NOT_LOGIC WITH A REASON:\n  ' + '\n  '.join(missing)))

    def test_and_the_walk_would_actually_notice(self):
        """Guard the guard: the walk must really find the lazy imports, or the test above passes
        for ever on an empty list."""
        targets = {t for t, _ in registry.model_imports(API_ROOT, 'apps/scholarship/verdict_engine.py')}
        self.assertIn('apps/scholarship/verdict_ladder.py', targets)
        self.assertIn('apps/scholarship/income_engine/__init__.py', targets)
        floor_count(targets, 12, 'modules imported by verdict_engine.py',
                    'the verdict engine reaches its parts through lazy imports (13 on 2026-11-18)')

    def test_every_dependency_of_a_listed_file_is_accounted_for(self):
        """One level out from every listed file: each `apps.*` import is a listed file, a pin,
        not logic (_NOT_LOGIC) or a reasoned known gap (_KNOWN_GAPS)."""
        for key in registry.MODELS:
            with self.subTest(model=key):
                bare = sorted({f'{dep}  (imported by {rel})'
                               for dep, rel, used in _unmet_dependencies(key) if used is None})
                self.assertEqual(bare, [], (
                    f"Model '{key}' depends on code the register does not cover. For each line: "
                    f"add the file to model_registry.MODELS['{key}']['files'], or pin the one "
                    "definition in 'pins', or (if it cannot change an answer) add it to "
                    '_NOT_LOGIC, or record it in _KNOWN_GAPS - always WITH A REASON:\n  '
                    + '\n  '.join(bare)))

    def test_no_exemption_is_stale(self):
        """The other direction: an exemption nothing needs any more is a hole waiting to be
        reused. Remove it."""
        used_global, stale = set(), []
        for key in registry.MODELS:
            used = {u for _, _, u in _unmet_dependencies(key) if u}
            used_global |= used & set(_NOT_LOGIC)
            stale += [f'{key}: {k}' for k in sorted(set(_KNOWN_GAPS.get(key, {})) - used)]
        stale += [f'_NOT_LOGIC: {k}' for k in sorted(set(_NOT_LOGIC) - used_global)]
        stale += [f'_KNOWN_GAPS: {k}' for k in sorted(set(_KNOWN_GAPS) - set(registry.MODELS))]
        self.assertEqual(stale, [], 'These exemptions cover nothing now; delete them:\n  '
                         + '\n  '.join(stale))

    def test_every_version_constant_in_the_app_is_registered_or_reasoned(self):
        """A NEW model cannot ship unregistered: any module-level `*VERSION` constant in the app
        is either a registered model's or listed in _NOT_A_MODEL_VERSION with a reason."""
        registered = {f'{f}:{n}' for f, n in (s['constant'] for s in registry.MODELS.values())}
        found = set()
        for path in walk_sources(API_ROOT / 'apps' / 'scholarship', '*.py', 550,
                                 'the census of version constants reads the whole app '
                                 '(609 source files on 2026-11-18)',
                                 skip_parts=SKIP_PARTS + ('tests', 'eval')):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            rel = path.relative_to(API_ROOT).as_posix()
            for node in tree.body:
                targets = node.targets if isinstance(node, ast.Assign) else (
                    [node.target] if isinstance(node, ast.AnnAssign) else [])
                found.update(f'{rel}:{t.id}' for t in targets
                             if isinstance(t, ast.Name) and _VERSION_NAME.search(t.id))
        self.assertTrue(registered <= found, sorted(registered - found))
        floor_count(found, 20, 'module-level *VERSION constants', 'the census must see them all')
        unknown = sorted(found - registered - set(_NOT_A_MODEL_VERSION))
        self.assertEqual(unknown, [], (
            'New version constant(s). If it versions a scoring model, register the model in '
            'model_registry.MODELS and give it a log in model_versions/; if not, add it to '
            '_NOT_A_MODEL_VERSION WITH A REASON:\n  ' + '\n  '.join(unknown)))
        self.assertEqual(sorted(set(_NOT_A_MODEL_VERSION) - found), [],
                         'these _NOT_A_MODEL_VERSION entries name nothing now; delete them')


# --- the digest itself -------------------------------------------------------------------------

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
