"""TD-254 — claiming a profile whose IC number is already registered.

**THE OLD DOOR.** `POST /api/v1/profile/claim-nric/` answered somebody else's IC with
`status: 'exists'` **and that person's NAME**, and a repeat call carrying `confirm: true` moved
the profile's primary key to the caller in raw SQL. Two defects in one endpoint: a name
disclosure to anyone who can type an IC, and an account takeover with no challenge and no
record. The raw SQL could not even do what it claimed — it repointed four child tables and left
`scholarship_applications` behind, so a target with an application would have failed at COMMIT.

**THE OWNER'S RULING (2026-09-18): a second factor the real owner holds, plus an audit line.**
This module is that ruling:

* **Never disclose the holder.** The look-up answers which challenge CHANNELS exist, as bare
  types — `['phone']`, `['email']`, `['phone', 'email']` or `[]`. No name, no masked address,
  no digits. The real owner knows their own phone.
* **A link, not a move.** A successful claim writes ONE `ProfileLoginAlias` row, which the auth
  seam resolves. Nothing is moved, renumbered or deleted, and deleting the row reverses it.
* **The challenge is conservative.** Only a contact ALREADY ON the target profile that is
  ALREADY VERIFIED. ⚠ `claim_channels()` is the ONE function the owner's two open rulings would
  change — see its docstring.
* **Everything is audited**, including the plain look-up, which is what makes *"has anybody been
  probing IC numbers?"* answerable for the first time.

**WHERE THINGS LIVE.** The views in `views.py` are thin orchestrators (house rule: thin views,
fat services); the models are in `models_claim.py`; the seam that makes an alias mean anything
is `halatuju/middleware/supabase_auth.py`.
"""
from datetime import timedelta
import hashlib
import logging
import secrets

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.dateparse import parse_datetime

from halatuju.middleware.supabase_auth import is_staff_or_sponsor_sub

from .models import ProfileClaimEvent, ProfileLoginAlias, StudentProfile

logger = logging.getLogger(__name__)

# ── The dials ───────────────────────────────────────────────────────────────────────────────
#: How long an emailed code lives. Twilio holds the phone code's own lifecycle.
CODE_TTL_MINUTES = 10
#: Wrong answers before the pending code is burnt. The RIGHT code stops working too — that is
#: the point: five guesses at a six-digit number, then start again from the send.
MAX_CODE_ATTEMPTS = 5
CODE_DIGITS = 6

#: Rate limits, per rolling hour. Cache-backed, the same shape the phone-verify views already
#: use (the production cache is a DatabaseCache, so these survive an instance). Twilio Verify's
#: own per-number limits are the backstop behind the phone door.
_WINDOW_SECONDS = 3600
MAX_LOOKUPS_PER_CALLER = 10     # look-ups that landed on SOMEBODY ELSE'S record
MAX_LOOKUPS_PER_NRIC = 20       # …and the same IC probed from many logins
MAX_SENDS_PER_CALLER = 5
MAX_SENDS_PER_NRIC = 5
MAX_CHECKS_PER_CALLER = 10

#: ⚠ SERVED, NOT MIRRORED. The browser maps a code to its copy and knows no policy; this tuple
#: is the whole vocabulary, and the web's drift test reads it from this file by name.
REFUSAL_CODES = (
    'confirm_removed',           # the old one-shot takeover door, now bricked
    'not_claimable',             # that IC is free, or already this caller's
    'no_verified_contact',       # nothing on the target is verified — route to a human
    'channel_unavailable',       # that channel is not verified on the target
    'caller_has_verified_nric',  # we cannot merge two real records
    'caller_has_application',    # …nor two real applications
    'caller_is_staff',           # staff and sponsors are not students
    'already_claimed',           # this login already acts as a profile
    'unconfigured',              # the phone transport is not configured
    'send_failed',
    'rate_limited',
    'code_required',
    'no_pending_code',
    'code_incorrect',
    'code_expired',
    'too_many_attempts',
)

#: Everything else is a 403: a policy refusal, not a bad request.
_HTTP_FOR = {
    'rate_limited': 429,
    'unconfigured': 503,
    'send_failed': 502,
    'code_required': 400,
    'no_pending_code': 400,
    'code_incorrect': 400,
    'code_expired': 400,
    'too_many_attempts': 400,
}

VALID_STATE_CODES = {
    '01', '02', '03', '04', '05', '06', '07', '08', '09', '10',
    '11', '12', '13', '14', '15', '16',
    '21', '22', '23', '24',
    '71', '72',
    '82',
}

# ── The trilingual code email ───────────────────────────────────────────────────────────────
#: ⚠ NO PROGRAMME IDENTITY IN THE LITERALS (tenancy rule 2): the sender, the sign-off and the
#: support address all come from the branding seam at send time.
CLAIM_CODE_SUBJECTS = {
    'en': 'Your verification code',
    'ms': 'Kod pengesahan anda',
    'ta': 'உங்கள் சரிபார்ப்புக் குறியீடு',
}
CLAIM_CODE_BODIES = {
    'en': (
        "Dear {name},\n\n"
        "Somebody has asked to sign in to the account that holds your IC number, using a "
        "different login.\n\n"
        "Your code is {code}. It expires in {minutes} minutes.\n\n"
        "If this was not you, do nothing — the account does not change without this code. "
        "If it keeps happening, write to us at {support}.\n\n"
        "Warm regards,\n{signoff}"
    ),
    'ms': (
        "Salam {name},\n\n"
        "Seseorang telah meminta untuk log masuk ke akaun yang memegang nombor KP anda, "
        "menggunakan log masuk yang berbeza.\n\n"
        "Kod anda ialah {code}. Ia tamat tempoh dalam {minutes} minit.\n\n"
        "Jika ini bukan anda, jangan buat apa-apa — akaun itu tidak berubah tanpa kod ini. "
        "Jika ia berulang, hubungi kami di {support}.\n\n"
        "Salam hormat,\n{signoff}"
    ),
    'ta': (
        "அன்புள்ள {name},\n\n"
        "வேறொரு உள்நுழைவைப் பயன்படுத்தி, உங்கள் அடையாள அட்டை எண்ணைக் கொண்ட கணக்கில் "
        "நுழைய ஒருவர் கேட்டுள்ளார்.\n\n"
        "உங்கள் குறியீடு {code}. இது {minutes} நிமிடங்களில் காலாவதியாகும்.\n\n"
        "இது நீங்கள் இல்லையெனில், எதுவும் செய்ய வேண்டாம் — இந்தக் குறியீடு இல்லாமல் கணக்கு "
        "மாறாது. இது மீண்டும் நிகழ்ந்தால், {support} என்ற முகவரியில் எங்களுக்கு எழுதுங்கள்.\n\n"
        "அன்புடன்,\n{signoff}"
    ),
}


# ── THE POLICY ──────────────────────────────────────────────────────────────────────────────
def claim_channels(profile):
    """Which challenge channels the REAL owner of `profile` could answer on.

    ⚠ **THIS IS THE ONE FUNCTION THE OWNER'S TWO OPEN RULINGS WOULD CHANGE.** Both were put to
    him on 2026-09-18 and neither has been answered, so the conservative reading stands:

      1. *Is an UNVERIFIED contact on the target profile good enough to receive the code?*
         Today: **no.** To widen it, drop `contact_*_verified` from the two conditions below.
      2. *Does the phone count when the email is the thing they lost?*
         Today both are offered and the student chooses. To narrow it to the phone, drop the
         email branch.

    Measured 2026-09-18: of 674 profiles carrying an IC, only 70 have a verified phone or
    email. So for nine accounts in ten this returns `[]` and the honest answer is to refuse and
    route to a human. That is a policy outcome, not a bug.

    Returns bare channel TYPES, in the order the UI offers them. Never an address or a number.
    """
    channels = []
    if profile.contact_phone and profile.contact_phone_verified:
        channels.append('phone')
    if profile.contact_email and profile.contact_email_verified:
        channels.append('email')
    return channels


# ── NRIC validation (moved here verbatim from the view) ─────────────────────────────────────
def validate_nric(nric):
    """The message to refuse `nric` with, or '' when it is usable. Same rules, same words, as
    before — `/profile` and `/scholarship/apply` read only the 400."""
    import re
    from datetime import date

    if not nric:
        return 'NRIC is required'
    if not re.match(r'^\d{6}-\d{2}-\d{4}$', nric):
        return 'Invalid NRIC format'
    yy, mm, dd = int(nric[:2]), int(nric[2:4]), int(nric[4:6])
    if not (1 <= mm <= 12 and 1 <= dd <= 31):
        return 'Invalid NRIC: date portion is not valid'
    year = 2000 + yy if yy <= 11 else 1900 + yy
    age = date.today().year - year
    if not (15 <= age <= 23):
        return 'IC number must belong to a student aged 15-23'
    if nric[7:9] not in VALID_STATE_CODES:
        return 'Invalid state code in IC number'
    return ''


# ── Small private machinery ─────────────────────────────────────────────────────────────────
def _digest(value):
    """A short, stable, non-reversing key fragment. ⚠ An IC never goes into a cache key in the
    clear — the production cache is an ordinary database table."""
    return hashlib.sha256(str(value).encode()).hexdigest()[:32]


def pending_key(caller_sub, nric):
    """Where a pending challenge for this (caller, IC) pair lives. Public because tests and any
    future operator tool need the same answer this module uses."""
    return 'claim:pending:%s' % _digest(f'{caller_sub}|{nric}')


def _hash_code(caller_sub, nric, code):
    """⚠ A six-digit code is trivially brute-forced from a bare digest, so the stored value is
    keyed on SECRET_KEY as well as on the caller and the IC — a stolen cache row is useless."""
    return salted_hmac('halatuju.profile_claim', f'{caller_sub}|{nric}|{code}',
                       secret=settings.SECRET_KEY).hexdigest()


def _new_code():
    return f'{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}'


def _twilio_verify():
    """The Twilio Verify helpers — the phone door's transport, already built for `/profile`.

    ⚠ Imported HERE AND ONLY HERE. The app-boundary standard counts every `courses ->
    scholarship` import statement, and two copies of one edge is one edge too many; the import
    stays inside a function so it does not run at app-load (that is the half that takes the
    service down at start-up)."""
    from apps.scholarship import whatsapp
    return whatsapp


def _within(key, limit):
    """True when this hit is inside `limit` for the hour, counting it. Best-effort, exactly like
    the phone-verify counter next door: this is abuse mitigation, not an auth boundary."""
    used = cache.get(key, 0)
    if used >= limit:
        return False
    cache.set(key, used + 1, _WINDOW_SECONDS)
    return True


def _record(event, *, caller_sub, target='', nric='', channel='', actor=''):
    """Append one audit line. ⚠ APPEND-ONLY: this is the only write path to the table."""
    return ProfileClaimEvent.objects.create(
        event=event, caller_sub=caller_sub or '', target_profile_id=target or '',
        nric=nric or '', channel=channel or '', actor=actor or '')


def _refuse(code, caller_sub, target, nric='', channel=''):
    """A refusal is a stable code, an HTTP status and an audit line — always all three."""
    _record(f'refused_{code}', caller_sub=caller_sub,
            target=getattr(target, 'supabase_user_id', '') or '', nric=nric, channel=channel)
    return {'status': 'refused', 'code': code}, _HTTP_FOR.get(code, 403)


def _holder_of(nric):
    """The profile that holds `nric`. ⚠ The uniqueness index is PARTIAL (`WHERE nric_verified
    AND nric <> ''`), so two UNVERIFIED profiles may legally share a number; prefer the VERIFIED
    holder, since that is the one whose claim actually stands."""
    return (StudentProfile.objects.filter(nric=nric)
            .order_by('-nric_verified', 'supabase_user_id').first())


def _caller_blocker(caller_sub):
    """Why this CALLER may not claim anything — the refusals that are about the caller rather
    than the target. ⚠ We cannot merge two real records, so a caller who already IS somebody
    goes to a human instead."""
    if is_staff_or_sponsor_sub(caller_sub):
        return 'caller_is_staff'
    if ProfileLoginAlias.objects.filter(alias_uid=caller_sub).exists():
        return 'already_claimed'
    caller = StudentProfile.objects.filter(supabase_user_id=caller_sub).first()
    if caller is None:
        return None
    if caller.nric and caller.nric_verified:
        return 'caller_has_verified_nric'
    if caller.scholarship_applications.exists():
        return 'caller_has_application'
    return None


# ── The metered send ────────────────────────────────────────────────────────────────────────
def send_claim_code_email(to_email, code, lang='en'):
    """The code, through the existing METERED email seam (tenancy rule 6) — never a bare
    `send_mail`. ⚠ The NAME of this function is what `emails._meter_email` records as the usage
    source, which is why it starts with `send_`."""
    from apps.scholarship import emails

    lang = emails.normalise_lang(lang)
    return emails._send(
        to_email, CLAIM_CODE_SUBJECTS, CLAIM_CODE_BODIES, '', '', lang,
        extra={'code': code, 'minutes': str(CODE_TTL_MINUTES),
               'support': emails.SUPPORT_EMAIL,
               'signoff': emails._P.team_signoff(lang)})


# ── The three doors ─────────────────────────────────────────────────────────────────────────
def handle_claim(caller_sub, acting_uid, data):
    """`POST /api/v1/profile/claim-nric/` — look the IC up. Returns `(payload, http_status)`.

    ⚠ **TWO IDENTITIES, ON PURPOSE.** `caller_sub` is the REAL login (what the audit line
    records, and what may go on to claim); `acting_uid` is the profile that login currently
    acts as — the same thing for everyone except a caller who already holds an alias. The IC
    the student is EDITING belongs to the acting profile; the attempt belongs to the login.

    ⚠ `confirm: true` IS GONE. A client still posting it gets a refusal; there is no code path
    from here to a transfer, because there is no transfer any more.
    """
    nric = (data.get('nric') or '').strip()
    error = validate_nric(nric)
    if error:
        return {'error': error}, 400

    acting = StudentProfile.objects.filter(supabase_user_id=acting_uid).first()
    if acting and acting.nric and acting.nric_verified and acting.nric != nric:
        return {'error': 'Your NRIC is verified and locked. Contact support to change it.',
                'code': 'nric_locked'}, 403

    holder = _holder_of(nric)
    if holder is None:
        profile, _created = StudentProfile.objects.get_or_create(supabase_user_id=acting_uid)
        profile.nric = nric
        profile.save(update_fields=['nric'])
        return {'status': 'created'}, 200
    if holder.supabase_user_id == acting_uid:
        return {'status': 'linked'}, 200

    # ── From here on we are looking at SOMEBODY ELSE'S record. Everything is counted and
    #    everything is recorded.
    if not (_within(f'claim:look:{caller_sub}', MAX_LOOKUPS_PER_CALLER)
            and _within('claim:look:n:%s' % _digest(nric), MAX_LOOKUPS_PER_NRIC)):
        return _refuse('rate_limited', caller_sub, holder, nric)
    if data.get('confirm'):
        return _refuse('confirm_removed', caller_sub, holder, nric)

    _record(ProfileClaimEvent.EXISTS_SHOWN, caller_sub=caller_sub,
            target=holder.supabase_user_id, nric=nric)
    return {'status': 'exists', 'channels': claim_channels(holder)}, 200


def send_code(caller_sub, acting_uid, data):
    """`POST /api/v1/profile/claim-nric/send-code/` — challenge the contact on the TARGET.

    `caller_sub` / `acting_uid` mean what they mean in `handle_claim`."""
    nric = (data.get('nric') or '').strip()
    channel = (data.get('channel') or '').strip()
    lang = data.get('lang') if data.get('lang') in ('en', 'ms', 'ta') else 'en'
    error = validate_nric(nric)
    if error:
        return {'error': error}, 400

    target = _holder_of(nric)
    if target is None or target.supabase_user_id in (caller_sub, acting_uid):
        return _refuse('not_claimable', caller_sub, target, nric)
    if not (_within(f'claim:send:{caller_sub}', MAX_SENDS_PER_CALLER)
            and _within('claim:send:n:%s' % _digest(nric), MAX_SENDS_PER_NRIC)):
        return _refuse('rate_limited', caller_sub, target, nric)

    blocker = _caller_blocker(caller_sub)
    if blocker:
        return _refuse(blocker, caller_sub, target, nric)

    channels = claim_channels(target)
    if not channels:
        return _refuse('no_verified_contact', caller_sub, target, nric)
    if channel not in channels:
        return _refuse('channel_unavailable', caller_sub, target, nric, channel=channel)

    code_hash = ''
    if channel == 'phone':
        ok, vstatus, _err = _twilio_verify().start_phone_verification(
            target.contact_phone, channel='whatsapp')
        if not ok:
            return _refuse('unconfigured' if vstatus == 'unconfigured' else 'send_failed',
                           caller_sub, target, nric, channel=channel)
    else:
        code = _new_code()
        code_hash = _hash_code(caller_sub, nric, code)
        if not send_claim_code_email(target.contact_email, code, lang):
            return _refuse('send_failed', caller_sub, target, nric, channel=channel)

    expires_at = timezone.now() + timedelta(minutes=CODE_TTL_MINUTES)
    cache.set(pending_key(caller_sub, nric),
              {'target': target.supabase_user_id, 'channel': channel, 'code_hash': code_hash,
               'attempts': 0, 'expires_at': expires_at.isoformat()},
              CODE_TTL_MINUTES * 60 + 60)
    _record(ProfileClaimEvent.CODE_SENT, caller_sub=caller_sub,
            target=target.supabase_user_id, nric=nric, channel=channel)
    logger.info('Profile-claim code sent over %s', channel)   # ⚠ no IC, no code, no address
    return {'status': 'sent', 'channel': channel}, 200


def confirm_code(caller_sub, data):
    """`POST /api/v1/profile/claim-nric/confirm-code/` — answer the challenge.

    On success this writes ONE `ProfileLoginAlias` row inside the same transaction as the
    `claimed` audit line. **It moves nothing and it deletes nothing** — the caller's own empty
    profile stays exactly where it is, simply unreachable while the alias stands.
    """
    nric = (data.get('nric') or '').strip()
    code = (data.get('code') or '').strip()
    error = validate_nric(nric)
    if error:
        return {'error': error}, 400
    if not _within(f'claim:check:{caller_sub}', MAX_CHECKS_PER_CALLER):
        return _refuse('rate_limited', caller_sub, None, nric)

    key = pending_key(caller_sub, nric)
    pending = cache.get(key)
    if not pending:
        return _refuse('no_pending_code', caller_sub, None, nric)
    target = StudentProfile.objects.filter(supabase_user_id=pending['target']).first()
    if target is None:                       # the record went away between send and confirm
        cache.delete(key)
        return _refuse('no_pending_code', caller_sub, None, nric)
    channel = pending['channel']

    if not code:
        return _refuse('code_required', caller_sub, target, nric, channel=channel)
    expires_at = parse_datetime(pending['expires_at'])
    if expires_at is None or timezone.now() > expires_at:
        cache.delete(key)
        return _refuse('code_expired', caller_sub, target, nric, channel=channel)
    if pending['attempts'] >= MAX_CODE_ATTEMPTS:
        cache.delete(key)
        return _refuse('too_many_attempts', caller_sub, target, nric, channel=channel)

    blocker = _caller_blocker(caller_sub)
    if blocker:
        return _refuse(blocker, caller_sub, target, nric, channel=channel)

    if channel == 'phone':
        approved, err = _twilio_verify().check_phone_verification(target.contact_phone, code)
        if err == 'unconfigured':
            return _refuse('unconfigured', caller_sub, target, nric, channel=channel)
    else:
        approved = constant_time_compare(pending['code_hash'],
                                         _hash_code(caller_sub, nric, code))

    if not approved:
        pending['attempts'] += 1
        cache.set(key, pending, CODE_TTL_MINUTES * 60 + 60)
        _record(ProfileClaimEvent.CODE_FAILED, caller_sub=caller_sub,
                target=target.supabase_user_id, nric=nric, channel=channel)
        return {'status': 'refused', 'code': 'code_incorrect'}, 400

    with transaction.atomic():
        event = _record(ProfileClaimEvent.CLAIMED, caller_sub=caller_sub,
                        target=target.supabase_user_id, nric=nric, channel=channel)
        ProfileLoginAlias.objects.create(
            alias_uid=caller_sub, profile=target, claim_event=event)
    cache.delete(key)
    logger.info('Profile-claim succeeded over %s', channel)    # ⚠ no IC, no code, no address
    return {'status': 'claimed'}, 200


def revoke_alias(alias_uid, by=''):
    """Reverse a claim. Deleting the row is the WHOLE undo — nothing was moved, so nothing has
    to be moved back, and the login returns to its own (empty) profile on its very next request.
    Returns True when there was an alias to remove.

    No UI yet: this is the operator's handle, and the `alias_revoked` line is what makes the
    reversal as auditable as the claim was.
    """
    alias = ProfileLoginAlias.objects.filter(alias_uid=alias_uid).first()
    if alias is None:
        return False
    target_id = alias.profile_id
    alias.delete()
    _record(ProfileClaimEvent.ALIAS_REVOKED, caller_sub=alias_uid, target=target_id, actor=by)
    return True
