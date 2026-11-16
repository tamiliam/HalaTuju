"""Outside calls (Google, email) that run only AFTER the database has committed (#75 re-check).

A call made inside a transaction cannot be taken back. If the request dies before COMMIT the rows
roll back, but a deleted calendar event stays deleted and a sent email stays sent. A call made under
a row lock also holds that lock for as long as Google or the mail provider takes. So a writer
collects its calls and hands them here: ``transaction.on_commit`` runs them once the commit lands
(at once when no transaction is open) and never after a rollback, a savepoint's included.

Each call is best-effort: one that fails is logged and never stops the next. They bill to the
application's organisation, as the scheduling entry points do (`scheduling._bills_to_application`),
because that decorator's usage context has closed by the time the commit lands.
"""
import logging

from django.db import transaction

from . import usage

logger = logging.getLogger(__name__)


def run_after_commit(application, calls):
    """Run each of ``calls`` (no-argument callables, in order) once the open transaction commits."""
    if not calls:
        return

    def _run():
        with usage.usage_context(application=application):
            for call in calls:
                try:
                    call()
                except Exception:
                    logger.exception('after-commit call failed: application %s', application.pk)

    transaction.on_commit(_run)
