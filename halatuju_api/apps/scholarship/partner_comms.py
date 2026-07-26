"""Partner-organisation comms — the ONE seam (2026-07-26).

Weekly + milestone emails to the referral organisations that run this bursary alongside us.
Roadmap: docs/plans/2026-07-26-partner-comms-roadmap.md.

Everything this feature decides is decided here: which organisations qualify, which
applications count as theirs, how the stages are counted, who the email goes to, whether a
kind is switched on, and how a stored template becomes a subject + text + HTML body.
Sending itself lives in the management commands; this module never talks to SMTP.

Three things that are easy to get wrong and are therefore fixed here:

1. **Attribution is the referral CHIP, never the FK.** `partner_applications` filters on
   `profile__referral_source == org.code`, the same signal the Sources student count and the
   Applications-list Source filter use. The stored `referred_by_org` FK drifts (a self-referral
   chip left pointing at an old partner), which is what previously inflated CUMIG.
   `views_admin._source_application_counts` calls this function, so the digest and the admin
   screen cannot disagree.

2. **Recipients are the organisation's own contact email and nothing else.** NOT
   `PartnerAdmin` rows: the only `partner`-role logins that exist belong to the HalaTuju
   course-selector relationship (created 2026-03-17, `owning_organisation` NULL, no B40 scope
   at all). Emailing them bursary progress would put applicant data in front of an audience
   attached for a different product. Owner correction, 2026-07-26.

3. **"Last activity" is a document upload, never `application.updated_at`.** `updated_at` is
   `auto_now`, so our own background work bumps it — verdict scoring, re-extraction, the
   institution sync, even a notification stamp. A student untouched for a month would read as
   active this morning, and the partner would stop chasing exactly the person who needs it.

Import direction: models + branding only. No view, no command, no email module imports here
(the renderer takes plain data), so this stays cheap to test.
"""
import hashlib
import re

from django.conf import settings
from django.db.models import Count, Max, Q

from .models import ApplicantDocument, PartnerEmailTemplate, ScholarshipApplication

# The platform's own bursary programme — the "house" organisation, i.e. us. It is the residual
# bucket in `_source_application_counts` (every applicant no external partner claimed), and it
# is NEVER a partner-email recipient: we have the officer cockpit, and a digest of our own
# students addressed to ourselves is noise. Kept as a code, mirroring views_admin.
HOUSE_ORG_CODE = 'brightpath'

# How many rows the chase table carries before it truncates with a note. Generous: with no
# partner console there is nowhere to go and look the rest up, so the email IS the list.
MAX_CHASE_ROWS = 50

# A date older than this many days is flagged in the chase table, so the reader can see whom
# to ring first without reading every row.
STALE_DAYS = 14

# `weekly_summary` skips a week whose counts are identical to the last one sent. The chase list
# does NOT: a partner whose stragglers have not moved is precisely who needs chasing, so it
# skips only when the list is empty. Owner-flagged interpretation, 2026-07-26 — flip this to
# make the rule literal for both.
SKIP_UNCHANGED = {'weekly_summary'}


# ── the five kinds ────────────────────────────────────────────────────────────

# Per-kind placeholder allowlist. A template saved with anything else is rejected: an unknown
# token would render literally into a partner's inbox as `{whatever}`.
PLACEHOLDERS = {
    'weekly_summary': {'org_name', 'contact_person', 'programme_name', 'counts_table',
                       'team_signoff'},
    'shortlisted_followup': {'org_name', 'contact_person', 'programme_name', 'count',
                             'student_table', 'team_signoff'},
    'awaiting_review': {'org_name', 'contact_person', 'programme_name', 'count',
                        'student_list', 'team_signoff'},
    'awarded': {'org_name', 'contact_person', 'programme_name', 'count', 'student_list',
                'team_signoff'},
    'assigned': {'org_name', 'contact_person', 'programme_name', 'student_name',
                 'team_signoff'},
}

KINDS = tuple(k for k, _ in PartnerEmailTemplate.KIND_CHOICES)

# The two kinds the weekly cron sends; the rest are event-driven.
WEEKLY_KINDS = ('weekly_summary', 'shortlisted_followup')

_TOKEN_RE = re.compile(r'\{([a-z_]+)\}')


def unknown_placeholders(kind, *parts):
    """Placeholder tokens in `parts` that this kind does not supply — sorted, so an error
    message is stable. Empty tuple means the template is safe to save."""
    allowed = PLACEHOLDERS.get(kind, set())
    found = set()
    for part in parts:
        found.update(_TOKEN_RE.findall(part or ''))
    return tuple(sorted(found - allowed))


# ── the voice guard ───────────────────────────────────────────────────────────

# Owner ruling, 2026-07-26: a partner organisation co-owns this bursary and may market it as
# its own; its students are the ORGANISATION's, not the reader's. These phrasings all cast the
# partner as a conduit or hand the students to the individual reading the email, so they are
# refused on save. A copy rule that lives only in a reviewer's head gets edited away later.
BANNED_PHRASES = (
    'students you send',
    'students you refer',
    'your referral',
    'referred by you',
    'thank you for referring',
    'your students',
)


def banned_phrases(*parts):
    """Conduit/ownership phrasings present in `parts`, sorted. Empty means the copy is clean."""
    haystack = ' '.join(p or '' for p in parts).lower()
    return tuple(sorted({p for p in BANNED_PHRASES if p in haystack}))


# ── who qualifies ─────────────────────────────────────────────────────────────

def qualifying_partners():
    """The organisations a partner email can actually reach, ordered by name.

    Active, has a contact email, and is not the house org. Today this is EMPTY on prod — nine
    referral partners, none with an address on file — which the admin screen states plainly
    rather than looking as though it is working.
    """
    from apps.courses.models import PartnerOrganisation
    return list(
        PartnerOrganisation.objects
        .filter(is_active=True)
        .exclude(code=HOUSE_ORG_CODE)
        .exclude(contact_email='')
        .order_by('name')
    )


def recipient_for(org):
    """The single address this organisation is written to, or '' when it has none.

    Deliberately NOT a list built from `PartnerAdmin` — see the module docstring. Returned as a
    list so a caller can log it and so adding a real multi-recipient field later does not
    change the call sites.
    """
    email = (getattr(org, 'contact_email', '') or '').strip().lower()
    return [email] if email else []


def is_enabled(kind):
    """True when this kind may send: the platform flag AND the template's own switch."""
    if not getattr(settings, 'PARTNER_COMMS_ENABLED', False):
        return False
    return PartnerEmailTemplate.objects.filter(kind=kind, enabled=True).exists()


# ── attribution + counts ──────────────────────────────────────────────────────

# The ONE field that attributes an application to an organisation. Named here so the digest and
# the Sources screen cannot drift onto different signals — see the module docstring.
CHIP_FIELD = 'profile__referral_source'


def partner_applications(org):
    """Every bursary application attributed to this organisation, by referral CHIP.

    THE single definition of "this partner's students". `views_admin._source_application_counts`
    derives from `chip_tally()` below, and a test asserts the two agree for every organisation,
    so the weekly digest and the Sources screen can never report different numbers.
    """
    return ScholarshipApplication.objects.filter(**{CHIP_FIELD: org.code})


def chip_tally():
    """`{chip: n}` across every application — one query. NULL/'' collapse to ''.

    Org-fence: intentionally GLOBAL. The Sources registry lists every organisation and the house
    org's count is the residual (total − claimed), so this tally must span all tenants. Single
    tenant today; revisit the residual split if that changes.
    """
    return {
        (row[CHIP_FIELD] or ''): row['n']
        # org-fence: GLOBAL by design (the house-org residual spans all tenants; see above)
        for row in ScholarshipApplication.objects.values(CHIP_FIELD).annotate(n=Count('pk'))
    }


# The reconciled stage lines. The owner asked for five figures; those five do not sum to the
# total, so three more exist — a partner must never receive numbers that do not add up.
# `recommended` is folded into "Under review" ON PURPOSE: it is masked from the student, so it
# must not reach a partner as a near-certainty either.
STAGE_LINES = (
    ('not_shortlisted', ('submitted',)),
    ('shortlisted', ('shortlisted',)),
    ('awaiting_review', ('profile_complete',)),
    ('under_review', ('interviewing', 'interviewed', 'recommended')),
    ('awarded', ('awarded', 'active', 'maintenance')),
    ('rejected', ('rejected',)),
    ('closed', ('withdrawn', 'expired', 'closed')),
)


def stage_counts(org):
    """`{line: n}` for this organisation, plus `total`. Every line sums to `total`.

    `total` is the sum of the RAW tally, not of the lines, so a status that no line claims
    would break the reconciliation test loudly instead of vanishing from the email.
    """
    rows = dict(
        partner_applications(org)
        .values_list('status')
        .annotate(n=Count('pk'))
        .values_list('status', 'n')
    )
    counts = {line: sum(rows.get(s, 0) for s in statuses) for line, statuses in STAGE_LINES}
    counts['total'] = sum(rows.values())
    return counts


def fingerprint(counts):
    """A short, stable hash of one organisation's counts — the weekly-summary skip test.

    Order-independent (sorted keys) so a dict-ordering change never looks like movement.
    """
    payload = ';'.join(f'{k}={counts[k]}' for k in sorted(counts))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:32]


def last_fingerprint(org, kind):
    """The fingerprint of the newest logged send for this pair, or '' if never sent.

    Send state has exactly one home — the log — so there is no second copy to drift.
    """
    from .models import PartnerEmailLog
    row = (PartnerEmailLog.objects
           .filter(organisation=org, kind=kind, ok=True)
           .order_by('-sent_at').values_list('fingerprint', flat=True).first())
    return row or ''


# ── the chase table ───────────────────────────────────────────────────────────

def chase_rows(org):
    """The organisation's shortlisted-but-incomplete students, oldest application first.

    Each row is `(name, applied, last_activity)` with both dates as `date` objects (or None):

    * `applied` — `submitted_at`, exact and set once.
    * `last_activity` — the newest LIVE document upload, falling back to `submitted_at` when
      they have uploaded nothing since. **Never `updated_at`** (see the module docstring): a
      system-side save must not make a dormant student look active.
    """
    apps = list(
        partner_applications(org)
        .filter(status='shortlisted')
        .select_related('profile')
        .order_by('submitted_at')
    )
    if not apps:
        return []
    newest = dict(
        ApplicantDocument.objects
        .filter(application__in=apps, superseded_at__isnull=True)
        .values_list('application_id')
        .annotate(last=Max('uploaded_at'))
        .values_list('application_id', 'last')
    )
    rows = []
    for app in apps:
        applied = app.submitted_at
        upload = newest.get(app.id)
        activity = upload if (upload and applied and upload > applied) else applied
        rows.append((
            (getattr(app.profile, 'name', '') or '').strip() or f'Applicant #{app.id}',
            applied.date() if applied else None,
            activity.date() if activity else None,
        ))
    return rows


def milestone_queryset(kind):
    """Applications due a milestone email: in the target state and not yet stamped.

    The state is re-checked here, at send time, rather than trusted from when the transition
    happened — which is what stops a reverted transition
    (`revert_if_profile_incomplete`, `awarded → recommended`) from producing an email.
    """
    if kind == 'awaiting_review':
        return ScholarshipApplication.objects.filter(
            status='profile_complete', partner_awaiting_notified_at__isnull=True,
        )
    if kind == 'awarded':
        return ScholarshipApplication.objects.filter(
            Q(status__in=('awarded', 'active', 'maintenance')),
            partner_awarded_notified_at__isnull=True,
        )
    raise ValueError(f'not a milestone kind: {kind}')
