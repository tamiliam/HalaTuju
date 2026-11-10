"""Sponsorship: the error the fund and accept paths raise, with a machine code.

Moved unchanged out of ``sponsorship.py`` when audit A3.8 (2026-11-10) made it a package.
"""


class SponsorshipError(Exception):
    """Raised by fund_student/respond_to_award with a machine code for the view."""
    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)
