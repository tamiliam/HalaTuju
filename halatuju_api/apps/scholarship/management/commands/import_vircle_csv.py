"""One-off backfill of the Vircle payment history from the owner's spreadsheet (D8).

The Disbursement ledger is empty in production, but two real batches were already paid via
Vircle (recorded only in the owner's CSV). This command makes "paid to date" truthful:

  * stamps ``vircle_id`` on every matched application (NRIC digits join);
  * creates the batches as FIRST-CLASS completed PaymentRuns (``backfill-YYYY-MM-DD``,
    no signatures), each with released Disbursement rows at the CSV's ACTUAL amounts
    (history is a record, not a rule — the two RM300s are preserved);
  * seeds the D6 regularisation credits, DERIVED from the data so no student is hard-coded:
      - overpayment credit  = amount − MONTHLY_RATE   (a batch paid above the flat rate);
      - paid-before-starting = the full amount          (batch date < the app's reporting_date).
    On the plan's cohort this reproduces exactly: the two RM300 students → credit 100 each,
    and the university student paid before reporting → credit 200.

Idempotent: re-running creates nothing that already exists and never re-seeds a credit for an
already-imported batch row. ``--dry-run`` reconciles + prints the table, writing nothing.

The CSV holds student PII (names + NRICs) and is NEVER committed — it is passed by path.
Expected columns: No, Student NRIC, Vircle ID, Phone, Student Name, Monthly, Batch, Remarks, Remark.
"""
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.scholarship import payments
from apps.scholarship.models import Disbursement, PaymentRun, PaymentRunItem, ScholarshipApplication


def _digits(value):
    return ''.join(ch for ch in (value or '') if ch.isdigit())


def _parse_batch_date(raw):
    """Parse a d/m/Y batch date ('30/6/2026', '16/07/2026'). Returns a date or None (blank)."""
    raw = (raw or '').strip()
    if not raw:
        return None
    for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise CommandError(f'Unrecognised Batch date: {raw!r}')


def _money(raw):
    try:
        return Decimal(str(raw or '0').strip() or '0').quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        raise CommandError(f'Unrecognised Monthly amount: {raw!r}')


class Command(BaseCommand):
    help = 'Backfill Vircle payment history + stamp vircle_id from the owner CSV (D8).'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', help='Path to the backfill CSV (PII — never committed).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Reconcile + print the table; write nothing.')

    def handle(self, *args, **opts):
        path = opts['csv_path']
        dry = opts['dry_run']
        try:
            with open(path, encoding='utf-8-sig', newline='') as fh:
                rows = [r for r in csv.DictReader(fh) if any((v or '').strip() for v in r.values())]
        except OSError as e:
            raise CommandError(f'Cannot read {path}: {e}')

        # Build the NRIC → application map once (only applications that have a profile+NRIC).
        by_nric = {}
        for app in (ScholarshipApplication.objects
                    .select_related('profile', 'cohort').all()):
            nric = _digits(getattr(app.profile, 'nric', '') if app.profile_id else '')
            if nric:
                by_nric.setdefault(nric, app)

        parsed, unmatched = [], []
        for r in rows:
            nric = _digits(r.get('Student NRIC'))
            app = by_nric.get(nric)
            if app is None:
                unmatched.append((r.get('No'), r.get('Student NRIC')))
                continue
            parsed.append({
                'app': app,
                'vircle_id': _digits(r.get('Vircle ID')),
                'monthly': _money(r.get('Monthly')),
                'batch': _parse_batch_date(r.get('Batch')),
            })

        # ── reconciliation summary ────────────────────────────────────────────
        batches = {}
        for p in parsed:
            if p['batch'] and p['monthly'] > 0:
                batches.setdefault(p['batch'], []).append(p)
        self.stdout.write(f'Rows: {len(rows)} · matched: {len(parsed)} · unmatched: {len(unmatched)}')
        for no, nr in unmatched:
            self.stdout.write(self.style.WARNING(f'  UNMATCHED row {no}: NRIC {nr}'))
        for bd in sorted(batches):
            group = batches[bd]
            total = sum((p['monthly'] for p in group), Decimal('0'))
            self.stdout.write(f'  Batch {bd.isoformat()}: {len(group)} paid, total RM{total}')
        # credit preview (derived)
        for p in parsed:
            credit = self._credit_for(p)
            if credit > 0:
                self.stdout.write(
                    f'  Credit RM{credit} → app {p["app"].id} '
                    f'({"overpay" if p["monthly"] > payments.MONTHLY_RATE else "advance"})')

        if unmatched:
            self.stdout.write(self.style.ERROR(
                f'{len(unmatched)} row(s) did not match an application by NRIC — fix before a live run.'))
        if dry:
            self.stdout.write(self.style.SUCCESS('DRY RUN — no changes written.'))
            return

        with transaction.atomic():
            self._apply(parsed, batches)
        self.stdout.write(self.style.SUCCESS('Backfill complete.'))

    # ── credit derivation (D6/D8) ─────────────────────────────────────────────
    def _credit_for(self, p):
        credit = Decimal('0')
        if p['monthly'] > payments.MONTHLY_RATE:                       # overpayment
            credit += p['monthly'] - payments.MONTHLY_RATE
        reporting = p['app'].reporting_date
        if reporting and p['batch'] and p['batch'] < reporting:        # paid before starting
            credit += p['monthly']
        return credit

    # ── writes (idempotent) ────────────────────────────────────────────────────
    def _apply(self, parsed, batches):
        # 1. Stamp vircle_id on every matched application (overwrite = idempotent).
        for p in parsed:
            app = p['app']
            if p['vircle_id'] and app.vircle_id != p['vircle_id']:
                app.vircle_id = p['vircle_id']
                app.save(update_fields=['vircle_id'])

        # 2. Batches → completed PaymentRuns with released Disbursements + items, oldest first.
        for bd in sorted(batches):
            group = batches[bd]
            org = group[0]['app'].owning_organisation
            ref = f'backfill-{bd.isoformat()}'
            run, _ = PaymentRun.objects.get_or_create(
                reference=ref,
                defaults={'organisation': org, 'payment_date': bd, 'status': 'completed'},
            )
            released_at = timezone.make_aware(datetime(bd.year, bd.month, bd.day, 12, 0))
            for p in group:
                app = p['app']
                if PaymentRunItem.objects.filter(run=run, application=app).exists():
                    continue   # already imported — leave everything as-is
                paid_before = payments.paid_to_date(app)
                top = app.disbursements.aggregate(m=Max('sequence'))['m'] or 0
                disb = Disbursement.objects.create(
                    application=app, amount=p['monthly'], status='released',
                    sequence=top + 1, released_at=released_at, scheduled_for=bd,
                    reference=f'vircle:{ref}'[:100], label=f'Vircle {bd:%b %Y}'[:100],
                )
                PaymentRunItem.objects.create(
                    run=run, application=app, included=True, amount=p['monthly'],
                    award_amount_snapshot=(app.award_amount or Decimal('0')),
                    paid_to_date_snapshot=paid_before,
                    vircle_id_snapshot=app.vircle_id or '',
                    disbursement=disb,
                )
                # 3. Seed the derived regularisation credit for this fresh row.
                credit = self._credit_for(p)
                if credit > 0:
                    app.payment_credit = (app.payment_credit or Decimal('0')) + credit
                    app.save(update_fields=['payment_credit'])
