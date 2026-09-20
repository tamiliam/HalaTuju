"""Sponsor and source invitation bodies, and the sponsor invitation send.

Moved here VERBATIM from `emails.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.core.mail import EmailMessage
from .reviewer_mail import _invite_render
from .shared import _P, _PROG_EN, logger


def build_sponsor_invitation_email(*, org_name='', note='', code='', invited_by=''):
    """The wording of an ADMIN-EXTENDED sponsor invitation → ``(subject, body)``.

    ⚠ **DISTINCT FROM `send_sponsor_referral_invite`, WHICH IS SPONSOR-TO-SPONSOR.** That one is a
    peer saying "come and join me" and is sent from the sponsor's own account page; this one is the
    organisation itself asking. The owner keeps them apart deliberately: the peer route is not shown
    on the admin Invitations page at all.

    ⚠ **IT CREATES NOTHING, AND THE WORDING MUST NOT IMPLY OTHERWISE.** The link goes to the
    ordinary public registration, where they give consent, sign the terms and are then vetted —
    exactly as a sponsor who arrived by any other route. An invitation is a prompt, never a way
    around any of that (owner's constraint: "invite, but nothing is skipped").
    """
    who = org_name or _PROG_EN
    link = f'{_P.frontend_url}/sponsor?ref={code}' if code else f'{_P.frontend_url}/sponsor'
    note_block = f'\nThey added a note for you:\n  "{note.strip()}"\n' if (note or '').strip() else ''

    stored = _invite_render('invite_sponsor', {
        'name': '', 'org_name': who, 'invited_by': invited_by or who, 'link': link,
        'note': (note or '').strip(), 'team_signoff': _P.team_signoff('en'),
    }, must_contain=(link,))
    if stored:
        return stored

    body = (
        f'Hello,\n\n'
        f'{invited_by or who} has invited you to become a donor of {who}.\n'
        f'{note_block}\n'
        f'Every year, students finish school with the results to go further and no way to pay for '
        f'it. A place is offered, the family works out what it would cost, and the place goes '
        f'unclaimed. Closing that gap is what {who} is for.\n\n'
        f'A donor gives to the {_PROG_EN}, and that gift puts a student through their studies — '
        f'the fees, and the ordinary costs of living away from home that quietly decide whether '
        f'somebody can stay. You can see the students waiting for support and tell us who you '
        f'would like your gift to help; we follow your choice wherever we can, and the final '
        f'decision on each award rests with the programme.\n\n'
        f'You can read how it works, and register, here:\n{link}\n\n'
        f'Registering costs nothing and commits you to nothing. You will be asked to agree to our '
        f'terms and confirm a few details, and we get to know you a little before anything goes '
        f'ahead — the same for everybody, however they reach us.\n\n'
        f'Thanks,\n{_P.team_signoff("en")}'
    )
    return f'An invitation to become a donor of {who}', body


def build_source_invitation_email(*, org_name='', contact_person='', login_link='', access=''):
    """The wording of a SOURCE PARTNER's invitation to the console → ``(subject, body)``.

    ⚠ **NOTHING SENDS THIS YET, AND THAT IS THE POINT OF IT EXISTING.** No Source Partner has a
    login and the Invitations page offers no way to invite one; the console is the next piece of
    work. The owner asked for the wording now so it is settled before the screen is built
    (2026-08-04). It is written for the console it will announce — *sign in and follow the students
    your organisation referred* — which is the whole reason it must not go out before that console
    does. `docs/decisions.md` records the standing rule: nothing may move out of an email into a
    console nobody can reach.

    A builder rather than seed-only prose so the eventual sender inherits a fallback body the way
    every other invitation has one, and so a test can assert the seed matches it word for word.

    ⚠ **A SOURCE PARTNER IS AN ORGANISATION-LEVEL BURSARY REFERRER, NEVER A REFERRAL PARTNER.**
    Those are separate relationships and the owner has ruled they stay named apart — do not widen
    this letter to cover the platform `partner` role.
    """
    org = org_name or 'your organisation'
    who = contact_person or 'there'
    stored = _invite_render('invite_source', {
        'org_name': org, 'contact_person': who, 'login_link': login_link, 'access': access,
        'team_signoff': _P.team_signoff('en'),
    }, must_contain=(access, login_link))
    if stored:
        return stored

    body = (
        f'Dear {who},\n\n'
        f'{org} has been referring students to the {_PROG_EN}, and until now the only word you '
        f'have had on how they are getting on is the summaries we email across.\n\n'
        f'We would like to give {org} its own access, so your team can look at any time — who has '
        f'applied, who is still finishing their application, and who has been awarded a bursary.\n\n'
        f'Sign in here:\n{login_link}\n\n'
        f'{access}\n\n'
        f'Nothing about how {org} refers students changes, and the summary emails carry on as '
        f'before.\n\n'
        f'Any trouble at all, just reply to this email.\n\n'
        f'Warm regards,\n{_P.team_signoff("en")}'
    )
    return f'Access to the {_PROG_EN} for {org}', body


def send_sponsor_invitation_email(to_email, *, org_name='', note='', code='', invited_by=''):
    """Best-effort send of the above. Returns (ok, error) so the invitation can record BOTH —
    a bounce is usually the whole explanation for an invitation nobody acted on."""
    if not to_email:
        return False, 'no address'
    subject, body = build_sponsor_invitation_email(
        org_name=org_name, note=note, code=code, invited_by=invited_by)
    try:
        # ⚠ Replies go to the SPONSOR alias, not general support — matching the peer-to-peer
        # invitation, which is the other letter a prospective donor might have received. Chosen
        # deliberately, 2026-08-04: a pitch invites a reply, and somebody weighing up whether to
        # give should reach the people who can answer for the programme rather than the queue that
        # helps students with their applications. (`_P.email_support` was inherited here, never
        # decided — the same shape as the interview-alias default that mis-sent request #3's mail.)
        EmailMessage(subject=subject, body=body, from_email=_P.email_from,
                     to=[to_email], reply_to=[_P.sponsor_reply_to]).send()
        return True, ''
    except Exception as e:      # noqa: BLE001
        logger.warning('Failed to send sponsor invitation to %s', to_email, exc_info=True)
        return False, str(e)[:300]
