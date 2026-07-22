"""Every verdict-item code the engine can emit MUST have an i18n string in all three locales.

Why this test exists (live bug, 2026-07-23): the cockpit showed a literal
`admin.scholarship.verdict.item.pathway_type_switch` on the Pathway card. The code was real,
emitted by `verdict_engine` and covered by its own tests — it simply had no translation.

Nothing caught it, and nothing could have:
  * i18n PARITY only proves en == ms == ta. All three were equally missing the key.
  * The web `admin-scholarship-i18n` guard scans source for STATIC `t('a.b.c')` calls. This key
    is assembled at runtime (`admin.scholarship.verdict.item.${item.code}`), so it is invisible
    to a static scan.
  * `next build` and jest never resolve i18n keys.

The only place the two sides can be compared is here, where the emitting codes live. This test
reads the web locale files directly — a cross-tree check, so it must FAIL LOUDLY rather than
skip if they cannot be found (lessons.md: a drift test that silently no-ops is worse than none).
"""
import ast
import json
import pathlib

from django.test import SimpleTestCase

_SCHOLARSHIP = pathlib.Path(__file__).resolve().parents[1]
_REPO = pathlib.Path(__file__).resolve().parents[4]
_MESSAGES = _REPO / 'halatuju-web' / 'src' / 'messages'

# `str_not_current` never reaches the UI verbatim: officerCockpit.verdictItemKey resolves it to
# a per-status key so the copy can be decisive. KEEP IN SYNC with that function.
_SUFFIXED = {'str_not_current': ('wrong_type', 'rejected', 'stale', 'unreadable', 'unconfirmed')}

# Dynamic `_item(code, ...)` call sites, where `code` is a variable chosen from a literal pair.
# Listed so a NEW dynamic site fails this test and gets a deliberate decision rather than
# silently escaping the check. (file, line) is informational; the count is what is asserted.
_KNOWN_DYNAMIC = 2


def _emitting_sources():
    """Modules that can construct a verdict Item — verdict_engine plus anything importing its
    private `_item` helper."""
    out = []
    for path in sorted(_SCHOLARSHIP.glob('*.py')):
        src = path.read_text(encoding='utf-8')
        if '_item(' not in src:
            continue
        if path.name == 'verdict_engine.py' or 'verdict_engine import' in src:
            out.append((path, src))
    return out


def _scan():
    """(literal codes, dynamic call sites) across every emitting module."""
    codes, dynamic = set(), []
    for path, src in _emitting_sources():
        for node in ast.walk(ast.parse(src)):
            if not (isinstance(node, ast.Call)
                    and getattr(node.func, 'id', '') == '_item' and node.args):
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                codes.add(first.value)
            else:
                dynamic.append(f'{path.name}:{node.lineno}')
    return codes, dynamic


def _required_keys(codes):
    required = set()
    for code in codes:
        required |= {f'{code}_{s}' for s in _SUFFIXED[code]} if code in _SUFFIXED else {code}
    return required


class TestVerdictItemI18n(SimpleTestCase):
    def setUp(self):
        # Loud failure, never a skip: if the web tree moved, this test must break, not pass.
        self.assertTrue(_MESSAGES.is_dir(),
                        f'web locale directory not found at {_MESSAGES} — fix this path, do not '
                        f'skip: the check is the only thing standing between a new verdict code '
                        f'and a raw key path rendering in the cockpit.')

    def _items(self, lang):
        path = _MESSAGES / f'{lang}.json'
        self.assertTrue(path.is_file(), f'{path} missing')
        data = json.loads(path.read_text(encoding='utf-8'))
        return data['admin']['scholarship']['verdict']['item']

    def test_the_scan_actually_finds_codes(self):
        """Sanity-check the scanner itself — a refactor that renames `_item` would otherwise
        turn this whole file into a silent no-op that passes forever."""
        codes, _ = _scan()
        self.assertGreater(len(codes), 40, 'verdict-item scan found too few codes — has _item '
                                           'been renamed or the engine restructured?')
        self.assertIn('pathway_type_switch', codes)   # the code from the original bug

    def test_every_emitted_code_has_english_copy(self):
        codes, _ = _scan()
        missing = sorted(_required_keys(codes) - set(self._items('en')))
        self.assertEqual(missing, [], f'verdict item code(s) with no en.json string — these '
                                      f'render as a raw key path in the cockpit: {missing}')

    def test_english_copy_is_mirrored_in_malay_and_tamil(self):
        codes, _ = _scan()
        required = _required_keys(codes)
        for lang in ('ms', 'ta'):
            missing = sorted(required - set(self._items(lang)))
            self.assertEqual(missing, [], f'{lang}.json is missing verdict item string(s): {missing}')

    def test_no_new_unverifiable_dynamic_call_site(self):
        """A `_item(code, ...)` whose code is a variable cannot be checked above. The two that
        exist each pick between a literal pair (both covered). A NEW one must be a deliberate
        decision — either make the code literal, or extend this test to enumerate its values."""
        _, dynamic = _scan()
        self.assertEqual(
            len(dynamic), _KNOWN_DYNAMIC,
            f'dynamic _item() call sites changed: {dynamic}. Each one escapes the i18n check '
            f'above — enumerate its possible codes here, or make the code a literal.')
