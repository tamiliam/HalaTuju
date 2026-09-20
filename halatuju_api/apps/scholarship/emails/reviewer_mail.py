"""Reviewer and partner staff mail: assignment, the templated render seam, the welcome and
invitation bodies, and the QC returned / rejected notices.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.core.mail import EmailMessage
from .sending import _send_html, _send_plain
from .shared import _P, logger


# ── Reviewer emails — shared bits (one greeting, one CTA, one sign-off) ────────
# All reviewer mail goes out via _send_plain → from the monitored interview@ alias with a
# working reply-to, so "reply to reassign" / replies actually reach a person. The subject
# carries the Scholar-code so a reviewer juggling several applicants can triage at a glance.
_REVIEWER_SIGNOFF = f'Thanks,\n{_P.team_signoff("en")}'


def _reviewer_dashboard_cta():
    """The single CTA every reviewer email shares — one name ('reviewer dashboard'), one link."""
    frontend = _P.frontend_url
    return f'Open in your reviewer dashboard:\n{frontend}/admin/login'


def _reviewer_subject(base, ref):
    """Append the Scholar-code (ref) so reviewers can triage from the subject line."""
    return f'{base} — {ref}' if ref else base


#: What `_reviewer_render` decided. `SENT` and `STOPPED` both mean the caller is done.
_REVIEWER_SENT = 'sent'
_REVIEWER_STOPPED = 'stopped'
_REVIEWER_LEGACY = 'legacy'


def _reviewer_render(kind, to_email, context):
    """Send one of the five reviewer emails FROM ITS STORED TEMPLATE, if there is one.

    Returns `_REVIEWER_SENT` (the row governed and we sent), `_REVIEWER_STOPPED` (the row exists
    and is switched OFF — send nothing), or `_REVIEWER_LEGACY` (no row: the caller falls through
    to its hard-coded body below).

    ⚠ **THE FALLBACK KEYS ON "NO ROW", NOT ON THE SWITCH, AND THAT IS THE WHOLE DESIGN.** These
    five are live emails today. Keying the fallback on `enabled` would mean an owner who ticks one
    OFF still has the old sender mailing behind their back — the switch would be a lie the screen
    tells (lessons.md, sponsor S3). Keying it on the row's EXISTENCE gives two honest worlds: with
    the rows seeded the templates govern completely, and if a seeding step is ever missed the mail
    still goes out rather than silently stopping.

    ⚠ **A RENDER FAILURE FALLS BACK, IT NEVER BLOCKS.** Everything here is best-effort mail on the
    side of an assignment or a QC decision; a template a human edited into an unrenderable state
    must not take the working sender down with it.
    """
    if not to_email:
        return _REVIEWER_STOPPED
    try:
        from .. import partner_comms
        from ..models import PartnerEmailTemplate as _T
        state = partner_comms.template_state(kind)
        if state == 'missing':
            return _REVIEWER_LEGACY
        if state == 'off':
            return _REVIEWER_STOPPED
        tpl = _T.objects.filter(kind=kind).first()
        ctx = dict(context)
        ctx.setdefault('dashboard_link', _reviewer_dashboard_cta())
        subject, text_body, html_body = partner_comms.render(kind, tpl, ctx)
    except Exception:
        logger.warning('Reviewer template render failed for %s; using the built-in body',
                       kind, exc_info=True)
        return _REVIEWER_LEGACY
    # ⚠ The SENDER stays `interview@` with the interview unsubscribe headers, the same envelope
    # these five have always used. `_send_html` defaults to it; naming it is cheaper than the
    # request-#3 trap in reverse, where the wrong alias looked identical at the call site.
    _send_html(to_email, subject, html_body, text_body)
    return _REVIEWER_SENT


def send_reviewer_assigned_email(to_email, reviewer_name, *, ref='', programme='', review_by=''):
    """F7: notify a reviewer that an applicant has been assigned to them. English-only
    (reviewers are internal staff). Sent on each (re)assignment — never re-sent for an
    unchanged assignee, because assign_reviewer short-circuits a no-op before this fires.
    From the monitored interview@ alias so 'reply to reassign' actually reaches a person.
    Best-effort — swallows send failures so a mail hiccup never breaks the assignment."""
    outcome = _reviewer_render('reviewer_assigned', to_email, {
        'reviewer_name': reviewer_name, 'ref': ref, 'programme': programme,
        'review_by': review_by,
    })
    if outcome is not _REVIEWER_LEGACY:
        return outcome is _REVIEWER_SENT
    reviewer = reviewer_name or 'there'
    details = [f'Reference: {ref or "—"}', f'Programme: {programme or "—"}']
    if review_by:
        details.append(f'Please review by: {review_by}')
    body = (
        f'Dear {reviewer},\n\n'
        f'A new applicant has been assigned to you for review.\n\n'
        + '\n'.join(details) + '\n\n'
        f'Everything you need — profile, documents, and the verification checks — is in your '
        f'reviewer dashboard:\n\n'
        f'{_reviewer_dashboard_cta()}\n\n'
        f"Can't take this one? Just reply and we'll reassign it.\n\n"
        f'{_REVIEWER_SIGNOFF}'
    )
    return _send_plain(to_email, _reviewer_subject('New applicant assigned to you', ref), body)


_PARTNER_ROLE_LABELS = {
    'admin': 'an administrator',
    'finance': 'a finance administrator',
    'org_admin': 'an organisation administrator',
    'partner': 'a partner organisation representative',
    'reviewer': 'a reviewer',
    'qc': 'a quality-control reviewer',
    'super': 'a super administrator',
}


def _invite_kind_for_role(role):
    """Which stored invitation template addresses this role, or None to use the built-in wording.

    ⚠ **IT READS `invitations.KIND_ROLES` RATHER THAN A MAP OF ITS OWN.** That is the same map that
    decides which of the four tables a person is LISTED in on the Invitations page, so the letter
    somebody receives and the table they appear in cannot disagree — finance is written to as an
    admin and qc as a reviewer because that is where each of them sits. A second hand-written map
    here would be correct on the day it was typed and wrong after the first regrouping.

    ⚠ **None FOR `partner` AND `super`, DELIBERATELY.** A Referral Partner is a PLATFORM-level
    account on a different product relationship (decisions.md, 2026-08-03) and a super is not any
    one organisation's; neither is invited from this page. If they fell through to the admin
    template, an org_admin editing "the admin invitation" would silently change what a
    platform-level account is told. `org_admin` is NOT in that exclusion: they are listed under
    Admins because an organisation admin belongs to the organisation, even though appointing one
    is a super's act.
    """
    from .. import invitations
    for kind, template_kind in ((invitations.KIND_ADMINS, 'invite_admin'),
                                (invitations.KIND_REVIEWERS, 'invite_reviewer')):
        if role in invitations.KIND_ROLES.get(kind, ()):
            return template_kind
    return None


def _invite_render(kind, context, must_contain=()):
    """The stored wording for an invitation kind → `(subject, body)`, or None to use the built-in.

    ⚠ **IT NEVER ASKS WHETHER THE TEMPLATE IS SWITCHED ON**, and that is the whole difference from
    `_reviewer_render`. For a reviewer email, `off` must mean STOP — they are live notifications and
    a switch that does not stop them is a lie the screen tells. An INVITATION is not a notification:
    switching it off would mean "Send invite" creates the account, issues the password and tells
    nobody, with nothing to report the silence. So the row supplies WORDING only. The console shows
    no toggle for these two kinds; this function is the reason that is safe.

    ⚠ **A RENDER FAILURE FALLS BACK, IT NEVER BLOCKS.** A template edited into an unrenderable state
    must not take invitations down with it — the built-in body below is always there.
    """
    try:
        from .. import partner_comms
        from ..models import PartnerEmailTemplate as _T
        tpl = _T.objects.filter(kind=kind).first()
        if tpl is None:
            return None
        subject, text_body, _html = partner_comms.render(kind, tpl, dict(context))
        # ⚠ SEND-TIME BACKSTOP, and it is not redundant with the save guard. The save guard refuses
        # a body missing a required token, which covers every edit made through the console. This
        # covers a row that got there any other way — a data fix, a restore, a future importer —
        # and it checks the RENDERED OUTPUT rather than the template, because an unresolvable token
        # does not raise: it simply leaves nothing behind, and the letter goes out looking fine
        # while containing no way to sign in. Fall back to the built-in body instead.
        for needle in must_contain:
            if needle and needle not in text_body:
                logger.warning('Invitation template %s rendered without required content; '
                               'using the built-in body', kind)
                return None
        return subject, text_body
    except Exception:
        logger.warning('Invitation template render failed for %s; using the built-in body',
                       kind, exc_info=True)
        return None


def _welcome_access_block(to_email, temp_password, google):
    """The sign-in paragraph — OURS, whatever the surrounding letter says.

    Three shapes that prose cannot express and an editor must not be able to reword: a fresh account
    gets a password, a Google address gets sign-in-with-Google and no password at all, an
    already-registered address is told to sign in as they always do. A reworded password
    instruction is a person locked out.
    """
    if google:
        return (f'Just click "Sign in with Google" and use this email address ({to_email}) — '
                f'there is no password to set up. Your access is waiting for you.')
    if temp_password:
        return (f'Your temporary password (valid for 7 days) is:\n\n'
                f'    {temp_password}\n\n'
                f"You'll be asked to choose your own password the first time you use it.\n\n"
                f'If it expires before you sign in, or you lose it, you can set a new one yourself '
                f'at any time with "Forgot password" on the sign-in page — or ask whoever added '
                f'you to re-send your details.')
    return ('You already have a HalaTuju account, so simply sign in the way you normally do '
            '— with Google, or with your existing password. Your new access is waiting for you.')


#: What a REVIEWER is told after the sign-in block. Owner, 2026-08-04: the one-paragraph letter was
#: too brief for somebody being handed unfamiliar work. It says what reviewing actually involves,
#: where the guidance lives, and — the part volunteers most need permission for — that handing a
#: case back is ordinary.
_REVIEWER_WELCOME_BODY = (
    'Once you are in, you will see the applicants assigned to you. For each one you read their '
    'application and the documents they have uploaded, meet them for a short interview, and record '
    'what you find. The system proposes interview times and emails the student, so you are not '
    'chasing anybody.\n\n'
    'There is a guide and a set of frequently asked questions in the dashboard, under Guide and '
    'FAQ. They cover what to look for, how to record a verdict, and what happens after you do.\n\n'
    'If a case is not one you can take — you know the family, or the timing does not work — just '
    'reply and we will reassign it. That is a normal thing to do.'
)

#: The same for an ADMIN. Deliberately shorter: an admin's work is not one repeated task, so the
#: honest thing is to say what the console holds and that their role decides what they may change.
_ADMIN_WELCOME_BODY = (
    'The console is where {org}’s bursary work happens: applications and where each one has '
    'got to, the students being supported, and the people who help run it. What you can see and '
    'change depends on your role, so some areas may be read-only for you.\n\n'
    'There is a guide and a set of frequently asked questions in the dashboard, under Guide and '
    'FAQ.'
)


def build_partner_welcome_email(to_email, name, role, temp_password=None, google=False):
    """The wording of the welcome email → ``(subject, body)``.

    Split out of the sender so the console's read-only system-email list renders THIS text rather
    than a second copy of it. A preview that can drift from the mail is worse than no preview —
    the whole point of showing these is that an org_admin knows what actually goes out.

    ⚠ **THREE NAMES, THREE LEVELS, AND THEY ARE NOT INTERCHANGEABLE** (owner, 2026-08-04):
    **HalaTuju** is the PLATFORM (the software they sign in to), **BrightPath** is the
    ORGANISATION they are joining, and the **BrightPath Bursary** is the PROGRAMME the work is
    about. This letter previously said "added to HalaTuju", which named the software instead of the
    body they now belong to. Take the org from `branding.org_short_name` and the programme from
    `programme_name` — never a literal.
    """
    who = name or 'there'
    role_label = _PARTNER_ROLE_LABELS.get(role, 'a team member')
    frontend = _P.frontend_url
    link = f'{frontend}/admin/login'
    org = _P.org_short_name
    # ⚠ ONE home for the access paragraph, shared with the editable template's `{access}` block —
    # so the wording an organisation cannot edit is also the wording the built-in body uses, and
    # the two can never say different things about how to sign in.
    access = _welcome_access_block(to_email, temp_password, google)

    # The organisation's own wording, if they have edited it. `{access}` is injected whole.
    # A role this page never invites (`partner`, `super`) reads no stored template at all — see
    # `_invite_kind_for_role`.
    template_kind = _invite_kind_for_role(role)
    stored = _invite_render(template_kind, {
        'name': who, 'role_label': role_label, 'login_link': link, 'access': access,
        'org_name': org, 'programme_name': _P.programme_name('en'),
        'team_signoff': _P.team_signoff('en'),
    }, must_contain=(access, link)) if template_kind else None
    if stored:
        return stored

    # The built-in body varies by the SAME kind that chooses the template, so the fallback a person
    # receives is the one written for their audience — not a generic letter that happens to be
    # shorter. `partner`/`super` (no kind) keep the plain paragraph: they are platform-level, and
    # neither the reviewer's workflow nor the admin's console description is true of them.
    detail = {
        'invite_reviewer': _REVIEWER_WELCOME_BODY,
        'invite_admin': _ADMIN_WELCOME_BODY.replace('{org}', org),
    }.get(template_kind, '')
    body = (
        f'Dear {who},\n\n'
        f'You have been added to {org} as {role_label}.\n\n'
        f'Sign in here:\n{link}\n\n'
        f'{access}\n\n'
        + (f'{detail}\n\n' if detail else '')
        + f'Any trouble at all, just reply to this email.\n\n'
        f'Warm regards,\n{_P.team_signoff("en")}'
    )
    return f'Your access to {org}', body


def send_partner_welcome_email(to_email, name, role, temp_password=None, google=False):
    """Onboard a new partner admin / reviewer. English-only (internal staff), like every other
    admin-facing email here.

    Replaces the Supabase "Invite user" email (2026-07-12). That one carried a magic link that
    EXPIRED IN 24 HOURS and, once expired, could not be re-sent by any route — an invitee who
    missed the window was stuck. This email carries no token: the account already exists when it is
    sent, so re-sending is always safe. The temp password itself now expires after 7 days (owner
    2026-07-14), but that is never a dead-end — Forgot-password (self-serve, any time) or a Resend
    re-issues it. The Google / already-registered variants get no password at all.

    ``temp_password`` is None when the person already had a HalaTuju account (they sign in with
    the credentials they already have). It is the ONLY copy of that password — it is not stored,
    logged, or returned to the caller — so a send failure must be surfaced, not swallowed; the
    bool return is what the view reports as ``emailed``.
    """
    if not to_email:
        return False
    subject, body = build_partner_welcome_email(to_email, name, role, temp_password, google)
    try:
        EmailMessage(
            subject=subject,
            body=body,
            from_email=_P.email_from,
            to=[to_email],
            reply_to=[_P.email_support],
        ).send()
        return True
    except Exception:
        logger.warning('Failed to send partner welcome email to %s', to_email, exc_info=True)
        return False


def send_qc_returned_email(to_email, reviewer_name, *, ref='', applicant_name='', qc_comments=''):
    """QC (2026-07): notify a reviewer that quality control has RETURNED their case for revision,
    carrying the QC's comments (what was missing / the gaps). English-only (internal staff), from
    the monitored interview@ alias. Best-effort — a mail hiccup never breaks the QC action."""
    outcome = _reviewer_render('qc_returned', to_email, {
        'reviewer_name': reviewer_name, 'ref': ref, 'applicant_name': applicant_name,
        'qc_comments': qc_comments,
    })
    if outcome is not _REVIEWER_LEGACY:
        return outcome is _REVIEWER_SENT
    reviewer = reviewer_name or 'there'
    details = [f'Reference: {ref or "—"}', f'Applicant: {applicant_name or "—"}']
    body = (
        f'Dear {reviewer},\n\n'
        f'Quality control has returned one of your cases for revision.\n\n'
        + '\n'.join(details) + '\n\n'
        f'What to address:\n{qc_comments}\n\n'
        f'Please review the points above, update your findings/verdict, and resubmit. Everything '
        f'you need is in your reviewer dashboard:\n\n'
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    return _send_plain(to_email, _reviewer_subject('Case returned by QC — action needed', ref), body)


def send_qc_rejected_email(to_email, reviewer_name, *, ref='', applicant_name='', qc_comments=''):
    """QC (2026-07): notify a reviewer that quality control has REJECTED one of their cases outright
    (not returned for revision — the case is closed). Carries the QC's reason. English-only (internal
    staff), from the monitored interview@ alias. Best-effort — a mail hiccup never breaks the action."""
    outcome = _reviewer_render('qc_rejected', to_email, {
        'reviewer_name': reviewer_name, 'ref': ref, 'applicant_name': applicant_name,
        'qc_comments': qc_comments,
    })
    if outcome is not _REVIEWER_LEGACY:
        return outcome is _REVIEWER_SENT
    reviewer = reviewer_name or 'there'
    details = [f'Reference: {ref or "—"}', f'Applicant: {applicant_name or "—"}']
    body = (
        f'Dear {reviewer},\n\n'
        f'After quality control review, one of your cases has been rejected. No further action is '
        f'needed from you — this note is for your records.\n\n'
        + '\n'.join(details) + '\n\n'
        f'QC reason:\n{qc_comments}\n\n'
        f'You can see the case in your reviewer dashboard:\n\n'
        f'{_reviewer_dashboard_cta()}\n\n'
        f'{_REVIEWER_SIGNOFF}'
    )
    return _send_plain(to_email, _reviewer_subject('Case rejected by QC', ref), body)
