"""TD-111 (Sprint A2.8b) - the COVERAGE CRITIC: every anomaly flag must be routed somewhere.

``anomaly_engine`` detects more than any one screen asks. A flag that is produced but routed nowhere
is silently dropped: the officer never sees it and no decision reads it. This test is the durable
safety net (TD-111 item 3): it discovers the WHOLE flag set from its one home (every ``Anomaly(...)``
the engine builds, read from its source) and fails on any flag without a route. A flag is routed when:

* **an officer reason line** - the cockpit draws every served anomaly on the interview agenda as
  ``admin.scholarship.anomaly.<code>.question`` (beside its ``.fact``), so the code needs both keys
  in en / ms / ta. Without them the officer reads a raw key, not a reason; or
* **a decision path** - the serializer dedupes the flag (``_DEDUPED_ANOMALIES``) because a decision
  owns it: the identity verdict and the consent gate's ``ic_identity_blockers`` (``DECISION_PATHS``).

A flag that Check 2 also asks the student (``CHECK2_OWNED_ANOMALIES``) still needs its officer line:
the cockpit shows it again once the query closes. Those map entries must name real flags and real
Check-2 queries, or the bridge to the student is dead.
"""
import ast
import inspect
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.scholarship import anomaly_engine, check2_queries
from apps.scholarship.interview_completeness import CHECK2_OWNED_ANOMALIES
from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
from apps.scholarship.services import blockers

_MESSAGES = Path(__file__).resolve().parents[4] / 'halatuju-web' / 'src' / 'messages'
_LANGS = ('en', 'ms', 'ta')

#: deduped flag -> the decision that owns it (and the gate code that decision raises).
DECISION_PATHS = {
    'vision_nric_mismatch': 'ic_nric_mismatch',
    'vision_name_mismatch': 'ic_name_mismatch',
}


def produced_codes():
    """Every flag code the engine can produce: the literal first argument of each ``Anomaly(...)``.
    A call whose code is not a literal fails the test (it could produce a flag this critic cannot see)."""
    tree = ast.parse(inspect.getsource(anomaly_engine))
    codes, opaque = set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'Anomaly':
            arg = node.args[0] if node.args else None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                codes.add(arg.value)
            else:
                opaque.append(node.lineno)
    return codes, opaque


def _officer_lines(lang):
    path = _MESSAGES / f'{lang}.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    return ((data.get('admin') or {}).get('scholarship') or {}).get('anomaly') or {}


def unrouted(codes, lines_by_lang, decision_paths):
    """The flags in ``codes`` with NO route: not owned by a decision path, and missing an officer
    reason line (``fact`` + ``question``) in any language. Returns ``{code: why}``."""
    out = {}
    for code in sorted(codes):
        if code in decision_paths:
            continue
        gaps = [lang for lang, lines in lines_by_lang.items()
                if not (isinstance(lines.get(code), dict) and lines[code].get('fact') and lines[code].get('question'))]
        if gaps:
            out[code] = 'no officer reason line (fact + question) in ' + ', '.join(gaps)
    return out


class TestEveryFlagIsRouted(SimpleTestCase):

    def setUp(self):
        self.assertTrue(_MESSAGES.is_dir(), f'{_MESSAGES} is missing - the i18n bundle moved; point '
                        'this critic at its new home, never skip it')
        self.lines = {lang: _officer_lines(lang) for lang in _LANGS}

    def test_the_flag_set_is_discovered_whole(self):
        codes, opaque = produced_codes()
        self.assertEqual(opaque, [], 'an Anomaly built with a non-literal code: the critic cannot see it')
        self.assertGreaterEqual(len(codes), 19, 'a flag set that shrank compares nothing')
        detectors = {n for n, f in inspect.getmembers(anomaly_engine, inspect.isfunction)
                     if n.startswith('_detect_')}
        registered = {f.__name__ for f in anomaly_engine._DETECTORS}
        self.assertEqual(sorted(detectors - registered), [],
                         'a detector that is not registered in _DETECTORS never fires')

    def test_no_flag_is_routed_nowhere(self):
        codes, _ = produced_codes()
        self.assertEqual(unrouted(codes, self.lines, DECISION_PATHS), {})

    def test_the_critic_fails_on_an_unrouted_flag(self):
        """The safety net is live: a new flag with no reason line and no decision path is reported."""
        codes, _ = produced_codes()
        self.assertEqual(set(unrouted(codes | {'brand_new_flag'}, self.lines, DECISION_PATHS)),
                         {'brand_new_flag'})
        half = {**self.lines, 'ta': {k: v for k, v in self.lines['ta'].items() if k != 'household_size_one'}}
        self.assertIn('household_size_one', unrouted(codes, half, DECISION_PATHS))

    def test_every_deduped_flag_has_a_decision_path(self):
        deduped = AdminApplicationDetailSerializer._DEDUPED_ANOMALIES
        self.assertEqual(set(deduped), set(DECISION_PATHS),
                         'a flag the serializer hides must name the decision that owns it')
        codes, _ = produced_codes()
        gate = inspect.getsource(blockers.ic_identity_blockers)
        for flag, gate_code in DECISION_PATHS.items():
            with self.subTest(flag=flag):
                self.assertIn(flag, codes)
                self.assertIn(f"'{gate_code}'", gate)

    def test_the_check2_bridge_names_real_flags_and_real_queries(self):
        codes, _ = produced_codes()
        self.assertEqual(sorted(set(CHECK2_OWNED_ANOMALIES) - codes), [],
                         'a Check-2 bridge entry for a flag the engine never produces')
        self.assertEqual(sorted(set(CHECK2_OWNED_ANOMALIES.values()) - set(check2_queries.CLARIFY_SPECS)), [],
                         'a Check-2 bridge entry pointing at a query Check 2 never asks')
