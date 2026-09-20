"""The email templates an officer authors: partner (source) emails and sponsor emails.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
from django.db.models import Count, Max
from rest_framework import status
from rest_framework.response import Response
from ..models import Sponsor
from .. import sponsor_comms as sponsor_comms_mod

from .base import _AdminBase

from .sources import _SourcesBase, _source_application_counts


def _partner_email_dict(tpl, last=None):
    """One partner-email template as the admin screen sees it: the wording, its switch, the
    placeholders it may use, and when it last went out."""
    from .. import partner_comms
    from ..models import PartnerEmailTemplate
    return {
        'kind': tpl.kind,
        'enabled': bool(tpl.enabled),
        # Who receives it. Every row on this screen but one goes to the partner ORGANISATION, and
        # the exception (request #3) goes to the STUDENT — a difference the screen must state
        # rather than leave a reader to infer from the wording. It also explains why the platform
        # partner-comms switch does not silence that row.
        'to_student': tpl.kind in PartnerEmailTemplate.STUDENT_KINDS,
        # Request #10: a third audience. Our own volunteers, edited on Organisation → Reviewers.
        # Like `to_student` this comes from the SERVER, never from the front end's kind list, so
        # the "who gets this" label cannot drift from the rule that decides who actually does.
        'to_reviewer': tpl.kind in PartnerEmailTemplate.REVIEWER_KINDS,
        'subject': tpl.subject,
        'body': tpl.body,
        'placeholders': sorted(partner_comms.PLACEHOLDERS.get(tpl.kind, set())),
        'updated_by_email': tpl.updated_by_email or '',
        'updated_at': tpl.updated_at.isoformat() if tpl.updated_at else None,
        'last_sent_at': last['sent_at'].isoformat() if last and last.get('sent_at') else None,
        'last_sent_orgs': (last or {}).get('orgs', 0),
    }


class AdminPartnerEmailsView(_SourcesBase):
    """GET .../admin/scholarship/partner-emails/ — the five partner-email templates plus who can
    currently receive one.

    `qualifying` is the honest answer to "if I switch this on, who hears about it?" — the screen
    states it rather than looking as though it works. Today, on prod, it is EMPTY: nine referral
    partners, none with a contact email on file.
    """
    def get(self, request):
        admin, err = self._sources_admin(request)
        if err:
            return err
        from django.conf import settings as _settings
        from apps.courses.models import PartnerOrganisation
        from .. import partner_comms
        from ..models import PartnerEmailLog, PartnerEmailTemplate

        by_kind = {t.kind: t for t in PartnerEmailTemplate.objects.all()}
        last = {}
        for row in (PartnerEmailLog.objects.filter(ok=True)
                    .values('kind').annotate(sent_at=Max('sent_at'), orgs=Count('organisation',
                                                                                distinct=True))):
            last[row['kind']] = row
        # ⚠ `?family=reviewer` splits this list in two, and the Sources screen must pass NOTHING
        # (the default) so the five reviewer emails stay OFF it. A reviewer is not a referral
        # partner, and a template about our own volunteers sitting under "Partner emails" would be
        # filed where nobody looking for it would look. One endpoint, two audiences, one filter —
        # a second endpoint would be a second copy of the fence.
        # THREE families now, and the default is "everything that is not one of the others" —
        # so a NEW family cannot leak onto the Sources screen by forgetting to exclude it. That is
        # exactly what happened when the invitation kinds were added: the reviewer filter was a
        # two-way split, and the two new kinds silently landed in the partner list.
        family = (request.GET.get('family') or '').strip()
        families = {
            'reviewer': PartnerEmailTemplate.REVIEWER_KINDS,
            'invite': PartnerEmailTemplate.INVITE_KINDS,
        }
        named = set().union(*families.values())
        wanted = families.get(family)
        templates = [
            _partner_email_dict(by_kind[k], last.get(k))
            for k in partner_comms.KINDS
            if k in by_kind and (k in wanted if wanted is not None else k not in named)
        ]
        qualifying = {o.id for o in partner_comms.qualifying_partners()}
        counts = _source_application_counts()
        # Every organisation, each with WHY it does or doesn't qualify — the house org is excluded
        # by rule (it is us), the rest simply need an address.
        # org-fence: GLOBAL by design — this mirrors the Sources registry, which lists every org.
        orgs = [
            {
                'id': o.id, 'code': o.code, 'name': o.name,
                'students': counts.get(o.id, 0),
                'has_email': bool((o.contact_email or '').strip()),
                'is_house_org': o.code == partner_comms.HOUSE_ORG_CODE,
                'qualifies': o.id in qualifying,
            }
            for o in PartnerOrganisation.objects.order_by('name')
        ]
        return Response({
            'templates': templates,
            'organisations': orgs,
            'qualifying_count': len(qualifying),
            'partner_count': sum(1 for o in orgs if not o['is_house_org']),
            'comms_enabled': bool(getattr(_settings, 'PARTNER_COMMS_ENABLED', False)),
        })


class AdminPartnerEmailDetailView(_SourcesBase):
    """PATCH .../admin/scholarship/partner-emails/<kind>/ {enabled?, subject?, body?} — switch one
    partner email on/off, or edit its wording.

    Two refusals, both deliberate: an unknown `{placeholder}` would render literally into a
    partner's inbox, and the co-owned voice the owner specified (2026-07-26) is enforced rather
    than left to a reviewer's memory — a partner organisation runs this bursary alongside us, so
    conduit phrasing and "your students" are refused.
    """
    def patch(self, request, kind):
        admin, err = self._sources_admin(request)
        if err:
            return err
        from .. import partner_comms
        from ..models import PartnerEmailTemplate

        tpl = PartnerEmailTemplate.objects.filter(kind=kind).first()
        if tpl is None:
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)

        subject = tpl.subject if 'subject' not in request.data else (
            (request.data.get('subject') or '').strip()[:255])
        body = tpl.body if 'body' not in request.data else (request.data.get('body') or '').strip()
        if 'subject' in request.data or 'body' in request.data:
            if not subject or not body:
                return Response({'error': 'subject_and_body_required',
                                 'code': 'subject_and_body_required'},
                                status=status.HTTP_400_BAD_REQUEST)
            unknown = partner_comms.unknown_placeholders(kind, subject, body)
            if unknown:
                return Response({'error': 'unknown_placeholder', 'code': 'unknown_placeholder',
                                 'placeholders': list(unknown)},
                                status=status.HTTP_400_BAD_REQUEST)
            banned = partner_comms.banned_phrases(subject, body)
            if banned:
                return Response({'error': 'conduit_phrasing', 'code': 'conduit_phrasing',
                                 'phrases': list(banned)},
                                status=status.HTTP_400_BAD_REQUEST)
            # ⚠ THE OPPOSITE-DIRECTION CHECK, and nothing did it before. The guard above refuses a
            # token the kind does not SUPPLY; this refuses a body that has dropped one it REQUIRES.
            # Without it a staff invitation could be saved with `{access}` deleted, and everybody
            # invited afterwards would get a warm letter containing no way to sign in — with
            # nothing to report it, because the send succeeds and the account exists.
            missing = partner_comms.missing_required_placeholders(kind, subject, body)
            if missing:
                return Response({'error': 'missing_required_placeholder',
                                 'code': 'missing_required_placeholder',
                                 'placeholders': list(missing)},
                                status=status.HTTP_400_BAD_REQUEST)

        fields = []
        if 'enabled' in request.data:
            tpl.enabled = bool(request.data.get('enabled'))
            fields.append('enabled')
        if subject != tpl.subject:
            tpl.subject = subject
            fields.append('subject')
        if body != tpl.body:
            tpl.body = body
            fields.append('body')
        if fields:
            tpl.updated_by_email = (getattr(admin, 'email', '') or '')[:254]
            fields += ['updated_by_email', 'updated_at']
            tpl.save(update_fields=fields)
        return Response(_partner_email_dict(tpl))


def _sponsor_email_dict(tpl, last=None):
    """Allowlist view of one sponsor-email template. Explicit fields — never model passthrough."""
    return {
        'kind': tpl.kind,
        'label': tpl.get_kind_display(),
        'enabled': tpl.enabled,
        'subject': tpl.subject,
        'body': tpl.body,
        'placeholders': sorted(sponsor_comms_mod.PLACEHOLDERS.get(tpl.kind, set())),
        'updated_by_email': tpl.updated_by_email or '',
        'updated_at': tpl.updated_at.isoformat() if tpl.updated_at else None,
        'last_sent_at': last['sent_at'].isoformat() if last and last.get('sent_at') else None,
        'last_sent_count': (last or {}).get('sponsors', 0),
    }


class _SponsorEmailsBase(_AdminBase):
    """Gate for the sponsor-email panel.

    The SAME gate as the Sponsors list it lives on (super / org_admin / admin / finance) would be
    wrong: deciding what every donor hears is an editorial power, not a reading one. So this
    mirrors the Sources gate instead — super, org_admin, admin. Finance reads sponsors because
    money is its business; the wording of a welcome email is not.
    """
    def _emails_admin(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not (self.has_role(admin, 'admin') or admin.role == 'org_admin'):
            return None, self._deny_role()
        return admin, None


class AdminSponsorEmailsView(_SponsorEmailsBase):
    """GET .../admin/scholarship/sponsor-emails/ — the nine templates + the honest state of play.

    `comms_enabled` is the PLATFORM gate, returned rather than assumed: the panel must be able to
    say "these switches do nothing yet" instead of implying a switched-on template will send.
    That is the lesson from the bursary panel, which rendered for everyone because its gate lived
    only in a comment (L380).
    """
    def get(self, request):
        admin, err = self._emails_admin(request)
        if err:
            return err
        from ..models import SponsorEmailLog, SponsorEmailTemplate

        by_kind = {t.kind: t for t in SponsorEmailTemplate.objects.all()}
        last = {}
        # org-fence: sponsor comms is platform-level by design — a Sponsor has no organisation
        # (see AdminSponsorListView), and one switch per email serves every sponsor.
        for row in (SponsorEmailLog.objects.filter(ok=True).values('kind')
                    .annotate(sent_at=Max('sent_at'), sponsors=Count('sponsor', distinct=True))):
            last[row['kind']] = row
        templates = [
            _sponsor_email_dict(by_kind[k], last.get(k))
            for k in sponsor_comms_mod.KINDS if k in by_kind
        ]
        return Response({
            'templates': templates,
            'comms_enabled': sponsor_comms_mod.comms_enabled(),
            'seeded': len(templates),
            'expected': len(sponsor_comms_mod.KINDS),
            'sponsor_count': Sponsor.objects.count(),
        })


class AdminSponsorEmailDetailView(_SponsorEmailsBase):
    """PATCH .../admin/scholarship/sponsor-emails/<kind>/ {enabled?, subject?, body?}.

    Two refusals, both deliberate. An unknown `{placeholder}` would render literally into a
    donor's inbox — and, more seriously, the allowlist is a privacy control: no token resolves to
    a student's identity, so a template cannot become a new route around the anonymity the pool
    serializers enforce. The voice guard refuses a tax-relief claim (we hold no s44(6) approval),
    student-ownership phrasing, and urgency copy that would turn account mail into marketing.
    """
    def patch(self, request, kind):
        admin, err = self._emails_admin(request)
        if err:
            return err
        from ..models import SponsorEmailTemplate

        tpl = SponsorEmailTemplate.objects.filter(kind=kind).first()
        if tpl is None:
            return Response({'error': 'not_found', 'code': 'not_found'},
                            status=status.HTTP_404_NOT_FOUND)

        subject = tpl.subject if 'subject' not in request.data else (
            (request.data.get('subject') or '').strip()[:255])
        body = tpl.body if 'body' not in request.data else (request.data.get('body') or '').strip()
        if 'subject' in request.data or 'body' in request.data:
            if not subject or not body:
                return Response({'error': 'subject_and_body_required',
                                 'code': 'subject_and_body_required'},
                                status=status.HTTP_400_BAD_REQUEST)
            unknown = sponsor_comms_mod.unknown_placeholders(kind, subject, body)
            if unknown:
                return Response({'error': 'unknown_placeholder', 'code': 'unknown_placeholder',
                                 'placeholders': list(unknown)},
                                status=status.HTTP_400_BAD_REQUEST)
            banned = sponsor_comms_mod.banned_phrases(subject, body)
            if banned:
                return Response({'error': 'banned_phrasing', 'code': 'banned_phrasing',
                                 'phrases': list(banned)},
                                status=status.HTTP_400_BAD_REQUEST)

        fields = []
        if 'enabled' in request.data:
            tpl.enabled = bool(request.data.get('enabled'))
            fields.append('enabled')
        if subject != tpl.subject:
            tpl.subject = subject
            fields.append('subject')
        if body != tpl.body:
            tpl.body = body
            fields.append('body')
        if fields:
            tpl.updated_by_email = (getattr(admin, 'email', '') or '')[:254]
            fields += ['updated_by_email', 'updated_at']
            tpl.save(update_fields=fields)
        return Response(_sponsor_email_dict(tpl))
