"""Give every staff member who predates the `Invitation` table the invitation they were sent.

⚠ **THE WRITE PATH EXISTS ALREADY — this is the other half, not the whole change.** New invitations
are recorded by `_record_invitation` in `apps/courses/views_admin.py`, called from `AdminInviteView`
(both branches) and `AdminResendView`; acceptance is closed by `invitations.accept_for_admin` off
`_touch_seen`'s first-arrival rowcount. Naming those here is deliberate: a backfill with no matching
write path is a bug with a delay on it — migration `0123` gave every existing sponsor a membership
and nothing kept doing it, so the next person to register belonged to nothing, three days later,
after everyone had moved on.

What it infers, and what it refuses to invent:

- `created_at` becomes the invitation date. It is the only date we have, and it is exact — the row
  was created by the invite.
- `credential_issued` is inferred from the address: a Google address is never issued a password
  (`is_google_email`). ⚠ It cannot distinguish the already-registered case, which also got none, so
  a handful of historic rows may read "expired" where "no reply" is truer. Stated rather than
  papered over; it self-corrects on the next Resend, which records what actually happened.
- **`accepted_at` comes from `first_seen_at`** — the sign-in signal, backfilled separately from
  Supabase. Where that is NULL the invitation stays OPEN, which is the honest answer: we do not
  know that they came.
- Platform-level **Referral Partners** (`role='partner'`) are SKIPPED. They belong to the HalaTuju
  course selector, not to any organisation's staff, and they never appear on the Invitations page.
  Source Partners are a different relationship entirely — see docs/decisions.md, 2026-08-03.

Idempotent: an admin who already has an invitation is left alone.

    python manage.py backfill_invitations
    python manage.py backfill_invitations --apply
"""
from django.core.management.base import BaseCommand

from apps.courses.models import PartnerAdmin
from apps.courses.views_admin import is_google_email
from apps.scholarship import invitations
from apps.scholarship.models import Invitation


class Command(BaseCommand):
    help = 'Create one Invitation per pre-existing staff member (one-off).'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **o):
        # The org staff table's own membership rule, so the backfill covers exactly the people the
        # page will show — no more (super, Referral Partners) and no fewer.
        staff_roles = ('reviewer', 'admin', 'qc', 'org_admin', 'finance')
        rows = (PartnerAdmin.objects.filter(role__in=staff_roles, is_super_admin=False)
                .exclude(invitations__isnull=False).order_by('id'))

        made = accepted = still_open = 0
        for a in rows:
            issued = not is_google_email(a.email)
            state = 'accepted' if a.first_seen_at else 'still open'
            if a.first_seen_at:
                accepted += 1
            else:
                still_open += 1
            made += 1
            self.stdout.write(f'  {a.email:38} {a.role:10} '
                              f'{"password" if issued else "google/existing":16} {state}')
            if o['apply']:
                inv = invitations.create_or_refresh(
                    audience='staff', email=a.email, name=a.name, role=a.role,
                    organisation=a.owning_organisation, partner_admin=a,
                    credential_issued=issued, now=a.created_at)
                # The send is historic and its outcome is unknowable — record that one went, with
                # no claim about whether it arrived. `last_send_ok` stays NULL, which the screen
                # must render as "not recorded" and never as a failure.
                Invitation.objects.filter(pk=inv.pk).update(
                    created_at=a.created_at, last_sent_at=a.created_at, send_count=1,
                    accepted_at=a.first_seen_at)

        skipped = PartnerAdmin.objects.filter(role='partner').count()
        self.stdout.write('')
        self.stdout.write(f'{made} to create · {accepted} already accepted (they have signed in) · '
                          f'{still_open} still open · {skipped} Referral Partners skipped')
        if not o['apply']:
            self.stdout.write('Report only — re-run with --apply to write.')
