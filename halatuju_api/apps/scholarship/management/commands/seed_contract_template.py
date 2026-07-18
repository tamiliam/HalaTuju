"""Seed a DRAFT ContractTemplate for an organisation from a fixture JSON.

Creates a draft ONLY — the owner then fills the counterparty NRIC, records the
lawyer-vetting attestation, and submits for deployment via the admin UI; a super
deploys. Re-running with an existing version refuses (a version is immutable once
it exists) unless --replace-draft is passed (only ever replaces a DRAFT).

    python manage.py seed_contract_template --org brightpath --template-version 2026-v1 \
        --fixture apps/scholarship/fixtures/brightpath_contract_v1.json

(``--version`` is reserved by Django's BaseCommand, so the flag is
``--template-version``.)
"""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.courses.models import PartnerOrganisation
from apps.scholarship import contracts
from apps.scholarship.models import ContractTemplate

LANGS = ('en', 'ms', 'ta')


def _flatten_clause(item):
    heading = item.get('heading', {})
    body = item.get('body', {})
    quiz = item.get('quiz', {})
    flat = {'is_quiz_candidate': bool(item.get('is_quiz_candidate'))}
    for lang in LANGS:
        flat[f'heading_{lang}'] = heading.get(lang, '') or ''
        flat[f'body_{lang}'] = body.get(lang, '') or ''
        flat[f'quiz_{lang}'] = quiz.get(lang) or {}
    return flat


def _flatten_row(item):
    label = item.get('label', {})
    flat = {
        'pathway': item.get('pathway', ''),
        'variant': item.get('variant', ''),
        'monthly_amount': item.get('monthly_amount', '0'),
        'start_month': item.get('start_month', 0),
        'paid_offsets': item.get('paid_offsets', []),
        'sort_order': item.get('sort_order', 0),
    }
    for lang in LANGS:
        flat[f'label_{lang}'] = label.get(lang, '') or ''
    return flat


def _config_kwargs(config):
    kwargs = {
        'counterparty_title': config.get('counterparty_title', '') or '',
        'counterparty_notify_emails': config.get('counterparty_notify_emails', []) or [],
        'parent_role': config.get('parent_role', 'co_signer_all'),
        'parent_pin_required': bool(config.get('parent_pin_required', True)),
        'witness_policy': config.get('witness_policy', 'optional'),
    }
    for field in ('title', 'preamble', 'progress_standard'):
        localised = config.get(field, {})
        for lang in LANGS:
            kwargs[f'{field}_{lang}'] = localised.get(lang, '') or ''
    return kwargs


class Command(BaseCommand):
    help = 'Seed a DRAFT ContractTemplate for an org from a fixture JSON.'

    def add_arguments(self, parser):
        parser.add_argument('--org', required=True, help="Organisation code (e.g. 'brightpath').")
        parser.add_argument('--template-version', required=True,
                            help='Template version string (unique per org).')
        parser.add_argument('--fixture', required=True, help='Path to the fixture JSON.')
        parser.add_argument('--created-by', default='', help='created_by_email stamp.')
        parser.add_argument('--replace-draft', action='store_true',
                            help='If a DRAFT of this version exists, delete and re-seed it.')

    def handle(self, *args, **opts):
        try:
            org = PartnerOrganisation.objects.get(code=opts['org'])
        except PartnerOrganisation.DoesNotExist:
            raise CommandError(f"No PartnerOrganisation with code '{opts['org']}'.")

        with open(opts['fixture'], encoding='utf-8') as f:
            fixture = json.load(f)

        version = opts['template_version']
        existing = ContractTemplate.objects.filter(organisation=org, version=version).first()
        if existing is not None:
            if not opts['replace_draft']:
                raise CommandError(
                    f"Template {org.code}/{version} already exists (status={existing.status}). "
                    f"Pass --replace-draft to re-seed a DRAFT."
                )
            if existing.status != 'draft':
                raise CommandError(
                    f"Refusing to replace a non-draft template ({existing.status})."
                )
            existing.delete()

        template = contracts.create_template(
            org, version, created_by_email=opts['created_by'] or '',
        )
        contracts.update_config(template, **_config_kwargs(fixture.get('config', {})))
        contracts.replace_clauses(template, [_flatten_clause(c) for c in fixture.get('clauses', [])])
        contracts.replace_schedule(template, [_flatten_row(r) for r in fixture.get('schedule', [])])

        candidates = template.clauses.filter(is_quiz_candidate=True).count()
        self.stdout.write(self.style.SUCCESS(
            f'Seeded DRAFT {org.code}/{version}: {template.clauses.count()} clauses '
            f'({candidates} quiz candidates), {template.schedule_rows.count()} schedule rows. '
            f'Owner: fill counterparty NRIC + attestation, then submit; super deploys.'
        ))
