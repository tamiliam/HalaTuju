"""Org and programme configuration — the layered settings an org admin edits.

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
import logging

from rest_framework import status
from rest_framework.response import Response
from ..models import Programme, ScholarshipApplication

from .base import _AdminBase


# ⚠ THE PACKAGE'S name, spelled out — never `__name__`. A submodule logger reads
# `apps.scholarship.views_admin.<module>` and drops every audit line it carries out
# of the Cloud Logging scrape metric. Guarded by `AuditLoggerNameTest` (H11).
logger = logging.getLogger('apps.scholarship.views_admin')


class AdminOrganisationConfigurationView(_AdminBase):
    """GET/PUT `admin/scholarship/organisation/configuration/` — the values an organisation tunes.

    Org Config Sprint A (2026-09-07). The second tab of Organisation → Settings, beside Colours.
    The tab shows a small registry of organisation-wide values (`courses.org_config.SETTINGS`);
    a blank field means "follow the platform default", and the stored row holds ONLY what the
    organisation changed. First (and so far only) setting: `pool_funded_grace_days` — how long a
    just-funded student's card stays on the sponsor browse page.

    ⚠ A SETTING APPEARS HERE ONLY WHEN CODE READS IT. The registry is the catalogue; the read
    sites are the feature. Adding a row without its consumer is the "UI asserts what nothing
    checks" defect — see `org_config`'s module docstring.

    ⚠ THE ORGANISATION IS DERIVED, NEVER SENT — same fence, same 404-not-403, same refusal to
    pick silently between two, mirroring `AdminOrganisationThemeView._organisation_for` next
    door. (Deliberately NOT a subclass of the theme view: inheriting would drag its GET/PUT/
    DELETE verbs onto this route, and a stray DELETE here must not discard a colour draft.)

    Who may write: `super` and `org_admin` only — these values change what every sponsor of the
    organisation sees, so they are the organisation's decision, held by its administrator.

    PUT is ALL-OR-NOTHING: everything validates before anything is stored, and each changed key
    writes an `AUDIT org_config_set` line carrying old → new ('default' = no stored value).
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
        """Mirrors `AdminOrganisationThemeView._organisation_for` — see its docstring."""
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
        from apps.courses import org_config
        rows = []
        for key, spec in org_config.SETTINGS.items():
            rows.append({
                'key': key,
                'group': spec['group'],
                'unit': spec['unit'],
                'min': spec['min'],
                'max': spec['max'],
                # None = "following the platform default" — the screen renders a blank box with
                # the default beside it, never the default AS the value (a copied default rots).
                'value': org_config.stored(org, key),
                'default': org_config.default(key),
                # Present only for a setting whose vocabulary is a short list rather than a
                # range (the slot step) — the tab renders a menu instead of a box.
                'allowed': list(spec['allowed']) if spec.get('allowed') else None,
            })
        return {
            'organisation': {'code': org.code, 'name': org.name},
            'settings': rows,
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
        from apps.courses import org_config
        from apps.courses.models import OrganisationConfiguration

        admin, err = self._gate(request)
        if err:
            return err
        org, err = self._organisation_for(admin, (request.query_params.get('org') or '').strip())
        if err:
            return err

        changes = request.data.get('values')
        if not isinstance(changes, dict):
            return Response({'error': 'bad_values', 'code': 'bad_values'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Validate EVERYTHING before writing ANYTHING (the programme-config rule): a half-applied
        # save is worse than a refused one. `None` means "clear back to the platform default" and
        # is valid for any known key; everything else goes through the registry's own fence.
        to_set = {k: v for k, v in changes.items() if v is not None}
        to_clear = [k for k, v in changes.items() if v is None]
        # The RESULT of the save, not the diff — a cross-field rule (Sprint D: the interview
        # window must open before it closes) is a statement about the two values that will be
        # STORED TOGETHER, and one of them may be arriving while the other is already on file
        # or is following the platform default. Validating the diff alone would let an inverted
        # window reach `row.save()`, where the model's own fence raises with the audit lines
        # already written — a 500 for what is an ordinary typo.
        # ⚠ Read the stored values by QUERY, never through `org.configuration`. Touching the
        # reverse OneToOne caches the row on this `org` instance, and `_payload` below would
        # then answer the save with the values as they were BEFORE it — a save that looks
        # ignored until the page is reloaded.
        existing = dict(OrganisationConfiguration.objects
                        .filter(organisation=org)
                        .values_list('values', flat=True).first() or {})
        merged = {k: v for k, v in existing.items() if k not in to_clear}
        merged.update(to_set)
        try:
            for key in to_clear:
                if key not in org_config.SETTINGS:
                    raise org_config.OrgConfigError('unknown_setting', key)
            # Per-key first, so the refusal names the key the person actually typed.
            org_config.validate_values(to_set, pairs=False)
            org_config.validate_values(merged)
        except org_config.OrgConfigError as exc:
            code = exc.code
            http = status.HTTP_404_NOT_FOUND if code == 'unknown_setting' else status.HTTP_400_BAD_REQUEST
            return Response({'error': code, 'code': code, 'key': exc.key}, status=http)

        row, _created = OrganisationConfiguration.objects.get_or_create(organisation=org)
        values = dict(row.values or {})
        for key in to_clear:
            was = values.pop(key, None)
            if was is not None:
                logger.info('AUDIT org_config_set org=%s key=%s was=%s now=default by=%s',
                            org.code, key, was, admin.email or '')
        for key, new in to_set.items():
            was = values.get(key)
            if was == new:
                continue
            values[key] = new
            logger.info('AUDIT org_config_set org=%s key=%s was=%s now=%s by=%s',
                        org.code, key, 'default' if was is None else was, new,
                        admin.email or '')
        row.values = values
        row.updated_by_email = admin.email or ''
        row.save()
        return Response(self._payload(org))


class AdminProgrammeConfigurationView(_AdminBase):
    """GET/PUT `admin/scholarship/programme/configuration/` — what ONE programme asks for.

    Layer 0 Sprint 5 (2026-08-30): the screen an `org_admin` uses to set, per catalogue item
    (documents AND questions), one of Off / Optional / Required. It writes
    `ProgrammeApplicationItem` rows — the same rows `requirements.programme_states` reads — so the
    gate, the payload, the verdict facts and Check-2 all follow the change with no edits of their
    own. That single seam is the design; do not teach this view a second copy of the rule.

    ⚠ THE CATALOGUE IS NOT A FENCE. Which items a programme asks for is configuration, never access
    control. The organisation fence is `_org_scoped` / `_org_allows` (cross-org ⇒ 404), and this
    view fences the PROGRAMME on `organisation_id` the same way: an org_admin may only ever load
    or write their own organisation's programme; a super passes `?programme=<code>`. A programme
    outside the caller's organisation is **404, never 403** — a 403 would confirm the tenant exists
    (the same reasoning that keeps the org fence on 404).

    Who may write: `super` and `org_admin` only — a plain `admin`/`qc`/`reviewer`/`finance` gets
    403 `_deny_role`. Configuration decides what every applicant to the programme is asked for;
    that is the organisation's decision, held by its administrator.

    Refuses to switch a CORE item off (`core_item`, 400) — the owner's 2026-07-28 policy floor.
    `programme_states` floors a stray row anyway, so this refusal is what the SCREEN reads; the
    floor underneath is what the data reads. Both are deliberate.

    Every change writes an `AUDIT programme_item_set` line (who, which programme, which item,
    old → new). Rows already at the requested state are not rewritten and not audited.

    `live_applicants` is COUNTED at request time (never typed in): applications on this programme
    still inside the submission gate (`shortlisted`). Those are the students a change reaches —
    a submitted student carries their frozen `requirements_snapshot` and is untouched.
    """

    ROLES = ('org_admin',)

    def _gate(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not self.has_role(admin, *self.ROLES):
            return None, self._deny_role()
        return admin, None

    def _programme_for(self, admin, code):
        """The one programme this request is about, or an error response.

        Fenced on `organisation_id` — derived from the same `owning_organisation` the org fence
        uses, so it cannot widen anything. Missing or cross-org → 404 (never 403).

        ⚠ NOT FILTERED ON `is_active`, AND THAT IS THE PRODUCT RULE (2026-09-03). A gift is created
        INACTIVE and is configured before it is switched on, so refusing to load the configuration
        of an unswitched gift refused the only screen that makes switching it on safe. It was
        `is_active=True` until the owner created a second gift and found they could not open it.
        Configuring an inactive programme reaches nobody: no cohort is open beneath it, so no
        application resolves through it. The FENCE is the organisation, and it is untouched.
        """
        qs = Programme.objects.all().select_related('organisation')
        if not self.has_role(admin, 'super'):
            org_id = admin.owning_organisation_id
            qs = qs.filter(organisation_id=org_id) if org_id else qs.none()
        if code:
            programme = qs.filter(code=code).first()
            if programme is None:
                return None, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
            return programme, None
        programmes = list(qs.order_by('code')[:2])
        if not programmes:
            return None, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        if len(programmes) > 1:
            # Never pick silently — the P2b/PF-1 rule. Name the choices so the client can ask.
            return None, Response(
                {'error': 'programme_required', 'code': 'programme_required',
                 'programmes': [p.code for p in qs.order_by('code')]},
                status=status.HTTP_400_BAD_REQUEST)
        return programmes[0], None

    def _payload(self, programme):
        from .. import requirements
        from ..models import ApplicationItem
        states = {
            'document': requirements.programme_states(programme, 'document'),
            'question': requirements.programme_states(programme, 'question'),
        }
        items = []
        for item in ApplicationItem.objects.filter(is_active=True).order_by('kind', 'code'):
            items.append({
                'kind': item.kind,
                'code': item.code,
                'label_key': item.label_key,
                'is_core': item.is_core,
                'default_state': item.default_state,
                'state': states[item.kind].get(item.code, item.default_state),
            })
        # org-fence: `programme` was fenced to the caller's organisation in _programme_for.
        live = ScholarshipApplication.objects.filter(
            programme=programme, status='shortlisted').count()
        return {
            'programme': {'code': programme.code, 'name': programme.name_en,
                          'organisation': programme.organisation.name},
            'live_applicants': live,
            'items': items,
        }

    def get(self, request):
        admin, err = self._gate(request)
        if err:
            return err
        programme, err = self._programme_for(
            admin, (request.query_params.get('programme') or '').strip())
        if err:
            return err
        return Response(self._payload(programme))

    def put(self, request):
        admin, err = self._gate(request)
        if err:
            return err
        programme, err = self._programme_for(
            admin, (request.query_params.get('programme') or '').strip())
        if err:
            return err

        from ..models import ITEM_STATE_CHOICES, ApplicationItem, ProgrammeApplicationItem
        valid_states = {s for s, _ in ITEM_STATE_CHOICES}
        changes = request.data.get('items')
        if not isinstance(changes, list):
            return Response({'error': 'bad_items', 'code': 'bad_items'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Validate EVERYTHING before writing ANYTHING — a half-applied save is worse than a
        # refused one, and the screen renders one refusal, not a list of partial outcomes.
        resolved = []
        for entry in changes:
            kind = (entry or {}).get('kind')
            code = (entry or {}).get('code')
            state = (entry or {}).get('state')
            item = ApplicationItem.objects.filter(kind=kind, code=code, is_active=True).first()
            if item is None:
                return Response({'error': 'unknown_item', 'code': 'unknown_item',
                                 'item': f'{kind}:{code}'}, status=status.HTTP_404_NOT_FOUND)
            if state not in valid_states:
                return Response({'error': 'bad_state', 'code': 'bad_state',
                                 'item': f'{kind}:{code}'}, status=status.HTTP_400_BAD_REQUEST)
            if item.is_core and state == 'off':
                return Response({'error': 'core_item', 'code': 'core_item',
                                 'item': f'{kind}:{code}'}, status=status.HTTP_400_BAD_REQUEST)
            resolved.append((item, state))

        from .. import requirements
        before = {
            'document': requirements.programme_states(programme, 'document'),
            'question': requirements.programme_states(programme, 'question'),
        }
        for item, state in resolved:
            was = before[item.kind].get(item.code, item.default_state)
            if was == state:
                continue
            ProgrammeApplicationItem.objects.update_or_create(
                programme=programme, item=item,
                defaults={'state': state, 'updated_by_email': admin.email or ''})
            logger.info('AUDIT programme_item_set programme=%s item=%s:%s was=%s now=%s by=%s',
                        programme.code, item.kind, item.code, was, state, admin.email or '')
        return Response(self._payload(programme))
