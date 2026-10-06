"""The two award timings, PER ORGANISATION (org-timing Sprint 1, 2026-10-07).

Until this sprint both were platform settings with one value for every tenant:
`AWARD_OFFER_EMAIL_COOLOFF_HOURS` (how long the award good-news email waits, so an award can be
reconsidered before the student is told) and `AWARD_COOLOFF_DAYS` (the flag-OFF acceptance hold
before "funding confirmed"). They are now org_config `award_email_delay_hours` and
`award_confirm_hold_days`, whose platform defaults still read those two settings.

A module of its own because `sponsorship.py` is on the oversize ledger with one line of room: the
read sites there call in here and stay the same length.
"""
from datetime import timedelta

from django.db.models import Q


def award_email_release_window(now):
    """The old-enough Q on `Sponsorship.offered_at` for `release_award_offer_emails`, PER
    ORGANISATION (the application's `owning_organisation`).

    ⚠ A NULL-ORG AWARD MUST FOLLOW THE DEFAULT ARM, or that student is never told they had won.
    The arm is spelled `~Q(…id__in=…) | Q(…isnull=True)`, the house spelling of
    `pool._funded_grace_window`, copied on purpose. Measured 2026-10-07 (bite-check): on this
    Django the explicit `isnull` half is BELT-AND-BRACES — Django already compiles the negation
    as `NOT (col IN (…) AND col IS NOT NULL)`, so removing it leaves the NULL-org test green. The
    test pins the OUTCOME (`test_org_timing.TestTheAwardTimings`), which is what matters. The
    filter stays in SQL so a too-young award never reaches the send loop at all.
    """
    from apps.courses import org_config

    custom = org_config.custom_values('award_email_delay_hours')
    default_cutoff = now - timedelta(hours=org_config.default('award_email_delay_hours'))
    if not custom:
        return Q(offered_at__lte=default_cutoff)
    window = (Q(offered_at__lte=default_cutoff)
              & (~Q(application__owning_organisation_id__in=list(custom))
                 | Q(application__owning_organisation_id__isnull=True)))
    for org_id, hours in custom.items():
        window |= Q(application__owning_organisation_id=org_id,
                    offered_at__lte=now - timedelta(hours=hours))
    return window


def award_confirm_hold(application):
    """The flag-OFF acceptance hold for this application's organisation, as a `timedelta`
    (`award_confirm_hold_days`). Zero is reachable only through a platform env value of 0 — an
    organisation's own value has a floor of 1 day — and means "confirm at once"."""
    from apps.courses import org_config
    return timedelta(days=org_config.value(application.owning_organisation,
                                           'award_confirm_hold_days'))
