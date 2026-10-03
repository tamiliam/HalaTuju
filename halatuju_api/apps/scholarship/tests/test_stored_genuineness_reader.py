"""TD-293 (2026-10-03): the stored genuineness status has ONE tolerant reader.

`genuineness.bands.stored_status` / `stored_authenticity` replaced the `(vf.get('authenticity') or
{}).get('status', '')` idiom at the engine sites, which guarded `vision_fields` and then assumed the
block was a dict. A malformed value reads as NO SIGNAL — the same as a document never scored.
The endpoint-level proof (the officer's page answers 200 for both shapes, snapshot open and
closed) is `test_document_snapshot.TheGarbageThatCrashedTheEndpointNowAnswers`; this pins the
readers themselves, and that no engine site has gone back to the old idiom.
"""
import os

from django.conf import settings
from django.test import SimpleTestCase

from apps.scholarship.genuineness.bands import (canonical_status, stored_authenticity,
                                                stored_status)
from apps.scholarship.tests.source_walk import floor_count, walk_sources


class TheReaderIsTolerant(SimpleTestCase):

    def test_well_formed_values_read_as_before(self):
        self.assertEqual(stored_status({'authenticity': {'status': 'genuine'}}), 'genuine')
        self.assertEqual(stored_authenticity({'authenticity': {'status': 's', 'reason': 'r'}}),
                         {'status': 's', 'reason': 'r'})
        self.assertEqual(canonical_status('likely_genuine'), 'genuine')
        self.assertEqual(canonical_status('not_ic', 'ic'), 'not_ic')

    def test_every_malformed_shape_is_no_signal(self):
        for vf in (None, [], 'a string', 42, {}, {'authenticity': 'not a dict'},
                   {'authenticity': ['x']}, {'authenticity': {'status': 12345}},
                   {'authenticity': {'status': None}}, {'authenticity': {'status': ['genuine']}}):
            with self.subTest(vision_fields=vf):
                self.assertEqual(stored_status(vf), '')
                self.assertIsInstance(stored_authenticity(vf), dict)
        for raw in (12345, None, ['genuine'], {'s': 1}):
            with self.subTest(raw=raw):
                self.assertEqual(canonical_status(raw, 'ic'), '')


class NoEngineSiteReadsTheBlockRaw(SimpleTestCase):
    """The idiom stays out of the engine code (management commands that only PRINT are exempt)."""

    IDIOM = "get('authenticity') or {}"

    def test_the_old_idiom_is_gone_from_the_engines(self):
        root = os.path.join(settings.BASE_DIR, 'apps', 'scholarship')
        files = walk_sources(root, '*.py', 150, 'TD-293: the scholarship app source, where the '
                                                 'stored-genuineness reads live')
        offenders, readers = [], []
        for path in files:
            text = path.read_text(encoding='utf-8')
            rel = os.path.relpath(path, root).replace('\\', '/')
            if rel.startswith(('tests/', 'management/')) or rel == 'genuineness/bands.py':
                continue
            if self.IDIOM in text:
                offenders.append(rel)
            readers += [rel] * (text.count('stored_status(') + text.count('stored_authenticity('))
        self.assertEqual(offenders, [], 'read the block through genuineness.bands.stored_status')
        floor_count(readers, 12, 'calls to the tolerant reader',
                    'TD-293 moved the engine sites onto stored_status / stored_authenticity; '
                    'if this falls, the reads have moved or been renamed')


class TheOfferOfficialStatusReadsTheSameWay(SimpleTestCase):
    """Review F7: `offer_official_status` read a truthy malformed status as `not_genuine`, where the
    one reader reads no signal. Aligned: malformed is `unknown`, exactly as unscored."""

    def test_malformed_is_unknown_and_well_formed_is_unchanged(self):
        from types import SimpleNamespace

        from apps.scholarship.pathway_engine import offer_official_status

        def read(vf):
            return offer_official_status(SimpleNamespace(vision_fields=vf))

        self.assertEqual(read({'authenticity': {'status': 'genuine'}}), 'genuine')
        self.assertEqual(read({'authenticity': {'status': 'suspect'}}), 'not_genuine')
        self.assertEqual(read({}), 'unknown')
        for vf in ({'authenticity': {'status': 12345}}, {'authenticity': 'x'}, 'junk'):
            with self.subTest(vision_fields=vf):
                self.assertEqual(read(vf), 'unknown')
