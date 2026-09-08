"""Organisation-wide configuration — the registry and the read seam (Org Config Sprint A).

An organisation may TUNE a small set of platform values from Organisation → Settings →
Configuration. This module is the ONE home for three things:

  * the REGISTRY (`SETTINGS`) — which keys exist, their bounds, their unit, and where the
    platform default comes from;
  * the STORAGE FENCE (`validate_values`) — run in `OrganisationConfiguration.save()`, so a
    shell caller cannot store junk any more than an endpoint can;
  * the READ SEAM (`value` / `stored` / `custom_values`) — what product code calls.

⚠ CATALOGUE, NOT A FORM BUILDER (the Layer 0 rule). An organisation sets a VALUE for a key we
defined, bounded by limits we defined; it never invents a key. Adding a setting means adding a
registry entry AND wiring the read site — a setting that appears on the tab with nothing reading
it is the "UI asserts what nothing checks" defect by construction, so do neither without the other.

⚠ BLANK MEANS PLATFORM DEFAULT, AND THE DEFAULT DELEGATES TO DJANGO SETTINGS. An organisation
with no row (or no key) behaves byte-identically to the platform before this module existed —
deploying a new registry entry changes nothing visible by itself. The stored dict holds ONLY what
the organisation changed, so tightening a platform default later reaches every org that never
chose (the same reasoning that keeps `None` meaning "not applied" on intake-year requirements).
"""
from django.conf import settings


class OrgConfigError(ValueError):
    """A value the registry refuses. `code` is machine-readable; `key` names the setting."""

    def __init__(self, code, key=''):
        self.code = code
        self.key = key
        super().__init__(f'{code}: {key}' if key else code)


def _default_pool_funded_grace_days():
    # The platform value has always lived in HOURS (`POOL_FUNDED_GRACE_HOURS`, default 48 —
    # owner 2026-07-21). The owner's unit for the tab is DAYS (owner 2026-09-06: "extend to
    # 30 days"), so the registry speaks days and converts here: 48h → 2.0. Kept as a float so a
    # fractional env override is honoured, never silently rounded.
    hours = float(getattr(settings, 'POOL_FUNDED_GRACE_HOURS', 48) or 48)
    return hours / 24.0


def _default_sponsor_email_max_cards():
    # The one platform home has always been the env-tunable `SPONSOR_EMAIL_MAX_CARDS` (owner
    # 2026-07-18: keep it to 5). `sponsor_comms` used to carry its OWN literal 5 beside it;
    # Sprint B collapsed both render sites onto this single default so they can never disagree.
    return int(getattr(settings, 'SPONSOR_EMAIL_MAX_CARDS', 5) or 5)


def _default_query_email_delay_hours():
    # The platform value is a module constant, not a Django setting — imported lazily because
    # `services` lives in apps.scholarship and importing it at module load would be circular.
    from apps.scholarship.services import QUERY_EMAIL_DELAY_HOURS
    return QUERY_EMAIL_DELAY_HOURS


def _default_nudge_auto_delay_minutes():
    return int(getattr(settings, 'NUDGE_AUTO_DELAY_MINUTES', 30))


def _default_nudge_cooldown_hours():
    return int(getattr(settings, 'NUDGE_COOLDOWN_HOURS', 24))


def _default_max_clarify_open():
    # Module constant (design §4: a long list suppresses student responses) — lazy import, as above.
    from apps.scholarship.check2_queries import MAX_CLARIFY
    return MAX_CLARIFY


def _default_review_sla_days():
    # ⚠ The getattr default here is 10 to match settings/base.py. Before Sprint C, THREE readers
    # carried their own defaults (10, 10 and 7 — `services.py`'s assign email said 7); all dead
    # because base.py always defines the setting, but a drift waiting to bite the day it moved.
    # All three now read through this one delegation.
    return int(getattr(settings, 'REVIEW_SLA_DAYS', 10))


def _default_review_nudge_soon_days():
    return int(getattr(settings, 'REVIEW_NUDGE_SOON_DAYS', 2))


def _default_review_escalate_grace_days():
    # Same story: `send_review_nudges` said 3 where base.py says 4 (→ escalate at day 14). The
    # dead default never fired; the delegation retires it.
    return int(getattr(settings, 'REVIEW_ESCALATE_GRACE_DAYS', 4))


def _default_temp_password_ttl_days():
    return int(getattr(settings, 'PARTNER_TEMP_PASSWORD_TTL_DAYS', 7))


def _default_admin_dormant_days():
    # No settings/base.py entry exists for this one — the env-var override is the getattr itself.
    return int(getattr(settings, 'ADMIN_DORMANT_DAYS', 90))


def _default_interview_duration_min():
    # ⚠ 30 to match settings/base.py ("matches the 'about 30 minutes' copy"). Before Sprint D
    # FOUR fallbacks said 45 — `emails.send_interview_booked_email`, `scheduling.propose_slots`
    # and both `meeting.py` event builders. None could fire while base.py defines the setting,
    # but a 45-minute .ics against a 30-minute promise was one deleted line away.
    return int(getattr(settings, 'INTERVIEW_DURATION_MIN', 30))


def _default_interview_window_start_min():
    # The platform home is a module constant, not a Django setting — lazy import, because
    # `scheduling` lives in apps.scholarship and importing it at module load would be circular.
    from apps.scholarship.scheduling import SLOT_WINDOW_START_MIN
    return SLOT_WINDOW_START_MIN


def _default_interview_window_end_min():
    from apps.scholarship.scheduling import SLOT_WINDOW_END_MIN
    return SLOT_WINDOW_END_MIN


def _default_interview_slot_step_min():
    from apps.scholarship.scheduling import SLOT_STEP_MIN
    return SLOT_STEP_MIN


def _default_interview_min_lead_hours():
    from apps.scholarship.scheduling import SLOT_MIN_LEAD_HOURS
    return SLOT_MIN_LEAD_HOURS


def _default_interview_reschedule_cutoff_hours():
    return int(getattr(settings, 'INTERVIEW_RESCHEDULE_CUTOFF_HOURS', 12))


def _default_max_doc_size_mb():
    # The platform value has always lived in BYTES (`MAX_DOC_SIZE_BYTES`, default 8 MB). The
    # owner's unit for the tab is MB, so the registry speaks MB and the read seam converts —
    # the same shape as `pool_funded_grace_days` (days on the tab, hours in the platform).
    # Integer division: a platform value that is not a whole MB rounds DOWN, so the number on
    # screen never promises more than the server accepts.
    return int(getattr(settings, 'MAX_DOC_SIZE_BYTES', 8 * 1024 * 1024)) // (1024 * 1024)


def _default_max_docs_per_application():
    return int(getattr(settings, 'MAX_DOCS_PER_APPLICATION', 40))


def _default_max_other_docs():
    return int(getattr(settings, 'MAX_OTHER_DOCS', 10))


def _default_doc_stage_max_attempts():
    return int(getattr(settings, 'DOC_STAGE_MAX_ATTEMPTS', 3))


def _default_sign_accept_deadline_days():
    return int(getattr(settings, 'SIGN_ACCEPT_DEADLINE_DAYS', 30))


def _default_sign_reminder_days():
    return int(getattr(settings, 'BURSARY_SIGN_REMINDER_DAYS', 3))


# key → {group, unit, min, max, default}, plus two OPTIONAL keys:
#   * `allowed` — the only values this setting may take (rendered as a menu, not a box). Use it
#     when the range is not the real constraint: a slot step of 45 leaves `minute % step` no
#     honest reading across an hour boundary, so the divisors of 60 are the whole vocabulary.
#   * cross-field rules live in `validate_values`, not here — see `_check_pairs`.
# `default` is a CALLABLE, evaluated per read, because several platform defaults are env vars
# that can change without a deploy.
SETTINGS = {
    # How long a just-funded student lingers as a read-only "Funded" card on the sponsor browse
    # page before dropping off (`pool.display_pool_queryset`). Owner 2026-09-06: BrightPath wants
    # 30 days; the platform default stays 2.
    'pool_funded_grace_days': {
        'group': 'sponsor_page',
        'unit': 'days',
        'min': 1,
        'max': 90,
        'default': _default_pool_funded_grace_days,
    },
    # How many student cards a sponsor notification email shows before "and N more" (a teaser —
    # the button leads to the full pool). ONE value drives BOTH render sites: the pre-template
    # sender (`emails._send_sponsor_notify`) and the template block
    # (`sponsor_comms.student_cards_blocks`). Deferred out of Sprint A because neither carried
    # an organisation; Sprint B threads it through the batch's applications.
    'sponsor_email_max_cards': {
        'group': 'sponsor_page',
        'unit': 'cards',
        'min': 1,
        'max': 20,
        'default': _default_sponsor_email_max_cards,
    },
    # ── student comms (Sprint B) ──
    # How long after submission the "we have a few questions" email is held, so it reads as a
    # human review rather than an instant bot reply (`services.send_due_query_emails`).
    'query_email_delay_hours': {
        'group': 'student_comms',
        'unit': 'hours',
        'min': 1,
        'max': 168,
        'default': _default_query_email_delay_hours,
    },
    # The one-time automatic "you haven't submitted yet" nudge fires this long after consent
    # (`nudge._auto_delay` — the highest-chance moment is while the student is still at their
    # device, hence a minutes-scale value).
    'nudge_auto_delay_minutes': {
        'group': 'student_comms',
        'unit': 'minutes',
        'min': 5,
        'max': 1440,
        'default': _default_nudge_auto_delay_minutes,
    },
    # How long an org admin's MANUAL re-nudge is rate-limited after any nudge (`nudge._cooldown`).
    'nudge_cooldown_hours': {
        'group': 'student_comms',
        'unit': 'hours',
        'min': 1,
        'max': 168,
        'default': _default_nudge_cooldown_hours,
    },
    # How many Check-2 clarify questions may be OPEN at once (`check2_queries`). Doc requests and
    # the one-tap confirms sit OUTSIDE this cap by design — only typed-answer questions count.
    'max_clarify_open': {
        'group': 'student_comms',
        'unit': 'questions',
        'min': 1,
        'max': 10,
        'default': _default_max_clarify_open,
    },
    # ── reviewers & staff (Sprint C) ──
    # A verdict is due `assigned_at + review_sla_days`. Read at THREE sites, all per-application:
    # the nudge sweep (`send_review_nudges`), the reviewer interview reminder's verdict-due line
    # (`send_interview_reminders`), and the review-by date in the assignment email
    # (`services.assign_reviewer`).
    'review_sla_days': {
        'group': 'reviewers_staff',
        'unit': 'days',
        'min': 1,
        'max': 60,
        'default': _default_review_sla_days,
    },
    # The "your verdict is due soon" nudge fires this many days BEFORE the due date.
    'review_nudge_soon_days': {
        'group': 'reviewers_staff',
        'unit': 'days',
        'min': 1,
        'max': 30,
        'default': _default_review_nudge_soon_days,
    },
    # Escalation to the org's admins fires this many days AFTER the due date.
    'review_escalate_grace_days': {
        'group': 'reviewers_staff',
        'unit': 'days',
        'min': 1,
        'max': 30,
        'default': _default_review_escalate_grace_days,
    },
    # How long an emailed temporary password stays usable. ⚠ ONE clock, FOUR readers that must
    # agree: the invitation's own expiry (`invitations.staff_ttl_days`), the daily rotate-dead
    # cron (`expire_temp_passwords`), the login gate (the FE check, served the resolved value on
    # the role payload — never a hard-coded mirror), and the Resend reset.
    'temp_password_ttl_days': {
        'group': 'reviewers_staff',
        'unit': 'days',
        'min': 1,
        'max': 30,
        'default': _default_temp_password_ttl_days,
    },
    # Days without opening the console before the Invitations page calls somebody dormant.
    # Descriptive only — never a permission state. Served per staff row on the list payload
    # (`AdminListView`) because a super's list spans organisations.
    'admin_dormant_days': {
        'group': 'reviewers_staff',
        'unit': 'days',
        'min': 7,
        'max': 365,
        'default': _default_admin_dormant_days,
    },
    # ── interviews (Sprint D) ──
    # How long one interview runs. Read where the time is WRITTEN DOWN for somebody: the slot
    # row (`propose_slots`), the student's .ics + Add-to-calendar links, and the Google Meet
    # event's end time. It is ALSO the length of the block conflict-checking reserves —
    # `scheduling.held_intervals` / `overlaps` compare blocks, so a duration LONGER than the
    # slot step is safe and supported (TD-233, resolved 2026-09-08). **Deliberately unfenced
    # against `interview_slot_step_min`:** the step is a grid to place a block on, not a
    # cadence to fill, and length 45 on a 30-minute grid is the owner's worked example of a
    # CORRECT setting — a 60 step cannot reach 11:30 and a 45 step drifts. Do not add that fence.
    'interview_duration_min': {
        'group': 'interviews',
        'unit': 'minutes',
        'min': 10,
        'max': 180,
        'default': _default_interview_duration_min,
    },
    # The earliest and latest an interview may START, in the organisation's clock (MYT). Stored
    # as minutes past midnight — the tab types them as HH:MM (owner 2026-09-07). Enforced at the
    # propose endpoint (`scheduling.slot_in_window`) and SERVED to the picker, never mirrored.
    'interview_window_start_min': {
        'group': 'interviews',
        'unit': 'time_of_day',
        'min': 0,
        'max': 1439,
        'default': _default_interview_window_start_min,
    },
    'interview_window_end_min': {
        'group': 'interviews',
        'unit': 'time_of_day',
        'min': 0,
        'max': 1439,
        'default': _default_interview_window_end_min,
    },
    # The grid the picker offers times on. Divisors of 60 ONLY: `slot_in_window` reads
    # `minute % step`, which is a lie for any step that does not tile an hour.
    'interview_slot_step_min': {
        'group': 'interviews',
        'unit': 'minutes',
        'min': 5,
        'max': 60,
        'allowed': (5, 10, 15, 20, 30, 60),
        'default': _default_interview_slot_step_min,
    },
    # Minimum notice: the earliest proposable slot is this far ahead, so the student has time to
    # see the email, pick and prepare. A reviewer RESCHEDULE relaxes this in the UI only (TD-137).
    'interview_min_lead_hours': {
        'group': 'interviews',
        'unit': 'hours',
        'min': 1,
        'max': 168,
        'default': _default_interview_min_lead_hours,
    },
    # How close to the start a student may still re-pick or cancel. Read at the two refusals
    # (`scheduling.book`/`cancel`) AND printed in the booked-interview email, so one value keeps
    # the promise and the enforcement identical.
    'interview_reschedule_cutoff_hours': {
        'group': 'interviews',
        'unit': 'hours',
        'min': 1,
        'max': 168,
        'default': _default_interview_reschedule_cutoff_hours,
    },
    # ── documents (Sprint E) ──
    # The biggest single upload. Stored in MB; `max_doc_size_bytes()` is the ONE conversion.
    # Ceiling 25 (owner 2026-09-07): the `b40-documents` bucket sets no file-size limit of its
    # own, so the real wall is the Supabase project ceiling (50 MB) — 25 leaves room for a long
    # payslip photo and stays well inside it. Read at BOTH upload doors (the student's and the
    # organisation-request attachment's) and SERVED to the student's uploader.
    'max_doc_size_mb': {
        'group': 'documents',
        'unit': 'megabytes',
        'min': 1,
        'max': 25,
        'default': _default_max_doc_size_mb,
    },
    # How many LIVE documents one application may hold. A superseded copy does not count —
    # re-uploading into a slot replaces it — so this bounds slots in use, not uploads ever made.
    'max_docs_per_application': {
        'group': 'documents',
        'unit': 'documents',
        'min': 5,
        'max': 200,
        'default': _default_max_docs_per_application,
    },
    # …of which how many may be 'other' (reviewer-requested extras). Each lands in its own
    # request-keyed slot, so without this a reviewer could ask for unbounded extras.
    'max_other_docs': {
        'group': 'documents',
        'unit': 'documents',
        'min': 1,
        'max': 50,
        'default': _default_max_other_docs,
    },
    # The stage-judge circuit-breaker (owner 2026-07-09): after this many not-usable re-uploads
    # of one named document, stop looping the student and hold it for an officer instead.
    'doc_stage_max_attempts': {
        'group': 'documents',
        'unit': 'attempts',
        'min': 1,
        'max': 10,
        'default': _default_doc_stage_max_attempts,
    },
    # ── agreements (Sprint F) ──
    # How long a student has to sign once the "your agreement is ready" email actually GOES OUT
    # — the clock arms on the send, not at offer time (`sponsorship.arm_sign_deadline`), and a
    # resend re-arms it. Beyond it the offer MAY lapse; nothing expires on its own.
    'sign_accept_deadline_days': {
        'group': 'agreements',
        'unit': 'days',
        'min': 1,
        'max': 180,
        'default': _default_sign_accept_deadline_days,
    },
    # How often the signing-chain cron may re-nudge the party whose signature is still missing
    # (the partner witness first, then the Foundation's countersignature).
    'sign_reminder_days': {
        'group': 'agreements',
        'unit': 'days',
        'min': 1,
        'max': 60,
        'default': _default_sign_reminder_days,
    },
}

# ⚠ THE FOUNDATION SIGNATORY IS NOT HERE, AND MUST NOT BE ADDED. The roadmap's Sprint F line said
# the signatory name/title/NRIC and the countersign notify list "currently live in platform env
# vars". They did once; Sprint 5 moved them onto `ContractTemplate` (`counterparty_name`,
# `counterparty_title`, `counterparty_nric`, `counterparty_notify_emails`), which is already owned
# by one organisation and is what actually prints on the agreement. Putting them on this tab would
# be a SECOND home for the same fact — the exact defect the catalogue rule exists to prevent. The
# three dead `FOUNDATION_SIGNATORY_*` settings were deleted in Sprint F for the same reason.

# Cross-field rules: (earlier key, later key, code). A single key's bounds cannot express
# "the window must open before it closes", and a window stored inverted would offer the
# reviewer an empty picker with nothing on screen saying why.
_ORDERED_PAIRS = (
    ('interview_window_start_min', 'interview_window_end_min', 'window_inverted'),
)


def default(key):
    """The platform default for `key`, read live from Django settings."""
    return SETTINGS[key]['default']()


def _check_pairs(values):
    """Cross-field rules, resolved against the platform default for any key not stored.

    ⚠ Runs on a WHOLE settings dict, never on a diff: an organisation that stores only the
    closing time is still describing a window whose other end is the platform default, so
    checking the pair needs both sides resolved — and a diff has only one.
    """
    for earlier, later, code in _ORDERED_PAIRS:
        a = values.get(earlier)
        b = values.get(later)
        if a is None and b is None:
            continue
        a = default(earlier) if a is None else a
        b = default(later) if b is None else b
        if a >= b:
            # Name the LATER key: it is the box the person was most likely typing in.
            raise OrgConfigError(code, later)


def validate_values(values, *, pairs=True):
    """The storage fence. Raises `OrgConfigError` on anything the registry refuses.

    Run inside `OrganisationConfiguration.save()` — the model is where the fence lives
    (the `OrganisationTheme.save()` precedent), so every writer passes it.

    `pairs=False` checks each key ALONE, for a caller holding only the changed keys (the
    endpoint's first pass, which wants a per-key refusal code before it merges).
    """
    if not isinstance(values, dict):
        raise OrgConfigError('bad_values')
    for key, value in values.items():
        spec = SETTINGS.get(key)
        if spec is None:
            raise OrgConfigError('unknown_setting', key)
        # `bool` IS an `int` in Python — refuse it explicitly or `True` stores as 1.
        if isinstance(value, bool) or not isinstance(value, int):
            raise OrgConfigError('bad_value', key)
        if value < spec['min'] or value > spec['max']:
            raise OrgConfigError('out_of_range', key)
        allowed = spec.get('allowed')
        if allowed is not None and value not in allowed:
            raise OrgConfigError('not_allowed', key)
    if pairs:
        _check_pairs(values)


def stored(organisation, key):
    """The value the organisation CHANGED, or None. None means "use the platform default"."""
    if organisation is None:
        return None
    # The reverse OneToOne raises RelatedObjectDoesNotExist, an AttributeError subclass —
    # which is exactly why getattr-with-default is the sanctioned spelling.
    row = getattr(organisation, 'configuration', None)
    if row is None:
        return None
    return (row.values or {}).get(key)


def value(organisation, key):
    """What the product should USE: the organisation's stored value, else the platform default."""
    v = stored(organisation, key)
    return default(key) if v is None else v


def max_doc_size_bytes(organisation):
    """The per-file upload cap in BYTES for one organisation.

    ⚠ THE ONE PLACE MB BECOMES BYTES. Every door that weighs an upload calls this; none of them
    carries its own `* 1024 * 1024`, because a second conversion is how one door starts refusing
    a file another door accepted. The value on the tab is MB (the owner's unit) and the wire
    talks bytes — this function is the join, and `views.py` reports the MB back on a refusal by
    dividing here-and-nowhere-else.
    """
    return value(organisation, 'max_doc_size_mb') * 1024 * 1024


def custom_values(key):
    """{organisation_id: stored value} for every organisation that changed `key`.

    For query-time consumers with no single organisation in hand — the sponsor pool filters
    applications of MANY organisations in one queryset, so it needs the whole map, not one value.
    Organisations absent from the map follow the platform default.
    """
    from .models import OrganisationConfiguration
    out = {}
    for org_id, values in OrganisationConfiguration.objects.values_list(
            'organisation_id', 'values'):
        v = (values or {}).get(key)
        if v is not None:
            out[org_id] = v
    return out
