"""TD-308 (2026-10-04): `str_check_memo` — one STR reading per Check-2 gap pass, and none outside it."""
from unittest import mock

from django.test import SimpleTestCase

from apps.scholarship import str_check_memo as memo


class _Doc:
    def __init__(self, pk):
        self.pk = pk


class TestTheMemo(SimpleTestCase):

    def test_outside_a_pass_every_call_reads(self):
        compute = mock.Mock(return_value={'name': 'x'})
        memo.remembered(_Doc(1), compute)
        memo.remembered(_Doc(1), compute)
        self.assertEqual(compute.call_count, 2)

    def test_inside_a_pass_one_document_is_read_once(self):
        compute = mock.Mock(side_effect=lambda d: {'pk': d.pk})

        @memo.one_str_reading
        def gap_pass():
            return [memo.remembered(_Doc(1), compute), memo.remembered(_Doc(1), compute),
                    memo.remembered(_Doc(2), compute)]

        self.assertEqual(gap_pass(), [{'pk': 1}, {'pk': 1}, {'pk': 2}])
        self.assertEqual(compute.call_count, 2)
        # The pass is over: the next pass reads afresh (no reading survives into a later write).
        gap_pass()
        self.assertEqual(compute.call_count, 4)

    def test_an_unsaved_document_is_never_remembered(self):
        compute = mock.Mock(return_value={})
        memo.one_str_reading(lambda: [memo.remembered(_Doc(None), compute) for _ in range(2)])()
        self.assertEqual(compute.call_count, 2)

    def test_a_caller_that_edits_its_reading_cannot_edit_the_next(self):
        @memo.one_str_reading
        def gap_pass():
            first = memo.remembered(_Doc(1), lambda d: {'ic_read_members': {'name': ['father']}})
            first['ic_read_members']['name'].append('mother')
            return memo.remembered(_Doc(1), lambda d: None)

        self.assertEqual(gap_pass(), {'ic_read_members': {'name': ['father']}})

    def test_the_memo_is_closed_even_when_the_pass_raises(self):
        @memo.one_str_reading
        def boom():
            raise RuntimeError('x')

        with self.assertRaises(RuntimeError):
            boom()
        self.assertIsNone(memo._MEMO.get())
