"""The MBPK special-needs gate: req_disability admits only students who declared a disability."""
from apps.courses.engine import StudentProfile, check_eligibility


def _student(disability):
    # Strong, otherwise-eligible profile; the only variable is `disability`.
    return StudentProfile(
        grades={'bm': 'A', 'eng': 'A', 'hist': 'A', 'math': 'A', 'sci': 'A'},
        gender='male', nationality='Warganegara',
        colorblind=False, disability=disability,
    )


# Permissive req — the ONLY gate is req_disability.
REQ = {'source_type': 'pismp', 'req_disability': 1, 'min_credits': 0, 'subject_group_req': None}


def test_req_disability_excludes_non_disability_student():
    ok, _ = check_eligibility(_student(disability=False), REQ)
    assert ok is False


def test_req_disability_admits_disability_student():
    ok, _ = check_eligibility(_student(disability=True), REQ)
    assert ok is True


def test_no_req_disability_unaffected():
    # Without the flag, disability status is irrelevant (regression guard).
    req = {'source_type': 'pismp', 'min_credits': 0, 'subject_group_req': None}
    assert check_eligibility(_student(disability=False), req)[0] is True
    assert check_eligibility(_student(disability=True), req)[0] is True
