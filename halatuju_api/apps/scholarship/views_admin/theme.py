"""An organisation's theme: the draft tokens, the contrast checks, publish and revert.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
import logging

from rest_framework import status
from rest_framework.response import Response

from .base import _AdminBase


# ⚠ THE PACKAGE'S name, spelled out — never `__name__`. A submodule logger reads
# `apps.scholarship.views_admin.<module>` and drops every audit line it carries out
# of the Cloud Logging scrape metric. Guarded by `AuditLoggerNameTest` (H11).
logger = logging.getLogger('apps.scholarship.views_admin')


def _checks_both_modes(tokens):
    """Every contrast result for a token set, in both modes, each row carrying its own `mode`.

    ONE helper rather than a call per site: the payload builder and the refusal path both report
    these numbers, and two independently-written list comprehensions is how they start disagreeing
    about which modes were measured.
    """
    from apps.courses import contrast, theme_tokens
    return [dict(r._asdict(), mode=mode)
            for mode in theme_tokens.MODES
            for r in contrast.check_tokens(tokens, mode)]


class AdminOrganisationThemeView(_AdminBase):
    """GET/PUT/DELETE `admin/scholarship/organisation/theme/` — an organisation's colour.

    Layer 1 A2. The second tab of the Programme screen, over the storage A1 built. An `org_admin`
    picks ONE colour; the server derives the ten shades, checks a person can read them, and freezes
    the result. What is stored is the approved SET, never the hex — `courses.theme_tokens` carries
    the argument for why that is the load-bearing decision of this arc.

    ⚠ THE CONTRAST GATE REFUSES; IT DOES NOT WARN. A tenant will pick a colour that renders at 4:1
    against white, and a warning is dismissed by the person who chose it while a student is the one
    who cannot read the page. So an unreadable colour is a `400 unreadable` carrying the failing
    pairs, and the screen turns them into sentences. The browser checks too — that is a courtesy,
    never the gate. This is the gate.

    ⚠ THE ORGANISATION IS DERIVED, NEVER SENT. It comes from `admin.owning_organisation`, the same
    field the org fence uses, so this cannot widen access by construction. A super names one with
    `?org=<code>`; more than one tenant and no code is `organisation_required`, never a silent pick
    (the PF-1 rule). A code outside the caller's organisation is **404, never 403** — a 403 would
    confirm the tenant exists.

    ⚠ `tenants()`, NOT `filter(is_active=True)`. `partner_organisations` is dual-role and holds nine
    referral organisations that are not tenants; the queryset that reads like "the organisations" is
    a trap the console has already fallen into once, in July.

    Who may write: `super` and `org_admin` only. A colour is the organisation's identity, held by
    its administrator — a reviewer or a plain admin gets 403.

    ⚠ THIS DOES NOT REFUSE THE PLATFORM ORGANISATION, AND `set_organisation_theme` DOES. That is
    deliberate, not drift. The command is the MECHANICAL path, where a casual backfill would give
    BrightPath a derived row and shift its own colours by a channel against the seeded ramp in
    `globals.css`. This is the DELIBERATE path: the person sees the ten shades and the six checks
    before they commit, and DELETE puts the stylesheet back exactly. A screen that showed its only
    live tenant a permanently disabled control would be a worse answer than either.

    Every write is audited (`AUDIT organisation_theme_set` / `organisation_theme_cleared`).
    """

    ROLES = ('org_admin',)

    def _gate(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not self.has_role(admin, *self.ROLES):
            return None, self._deny_role()
        return admin, None

    def _organisation_for(self, admin, code):
        """The one organisation this request is about, or an error response.

        Mirrors `AdminProgrammeConfigurationView._programme_for` deliberately — same fence, same
        404-not-403, same refusal to pick silently between two.
        """
        from apps.courses.models import PartnerOrganisation
        qs = PartnerOrganisation.objects.filter(is_active=True).tenants()
        if not self.has_role(admin, 'super'):
            org_id = admin.owning_organisation_id
            qs = qs.filter(id=org_id) if org_id else qs.none()
        if code:
            org = qs.filter(code=code).first()
            if org is None:
                return None, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
            return org, None
        orgs = list(qs.order_by('code')[:2])
        if not orgs:
            return None, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        if len(orgs) > 1:
            return None, Response(
                {'error': 'organisation_required', 'code': 'organisation_required',
                 'organisations': [o.code for o in qs.order_by('code')]},
                status=status.HTTP_400_BAD_REQUEST)
        return orgs[0], None

    def _payload(self, org):
        """What the screen needs to tell the two states apart.

        ⚠ `live` AND `draft` ARE SEPARATE KEYS, never one "colour" that means whichever exists.
        The entire point of A3 is that those are different things, and a payload that folds them
        together would invite a screen that cannot say which one a visitor is seeing.
        """
        from apps.courses import contrast, theme_tokens
        from apps.courses import theme_versions

        live = theme_versions.active_for(org)
        draft = theme_versions.draft_for(org)
        previous = theme_versions.previous_for(org)
        live_tokens = theme_tokens.applied_tokens(live.tokens) if live else None
        draft_tokens = theme_tokens.applied_tokens(draft.tokens) if draft else None

        def block(row, tokens):
            if row is None:
                return None
            return {
                'colour': row.source_colour or '',
                # Checks travel with whichever set they describe, so the screen never has to guess
                # which colour a number belongs to.
                # ⚠ BOTH MODES since F7a. A colour is stored once and rendered in light AND dark,
                # so a screen showing only the light numbers would report a colour as fine while
                # the gate that saves it disagrees.
                'checks': _checks_both_modes(tokens) if tokens else [],
            }

        return {
            'organisation': {'code': org.code, 'name': org.name},
            'live': block(live, live_tokens),
            'draft': block(draft, draft_tokens),
            # What Revert would put back. '' means "the platform colours" — a real answer, because
            # reverting the first colour an organisation ever published lands them there.
            'previous_colour': (previous.source_colour if previous else '') or '',
            'can_revert': live is not None,
            'published_at': live.published_at.isoformat() if live and live.published_at else '',
            'published_by': (live.published_by_email if live else '') or '',
            # The LIVE tokens — what a visitor is seeing right now, never the draft.
            'tokens': live_tokens,
        }

    def get(self, request):
        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err
        return Response(self._payload(org))

    def put(self, request):
        """Save the DRAFT. **What visitors see is untouched** — that is the whole sprint."""
        from apps.courses import contrast, theme_tokens
        from apps.courses import theme_versions

        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err

        colour = (request.data.get('colour') or '').strip()
        try:
            tokens = theme_tokens.tokens_from_colour(colour)
        except theme_tokens.ThemeTokenError:
            return Response({'error': 'bad_colour', 'code': 'bad_colour'},
                            status=status.HTTP_400_BAD_REQUEST)

        # ⚠ THE GATE RUNS AT DRAFT TIME, NOT ONLY AT PUBLISH. An unreadable colour should be
        # refused at the moment somebody types it, not saved and refused later — a draft that
        # cannot ever be published is a trap you walk into twice.
        # ⚠ AND IT RUNS IN BOTH MODES since F7a. A2 could honestly gate light alone because dark was
        # unreachable; it is reachable now, and a tenant refused only after somebody flips the
        # switch has been let down by the gate rather than protected by it.
        fails = contrast.failures_all_modes(tokens)
        if fails:
            return Response(
                {'error': 'unreadable', 'code': 'unreadable',
                 'checks': _checks_both_modes(tokens),
                 'failing': [f'{mode}:{r.key}' for mode, r in fails]},
                status=status.HTTP_400_BAD_REQUEST)

        theme_versions.save_draft(org, colour, tokens)
        logger.info('AUDIT organisation_theme_draft_saved org=%s colour=%s by=%s',
                    org.code, colour, admin.email or '')
        return Response(self._payload(org))

    def delete(self, request):
        """Discard the DRAFT. What is live stays live — a draft you throw away costs nobody."""
        from apps.courses import theme_versions

        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err
        if theme_versions.discard_draft(org):
            logger.info('AUDIT organisation_theme_draft_discarded org=%s by=%s',
                        org.code, admin.email or '')
        return Response(self._payload(org))


class AdminOrganisationThemePublishView(AdminOrganisationThemeView):
    """POST `admin/scholarship/organisation/theme/publish/` — the draft becomes what visitors see.

    Inherits the gate, the org fence and the payload from the view above deliberately: three
    endpoints acting on one resource should not each grow their own copy of "which organisation is
    this, and may you touch it".

    An `org_admin` may publish a draft they wrote themselves — the owner's 2026-07-28 ruling for
    sponsor terms, where a same-author check is deliberately absent and a test pins its absence. A
    colour is a smaller decision than a binding document, so the same answer holds.
    """

    def post(self, request):
        from apps.courses import theme_versions

        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err
        try:
            # `allowed=True` asserts the ROLE GATE ABOVE HAS PASSED. The service defaults it False
            # so a shell caller fails closed — mirroring `sponsor_terms.publish`.
            theme_versions.publish(org, by_email=admin.email or '', allowed=True)
        except theme_versions.ThemeVersionError as exc:
            return Response({'error': exc.code, 'code': exc.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self._payload(org))


class AdminOrganisationThemeRevertView(AdminOrganisationThemeView):
    """POST `admin/scholarship/organisation/theme/revert/` — put back the colour that was live before.

    ⚠ REVERTING THE FIRST COLOUR EVER PUBLISHED LEAVES THE ORGANISATION ON THE PLATFORM STYLESHEET,
    and that is a correct outcome rather than an error: it is genuinely what they had before, and it
    is how a tenant gets all the way back to the default. The payload says so with an empty
    `live`; the screen renders it as "using the default colours".
    """

    def post(self, request):
        from apps.courses import theme_versions

        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err
        try:
            theme_versions.revert(org, by_email=admin.email or '', allowed=True)
        except theme_versions.ThemeVersionError as exc:
            return Response({'error': exc.code, 'code': exc.code},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self._payload(org))
