"""Contract module: the error with a machine code, the deploy-check result and the draft guard.

Moved unchanged out of ``contracts.py`` when audit A3.8 (2026-11-10) made it a package.
"""


class ContractsError(Exception):
    """Raised by the service with a machine code for the view (e.g. 'not_draft',
    'version_exists', 'deploy_forbidden', 'not_deployable')."""

    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)


class ValidationResult:
    """Outcome of ``validate_for_deployment``: deduped, sorted error/warning
    code lists. ``ok`` is True when there are no errors."""

    def __init__(self, errors, warnings):
        self.errors = sorted(set(errors))
        self.warnings = sorted(set(warnings))

    @property
    def ok(self):
        return not self.errors

    def __repr__(self):
        return f'ValidationResult(errors={self.errors}, warnings={self.warnings})'


def _require_draft(template):
    if template.status != 'draft':
        raise ContractsError('not_draft')
