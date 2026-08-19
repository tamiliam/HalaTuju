"""Partner-organisation notifications — the send orchestration (2026-07-26).

Mirrors `sponsor_notifications.py`: the decisions live in `partner_comms`, the envelope lives in
`emails.send_partner_email`, and this module only sequences them and writes the log. The two
management commands are thin wrappers over the two entry points.

  * `send_partner_digests()`    — weekly. The stage summary + the chase list.
  * `send_partner_milestones()` — hourly. Awaiting-review + awarded, batched per organisation.
  * `notify_partner_assigned()` — inline, at the moment an administrator assigns a student.

Four rules hold everywhere in here, each of which is a way this could otherwise fail quietly:

1. **Every attempt is logged, including a skip.** `PartnerEmailLog` records `ok=False` with a note
   for "no recipient" / "unchanged" / "nobody waiting", so silence is visible rather than
   indistinguishable from success.
2. **A repeated identical skip is logged once.** An hourly sweep would otherwise write the same
   `no_recipient` row 24 times a day per organisation, and the useful signal would drown.
3. **A milestone is stamped only on a SUCCESSFUL send.** An unreachable organisation's students
   stay unstamped, so they are told once an address exists rather than silently skipped forever.
4. **Both switches are checked** (`partner_comms.is_enabled` = the platform flag AND the template's
   own), and nothing here raises into a caller: a partner email must never break a payment run, an
   assignment, or a cron.
"""
import logging

from django.conf import settings
from django.utils import timezone

from . import partner_comms
from . import usage
from .emails import send_partner_email
from .models import PartnerEmailLog, PartnerEmailTemplate

logger = logging.getLogger(__name__)

# How many students one milestone email names before the rest wait for the next sweep. Bounds the
# email when an address is added to an organisation that already has a backlog — nobody is lost,
# they simply arrive over a few hours.
MAX_MILESTONE_STUDENTS = 20

_STAMP_FIELD = {
    'awaiting_review': 'partner_awaiting_notified_at',
    'awarded': 'partner_awarded_notified_at',
}


def _max_per_run():
    return int(getattr(settings, 'PARTNER_NOTIFY_MAX_PER_RUN', 100) or 100)


def _template(kind):
    return PartnerEmailTemplate.objects.filter(kind=kind).first()


def _already_noted(org, kind, note):
    """True when the newest log row for this pair is ALREADY this same skip.

    Rule 2: an hourly sweep must not write the same `no_recipient` row every hour. A change of
    outcome (a real send, or a different reason) is always recorded.
    """
    latest = (PartnerEmailLog.objects
              .filter(organisation=org, kind=kind)
              .order_by('-sent_at')
              .values('ok', 'note').first())
    return bool(latest and not latest['ok'] and latest['note'] == note)


def _log(org, kind, *, ok, note='', recipients=None, subject='', students=0,
         fingerprint='', application=None):
    """Record one attempt. Never raises — a logging failure must not lose the email."""
    try:
        PartnerEmailLog.objects.create(
            organisation=org, kind=kind, ok=ok, note=note[:200],
            recipients=list(recipients or []), subject=(subject or '')[:255],
            students=students, fingerprint=fingerprint, application=application,
        )
    except Exception:  # noqa: BLE001 — the send matters more than its audit row
        logger.warning('partner_comms: could not log %s for org=%s', kind, org.id, exc_info=True)


def _skip(org, kind, note, *, once=True):
    """Log a skip (deduplicated by default) and return False."""
    if not (once and _already_noted(org, kind, note)):
        _log(org, kind, ok=False, note=note)
    return False


def _owning_org_id(org, application=None):
    """Which tenant does this partner email bill to?

    A milestone names one application, so that application's owner answers it. A digest is
    about the whole set of students attributed to this Source Partner, so the answer is the
    owner they share — and `sole_organisation_id` returns None rather than picking when they
    do not share one (possible from the second tenant onward; see its docstring).
    """
    if application is not None:
        return getattr(application, 'owning_organisation_id', None)
    return usage.sole_organisation_id(
        partner_comms.partner_applications(org)
        .values_list('owning_organisation_id', flat=True).distinct())


def _deliver(org, kind, template, context, *, students=0, fingerprint='', application=None,
             dry_run=False, out=None):
    """Render → send → log. Returns True only when the email actually went."""
    recipients = partner_comms.recipient_for(org)
    if not recipients:
        return _skip(org, kind, 'no_recipient')

    context.setdefault('org_name', org.name)
    context.setdefault('contact_person', getattr(org, 'contact_person', '') or '')
    subject, text_body, html_body = partner_comms.render(kind, template, context)

    if dry_run:
        if out is not None:
            out.write(f'[dry-run] {kind} → {org.code} <{recipients[0]}> '
                      f'({students} student(s))\n  subject: {subject}\n')
            out.write('  ' + text_body.replace('\n', '\n  ') + '\n\n')
        return True

    # Bill the organisation whose STUDENTS this email is about — NOT `org`, which is the
    # Source Partner RECEIVING it. Attributing to the recipient would put BrightPath's costs
    # on a referrer's invoice. Derived (never a house-org literal, per the tenancy
    # conventions) and refused when ambiguous — see usage.sole_organisation_id.
    with usage.usage_context(organisation_id=_owning_org_id(org, application)):
        ok = send_partner_email(recipients[0], subject=subject, text_body=text_body,
                                html_body=html_body)
    _log(org, kind, ok=bool(ok), note='' if ok else 'send_failed', recipients=recipients,
         subject=subject, students=students, fingerprint=fingerprint, application=application)
    return bool(ok)


# ── the two weekly emails ─────────────────────────────────────────────────────

def send_partner_digests(dry_run=False, out=None):
    """Weekly: the stage summary and the chase list, per qualifying organisation.

    The two kinds skip a quiet week DIFFERENTLY, by owner ruling (2026-07-26):

    * `weekly_summary` skips when the counts are identical to the last one sent — an unchanged
      scoreboard is not news, and repeated identical emails train a reader to ignore them.
    * `shortlisted_followup` skips ONLY when nobody is waiting. An unchanged list of stragglers is
      exactly who needs chasing, so it goes out again.
    """
    summary = {}
    partners = partner_comms.qualifying_partners()
    cap = _max_per_run()
    if len(partners) > cap:
        logger.warning('send_partner_digests: %d qualifying partners exceeds cap %d; '
                       'sending to the first %d this run', len(partners), cap, cap)
        if out is not None:
            out.write(f'cap {cap} reached — {len(partners) - cap} organisation(s) deferred '
                      f'to the next run\n')
        partners = partners[:cap]

    for kind in partner_comms.WEEKLY_KINDS:
        sent = skipped = 0
        template = _template(kind)
        if not partner_comms.is_enabled(kind) or template is None:
            summary[kind] = {'sent': 0, 'skipped': 0, 'off': True}
            if out is not None:
                out.write(f'{kind}: off (platform flag or template switch)\n')
            continue

        for org in partners:
            if kind == 'weekly_summary':
                counts = partner_comms.stage_counts(org)
                if not counts.get('total'):
                    skipped += 1
                    _skip(org, kind, 'no_students')
                    continue
                fp = partner_comms.fingerprint(counts)
                if kind in partner_comms.SKIP_UNCHANGED and \
                        fp == partner_comms.last_fingerprint(org, kind):
                    skipped += 1
                    _skip(org, kind, 'unchanged')
                    continue
                ok = _deliver(org, kind, template, {'counts': counts},
                              students=counts['total'], fingerprint=fp,
                              dry_run=dry_run, out=out)
            else:
                rows = partner_comms.chase_rows(org)
                if not rows:
                    skipped += 1
                    _skip(org, kind, 'nobody_waiting')
                    continue
                fp = partner_comms.fingerprint({
                    'n': len(rows),
                    'who': '|'.join(sorted(name for name, _, _ in rows)),
                })
                ok = _deliver(org, kind, template,
                              {'count': len(rows), 'rows': rows,
                               'today': timezone.localdate()},
                              students=len(rows), fingerprint=fp, dry_run=dry_run, out=out)
            sent += 1 if ok else 0
            skipped += 0 if ok else 1

        summary[kind] = {'sent': sent, 'skipped': skipped, 'off': False}
        if out is not None:
            out.write(f'{kind}: sent {sent}, skipped {skipped}\n')
    return summary


# ── the two milestone emails ──────────────────────────────────────────────────

def _partner_by_chip():
    """`{referral chip: organisation}` for every ACTIVE partner (never the house org).

    Used to fetch only students who belong to a real partner: a self-referred or unattributed
    application is the house org's residual and is never the subject of a partner email.
    """
    from apps.courses.models import PartnerOrganisation
    return {
        o.code: o for o in PartnerOrganisation.objects
        .filter(is_active=True).exclude(code=partner_comms.HOUSE_ORG_CODE)
    }


def send_partner_milestones(dry_run=False, out=None):
    """Hourly: tell an organisation which of its students completed, or were awarded.

    Batched per organisation — several students arriving close together share one email, like
    `send_sponsor_realtime`. The queryset re-checks the CURRENT status, so a transition that was
    reverted (`revert_if_profile_incomplete`, `awarded → recommended`) never produces an email.

    Stamps only what was actually sent: an organisation with no address keeps its students
    unstamped, so they are told once an address exists.
    """
    summary = {}
    by_chip = _partner_by_chip()
    qualifying = {o.id for o in partner_comms.qualifying_partners()}

    for kind in ('awaiting_review', 'awarded'):
        sent = stamped = 0
        template = _template(kind)
        if not partner_comms.is_enabled(kind) or template is None:
            summary[kind] = {'sent': 0, 'students': 0, 'off': True}
            if out is not None:
                out.write(f'{kind}: off (platform flag or template switch)\n')
            continue

        pending = {}
        for app in (partner_comms.milestone_queryset(kind)
                    .filter(profile__referral_source__in=list(by_chip))
                    .select_related('profile').order_by('pk')):
            chip = (getattr(app.profile, 'referral_source', '') or '')
            pending.setdefault(chip, []).append(app)

        for chip, apps in sorted(pending.items()):
            org = by_chip[chip]
            if org.id not in qualifying:
                _skip(org, kind, 'no_recipient')
                continue
            batch = apps[:MAX_MILESTONE_STUDENTS]
            names = [
                (getattr(a.profile, 'name', '') or '').strip() or f'Applicant #{a.id}'
                for a in batch
            ]
            ok = _deliver(org, kind, template,
                          {'count': len(batch), 'names': names},
                          students=len(batch), dry_run=dry_run, out=out)
            if not ok:
                continue
            sent += 1
            if not dry_run:
                field = _STAMP_FIELD[kind]
                now = timezone.now()
                # Stamp AFTER a successful send, and only the students this email named.
                stamped += type(batch[0]).objects.filter(
                    pk__in=[a.pk for a in batch]).update(**{field: now})
        summary[kind] = {'sent': sent, 'students': stamped, 'off': False}
        if out is not None:
            out.write(f'{kind}: {sent} email(s), {stamped} student(s) stamped\n')
    return summary


# ── the assignment email (inline, not a sweep) ────────────────────────────────

def notify_partner_assigned(application, org):
    """Tell ONE organisation that a student with no referring organisation has been placed with it.

    Inline and immediate: an explicit administrator action, low volume, and nothing to revert. Fully
    best-effort — an email problem must never fail the assignment that triggered it.
    """
    if org is None or application is None:
        return False
    try:
        if not partner_comms.is_enabled('assigned'):
            return False
        template = _template('assigned')
        if template is None:
            return False
        if org.id not in {o.id for o in partner_comms.qualifying_partners()}:
            return _skip(org, 'assigned', 'no_recipient')
        profile = getattr(application, 'profile', None)
        student = (getattr(profile, 'name', '') or '').strip() or f'Applicant #{application.id}'
        return _deliver(org, 'assigned', template,
                        {'student_name': student}, students=1, application=application)
    except Exception:  # noqa: BLE001 — never break the assignment
        logger.warning('partner_comms: assigned email failed for app=%s org=%s',
                       getattr(application, 'id', None), getattr(org, 'id', None), exc_info=True)
        return False


def notify_student_assigned(application, org):
    """Tell the STUDENT that a partner organisation has been placed with them (request #3).

    The other half of ``notify_partner_assigned``, sent at the same moment to the other party. It
    goes through the same stored-template machinery — so the owner switches it on and edits its
    wording on the same screen as the five organisation emails, and the row they read IS what
    sends. The screen labels its recipient, because it is the one entry there that a partner
    never receives.

    ⚠ The recipient check is the STUDENT's address, so ``qualifying_partners()`` is deliberately
    NOT consulted: an organisation with no contact email of its own must still not stop the
    student being told. Fully best-effort — an email problem must never fail the assignment.
    """
    if org is None or application is None:
        return False
    try:
        if not partner_comms.is_enabled('student_assigned'):
            return False
        template = _template('student_assigned')
        if template is None:
            return False
        profile = getattr(application, 'profile', None)
        to_email = (getattr(application, 'notify_email', '')
                    or getattr(profile, 'contact_email', '') or '')
        if not to_email:
            return _skip(org, 'student_assigned', 'no_student_address')
        first = ((getattr(profile, 'name', '') or '').strip().split(' ') or [''])[0]
        subject, text_body, html_body = partner_comms.render(
            'student_assigned', template,
            {'org_name': org.name, 'student_name': first or 'there'})
        # This one goes to the STUDENT about their referrer; it is the programme's work.
        with usage.usage_context(organisation_id=_owning_org_id(org, application)):
            ok = send_partner_email(to_email, subject=subject, text_body=text_body,
                                    html_body=html_body)
        _log(org, 'student_assigned', ok=bool(ok), note='' if ok else 'send_failed',
             recipients=[to_email], subject=subject, students=1, application=application)
        return bool(ok)
    except Exception:  # noqa: BLE001 — never break the assignment
        logger.warning('partner_comms: student assigned email failed for app=%s org=%s',
                       getattr(application, 'id', None), getattr(org, 'id', None), exc_info=True)
        return False
