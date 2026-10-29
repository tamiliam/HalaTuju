"""Count-once blocks (`spm_count_once.py`, Bumi Sprint D1): "N more subjects not yet counted",
exclude lists, bullet slots — each student subject used at most once, by a MATCHING."""
from apps.courses.engine import check_complex_requirements
from apps.courses.spm_count_once import block_passes, count_once_failure

# DIPLOMA KEJURURAWATAN (UE4723001): C in Math/AddMath, C in a science, C in one more subject.
NURSING = {'counted': ['eng'],
           'groups': [{'count': 1, 'grade': 'C', 'subjects': ['math', 'addmath']},
                      {'count': 1, 'grade': 'C', 'subjects': ['bio', 'phy', 'chem', 'sci']}],
           'remaining': [{'count': 1, 'grade': 'C', 'exclude': []}]}


class TestRemaining:
    def test_three_distinct_subjects_pass(self):
        assert block_passes({'eng': 'C', 'math': 'C', 'bio': 'C', 'bm': 'C'}, NURSING)

    def test_a_subject_is_never_counted_twice(self):
        # Math meets the maths group; Bio the science; nothing is left for "one more".
        assert not block_passes({'eng': 'A', 'math': 'A', 'bio': 'A'}, NURSING)

    def test_a_counted_subject_cannot_be_the_extra_one(self):
        # English already counted by its flag (credit_english), so it is not "one more".
        assert not block_passes({'eng': 'A', 'math': 'A', 'bio': 'A', 'bm': 'D'}, NURSING)

    def test_the_spare_of_an_either_or_group_counts_as_the_extra(self):
        # Math meets the group; Add Math is not yet counted, so it is the extra subject.
        assert block_passes({'math': 'C', 'addmath': 'C', 'bio': 'C'}, NURSING)

    def test_matching_not_first_fit(self):
        """A first-fit loop gives Fizik to the first group (Fizik / Kimia) and starves the second
        (Fizik only); the matching re-routes the first to Kimia. The grades are ordered so a
        greedy pass goes wrong; the same holds for a remaining slot."""
        block = {'groups': [{'count': 1, 'grade': 'C', 'subjects': ['phy', 'chem']},
                            {'count': 1, 'grade': 'C', 'subjects': ['phy']}],
                 'remaining': [{'count': 1, 'grade': 'C', 'exclude': []}]}
        assert block_passes({'phy': 'A', 'chem': 'C', 'bm': 'C'}, block)
        assert not block_passes({'phy': 'A', 'chem': 'C'}, block)

    def test_exclude_list(self):
        # ASASI UNDANG-UNDANG: A- in any THREE not counted, not English / Maths / Add Maths.
        block = {'counted': ['eng'], 'groups': [{'count': 1, 'grade': 'C', 'subjects': ['math', 'addmath']}],
                 'remaining': [{'count': 3, 'grade': 'A-', 'exclude': ['eng', 'math', 'addmath']}]}
        strong = {'eng': 'A', 'math': 'A', 'addmath': 'A', 'bm': 'A', 'hist': 'A'}
        assert not block_passes(strong, block)
        assert block_passes(dict(strong, geo='A-'), block)

    def test_grade_threshold(self):
        block = {'remaining': [{'count': 2, 'grade': 'C', 'exclude': []}]}
        assert not block_passes({'bm': 'C', 'hist': 'D'}, block)
        assert block_passes({'bm': 'C', 'hist': 'C+'}, block)
        assert not block_passes({'bm': 'G', 'hist': 'C'}, block)


class TestSlots:
    # The UiTM engineering lists: a bullet of alternatives counts ONCE.
    BLOCK = {'groups': [{'count': 2, 'grade': 'D',
                         'slots': [['geo', 'poa', 'ekonomi'], ['bio'], ['phy']]}]}

    def test_two_from_one_bullet_is_one_slot(self):
        assert not block_passes({'geo': 'A', 'poa': 'A'}, self.BLOCK)

    def test_two_bullets_pass(self):
        assert block_passes({'geo': 'D', 'phy': 'D'}, self.BLOCK)
        assert block_passes({'bio': 'D', 'phy': 'D'}, self.BLOCK)

    def test_more_than_there_are_slots_fails(self):
        assert not block_passes({'bio': 'A', 'phy': 'A'},
                                {'groups': [{'count': 3, 'grade': 'D', 'slots': [['bio'], ['phy']]}]})


class TestEngineDoor:
    def test_failure_names_the_block(self):
        assert count_once_failure({}, [NURSING]) == 'Count-once block 1 not met (each subject counts once)'
        assert count_once_failure({'math': 'C', 'bio': 'C', 'bm': 'C'}, [NURSING]) is None

    def test_check_complex_requirements_reads_count_once_without_or_groups(self):
        ok, reason = check_complex_requirements({'math': 'C', 'bio': 'C'}, {'count_once': [NURSING]})
        assert not ok and 'Count-once' in reason
        assert check_complex_requirements({'math': 'C', 'bio': 'C', 'bm': 'C'}, {'count_once': [NURSING]})[0]

    def test_legacy_or_groups_are_unchanged(self):
        """Without `count_once`, one subject may still satisfy two groups (the golden master)."""
        legacy = {'or_groups': [{'count': 1, 'grade': 'C', 'subjects': ['phy']},
                                {'count': 1, 'grade': 'C', 'subjects': ['phy', 'chem']}]}
        assert check_complex_requirements({'phy': 'A'}, legacy) == (True, None)

    def test_an_or_group_counts_distinct_subjects(self):
        """Review round 1 (owner ruling: a subject counts once per group): a key listed twice, or
        two codes that fold to one key, is ONE subject — "2 of" needs two subjects."""
        twice = {'or_groups': [{'count': 2, 'grade': 'E', 'subjects': ['pertanian', 'pertanian', 'chem']}]}
        assert not check_complex_requirements({'pertanian': 'E'}, twice)[0]
        assert check_complex_requirements({'pertanian': 'E', 'chem': 'E'}, twice)[0]
        folded = {'or_groups': [{'count': 2, 'grade': 'C', 'subjects': ['PHYSICS', 'phy']}]}
        assert not check_complex_requirements({'phy': 'A'}, folded)[0]

    def test_both_must_pass(self):
        data = {'or_groups': [{'count': 1, 'grade': 'C', 'subjects': ['chem']}], 'count_once': [NURSING]}
        assert not check_complex_requirements({'math': 'C', 'bio': 'C', 'bm': 'C'}, data)[0]
        assert check_complex_requirements({'math': 'C', 'bio': 'C', 'bm': 'C', 'chem': 'C'}, data)[0]


# Bumi Sprint D2: MOHE's "ATAU" (`any_of`) and "A- in ONE AND B in THREE of" (two groups, one list).
# ASASI KEJURURAWATAN (UY0000004): C in Kimia / Fizik / Biologi ATAU A in Sains ATAU B in Sains
# Tambahan, then C in two more subjects not listed.
SCIENCE_ATAU = {'any_of': [[{'count': 1, 'grade': 'C', 'subjects': ['chem', 'phy', 'bio']}],
                           [{'count': 1, 'grade': 'A', 'subjects': ['sci']}],
                           [{'count': 1, 'grade': 'B', 'subjects': ['addsci']}]]}
NURSING_D2 = {'counted': [], 'groups': [SCIENCE_ATAU],
              'remaining': [{'count': 1, 'grade': 'C', 'exclude': ['chem', 'phy', 'bio', 'sci', 'addsci']}]}


class TestAnyOf:
    def test_each_alternative_alone_is_enough(self):
        for science in ({'bio': 'C'}, {'sci': 'A'}, {'addsci': 'B'}):
            assert block_passes({**science, 'geo': 'C'}, NURSING_D2), science

    def test_an_alternative_below_its_own_grade_fails(self):
        # Sains at B is not the A the second alternative asks for; B in Sains is no Kimia etc.
        assert not block_passes({'sci': 'B', 'geo': 'C'}, NURSING_D2)
        assert not block_passes({'addsci': 'C', 'geo': 'C'}, NURSING_D2)

    def test_the_chosen_alternative_counts_once_with_the_rest(self):
        # One science only: it fills the ATAU, so nothing is left for "one more".
        assert not block_passes({'bio': 'A'}, NURSING_D2)

    def test_an_alternative_of_several_groups_needs_all_of_them(self):
        # ASASI PENGAJIAN ISLAM (UM0221002): B in THREE of a science list ATAU (B in TWO Islamic
        # AND B in TWO others).
        group = {'any_of': [[{'count': 3, 'grade': 'B', 'subjects': ['phy', 'chem', 'bio', 'math']}],
                            [{'count': 2, 'grade': 'B', 'slots': [['islam', 'tdi'], ['syariah'], ['usul']]},
                             {'count': 2, 'grade': 'B', 'subjects': ['geo', 'ekonomi', 'math']}]]}
        block = {'counted': [], 'groups': [group], 'remaining': []}
        assert block_passes({'phy': 'B', 'chem': 'B', 'bio': 'B'}, block)
        assert block_passes({'islam': 'B', 'usul': 'B', 'geo': 'B', 'math': 'B'}, block)
        # Two Islamic subjects but only one other: the second alternative is not whole.
        assert not block_passes({'islam': 'B', 'usul': 'B', 'geo': 'B', 'phy': 'B'}, block)
        # Two subjects from ONE bullet (Pendidikan Islam / Turath Dirasat Islamiah) are one slot.
        assert not block_passes({'islam': 'B', 'tdi': 'B', 'geo': 'B', 'math': 'B'}, block)

    def test_one_grade_for_one_and_another_for_three_of_one_list(self):
        # ASASI KEJURUTERAAN (UE0520001): A- in ONE AND B in THREE of Fizik / Add Maths / Kimia /
        # Matematik — four different subjects.
        block = {'counted': [], 'remaining': [],
                 'groups': [{'count': 1, 'grade': 'A-', 'subjects': ['phy', 'addmath', 'chem', 'math']},
                            {'count': 3, 'grade': 'B', 'subjects': ['phy', 'addmath', 'chem', 'math']}]}
        assert block_passes({'phy': 'A-', 'addmath': 'B', 'chem': 'B', 'math': 'B'}, block)
        assert not block_passes({'phy': 'A', 'addmath': 'A', 'chem': 'A'}, block)   # three, not four
        assert not block_passes({'phy': 'B+', 'addmath': 'B', 'chem': 'B', 'math': 'B'}, block)  # no A-

    def test_through_the_engine_door(self):
        data = {'count_once': [NURSING_D2]}
        assert check_complex_requirements({'sci': 'A', 'geo': 'C'}, data)[0]
        assert not check_complex_requirements({'sci': 'A'}, data)[0]
