"""PF-2 — do an organisation's module flags agree with what it actually does? (2026-07-28)

The four `PartnerOrganisation.module_*` flags drifted from production because **nothing
connected them to reality**: they are written once at onboarding and read by no gate, so a
module could ship, go live, move real money, and leave its flag sitting at False for months.
That is what happened to BrightPath's `module_payout`.

This module closes that loop. It does NOT enforce anything — enforcement is a later sprint
(platform roadmap S10b), and enforcing before reconciling is precisely how a live tenant's
payout surfaces go dark. What it provides is the check that makes enforcement *safe to turn on*:
for any organisation, which modules does the data prove are in use, and does the flag agree?

**Evidence, not intent.** A flag records a commercial decision; the evidence records what the
software is doing. When they disagree the evidence wins, because the evidence is what a user
will experience the moment a gate starts reading the flag.

Pure and read-only: no writes, no side effects, safe to run against production.
"""

# What counts as proof that a module is genuinely in use. Deliberately "has this EVER happened",
# not "has it happened recently" — a dormant module is still an enabled one, and a quiet month
# must never be read as grounds to switch a tenant's feature off.
MODULE_EVIDENCE = {
    'module_scholarship': 'applications',
    'module_sponsor_pool': 'sponsorships',
    'module_comms_whatsapp': 'whatsapp_messages',
    'module_payout': 'payment_runs',
}


def evidence_counts(organisation):
    """Per-module evidence counts for ONE organisation. Read-only.

    Every count is org-scoped by traversing a relationship that is already fenced, so this
    cannot accidentally report another tenant's activity as this one's.
    """
    from .models import PaymentRun, ScholarshipApplication, Sponsorship, WhatsAppMessage

    apps_qs = ScholarshipApplication.objects.filter(owning_organisation=organisation)
    return {
        'applications': apps_qs.count(),
        'sponsorships': Sponsorship.objects.filter(
            application__owning_organisation=organisation).count(),
        'whatsapp_messages': WhatsAppMessage.objects.filter(
            application__owning_organisation=organisation).count(),
        'payment_runs': PaymentRun.objects.filter(organisation=organisation).count(),
    }


def drift(organisation):
    """Flags that CONTRADICT the evidence, as {flag: (flag_value, evidence_count)}.

    Only one direction is reported: **flag False while evidence exists.** That is the dangerous
    case — the one where switching enforcement on would darken something a tenant is really
    using, which is exactly the BrightPath `module_payout` situation this work came from.

    The opposite (flag True, no evidence yet) is deliberately NOT drift: a module is routinely
    switched on before the first row exists, and reporting that as an error would train whoever
    runs this to ignore it.
    """
    counts = evidence_counts(organisation)
    out = {}
    for flag, key in MODULE_EVIDENCE.items():
        n = counts[key]
        if n > 0 and not getattr(organisation, flag, False):
            out[flag] = (False, n)
    return out
