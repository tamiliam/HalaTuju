"""LL3: a model's version must move whenever its source can move its answers.

`apps/scholarship/model_registry.py` lists each scoring model, its version constant and the source
it depends on. `model_versions/<model>.json` logs every version with the fingerprint (digest) of
the source it was recorded against. This file is the guard: change a model's logic without
bumping its version and it goes red, with a message saying what to do.

Built like `test_ai_registry.TestTheRegistryCannotGoStale`: the load-bearing tests are not that
the register is right today, but that it cannot quietly go stale. A new dependency, a new version
constant or a moved file each fails here until somebody accounts for it, with a reason. The
digest itself (what it reads, ignores and refuses) is tested in `test_model_digest.py`.
"""
import ast
import json
import pathlib
import re
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
_G = 'apps/scholarship/genuineness'
_NOT_REACHED_FROM_MISFILED_AS = (
    "Named in the pinned results_doc.misfiled_as closure, but only on branches misfiled_as never "
    "takes: it scores STR with doc_type='str', whose identity path returns before the band, the "
    'EPF screen and every offer branch. A change here cannot move school_leaving_doc answers; a '
    'change to that routing is in the pinned closure and moves the digest itself.')
_MISFILED_AS_UNREACHED = [
    f'{_G}/bands.py:band_for', f'{_G}/epf_app_doc.py:epf_app_scores',
    f'{_G}/epf_app_doc.py:screen_at_most_suspect', f'{_G}/offer_issuers.py:unfingerprinted_offer',
    f'{_G}/offer_rulings.py:apply_rulings', f'{_G}/offer_signatures.py:english_ua_lists'] + [
    f'{_G}/offer_signatures.py:{kind}_OFFER_SIGNATURES' for kind in ('MATRIC', 'PISMP', 'POLY', 'STPM', 'UA')]
_MISFILED_AS_PIN = f'pin:{_G}/results_doc.py:misfiled_as'

#: Per model: dependencies that are logic but are not (yet) in the model's files. A key
#: `<dependency> via <importer>` excuses it only when that one file or pin imports it.
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
    'school_leaving_doc': {f'{dep} via {_MISFILED_AS_PIN}': _NOT_REACHED_FROM_MISFILED_AS
                           for dep in _MISFILED_AS_UNREACHED},
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
    'apps/scholarship/doc_parse.py:ELECTRICITY_PARSER_VERSION':
        'The OCR-first TNB bill field read (OCR to fields), stamped on the stored read. A reader, '
        'not a scorer, and switched off for the photo lane; the genuineness cascade is its own '
        "registered model ('electricity_doc'). To register it, add it to MODELS.",
    'apps/scholarship/doc_parse_epf.py:EPF_PARSER_VERSION':
        'The OCR-first EPF statement field read (OCR to fields), stamped on the stored read. A '
        'reader, not a scorer; the income engine decides from its figures. To register it, add '
        'it to MODELS.',
    'apps/scholarship/services/consent.py:CONSENT_VERSION':
        'The version of the consent wording a student agreed to. Legal text, not a model.',
    'apps/scholarship/views_sponsor.py:SPONSOR_CONSENT_VERSION':
        'The version of the consent wording a sponsor agreed to. Legal text, not a model.',
    'apps/scholarship/management/commands/seed_sponsor_terms.py:VERSION':
        'The version of the sponsor terms text it seeds. Legal text, not a model.',
}

#: Gaps no import walk can see, each with where it lives (`<file>:<text that must still be
#: there>`, checked below so the record cannot outlive the code) or `guard:` for a limit of the
#: guard itself. A change through any of these can move answers with no version bump.
_KNOWN_GAPS_OUTSIDE_THE_WALK = {
    'apps/scholarship/offer_reader.py:OFFER_RETRY_MODEL':
        'A setting (Django setting or env var) that picks the Gemini model of the offer second '
        'read. Not in any digest: switching it changes offer_reader answers with no bump.',
    'apps/scholarship/income_engine/amounts.py:SGD_TO_MYR_RATE':
        'A setting: the SGD to MYR rate behind Singapore salaries. Changing it moves verdict '
        'engine income answers with no bump.',
    'apps/scholarship/genuineness/sample_stamp.py:SAMPLE_CHECK_ENABLED':
        'An env var that turns the sample check on or off. Not in any digest.',
    'apps/scholarship/genuineness/__init__.py:def assess':
        'Decision logic no model registers: which scorer each document type goes to, and the STR '
        'choice (signature scorer first, the holistic supporting_doc read only when it says '
        'unrecognised). It routes between models, so it belongs to none of them alone.',
    "apps/scholarship/vision/authenticity.py:st = 'suspect' if auth['status'] == 'unrecognised'":
        "Decision logic no model registers: the offer's legacy 'unrecognised' is stored as "
        "'suspect', and an empty or failed OCR gives no signal (never a penalty). This file "
        'stores what the scorers return; it is not in any digest.',
    'guard:append-only logs':
        'The logs are append-only by convention plus two checks (the last entry is the current '
        'version; no repeated keys). Editing the current entry\'s digest in place, deleting old '
        'entries or a version that goes backwards is caught by review only.',
    'guard:version census':
        'The *VERSION census sees only top-level names ending in VERSION inside apps/scholarship. '
        'A model versioned under another name, or in another app, is not found.',
    'guard:income_engine glob':
        'The glob income_engine/*.py also reads untracked local files, so a scratch file there '
        'turns the guard red on that machine only.',
    'guard:pinned name changed later':
        'A pin refuses a later change to a pinned name only in import-time, module-level '
        'statements. It does NOT see a change made inside a function that is then called '
        "(def _init(): CASCADE.append('b')), a global rebind inside a function, an alias "
        '(ALIAS = CASCADE; ALIAS.append(...)), or globals()[...] / setattr(...).',
    'guard:python 3.11':
        'The guard has run on Python 3.13 only. Cloud Build runs after a push to main, so it is '
        'not a before-merge check: its first run on 3.11 is the proof, and it fails closed (the '
        'build goes red, nothing wrong ships). A hand run on a 3.11 interpreter before merge is '
        'better if one is available. The 72 registered and pinned files were scanned on '
        '2026-11-19: no multi-line f-string, BOM or form feed, so the digests should match.',
}

_VERSION_NAME = registry.VERSION_NAME

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


def _model_dependencies(key):
    """(importing file or pin label, target, name) for every `apps.*` import of every listed
    file AND of every pin's closure (a pinned helper's lazy import is a dependency too)."""
    spec = registry.MODELS[key]
    for rel in _registered_files(key):
        if rel not in _WALK_SKIPS_SOURCE:
            for target, name in registry.model_imports(API_ROOT, rel):
                yield rel, target, name
    for pin_file, pin_name in spec['pins']:
        for target, name in registry.pin_imports(API_ROOT, pin_file, pin_name):
            yield f'pin:{pin_file}:{pin_name}', target, name


def _unmet_dependencies(key):
    """(dependency, importing file or pin, exemption used or None) for every `apps.*` import of
    every listed file and pin that is not itself a listed file or a pin."""
    spec, files = registry.MODELS[key], _registered_files(key)
    gaps = _KNOWN_GAPS.get(key, {})
    out = []
    for rel, target, name in _model_dependencies(key):
        if target in files or _pinned_by(spec, target, name):
            continue
        used = next((k for dep in (f'{target}:{name}', f'{target}:*')
                     for k in (f'{dep} via {rel}', dep) if k in _NOT_LOGIC or k in gaps), None)
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

    def test_a_pins_own_imports_are_walked_too(self):
        """Guard the guard (LL3 review): a pinned helper's lazy import is a dependency. These three
        were missed when only listed files were walked."""
        deps = {key: {(rel, f'{t}:{n}') for rel, t, n in _model_dependencies(key)}
                for key in ('matric_parse', 'offer_reader', 'school_leaving_doc')}
        self.assertIn(('pin:apps/scholarship/stpm_parse.py:_rows_of',
                       'apps/scholarship/academic_engine.py:_group_rows'), deps['matric_parse'])
        self.assertIn(('pin:apps/scholarship/offer_ic.py:guard_nric', f'{_VISION}:nric_close'),
                      deps['offer_reader'])
        self.assertIn((f'pin:{_G}/results_doc.py:misfiled_as', f'{_G}/offer_rulings.py:apply_rulings'),
                      deps['school_leaving_doc'])

    def test_a_pin_exemption_does_not_excuse_the_model_file(self):
        """Review round 2: the misfiled_as reasons excuse only that pin's closure. If
        school_leaving_doc.py itself imported band_for, the reason would be false, so it is bare."""
        real, model_file, dep = registry.model_imports, f'{_G}/school_leaving_doc.py', f'{_G}/bands.py'
        def walk(root, rel):
            return real(root, rel) + ([(dep, 'band_for')] if rel == model_file else [])
        with mock.patch.object(registry, 'model_imports', walk):
            unmet = _unmet_dependencies('school_leaving_doc')
        self.assertIn((f'{dep}:band_for', model_file, None), unmet)
        self.assertIn((f'{dep}:band_for', _MISFILED_AS_PIN, f'{dep}:band_for via {_MISFILED_AS_PIN}'),
                      unmet)

    def test_every_gap_outside_the_walk_still_names_real_code(self):
        for key in _KNOWN_GAPS_OUTSIDE_THE_WALK:
            if not key.startswith('guard:'):
                rel, needle = key.split(':', 1)
                with self.subTest(gap=key):
                    self.assertIn(needle, (API_ROOT / rel).read_text(encoding='utf-8'),
                                  'the code this gap names has moved; update or delete the record')

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
