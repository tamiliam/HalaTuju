"""
The exceptions the service layer raises, gathered in one place.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""

class IncompleteProfileError(Exception):
    """Raised when a student tries to confirm a Step-4 profile that isn't complete.
    Carries the completeness dict so the view can tell the FE what's missing."""
    def __init__(self, completeness):
        self.completeness = completeness
        super().__init__('Profile is not complete.')


class RoundFinishedError(Exception):
    """Raised when a student tries to submit into an intake round that was closed FOR GOOD.

    Distinct from `IncompleteProfileError` on purpose: nothing the student can do fixes it, so the
    screen must not point them at a missing document. It is the end of the grace period a closed
    round grants (see `confirm_profile`), and it is terminal.
    """
    def __init__(self, cohort_code=''):
        self.cohort_code = cohort_code
        super().__init__('This intake round has closed for good.')


class OnboardingError(Exception):
    """Raised when a student tries to complete onboarding out of order (e.g. before
    their award has been accepted). Carries a short ``code`` for the view."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class AmbiguousOpenCohort(Exception):
    """More than one round is open and nothing in the request says which (PF-1).

    Carries the candidate codes so the operator reading the log can see what to close, or which
    code the apply link should have carried.
    """

    def __init__(self, codes):
        self.codes = list(codes)
        super().__init__(
            'More than one open cohort and no cohort_code given: ' + ', '.join(self.codes)
        )


class AssignmentError(Exception):
    """Raised by assign_reviewer with a machine-readable .code for the API."""
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class PauseError(Exception):
    """Raised with a stable .code the view surfaces (e.g. 'not_reviewable')."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)
