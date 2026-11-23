"""Request #78: the one row score for relationship documents (owner rulings 23 Nov 2026).

Pure tests of `income_engine.match_bands`: every row band, every link combination, the chip
words, and the case-177 shape. All names and IC numbers are made up.
"""
import itertools

import pytest

from apps.scholarship.income_engine import match_bands as mb
from apps.scholarship.income_engine.match_bands import (
    AMBER, BLUE, CLOSE, EXACT, FAR, GREEN, GREY, MISSING, RED,
)

STUDENT_IC = '050312101234'
MOTHER_IC = '780405105678'


# --- the two cells --------------------------------------------------------------------------

@pytest.mark.parametrize('read, ref, level', [
    (STUDENT_IC, STUDENT_IC, EXACT),
    ('050312-10-1234', STUDENT_IC, EXACT),
    ('050312101236', STUDENT_IC, CLOSE),          # one digit substituted
    ('05031210123', STUDENT_IC, FAR),             # a dropped digit is not the owner's close
    ('050312101299', STUDENT_IC, FAR),            # two digits
    ('', STUDENT_IC, MISSING),
    (STUDENT_IC, '', MISSING),
])
def test_number_level(read, ref, level):
    assert mb.number_level(read, ref) == level


@pytest.mark.parametrize('read, ref, level', [
    ('ARUN A/L KUMAR', 'ARUN KUMAR', EXACT),       # connectors ignored
    ('KUMAR ARUN', 'ARUN KUMAR', EXACT),           # word order ignored
    ('ARUN KUMR', 'ARUN KUMAR', CLOSE),            # case-177 shape: a 5-letter word, one letter dropped
    ('ARUN KUMAR RAJ', 'ARUN KUMAR', CLOSE),       # one extra word
    ('BALA SUNDRAM', 'ARUN KUMAR', FAR),
    ('', 'ARUN KUMAR', MISSING),
])
def test_name_level(read, ref, level):
    assert mb.name_level(read, ref) == level


def test_a_name_that_passes_today_is_never_far():
    # Anything today's tolerant matcher accepts stays at least CLOSE (never newly red).
    from apps.scholarship.vision import relationship_name_match
    for a, b in [('MUTHU VELU', 'MUTU VELU'), ('SIVAM', 'SIVAMM'), ('DEVI', 'DEVIH')]:
        if relationship_name_match(a, b) != 'mismatch':
            assert mb.name_level(a, b) in (EXACT, CLOSE)


# --- the row table --------------------------------------------------------------------------

ROW_TABLE = {
    (EXACT, EXACT): GREEN, (EXACT, CLOSE): GREEN, (CLOSE, EXACT): GREEN,
    (CLOSE, CLOSE): BLUE, (FAR, EXACT): BLUE,
    (CLOSE, FAR): AMBER, (FAR, CLOSE): AMBER, (EXACT, FAR): AMBER,
    (EXACT, MISSING): GREEN, (CLOSE, MISSING): GREEN,     # ruling: no number → the name decides
    (MISSING, EXACT): AMBER, (MISSING, CLOSE): AMBER,     # no name: a number alone is not green
    (FAR, FAR): RED, (FAR, MISSING): RED, (MISSING, FAR): RED,
    (MISSING, MISSING): GREY,
}


@pytest.mark.parametrize('cells, band', sorted(ROW_TABLE.items()))
def test_every_row_band(cells, band):
    assert mb.row_band(*cells) == band


def test_case_177_child_row_is_green():
    row = mb.score_row('ARUN KUMR', STUDENT_IC, ('ARUN KUMAR',), STUDENT_IC)
    assert (row['name'], row['number'], row['band']) == (CLOSE, EXACT, GREEN)


def test_exact_name_far_number_is_amber_not_match():
    row = mb.score_row('ARUN KUMAR', '990101109999', 'ARUN KUMAR', STUDENT_IC)
    assert row['band'] == AMBER
    assert mb.chip_status(row) == 'check'


def test_both_far_is_red():
    row = mb.score_row('BALA SUNDRAM', '990101109999', 'ARUN KUMAR', STUDENT_IC)
    assert row['band'] == RED and mb.chip_status(row) == 'mismatch'


def test_a_number_alone_is_never_green():
    # BrightPath #23, as the 23 Nov ruling leaves it: a row with a number and NO NAME is amber.
    for num_lvl in (EXACT, CLOSE):
        assert mb.row_band(MISSING, num_lvl) == AMBER


@pytest.mark.parametrize('name, band', [
    ('ARUN KUMAR', GREEN), ('KUMAR ARUN', GREEN), ('ARUN KUMR', GREEN),
    ('BALA SUNDRAM', RED), ('', GREY),
])
def test_no_number_means_the_name_alone_decides(name, band):
    # Owner ruling 23 Nov 2026 (later the same evening): no IC number on the document, or none
    # on the reference IC, → the name decides the row, as the name-only check did before #78.
    assert mb.score_row(name, '', ('ARUN KUMAR',), STUDENT_IC)['band'] == band
    assert mb.score_row(name, STUDENT_IC, ('ARUN KUMAR',), '')['band'] == band


# --- the link (Part B) ----------------------------------------------------------------------

def _row(band, number=EXACT, waiting=False):
    return {'name': EXACT, 'number': number, 'band': band, 'waiting': waiting}


@pytest.mark.parametrize('a, b, want', [
    (GREEN, GREEN, GREEN),
    (GREEN, BLUE, AMBER), (BLUE, GREEN, AMBER),
    (GREEN, AMBER, AMBER), (AMBER, GREEN, AMBER),
    (AMBER, BLUE, AMBER), (BLUE, AMBER, AMBER), (AMBER, AMBER, AMBER),
    (RED, GREEN, RED), (GREEN, RED, RED), (RED, BLUE, RED), (AMBER, RED, RED),
    (RED, GREY, RED), (GREY, RED, RED), (RED, RED, RED),
    (GREY, GREY, GREY),
    (GREY, BLUE, AMBER), (AMBER, GREY, AMBER),
])
def test_link_combinations(a, b, want):
    assert mb.link_band(_row(a), _row(b)) == want


def test_blue_blue_is_green_only_with_both_numbers_exact():
    assert mb.link_band(_row(BLUE, EXACT), _row(BLUE, EXACT)) == GREEN
    assert mb.link_band(_row(BLUE, CLOSE), _row(BLUE, EXACT)) == AMBER
    assert mb.link_band(_row(BLUE, EXACT), _row(BLUE, CLOSE)) == AMBER


def test_grey_plus_green_waits_then_turns_amber():
    assert mb.link_band(_row(GREEN), _row(GREY, MISSING, waiting=True)) == GREY
    assert mb.link_band(_row(GREEN), _row(GREY, MISSING, waiting=False)) == AMBER


@pytest.mark.parametrize('band, status', [
    (GREEN, 'match'), (RED, 'mismatch'), (AMBER, 'pending'), (BLUE, 'pending'), (GREY, 'pending'),
])
def test_link_status(band, status):
    assert mb.link_status(band) == status


@pytest.mark.parametrize('cells, chip', [
    ((EXACT, EXACT), 'match'), ((FAR, FAR), 'mismatch'), ((MISSING, MISSING), 'no_ref'),
    ((FAR, EXACT), 'check_name'), ((EXACT, FAR), 'check'), ((CLOSE, FAR), 'check'),
    ((CLOSE, CLOSE), 'check_near'), ((EXACT, MISSING), 'match'), ((CLOSE, MISSING), 'match'),
    ((MISSING, EXACT), 'check_one'), ((FAR, CLOSE), 'check_one'),
])
def test_chip_words(cells, chip):
    n, k = cells
    assert mb.chip_status({'name': n, 'number': k, 'band': mb.row_band(n, k)}) == chip


# --- the two documents ----------------------------------------------------------------------

def test_mother_link_case_177_is_green():
    rows = mb.mother_link('ARUN KUMR', STUDENT_IC, 'LATHA DEVI', MOTHER_IC,
                          ('ARUN KUMAR',), STUDENT_IC, 'LATHA DEVI', MOTHER_IC)
    assert rows['child']['band'] == GREEN and rows['link'] == GREEN


def test_mother_link_waits_for_the_mothers_ic():
    rows = mb.mother_link('ARUN KUMAR', STUDENT_IC, 'LATHA DEVI', MOTHER_IC,
                          ('ARUN KUMAR',), STUDENT_IC, '', '')
    assert rows['parent']['waiting'] and rows['link'] == GREY


def test_guardianship_uses_the_same_bands():
    rows = mb.guardian_link_rows('SITI AMINAH', MOTHER_IC, 'ARUN KUMAR', ('ARUN KUMAR',),
                                 'SITI AMINAH', MOTHER_IC)
    assert rows['link'] == GREEN
    far = mb.guardian_link_rows('SITI AMINAH', '990101109999', 'ARUN KUMAR', ('ARUN KUMAR',),
                                'SITI AMINAH', MOTHER_IC)
    assert far['parent']['band'] == AMBER and far['link'] == AMBER
    red = mb.guardian_link_rows('BALA SUNDRAM', '990101109999', 'ARUN KUMAR', ('ARUN KUMAR',),
                                'SITI AMINAH', MOTHER_IC)
    assert red['link'] == RED


def test_ward_row_is_scored_on_the_name_alone():
    # Owner ruling 23 Nov 2026: letters never print the ward's number, so the ward row is the name
    # alone, always: exact or close → GREEN (the case-177 slip included), far → RED.
    assert mb.score_name_only_row('ARUN KUMAR', 'ARUN KUMAR')['band'] == GREEN
    assert mb.score_name_only_row('ARUN KUMR', 'ARUN KUMAR')['band'] == GREEN
    assert mb.score_name_only_row('BALA SUNDRAM', 'ARUN KUMAR')['band'] == RED
    assert mb.score_name_only_row('', 'ARUN KUMAR')['band'] == GREY


def test_mother_link_with_no_numbers_is_the_name_alone():
    # Neither the certificate nor the reference IC gave a number: both rows decided by name.
    rows = mb.mother_link('ARUN KUMAR', '', 'LATHA DEVI', '', ('ARUN KUMAR',), STUDENT_IC,
                          'LATHA DEVI', MOTHER_IC)
    assert rows['link'] == GREEN
    rows = mb.mother_link('ARUN KUMAR', '', 'SITI AMINAH', '', ('ARUN KUMAR',), STUDENT_IC,
                          'LATHA DEVI', MOTHER_IC)
    assert rows['link'] == RED


def test_an_unread_ward_has_no_say_as_before():
    # Review F1 as it stood: an unread ward changes nothing; the guardian row decides the link.
    rows = mb.guardian_link_rows('SITI AMINAH', '', '', ('ARUN KUMAR',), 'SITI AMINAH', '')
    assert rows['child']['band'] == GREY and rows['link'] == GREEN
    rows = mb.guardian_link_rows('SITI AMINAH', '990101109999', '', ('ARUN KUMAR',),
                                 'SITI AMINAH', MOTHER_IC)
    assert rows['link'] == AMBER                       # exact name + far number, the ward unread
    rows = mb.guardian_link_rows('BALA SUNDRAM', '', '', ('ARUN KUMAR',), 'SITI AMINAH', '')
    assert rows['link'] == RED
