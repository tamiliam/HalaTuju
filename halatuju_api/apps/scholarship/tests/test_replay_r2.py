"""A5 replay, R2: the scrubber carry-overs (5a amounts by key, 5b course codes by key), the normaliser,
the ruling catalogue (a matching and a non-matching pair per encoded ruling, both through the REAL
scrubber), the comparer's A / B split, the report writer, the adapter table and one end-to-end run (real
engine names through child -> side file -> parent.report -> report_md, nothing bypassing the scrubber).
No live database, no network, no real replay."""
import ast
import json
import os
import tempfile
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.scholarship.eval.replay import adapters, child, engine_map, normalise as N, parent, report_md, rulings, scrub
from apps.scholarship.tests.factories import make_application


class AmountsOnlyUnderAmountKeysTest(SimpleTestCase):
    """5a: a float / Decimal / amount string leaves as written ONLY under scrub.AMOUNT_KEYS."""

    def test_an_amount_under_an_amount_key_passes(self):
        out = scrub.scrub({'amount': Decimal('3000'), 'monthly_amount': 250.5, 'total': '1200.00'})
        self.assertEqual(out, {'amount': '3000.00', 'monthly_amount': '250.50', 'total': '1200.00'})

    def test_a_number_under_any_other_key_is_dropped(self):
        out = scrub.scrub({'value': Decimal('12.30'), 'reason': 81.25})
        self.assertEqual(out, {'value': scrub.DROPPED, 'reason': scrub.DROPPED})

    def test_an_amount_shaped_string_under_any_other_key_is_hashed(self):
        self.assertTrue(scrub.scrub({'value': '12.30'})['value'].startswith(scrub.SCRUB_HASH_PREFIX))

    def test_a_number_in_a_list_takes_its_parent_key(self):
        self.assertEqual(scrub.scrub({'amount': [Decimal('1.5')], 'value': [Decimal('1.5')]}),
                         {'amount': ['1.50'], 'value': [scrub.DROPPED]})


class CourseCodesByKeyTest(SimpleTestCase):
    """5b: course codes pass through by KEY (scrub.COURSE_KEYS, design 3.2 allows course codes), never by
    the registry; the same shape under any other key is hashed, and an IC / passport shape never passes."""

    def test_catalogue_ids_pass_under_eligible_courses(self):
        out = scrub.scrub({'eligible_courses': ['UP6500001', 'FB5420001', 'P-DIP-12']})
        self.assertEqual(out, {'eligible_courses': ['UP6500001', 'FB5420001', 'P-DIP-12']})

    def test_a_course_shape_under_another_key_is_hashed(self):
        self.assertTrue(scrub.scrub({'value': 'UP6500001'})['value'].startswith(scrub.SCRUB_HASH_PREFIX))

    def test_personal_shapes_never_pass_as_course_codes(self):
        # A two-letter + digits value IS a course-id shape (UP6500001): the adapter writes only the
        # catalogue's own ids under this key (adapters._spm_courses / _stpm_courses).
        out = scrub.scrub({'eligible_courses': ['A12345678', '900101145678', '0123456789', 'ALI BIN ABU']})
        self.assertTrue(all(v.startswith(scrub.SCRUB_HASH_PREFIX) for v in out['eligible_courses']))


class NormaliserTest(SimpleTestCase):

    def test_a_fact_keeps_codes_and_hashes_params(self):
        f = N.fact({'fact': 'academic', 'status': 'review',
                    'unresolved': [{'code': 'academic_extra_subjects', 'params': {'name': 'ALI BIN ABU'}}],
                    'evidence': []})
        self.assertEqual((f['fact'], f['status'], f['unresolved'], f['evidence']),
                         ('academic', 'review', ['academic_extra_subjects'], []))
        self.assertNotIn('ALI', json.dumps(f))

    def test_free_text_and_unknown_keys_are_hashed(self):
        out = N.canon({'Some Name': 'ALI BIN ABU', 'monthly': Decimal('100'), 'value': 3.5})
        self.assertEqual(out['monthly'], '100.00')
        self.assertTrue(out['value'].startswith('h:'))
        self.assertTrue(out['other_keys'][0][0].startswith('h:'))
        self.assertNotIn('ALI', json.dumps(out))

    def test_canon_hashes_every_int_even_under_an_int_key(self):
        # R2 review (5): an 8-digit landline under `expected` (an INT_KEYS key) left as written.
        out = N.canon({'expected': 41234567, 'key': 7, 'doc': [990101, 14, 5678]})
        self.assertTrue(all(isinstance(v, str) and v.startswith('h:')
                            for v in [out['expected'], out['key'], *out['doc']]), out)
        self.assertNotIn('41234567', json.dumps(scrub.scrub(out)))

    def test_one_params_hash_per_item(self):
        # R2 review (6): a params change on one item shows as its own hash, the other item's is unchanged.
        items = [{'code': 'academic_extra_subjects', 'params': {'s': 'A'}}, {'code': 'results_slip_name_ok'}]
        a = N.fact({'fact': 'academic', 'status': 'review', 'unresolved': items[:1], 'evidence': items[1:]})
        b = N.fact({'fact': 'academic', 'status': 'review', 'evidence': items[1:],
                    'unresolved': [{'code': 'academic_extra_subjects', 'params': {'s': 'B'}}]})
        self.assertEqual(len(a['params']), 2)
        changed = [p for p in a['params'] if p not in b['params']]
        self.assertEqual([p[:2] for p in changed], [['unresolved', 'academic_extra_subjects']])

    def test_schedule_row_ids_are_registered_keys(self):
        # R2 review (5): template_id / doc were in INT_KEYS but unregistered, so every schedule record
        # reported a dropped key.
        row = SimpleNamespace(pk=3, template_id=12, pathway='university', variant='', monthly_amount=Decimal('250'))
        out = scrub.scrub(adapters.row_record(row))
        self.assertEqual(out['template_id'], 12)
        self.assertEqual(scrub.count_dropped(out), 0, out)
        self.assertEqual(scrub.scrub({'doc': 9}), {'doc': 9})


def _fact(name, unresolved=(), status='review', evidence=(), params=None):
    """A normalised verdict fact (as `normalise.fact` writes it)."""
    raw = {'fact': name, 'status': status,
           'unresolved': [{'code': c, 'params': (params or {}).get(c, {})} for c in unresolved],
           'evidence': [{'code': c} for c in evidence]}
    return N.fact(raw)


SPM = {'academic_card': 'spm'}
HIGHER = {'academic_card': 'higher'}


def _verdict(fact_old, fact_new, **facts):
    return ({'verdict': [fact_old], 'facts': facts}, {'verdict': [fact_new], 'facts': facts})


def _classify(engine, old, new):
    """Through the REAL scrubber first, as every record is (child.run_engines)."""
    return rulings.classify_difference(engine, scrub.scrub(old), scrub.scrub(new))


V = 'verdict.build_verdict'
# (ruling, engine, matching (old, new), non-matching (old, new)). Real engine codes only.
PAIRS = {
    'R-TD465': ('award.proposed_award_amount',
                ({'amount': '3000.00', 'facts': {'start_unknown': True, 'pathway_code': 'stpm'}},
                 {'amount': None, 'facts': {'start_unknown': True, 'pathway_code': 'stpm'}}),
                ({'amount': '3000.00', 'facts': {'start_unknown': True, 'pathway_code': 'matric'}},
                 {'amount': None, 'facts': {'start_unknown': True, 'pathway_code': 'matric'}})),
    # R2 review (4): inverted; False -> True is a regression and stays B.
    'R-TD465-UNKNOWN': ('award.course_start_unknown',
                        ({'value': True, 'facts': {'pathway_code': 'stpm', 'degree_bound': True}},
                         {'value': False, 'facts': {'pathway_code': 'stpm', 'degree_bound': True}}),
                        ({'value': False, 'facts': {'pathway_code': 'stpm', 'degree_bound': True}},
                         {'value': True, 'facts': {'pathway_code': 'stpm', 'degree_bound': True}})),
    'R-DEG7-AWARD': ('award.proposed_award_amount',
                     ({'amount': '3000.00', 'facts': {'degree_bound': True}},
                      {'amount': '2000.00', 'facts': {'degree_bound': True}}),
                     ({'amount': '3000.00', 'facts': {'degree_bound': False}},
                      {'amount': '2000.00', 'facts': {'degree_bound': False}})),
    'R-DEG7-PATHWAY': ('funding.classify_pathway',
                       ({'value': 'stpm', 'facts': {'degree_bound': True}},
                        {'value': 'degree', 'facts': {'degree_bound': True}}),
                       ({'value': 'stpm', 'facts': {'degree_bound': False}},
                        {'value': 'degree', 'facts': {'degree_bound': False}})),
    'R-DEG7-ESTIMATE': ('funding.estimate_funding',
                        ({'pathway': 'unknown', 'total': None, 'facts': {'pathway_code': 'tvet'}},
                         {'pathway': 'tvet', 'total': '4800.00', 'facts': {'pathway_code': 'tvet'}}),
                        ({'pathway': 'stpm', 'total': '100.00', 'facts': {}},
                         {'pathway': 'stpm', 'total': '200.00', 'facts': {}})),
    'R-DEG7-SCHEDULE': ('payments.schedule_row',
                        ({'pathway': 'stpm', 'facts': {'degree_bound': True, 'stored_award': '2000.00'}},
                         {'pathway': 'university', 'facts': {'degree_bound': True, 'stored_award': '2000.00'}}),
                        ({'pathway': 'stpm', 'facts': {'degree_bound': True, 'stored_award': '3000.00'}},
                         {'pathway': 'university',
                          'facts': {'degree_bound': True, 'stored_award': '3000.00'}})),
    'R-56': (V, _verdict(_fact('academic', ['results_slip_name_mismatch'], 'gap'),
                         _fact('academic', ['results_slip_name_near'])),
             _verdict(_fact('academic', ['results_slip_name_mismatch'], 'gap'),
                      _fact('academic', ['results_slip_name_near'], 'verified'))),
    'R-62': (V, _verdict(_fact('academic'), _fact('academic', ['academic_extra_subjects']), **SPM),
             _verdict(_fact('academic'), _fact('academic', ['academic_extra_subjects', 'results_slip_name_near']),
                      **SPM)),
    'R-388': (V, _verdict(_fact('academic', ['higher_results_not_on_file']),
                          _fact('academic', ['higher_results_not_on_file'], 'recommend')),
              _verdict(_fact('academic', ['higher_results_not_on_file']),
                       _fact('academic', ['higher_results_not_on_file'], 'gap'))),
    'R-OWED': (V, _verdict(_fact('academic'), _fact('academic', ['higher_results_not_declared'], 'recommend'),
                           degree_bound=True),
               _verdict(_fact('academic'), _fact('academic', ['higher_results_not_declared'], 'recommend'),
                        degree_bound=False)),
    'R-F1-Q1': (V, _verdict(_fact('academic'), _fact('academic', ['academic_slip_rows_unread']), **SPM),
                _verdict(_fact('academic'), _fact('academic', ['academic_slip_rows_unread'], 'verified'), **SPM)),
    'R-F1-Q4': (V, _verdict(_fact('academic', ['higher_results_grade_mismatch'], 'gap'),
                            _fact('academic', ['higher_results_grade_uncertain'])),
                _verdict(_fact('academic', ['higher_results_grade_mismatch'], 'gap'),
                         _fact('academic', ['higher_results_grade_uncertain', 'academic_extra_subjects']))),
}


class RulingCatalogueTest(SimpleTestCase):
    """One matching and one non-matching pair per encoded ruling (through the real scrubber); the rest
    never match."""

    def test_every_encoded_ruling_has_a_pair(self):
        encoded = {r.id for r in rulings.CATALOGUE if r.test is not None}
        self.assertEqual(encoded, set(PAIRS))
        self.assertEqual(len(encoded), 12)

    def test_each_matching_pair_is_expected_and_names_its_ruling(self):
        for rid, (engine, (old, new), _) in PAIRS.items():
            with self.subTest(rid):
                klass, ids = _classify(engine, old, new)
                self.assertEqual(klass, 'expected')
                self.assertIn(rid, ids)

    def test_each_non_matching_pair_is_unexplained_and_does_not_name_it(self):
        for rid, (engine, _, (old, new)) in PAIRS.items():
            with self.subTest(rid):
                klass, ids = _classify(engine, old, new)
                self.assertEqual(klass, 'unexplained')
                self.assertNotIn(rid, ids)

    def test_a_record_is_a_only_when_every_unit_matches(self):
        old = {'verdict': [_fact('academic'), _fact('income')], 'facts': SPM}
        new = {'verdict': [_fact('academic', ['academic_extra_subjects']),
                           _fact('income', ['income_above_b40_line'])], 'facts': SPM}
        self.assertEqual(_classify(V, old, new), ('unexplained', ['R-62']))

    def test_catalogued_unencoded_and_pending_never_match(self):
        unencoded = [r for r in rulings.CATALOGUE if r.test is None]
        self.assertEqual({r.id for r in unencoded}, {'R-67', 'R-3ROUTES', 'R-278', 'R-F1-Q2', 'R-F1-Q3', 'R-F1-Q6'})
        self.assertEqual([p[0] for p in rulings.PENDING], ['TD-617'])
        self.assertNotIn('TD-617', rulings.BY_ID)

    def test_facts_alone_are_never_a_difference(self):
        self.assertEqual(rulings.units('award.proposed_award_amount', {'amount': '1.00', 'facts': {'a': 1}},
                                       {'amount': '1.00', 'facts': {'a': 2}}), [])


class RulingRegistryTest(SimpleTestCase):
    """R2 review (1, 2): a code a ruling compares must be registered, or the scrubber hashes it and the
    ruling can never match a real record."""

    def test_every_engine_name_is_registered(self):
        self.assertEqual([n for n in engine_map.ENGINES if not scrub.is_code(n)], [])
        self.assertEqual(scrub.scrub({'engine': 'verdict.build_verdict'}), {'engine': 'verdict.build_verdict'})

    def test_every_code_named_by_the_catalogue_is_registered(self):
        self.assertEqual([c for c in rulings.NAMED_CODES if not scrub.is_code(c)], [])
        for r in rulings.CATALOGUE:
            self.assertTrue(scrub.is_code(r.id), r.id)
            self.assertEqual([e for e in r.engines if not scrub.is_code(e)], [], r.id)

    def test_every_code_shaped_literal_in_the_rulings_module_is_registered(self):
        with open(rulings.__file__, encoding='utf-8') as fh:
            tree = ast.parse(fh.read())
        literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        codes = {s for s in literals if scrub._CODE_SHAPE.match(s) and not scrub._AMOUNT.match(s)}
        self.assertGreater(len(codes), 40)
        self.assertEqual(sorted(c for c in codes if not scrub.is_code(c)), [])


class NarrowRulingsTest(SimpleTestCase):
    """R2 review (3, 4, 8): the rulings that were too broad, each through the real scrubber."""

    def test_r62_and_q1_never_match_on_the_higher_card(self):
        for code in ('academic_extra_subjects', 'academic_grades_unchecked', 'academic_slip_rows_unread'):
            with self.subTest(code):
                old, new = _verdict(_fact('academic'), _fact('academic', [code]), **HIGHER)
                self.assertEqual(_classify(V, old, new), ('unexplained', []))

    def test_r62_needs_both_sides_on_the_spm_card(self):
        old = {'verdict': [_fact('academic')], 'facts': HIGHER}
        new = {'verdict': [_fact('academic', ['academic_extra_subjects'])], 'facts': SPM}
        self.assertEqual(_classify(V, old, new)[0], 'unexplained')

    def test_r62_is_amber_only(self):
        old, new = _verdict(_fact('academic'), _fact('academic', ['academic_extra_subjects'], 'gap'), **SPM)
        self.assertEqual(_classify(V, old, new), ('unexplained', []))

    def test_r56_a_lost_mismatch_with_nothing_added_is_b(self):
        old, new = _verdict(_fact('academic', ['results_slip_name_mismatch'], 'gap'), _fact('academic', [], 'gap'))
        self.assertEqual(_classify(V, old, new), ('unexplained', []))

    def test_r56_the_twin_must_be_on_the_same_card(self):
        old, new = _verdict(_fact('academic', ['results_slip_name_mismatch'], 'gap'),
                            _fact('academic', ['higher_results_name_near']))
        self.assertEqual(_classify(V, old, new), ('unexplained', []))

    def test_r56_higher_card_pair_matches(self):
        old, new = _verdict(_fact('academic', ['higher_results_name_mismatch'], 'gap'),
                            _fact('academic', ['higher_results_name_near']))
        self.assertEqual(_classify(V, old, new), ('expected', ['R-56']))

    def test_a_params_change_on_another_item_is_b(self):
        old = {'verdict': [_fact('academic', ['academic_grades_unchecked'], params={'academic_grades_unchecked': {'n': 1}})],
               'facts': SPM}
        new = {'verdict': [_fact('academic', ['academic_grades_unchecked', 'academic_extra_subjects'],
                                 params={'academic_grades_unchecked': {'n': 2}})], 'facts': SPM}
        self.assertEqual(_classify(V, old, new), ('unexplained', []))

    def test_r388_and_owed_expect_unsure_not_probable(self):
        old, new = _verdict(_fact('academic', ['higher_results_not_on_file'], 'verified'),
                            _fact('academic', ['higher_results_not_on_file'], 'review'))
        self.assertEqual(_classify(V, old, new), ('unexplained', []))
        old, new = _verdict(_fact('academic', [], 'verified'),
                            _fact('academic', ['higher_results_undeclared'], 'recommend'), degree_bound=True)
        self.assertEqual(_classify(V, old, new), ('expected', ['R-OWED']))

    def test_r67_is_listed_not_encoded(self):
        old, new = _verdict(_fact('pathway', ['offer_name_mismatch'], 'gap'), _fact('pathway', [], 'verified'))
        self.assertEqual(_classify(V, old, new), ('unexplained', []))
        self.assertIsNone(rulings.BY_ID['R-67'].test)

    def test_td465_unknown_false_to_true_is_b(self):
        for facts in ({'pathway_code': 'stpm', 'degree_bound': True}, {'pathway_code': 'stpm', 'degree_bound': False}):
            with self.subTest(facts):
                self.assertEqual(_classify('award.course_start_unknown', {'value': False, 'facts': facts},
                                           {'value': True, 'facts': facts}), ('unexplained', []))
        not_degree = {'pathway_code': 'stpm', 'degree_bound': False}
        self.assertEqual(_classify('award.course_start_unknown', {'value': True, 'facts': not_degree},
                                   {'value': False, 'facts': not_degree}), ('unexplained', []))

    def test_deg7_unknown_to_tvet_is_gated_on_the_stored_code(self):
        e = 'funding.classify_pathway'
        for stored, new, klass in (('kkom', 'kkom', 'expected'), ('mara', 'mara_cert', 'expected'),
                                   ('', 'kkom', 'unexplained'), ('stpm', 'tvet', 'unexplained'),
                                   ('kkom', 'ilkbs', 'unexplained'), (None, 'tvet', 'unexplained')):
            with self.subTest(stored=stored, new=new):
                facts = {'pathway_code': N.code(stored)}
                self.assertEqual(_classify(e, {'value': 'unknown', 'facts': facts},
                                           {'value': new, 'facts': facts})[0], klass)


class RecheckFixesTest(SimpleTestCase):
    """A5 R2 re-check: a worse band is never A (MED-1); a case fact the rulings gate on must hold on BOTH
    sides, and any fact that changes between sides makes the record B (MED-2)."""

    def test_a_move_out_of_gap_is_never_a(self):
        # MED-1: red -> amber / Unsure while a note is added is a softened band, not the ruling.
        cases = (
            ('R-OWED', _verdict(_fact('academic', [], 'gap'),
                                _fact('academic', ['higher_results_not_declared'], 'recommend'), degree_bound=True)),
            ('R-62', _verdict(_fact('academic', [], 'gap'), _fact('academic', ['academic_extra_subjects']), **SPM)),
            ('R-F1-Q1', _verdict(_fact('academic', [], 'gap'), _fact('academic', ['academic_slip_rows_unread']),
                                 **SPM)),
        )
        for rid, (old, new) in cases:
            with self.subTest(rid):
                self.assertEqual(_classify(V, old, new), ('unexplained', []))

    def test_a_move_from_unsure_up_to_probable_is_b(self):
        old, new = _verdict(_fact('academic', [], 'recommend'), _fact('academic', ['academic_extra_subjects']), **SPM)
        self.assertEqual(_classify(V, old, new), ('unexplained', []))

    def test_verified_or_review_into_the_target_still_matches(self):
        for status in ('verified', 'review'):
            with self.subTest(status):
                old, new = _verdict(_fact('academic', [], status),
                                    _fact('academic', ['higher_results_not_declared'], 'recommend'), degree_bound=True)
                self.assertEqual(_classify(V, old, new), ('expected', ['R-OWED']))

    def test_degree_bound_on_the_new_side_only_is_b(self):
        # MED-2: degree_bound is computed by engine code that is not itself replayed.
        for old_db in (None, False):
            o, n = {'degree_bound': old_db}, {'degree_bound': True}
            cases = (
                ('award.proposed_award_amount', {'amount': '3000.00', 'facts': o},
                 {'amount': '2000.00', 'facts': n}),
                ('funding.classify_pathway', {'value': 'stpm', 'facts': o}, {'value': 'degree', 'facts': n}),
                ('payments.schedule_row', {'pathway': 'stpm', 'facts': {**o, 'stored_award': None}},
                 {'pathway': 'university', 'facts': {**n, 'stored_award': None}}),
                ('award.course_start_unknown', {'value': True, 'facts': {**o, 'pathway_code': 'stpm'}},
                 {'value': False, 'facts': {**n, 'pathway_code': 'stpm'}}),
                (V, {'verdict': [_fact('academic', [], 'verified')], 'facts': o},
                 {'verdict': [_fact('academic', ['higher_results_not_declared'], 'recommend')], 'facts': n}),
            )
            for engine, old, new in cases:
                with self.subTest(engine=engine, old_db=old_db):
                    self.assertEqual(_classify(engine, old, new)[0], 'unexplained')

    def test_any_fact_change_between_sides_is_b(self):
        engine, (old, new), _ = PAIRS['R-TD465']
        self.assertEqual(_classify(engine, old, new)[0], 'expected')
        new = {**new, 'facts': {**new['facts'], 'stored_award': '3000.00'}}
        self.assertEqual(_classify(engine, old, new)[0], 'unexplained')

    def test_start_unknown_echoing_its_own_engine_answer_is_not_a_fact_change(self):
        # The `start_unknown` fact IS `award.course_start_unknown`'s answer on each side (adapters.app_facts).
        f = {'pathway_code': 'stpm', 'degree_bound': True}
        old = {'value': True, 'facts': {**f, 'start_unknown': True}}
        new = {'value': False, 'facts': {**f, 'start_unknown': False}}
        self.assertEqual(_classify('award.course_start_unknown', old, new), ('expected', ['R-TD465-UNKNOWN']))
        self.assertEqual(_classify('award.proposed_award_amount', {'amount': '3000.00', 'facts': old['facts']},
                                   {'amount': '2000.00', 'facts': new['facts']})[0], 'unexplained')


class ComparerAndReportTest(SimpleTestCase):

    def _rows(self):
        engine, (old, new), _ = PAIRS['R-TD465']
        b_old, b_new = {'amount': '1.00', 'facts': {}}, {'amount': '2.00', 'facts': {}}
        return [
            (engine, [1], parent.classify(old, new, new), old, new),
            (engine, [2], parent.classify(b_old, b_new, b_new), b_old, b_new),
            (engine, [3], parent.classify({'amount': '1.00', 'facts': {'degree_bound': None}},
                                          {'amount': '1.00', 'facts': {'degree_bound': True}},
                                          {'amount': '1.00', 'facts': {'degree_bound': True}}), None, None),
            (engine, [4], 'could_not_run', {'error': 'ValueError'}, b_new),
            (engine, [5], 'noise', b_old, b_new),
        ]

    def test_facts_do_not_make_a_record_differ(self):
        self.assertEqual(self._rows()[2][2], 'same')

    def test_report_lines_carry_the_class_and_rulings(self):
        lines = []
        totals = parent.report(self._rows(), out=lines.append)
        e = 'award.proposed_award_amount'
        self.assertEqual(totals[e]['expected'], 1)
        self.assertEqual(totals[e]['unexplained'], 1)
        diffs = [d for d in map(json.loads, lines) if d.get('outcome') == 'differs']
        self.assertEqual([(d['class'], d['rulings']) for d in diffs],
                         [('expected', ['R-TD465']), ('unexplained', [])])
        self.assertTrue(all('facts' not in d['fields'] for d in diffs))

    def test_markdown_report_sections(self):
        md = report_md.render(self._rows(), old_commit='442b21f4d', new_commit='abc1234')
        self.assertIn('| award | 5 | 1 | 1 | 1 | 1 | 1 |', md)
        self.assertIn('**R-TD465** (1)', md)
        self.assertIn('| award.proposed_award_amount | amount | 1 | 2 |', md)
        self.assertIn('TD-617', md)


class _FakeEngine:
    """An engine as `child.run_engines` sees it: a real engine NAME, cases, and a record built by the real
    normaliser from a raw engine-shaped answer."""

    def __init__(self, name, records):
        self.name, self._records = name, records

    def cases(self):
        return sorted(self._records)

    def run(self, key, *, months=()):
        return self._records[key]()


def _raw_fact(name, status, unresolved=(), evidence=()):
    return {'fact': name, 'status': status, 'unresolved': [{'code': c, 'params': {'n': 'SITI'}} for c in unresolved],
            'evidence': [{'code': c, 'params': {}} for c in evidence]}


def _side_engines(side):
    """Per side, the records of five real engines (old against new)."""
    new = side != 'old'
    identity = _raw_fact('identity', 'verified', evidence=['ic_name_ok'])

    def verdict(academic, income=None, **facts):
        return lambda: {'verdict': [N.fact(identity), N.fact(academic)] + ([N.fact(income)] if income else []),
                        'facts': {'academic_card': 'spm', 'pathway_code': N.code('stpm'), **facts}}

    verdicts = {
        (1,): verdict(_raw_fact('academic', 'review', ['academic_extra_subjects'] if new else [],
                                ['results_slip_name_ok'])),                                      # R-62
        (2,): verdict(_raw_fact('academic', 'recommend' if new else 'review',
                                ['higher_results_not_on_file'])),                               # R-388
        (6,): verdict(_raw_fact('academic', 'review'),
                      _raw_fact('income', 'gap', ['income_above_b40_line'] if new else [])),   # B
    }
    stpm = {'pathway_code': N.code('stpm'), 'start_unknown': True, 'degree_bound': None}
    return [
        _FakeEngine('verdict.build_verdict', verdicts),
        _FakeEngine('award.proposed_award_amount',
                    {(3,): lambda: {'amount': N.amt(None if new else Decimal('3000')), 'facts': dict(stpm)}}),
        _FakeEngine('award.course_start_unknown',
                    {(4,): lambda: {'value': not new, 'facts': {'pathway_code': N.code('stpm'),
                                                                'degree_bound': True if new else None}}}),
        _FakeEngine('funding.classify_pathway',
                    {(5,): lambda: {'value': N.code('kkom' if new else 'unknown'),
                                    'facts': {'pathway_code': N.code(' KKOM '.strip().lower())}}}),
    ]


class EndToEndTest(TestCase):
    """R2 review (1): real engine names, through `child.run_engines` and the child's own line scrub, a side
    file, `parent.read_side`, `parent.report` and `report_md.render`. Nothing bypasses the scrubber."""

    def _run(self, workdir):
        for side in parent.RUN_SIDES:
            with open(os.path.join(workdir, f'{side}.jsonl'), 'w', encoding='utf-8') as fh:
                def write(obj, fh=fh):
                    fh.write(json.dumps(scrub.scrub(obj), sort_keys=True) + '\n')   # as child.main writes
                child.run_engines(_side_engines(side), months=(), write=write)
        sides = {s: parent.read_side(os.path.join(workdir, f'{s}.jsonl'))[0] for s in parent.RUN_SIDES}
        return sides, parent.compare_sides(sides)

    def test_real_engine_names_reach_the_rulings_and_the_report(self):
        with tempfile.TemporaryDirectory() as workdir:
            sides, rows = self._run(workdir)
        self.assertEqual(sum(scrub.count_dropped(list(s.values())) for s in sides.values()), 0)
        engines = {r[0] for r in rows}
        self.assertEqual(engines, {'verdict.build_verdict', 'award.proposed_award_amount',
                                   'award.course_start_unknown', 'funding.classify_pathway'})
        lines = []
        totals = parent.report(rows, out=lines.append)
        self.assertEqual(totals['verdict.build_verdict']['expected'], 2)
        self.assertEqual(totals['verdict.build_verdict']['unexplained'], 1)
        for e in ('award.proposed_award_amount', 'funding.classify_pathway'):
            self.assertEqual(totals[e]['expected'], 1, e)
        # Case 4 (re-check MED-2): degree_bound None on the old side, True on the new is a fact change the
        # rulings cannot see behind (engine code, not replayed), so R-TD465-UNKNOWN does not match: B.
        self.assertEqual(totals['award.course_start_unknown']['unexplained'], 1)
        got = {(d['key'][0], d['class'], tuple(d['rulings'])) for d in map(json.loads, lines)
               if d.get('outcome') == 'differs'}
        self.assertEqual(got, {(1, 'expected', ('R-62',)), (2, 'expected', ('R-388',)), (6, 'unexplained', ()),
                               (3, 'expected', ('R-TD465',)), (4, 'unexplained', ()),
                               (5, 'expected', ('R-DEG7-PATHWAY',))})
        md = report_md.render(rows, old_commit='442b21f4d', new_commit='abc1234')
        self.assertNotIn('| other |', md)
        for fam_row in ('| verdict | 3 | 0 | 2 | 1 | 0 | 0 |', '| award | 2 | 0 | 1 | 1 | 0 | 0 |',
                        '| funding_estimate | 1 | 0 | 1 | 0 | 0 | 0 |'):
            self.assertIn(fam_row, md)
        for rid in ('R-62', 'R-388', 'R-TD465', 'R-DEG7-PATHWAY'):
            self.assertIn(f'**{rid}** (1)', md)
        self.assertNotIn('**R-TD465-UNKNOWN**', md)
        self.assertIn('| verdict.build_verdict | verdict | 1 | 6 |', md)
        self.assertNotIn('SITI', md + ''.join(lines))


class RealAdapterToRulingTest(TestCase):
    """A5 R2 re-check (LOW-3): a REAL engine adapter on a built application, through the real facts, the
    scrubber, `parent.classify` and the rulings, to a ruling match. The new side is this tree's real
    `classify_pathway`; the old side is the same adapter with the pre-decision-11 answer ('unknown')."""

    def test_real_classify_pathway_reaches_r_deg7_pathway(self):
        app = make_application(chosen_pathway='kkom')
        name = 'funding.classify_pathway'
        resolved = engine_map.resolve_tree('new')
        new = scrub.scrub(engine_map.ADAPTERS[name](resolved).run((app.pk,)))
        old = scrub.scrub(engine_map.ADAPTERS[name]({**resolved, name: lambda a: 'unknown'}).run((app.pk,)))
        self.assertEqual(new['value'], 'kkom')
        self.assertEqual(new['facts']['pathway_code'], 'kkom')
        self.assertIs(new['facts']['degree_bound'], False)
        self.assertEqual(scrub.count_dropped([old, new]), 0)
        self.assertEqual(parent.classify(old, new, new), 'differs')
        self.assertEqual(parent.explain(name, old, new), ('expected', ['R-DEG7-PATHWAY']))


class AdapterTableTest(SimpleTestCase):

    def test_every_engine_has_an_adapter_and_a_family(self):
        self.assertEqual(set(engine_map.ADAPTERS), set(engine_map.ENGINES))
        self.assertEqual(set(adapters.FAMILY), set(engine_map.ENGINES))

    def test_the_gemini_gap_call_is_not_replayed(self):
        self.assertNotIn('gaps.generate_interview_gaps', engine_map.ENGINES)
        self.assertIn('gaps.flags_summary', engine_map.ENGINES)

    def test_the_registry_is_frozen_after_the_adapters(self):
        with self.assertRaises(scrub.RegistryFrozen):
            scrub.register_codes(('late_code',))

    def test_merit_with_a_null_coq_score(self):
        # R2 review (7): the engine raised TypeError on coq_score None; the profile page passes 5.0.
        from apps.courses.eligibility_service import compute_student_merit
        profile = SimpleNamespace(grades={'bm': 'A', 'eng': 'B', 'math': 'A', 'hist': 'C'}, coq_score=None)
        with mock.patch.object(adapters, '_profile', return_value=profile):
            out = adapters._merit(compute_student_merit, (1,), {})
        self.assertRegex(out['merit'], r'^\d+\.\d\d$')


class AdapterRunTest(TestCase):
    """A few application adapters run against THIS tree on a factory application; the record scrubs
    without a dropped value."""

    def test_application_adapters_produce_a_clean_record(self):
        app = make_application()
        resolved = engine_map.resolve_tree('new')
        for name in ('award.proposed_award_amount', 'award.course_start_unknown', 'funding.classify_pathway',
                     'verdict.build_verdict'):
            with self.subTest(name):
                ad = engine_map.ADAPTERS[name](resolved)
                self.assertIn((app.pk,), ad.cases())
                record = ad.run((app.pk,))
                self.assertIn('facts', record)
                self.assertIn(record['facts']['academic_card'], ('spm', 'higher'))
                self.assertEqual(scrub.count_dropped(scrub.scrub(record)), 0, scrub.scrub(record))
