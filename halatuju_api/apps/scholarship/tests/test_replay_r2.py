"""A5 replay, R2: the scrubber carry-overs (5a amounts by key, 5b course codes by key), the normaliser,
the ruling catalogue (a matching and a non-matching pair per encoded ruling), the comparer's A / B split,
the report writer and the adapter table. No live database, no network, no real replay."""
import json
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.scholarship.eval.replay import adapters, engine_map, normalise as N, parent, report_md, rulings, scrub
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


def _fact(name, unresolved=(), status='review', evidence=()):
    return {'fact': name, 'status': status, 'unresolved': sorted(unresolved), 'evidence': sorted(evidence),
            'params': 'h:0'}


def _verdict(fact_old, fact_new, **facts):
    return ({'verdict': [fact_old], 'facts': facts}, {'verdict': [fact_new], 'facts': facts})


V = 'verdict.build_verdict'
# (ruling, engine, matching (old, new), non-matching (old, new))
PAIRS = {
    'R-TD465': ('award.proposed_award_amount',
                ({'amount': '3000.00', 'facts': {'start_unknown': True, 'pathway_code': 'stpm'}},
                 {'amount': None, 'facts': {'start_unknown': True, 'pathway_code': 'stpm'}}),
                ({'amount': '3000.00', 'facts': {'start_unknown': True, 'pathway_code': 'matric'}},
                 {'amount': None, 'facts': {'start_unknown': True, 'pathway_code': 'matric'}})),
    'R-TD465-UNKNOWN': ('award.course_start_unknown',
                        ({'value': False, 'facts': {'pathway_code': 'stpm'}},
                         {'value': True, 'facts': {'pathway_code': 'stpm'}}),
                        ({'value': True, 'facts': {'pathway_code': 'stpm'}},
                         {'value': False, 'facts': {'pathway_code': 'stpm'}})),
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
                        ({'pathway': 'unknown', 'total': None, 'facts': {}},
                         {'pathway': 'tvet', 'total': '4800.00', 'facts': {}}),
                        ({'pathway': 'stpm', 'total': '100.00', 'facts': {}},
                         {'pathway': 'stpm', 'total': '200.00', 'facts': {}})),
    'R-DEG7-SCHEDULE': ('payments.schedule_row',
                        ({'pathway': 'stpm', 'facts': {'degree_bound': True, 'stored_award': '2000.00'}},
                         {'pathway': 'university', 'facts': {'degree_bound': True, 'stored_award': '2000.00'}}),
                        ({'pathway': 'stpm', 'facts': {'degree_bound': True, 'stored_award': '3000.00'}},
                         {'pathway': 'university',
                          'facts': {'degree_bound': True, 'stored_award': '3000.00'}})),
    'R-56': (V, _verdict(_fact('identity', ['name_mismatch'], 'gap'), _fact('identity', ['name_near'])),
             _verdict(_fact('identity', ['name_mismatch'], 'gap'), _fact('identity', ['name_near'], 'verified'))),
    'R-62': (V, _verdict(_fact('academic'), _fact('academic', ['academic_extra_subjects'])),
             _verdict(_fact('academic'), _fact('academic', ['academic_extra_subjects', 'something_else']))),
    'R-388': (V, _verdict(_fact('academic'), _fact('academic', ['higher_results_not_on_file'])),
              _verdict(_fact('academic', ['x_code']), _fact('academic', ['higher_results_not_on_file']))),
    'R-OWED': (V, _verdict(_fact('academic'), _fact('academic', ['higher_results_not_declared']),
                           degree_bound=True),
               _verdict(_fact('academic'), _fact('academic', ['higher_results_not_declared']),
                        degree_bound=False)),
    'R-F1-Q1': (V, _verdict(_fact('academic'), _fact('academic', ['academic_slip_rows_unread'])),
                _verdict(_fact('academic'), _fact('academic', ['academic_slip_rows_unread'], 'verified'))),
    'R-F1-Q4': (V, _verdict(_fact('academic', ['higher_results_grade_mismatch'], 'gap'),
                            _fact('academic', ['higher_results_grade_uncertain'])),
                _verdict(_fact('academic', ['higher_results_grade_mismatch'], 'gap'),
                         _fact('academic', ['higher_results_grade_uncertain', 'other'])))
    ,
    'R-67': (V, _verdict(_fact('pathway', ['offer_letter_mismatch'], 'gap'), _fact('pathway', [], 'verified')),
             _verdict(_fact('pathway', ['offer_letter_mismatch'], 'gap'),
                      _fact('pathway', ['offer_letter_missing'], 'verified'))),
}


class RulingCatalogueTest(SimpleTestCase):
    """One matching and one non-matching pair per encoded ruling; the rest never match."""

    def test_every_encoded_ruling_has_a_pair(self):
        encoded = {r.id for r in rulings.CATALOGUE if r.test is not None}
        self.assertEqual(encoded, set(PAIRS))
        self.assertEqual(len(encoded), 13)

    def test_each_matching_pair_is_expected_and_names_its_ruling(self):
        for rid, (engine, (old, new), _) in PAIRS.items():
            with self.subTest(rid):
                klass, ids = rulings.classify_difference(engine, old, new)
                self.assertEqual(klass, 'expected')
                self.assertIn(rid, ids)

    def test_each_non_matching_pair_is_unexplained_and_does_not_name_it(self):
        for rid, (engine, _, (old, new)) in PAIRS.items():
            with self.subTest(rid):
                klass, ids = rulings.classify_difference(engine, old, new)
                self.assertEqual(klass, 'unexplained')
                self.assertNotIn(rid, ids)

    def test_a_record_is_a_only_when_every_unit_matches(self):
        old = {'verdict': [_fact('academic'), _fact('income')], 'facts': {}}
        new = {'verdict': [_fact('academic', ['academic_extra_subjects']), _fact('income', ['x_new'])],
               'facts': {}}
        self.assertEqual(rulings.classify_difference(V, old, new), ('unexplained', ['R-62']))

    def test_catalogued_unencoded_and_pending_never_match(self):
        unencoded = [r for r in rulings.CATALOGUE if r.test is None]
        self.assertEqual({r.id for r in unencoded}, {'R-3ROUTES', 'R-278', 'R-F1-Q2', 'R-F1-Q3', 'R-F1-Q6'})
        self.assertEqual([p[0] for p in rulings.PENDING], ['TD-617'])
        self.assertNotIn('TD-617', rulings.BY_ID)

    def test_facts_alone_are_never_a_difference(self):
        self.assertEqual(rulings.units('award.proposed_award_amount', {'amount': '1.00', 'facts': {'a': 1}},
                                       {'amount': '1.00', 'facts': {'a': 2}}), [])


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
                self.assertEqual(scrub.count_dropped(scrub.scrub(record)), 0, scrub.scrub(record))
