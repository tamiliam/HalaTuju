"""The colour lifecycle: draft → publish → revert (Layer 1 A3).

`theme_tokens` says what a tenant may STORE. `contrast` says whether anybody can READ it. This
module says WHEN it becomes what visitors see — and the whole point is that those are different
moments.

Before A3, saving a colour changed it for every applicant instantly. That is a live experiment on
people mid-application, and it has no undo: the previous hex is simply gone. So:

    draft     — being worked on. NEVER served. One per organisation.
    active    — what visitors see. One per organisation.
    archived  — what they used to see. KEPT, because keeping it is what makes Revert a real undo
                rather than "try to remember the old colour".

── WHY THE TRANSITIONS LIVE HERE AND NOT ON THE MODEL ─────────────────────────────────────────────
Publishing is two writes that must happen together — the new row becomes active AND the old one
becomes archived. Split across callers, that is one deploy away from an organisation with two
active themes or none. Each function below is `@transaction.atomic` and is the ONLY sanctioned way
to move a row between states.

── THE SHAPE IS THE SPONSOR-TERMS ONE, ON PURPOSE ────────────────────────────────────────────────
`SponsorTermsVersion` already solved this in this codebase: draft immutability, a publish that
archives the previous active row inside one transaction, and a version a past decision can point
at forever. Copying a shape that has been in production for a month beats inventing a second one.
What is dropped: the lawyer attestation, the .docx import, the quiz. What is kept is the state
machine.

── WHO MAY PUBLISH ────────────────────────────────────────────────────────────────────────────────
An `org_admin`, including a draft they wrote themselves. Owner ruling for sponsor terms, 2026-07-28
(*"I'll allow Suresh to publish the terms"*), with **deliberately no same-author check** — a test
there pins that so nobody restores one thinking it an oversight. A colour is a smaller decision
than a binding document, so the same answer holds a fortiori. The ROLE GATE LIVES IN THE VIEW, not
here, mirroring `sponsor_terms.publish`: a bare shell call must not be able to publish by accident.
"""
import logging

from django.db import transaction
from django.utils import timezone

from .models import OrganisationTheme

logger = logging.getLogger(__name__)


class ThemeVersionError(Exception):
    """A transition that does not make sense. Carries a short machine code."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def draft_for(organisation):
    """The organisation's unpublished draft, or None."""
    return OrganisationTheme.objects.filter(
        organisation=organisation, status=OrganisationTheme.STATUS_DRAFT).first()


def active_for(organisation):
    """What visitors currently see, or None. The same seam the serve path reads."""
    return OrganisationTheme.active_for(organisation)


def previous_for(organisation):
    """The most recently archived version — what Revert would put back, or None.

    Ordered by when it was ARCHIVED, not when it was created: a version can be published, archived,
    republished and archived again, and the one to go back to is the one that was live most
    recently. Falls back to `created_at` for any row archived before that stamp existed.
    """
    return (OrganisationTheme.objects
            .filter(organisation=organisation, status=OrganisationTheme.STATUS_ARCHIVED)
            .order_by('-archived_at', '-created_at')
            .first())


@transaction.atomic
def save_draft(organisation, colour, tokens):
    """Create or update the draft. **Never touches what is live** — that is the sprint.

    Returns the draft row. Validation (the token fence, the contrast gate) belongs to the caller;
    by the time a set arrives here it is one somebody is allowed to store and able to read.
    """
    draft = draft_for(organisation)
    if draft is None:
        draft = OrganisationTheme(
            organisation=organisation, status=OrganisationTheme.STATUS_DRAFT)
    draft.source_colour = colour
    draft.tokens = tokens
    draft.save()
    return draft


@transaction.atomic
def discard_draft(organisation):
    """Throw the draft away. What is live is untouched, which is the point of a draft."""
    draft = draft_for(organisation)
    if draft is None:
        return False
    draft.delete()
    return True


@transaction.atomic
def publish(organisation, by_email='', allowed=False):
    """Make the draft what visitors see, archiving whatever they saw before. One transaction.

    ⚠ `allowed` IS THE CALLER'S ASSERTION THAT THE ROLE GATE PASSED, and it defaults to False —
    copied from `sponsor_terms.publish` for the same reason: a shell caller or a future endpoint
    that forgets the gate fails closed rather than publishing quietly.
    """
    if not allowed:
        return _refuse('not_allowed')
    draft = draft_for(organisation)
    if draft is None:
        return _refuse('no_draft')

    now = timezone.now()
    live = active_for(organisation)
    if live is not None:
        live.status = OrganisationTheme.STATUS_ARCHIVED
        live.archived_at = now
        live.save(update_fields=['status', 'archived_at', 'updated_at'])

    draft.status = OrganisationTheme.STATUS_ACTIVE
    draft.published_by_email = by_email or ''
    draft.published_at = now
    draft.save(update_fields=['status', 'published_by_email', 'published_at', 'updated_at'])

    logger.info('AUDIT organisation_theme_published org=%s colour=%s was=%s by=%s',
                organisation.code, draft.source_colour or 'hand-set',
                (live.source_colour if live else 'default') or 'hand-set', by_email or '')
    return draft


@transaction.atomic
def revert(organisation, by_email='', allowed=False):
    """Put back the colour that was live before this one. Returns the row now live, or None.

    ⚠ **None IS A REAL OUTCOME, NOT A FAILURE.** Reverting the FIRST colour an organisation ever
    published leaves them on the platform stylesheet — which is genuinely "what they had before",
    and is also how a tenant gets all the way back to the default. The caller renders that, rather
    than treating it as an error.
    """
    if not allowed:
        return _refuse('not_allowed')
    live = active_for(organisation)
    if live is None:
        return _refuse('nothing_live')

    now = timezone.now()
    previous = previous_for(organisation)

    live.status = OrganisationTheme.STATUS_ARCHIVED
    live.archived_at = now
    live.save(update_fields=['status', 'archived_at', 'updated_at'])

    if previous is not None:
        previous.status = OrganisationTheme.STATUS_ACTIVE
        previous.published_by_email = by_email or ''
        previous.published_at = now
        previous.archived_at = None
        previous.save(update_fields=[
            'status', 'published_by_email', 'published_at', 'archived_at', 'updated_at'])

    logger.info('AUDIT organisation_theme_reverted org=%s from=%s to=%s by=%s',
                organisation.code, live.source_colour or 'hand-set',
                (previous.source_colour if previous else 'default') or 'hand-set', by_email or '')
    return previous


def _refuse(code):
    raise ThemeVersionError(code)
