"""Gift programmes — the admin endpoints, moved verbatim from `views_admin.py` at H11.
The readers they share with the intake-year screens are in `gifts.py`.

Part of the `views_admin` package. Every name below is re-exported from
`views_admin/__init__.py`, so `urls.py` and every importer are unchanged.
"""
import logging
import re

from django.db import transaction
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.response import Response

from ..models import Programme
from .base import _AdminBase
from .gifts import _programme_row, programme_delete_blocker

#: The package's logger name, spelled out — see the note in `requests.py`.
logger = logging.getLogger('apps.scholarship.views_admin')


class _ProgrammeScopedBase(_AdminBase):
    """Shared gate + org fence for the two screens. `org_admin` and `super` only — deciding what a
    programme is and who it asks for is the organisation's own decision, held by its administrator
    (the same rule and the same roles as the Layer 0 configuration screen)."""

    ROLES = ('org_admin',)

    def _gate(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not self.has_role(admin, *self.ROLES):
            return None, self._deny_role()
        return admin, None

    def _programmes_for(self, admin):
        """Every gift this caller may touch. ⚠ INCLUDES INACTIVE ONES, unlike the configuration
        screen's `_programme_for` — you cannot switch a programme on if you cannot see it."""
        from ..models import Programme
        qs = Programme.objects.select_related('organisation')
        if not self.has_role(admin, 'super'):
            org_id = admin.owning_organisation_id
            qs = qs.filter(organisation_id=org_id) if org_id else qs.none()
        return qs

    def _programme_or_404(self, admin, pk):
        p = self._programmes_for(admin).filter(pk=pk).first()
        if p is None:
            return None, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        return p, None


# A URL-safe slug, because this is what an apply link carries (`?p=<code>`), and lower-case only
# so two codes cannot differ by case alone in a place people retype by hand.
CODE_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,49}$')


class AdminProgrammeListView(_ProgrammeScopedBase):
    """GET the organisation's gift programmes · POST create one."""

    def get(self, request):
        admin, err = self._gate(request)
        if err:
            return err
        rows = [_programme_row(p) for p in self._programmes_for(admin).order_by('code')]
        return Response({'programmes': rows})

    def post(self, request):
        admin, err = self._gate(request)
        if err:
            return err
        org = admin.owning_organisation
        if org is None:
            return Response({'error': 'no_org', 'code': 'no_org'}, status=status.HTTP_400_BAD_REQUEST)

        from ..models import Programme, code_is_free
        code = (request.data.get('code') or '').strip().lower()
        name_en = (request.data.get('name_en') or '').strip()
        if not CODE_RE.match(code):
            return Response({'error': 'bad_code', 'code': 'bad_code'}, status=status.HTTP_400_BAD_REQUEST)
        if not name_en:
            return Response({'error': 'name_required', 'code': 'name_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        # `Programme.code` is unique PLATFORM-WIDE, not per organisation, because it is what an
        # apply link carries (`/scholarship/apply?p=<code>`) — PF-1. So the clash a tenant hits may
        # be with another tenant's code, and the message must not say whose.
        # ⚠ `code_is_free` ALSO refuses a RETIRED code. A code some other gift used to answer to
        # still routes students there through `resolve_open_cohort`; handing it to a new gift would
        # send them to the wrong foundation with nothing raising an error.
        if not code_is_free(code):
            return Response({'error': 'code_taken', 'code': 'code_taken'},
                            status=status.HTTP_400_BAD_REQUEST)

        # ⚠ CREATED INACTIVE, ALWAYS, whatever the client sends. An active second programme changes
        # live behaviour the moment it exists: the payment-run picker appears (Sabah S1) and the
        # configuration screen starts asking which programme. Switching it on is a separate,
        # deliberate press once its first intake year is set up.
        p = Programme.objects.create(
            organisation=org, code=code, name_en=name_en,
            name_ms=(request.data.get('name_ms') or '').strip(),
            name_ta=(request.data.get('name_ta') or '').strip(),
            is_active=False,
        )
        logger.info('AUDIT programme_created code=%s org=%s by=%s', p.code, org.id, admin.email or '')
        return Response(_programme_row(p), status=status.HTTP_201_CREATED)


class AdminProgrammeDetailView(_ProgrammeScopedBase):
    """PATCH one gift — its three names, its CODE, and whether it is active.

    ⚠ THE CODE IS EDITABLE NOW, AND THE OLD ONE IS KEPT AS AN ALIAS. It is printed on posters and
    typed into `/scholarship/apply?p=<code>`; an unknown code makes `resolve_open_cohort` answer
    "no open round", so a rename with no alias would tell every student on a printed link that
    applications are closed — silently, with nothing failing. This endpoint is the ONE writer of
    `ProgrammeCodeAlias`.
    """

    def patch(self, request, pk):
        admin, err = self._gate(request)
        if err:
            return err
        p, err = self._programme_or_404(admin, pk)
        if err:
            return err

        changed = []

        if 'code' in request.data:
            from ..models import ProgrammeCodeAlias, code_is_free
            new_code = (request.data.get('code') or '').strip().lower()
            if not CODE_RE.match(new_code):
                return Response({'error': 'bad_code', 'code': 'bad_code'},
                                status=status.HTTP_400_BAD_REQUEST)
            if new_code != p.code:
                # ⚠ The clash may be with ANOTHER tenant's live code OR with any gift's retired
                # one — both still route students — so the message must not say whose.
                if not code_is_free(new_code, exclude_programme=p):
                    return Response({'error': 'code_taken', 'code': 'code_taken'},
                                    status=status.HTTP_400_BAD_REQUEST)
                old_code = p.code
                with transaction.atomic():
                    # Renaming BACK to a code this gift used to answer to: that alias becomes the
                    # live code, so the row must go or the gift would alias itself.
                    ProgrammeCodeAlias.objects.filter(programme=p, code=new_code).delete()
                    ProgrammeCodeAlias.objects.create(
                        programme=p, code=old_code, created_by=admin.email or '')
                    p.code = new_code
                    p.save(update_fields=['code'])
                logger.info('AUDIT programme_code_changed old=%s new=%s org=%s by=%s',
                            old_code, new_code, p.organisation_id, admin.email or '')

        for f in ('name_en', 'name_ms', 'name_ta'):
            if f in request.data:
                v = (request.data.get(f) or '').strip()
                if f == 'name_en' and not v:
                    return Response({'error': 'name_required', 'code': 'name_required'},
                                    status=status.HTTP_400_BAD_REQUEST)
                setattr(p, f, v); changed.append(f)

        if 'apply_copy' in request.data:
            # ⚠ VALIDATED SERVER-SIDE, NOT ONLY ON THE FORM. This is free text that renders on a
            # PUBLIC page, and the `parents_occupation` overflow (2026-06-07) is the standing
            # lesson: a form `maxLength` is a courtesy, the serializer is the guarantee.
            from .. import apply_copy as ac
            try:
                p.apply_copy = ac.normalise(request.data.get('apply_copy'))
            except ac.ApplyCopyError as e:
                return Response({'error': e.code, 'code': e.code, 'field': e.field},
                                status=status.HTTP_400_BAD_REQUEST)
            changed.append('apply_copy')

        if 'is_active' in request.data:
            want = bool(request.data.get('is_active'))
            # ⚠ SWITCHING OFF A GIFT THAT IS TAKING APPLICATIONS WOULD STRAND THEM MID-FLIGHT: the
            # apply link would stop resolving (`resolve_open_cohort` filters `programme__is_active`)
            # while a half-finished application still points at it. Close the year first.
            if not want:
                from ..models import ScholarshipCohort
                if ScholarshipCohort.objects.filter(programme=p, is_open=True, is_active=True).exists():
                    return Response({'error': 'has_open_year', 'code': 'has_open_year'},
                                    status=status.HTTP_400_BAD_REQUEST)
            p.is_active = want; changed.append('is_active')

        if changed:
            p.save(update_fields=changed)
            logger.info('AUDIT programme_updated code=%s fields=%s by=%s',
                        p.code, ','.join(changed), admin.email or '')
        return Response(_programme_row(p))

    def delete(self, request, pk):
        """DELETE one gift — only ever a gift that never became anything.

        ⚠⚠ THE RULE IS ALREADY WRITTEN IN THE MODEL, AND THIS ENDPOINT ONLY SURFACES IT. Every
        relation that means a gift has BECOME something is `on_delete=PROTECT`: its applications,
        the benefactors accepted into it, the money recorded against it, and the payment runs that
        paid from it. The database would refuse regardless; what this adds is a refusal that SAYS
        WHICH of those is holding it, at the moment somebody asks, instead of a 500 from a
        constraint.

        So the honest line is: **a gift that has ever taken a student or a ringgit cannot be
        deleted.** What can be deleted is the one you created by mistake a minute ago.

        ⚠⚠ AND ITS EMPTY INTAKE YEARS GO WITH IT — the owner's ruling, 2026-09-07: *"I don't [want]
        the ability to delete a gift programme that has students, and not merely intake years."* A
        year on its own is the rules somebody typed a minute ago; students are what make a gift
        undeletable. A year is `PROTECT` from the gift, so this handler clears the years EXPLICITLY,
        in the same transaction, rather than the MODEL being relaxed to `CASCADE`. Both halves of
        that matter: `PROTECT` stays the backstop for every other path that might ever delete a
        programme, and a year that is NOT empty is still refused — `programme_delete_blocker` has
        already established that no application exists under this gift, by cohort as well as by
        column, so the years removed here can only be rules nobody has used.

        This is what closes TD-232: a gift created by mistake and given one stray year used to be
        stuck for ever, and so was the year (there is still no way to delete a year on its own).

        ⚠ WHAT ELSE GOES WITH IT, deliberately: `ProgrammeApplicationItem` is CASCADE — those rows
        are the gift's own configuration, meaningless without it. And `Invitation`,
        `PartnerOrganisation.programme` and `PartnerAdmin.programme` are SET_NULL, which is exactly
        right: those are NARROWINGS, and a narrowing whose gift is gone falls back to "every gift"
        (the S-ASSIGN rule — NULL means every gift). Nobody loses an invitation or a reviewer.

        ⚠ THE TYPED CONFIRMATION IS SERVER-SIDE, not a client courtesy. `confirm` must equal the
        gift's own code. A destructive verb that any client can fire with an empty body is one
        mis-wired button away from deleting somebody's gift, and the browser dialog is not the
        guard — it is the explanation of the guard.
        """
        admin, err = self._gate(request)
        if err:
            return err
        p, err = self._programme_or_404(admin, pk)
        if err:
            return err

        # ⚠ THE PHRASE CARRIES THE VERB — `delete <code>`, not the bare code (owner, 2026-09-07).
        # The code is printed on the card AND in the dialog's own label, so typing it alone is
        # closer to copying what is already on screen than to stating an intention. "delete test2"
        # cannot be produced by reflex, and it says what it does.
        want = f'delete {p.code}'.lower()
        if ' '.join((request.data.get('confirm') or '').split()).lower() != want:
            return Response({'error': 'confirm_mismatch', 'code': 'confirm_mismatch'},
                            status=status.HTTP_400_BAD_REQUEST)

        # ⚠ THE SAME FUNCTION THE LIST ROW READS, so the disabled button and this refusal can never
        # disagree. Two copies of "what holds a gift" would drift, and the drift shows up as a
        # button that looked safe and a refusal after the phrase was typed out in full.
        blocked_by, count = programme_delete_blocker(p)
        if blocked_by:
            return Response({'error': blocked_by, 'code': blocked_by, 'count': count},
                            status=status.HTTP_400_BAD_REQUEST)

        from ..models import ScholarshipCohort
        code, name = p.code, p.name_en
        try:
            # ⚠ ONE TRANSACTION, YEARS FIRST. If the gift's delete were to fail after the years had
            # gone, an untouched gift would be left with its rules missing — which is worse than
            # either outcome on its own. `atomic` is what makes "the years go with it" true rather
            # than "the years go, and then we try".
            with transaction.atomic():
                # org-fence: `p` was reached through `_programme_or_404`, so these are this
                # organisation's own years; the blocker above proved none of them holds a student.
                years = ScholarshipCohort.objects.filter(programme=p)
                year_count = years.count()
                years.delete()
                p.delete()
        except ProtectedError:
            # The backstop, and it should be unreachable: a relation added later without a check
            # above lands here rather than as a 500. Deliberately generic — this arm knows only
            # that something protects it, which is exactly why the named checks exist.
            return Response({'error': 'in_use', 'code': 'in_use'},
                            status=status.HTTP_400_BAD_REQUEST)

        # The year count is ON the audit line because it is the part a person cannot see afterwards:
        # the gift's own row is gone either way, but "and it took three years with it" is the fact
        # somebody reading this log later would otherwise have to guess at.
        logger.info('AUDIT programme_deleted code=%s name=%s years=%s by=%s',
                    code, name, year_count, admin.email or '')
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminApplyCopyDraftView(_ProgrammeScopedBase):
    """POST a target locale -> a DRAFTED Malay/Tamil block, from this gift's own English.

    ⚠⚠ IT RETURNS THE DRAFT AND SAVES NOTHING. The browser fills the boxes with it; the person
    reads it and presses Save, which is the existing PATCH and the existing validation. Making
    this write would put a machine's wording on a public page with no human between — the rule
    `decisions.md` settled for the document engines (*the model extracts, a person decides*), and
    the reason `apply_copy` exists at all is that an organisation owns what its gift advertises.

    ⚠ IT IS BILLABLE. One Gemini call per press, metered through `usage_context` like every other
    seam, so a tenant's drafting shows up on their own usage row rather than the platform's.
    """

    def post(self, request, pk):
        admin, err = self._gate(request)
        if err:
            return err
        p, err = self._programme_or_404(admin, pk)
        if err:
            return err

        from .. import apply_copy_draft as acd, usage
        locale = (request.data.get('locale') or '').strip().lower()
        try:
            with usage.usage_context(source='apply_copy_draft',
                                     organisation_id=p.organisation_id):
                block = acd.draft(p, locale)
        except acd.DraftError as e:
            return Response({'error': e.code, 'code': e.code},
                            status=status.HTTP_400_BAD_REQUEST)

        logger.info('AUDIT apply_copy_drafted code=%s locale=%s by=%s',
                    p.code, locale, admin.email or '')
        return Response({'locale': locale, 'block': block})
