"""Which bursary agreement template governs a GIFT, and an application (TD-229, 2026-10-03).

The owner ruled on 2026-09-04 that the template is PER GIFT. Until TD-229 was built the readers
here lived in ``contracts.py`` and answered per ORGANISATION, so the day an organisation ran a
second gift its students would have signed the first gift's wording — its programme name, its
amounts, its conditions. They moved here (rather than growing ``contracts.py``, a ledgered
giant file) when the question changed.

⚠ THE GIFT IS ``application.programme`` — NEVER ``chosen_programme``. ``chosen_programme`` is the
student's COURSE (a dict of institution and course name); ``programme`` is the gift they applied
to, copied from the cohort at first save and set-once.

⚠ NO GIFT, NO TEMPLATE — NEVER A NEIGHBOUR'S. A gift with no active template resolves to
``None``, and the signing path refuses with ``NO_TEMPLATE`` rather than borrowing another gift's
document. An application with no gift resolves to ``None`` too. A template whose ``programme`` is
NULL (one the migration-0163 back-fill did not reach) resolves for NOBODY; that is why the
back-fill is load-bearing and why TD-327 owes a NOT NULL.

⚠ NOT A FENCE. The organisation wall is still ``ContractTemplate.organisation`` and the admin
views' own checks. A gift narrows inside it.
"""
from .models import ContractTemplate, Programme

#: The refusal when the application's gift has no ACTIVE template. The name predates TD-229 (it
#: meant "the organisation has none"); since 2026-10-03 it means "THIS GIFT has none".
NO_TEMPLATE = 'no_active_template'


def active_template_for(programme):
    """The ACTIVE template of ONE gift, or ``None``. Never another gift's, never the org's."""
    if programme is None:
        return None
    return (ContractTemplate.objects
            .filter(programme=programme, status='active')
            .order_by('-deployed_by_at', '-created_at')
            .first())


def template_for_application(application):
    """The template governing this application: the signed agreement's PINNED template if there
    is one (a signed document never changes under the student), else the ACTIVE template of the
    application's own gift — or ``None`` when that gift has none."""
    agreement = getattr(application, 'bursary_agreement', None)
    if agreement is not None and agreement.template_id:
        return agreement.template
    return active_template_for(getattr(application, 'programme', None))


def gift_for_new_template(organisation, code):
    """The gift a NEW template is written for, inside ``organisation``. ``(programme, error)``.

    A named ``code`` must be one of THIS organisation's gifts (``'not_found'`` otherwise — the
    caller answers 404, so another tenant's code confirms nothing). With no code, the
    organisation's one LIVE gift is used, as ``create_run`` does; with none or several the
    answer is ``'programme_required'`` — never a silent pick.
    """
    gifts = Programme.objects.filter(organisation=organisation)
    if code:
        programme = gifts.filter(code=code).first()
        return (programme, None) if programme is not None else (None, 'not_found')
    live = list(gifts.filter(is_active=True)[:2])
    if len(live) != 1:
        return None, 'programme_required'
    return live[0], None
