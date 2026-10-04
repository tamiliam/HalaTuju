"""Give every stored transaction one of the ten categories. **The four-rung ladder.**

    python manage.py sort_spending                    # REPORT ONLY - nothing is written
    python manage.py sort_spending --apply            # …and write the categories
    python manage.py sort_spending --all --apply      # re-sort EVERY row except an owner one
    python manage.py sort_spending --no-ai --apply    # rungs 1-3 only; no model call, no cost
    python manage.py sort_spending --reask-version spend-cat-v2 --apply
                                                      # re-ask every `ai` answer an OLDER prompt gave

The rungs, the thresholds and the reasoning all live in `apps/scholarship/spend_category.py`.
Nothing about how a category is chosen belongs in this file.

⚠ **A SEPARATE COMMAND ON PURPOSE (owner, 2026-09-10).** Keyword rules get tuned, and tuning them
must not mean re-importing. `ingest_spending --apply` still calls the same sorter after a
successful import, so the daily job stays ONE Cloud Scheduler entry — this is the door you use by
hand, not a second schedule.

⚠ **REPORT MODE IS THE DEFAULT AND IT CANNOT WRITE.** Read the report before applying it.

⚠ **`--all` NEVER TOUCHES AN `owner` ROW.** A person's correction outranks every rung, for ever.

⚠ **`--reask-version` IS PAID AND NEVER AUTOMATIC (TD-239).** Bumping `PROMPT_VERSION` re-asks
nothing by itself. This flag re-asks the merchants whose stored `ai` answer carries another version,
and it must name the CURRENT one, so a typo is refused instead of re-billing the whole list.
⚠ REPORT MODE ALSO CALLS THE MODEL AND PAYS (the ladder has no apply flag), and `merchants
re-asked` overcounts — a merchant a keyword or the pattern now places is never asked. The paid count
is `merchants asked`. So run `--reask-version` ONCE, with `--apply`.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.scholarship import spend_category


class Command(BaseCommand):
    help = 'Sort stored bursary transactions into the ten spending categories.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Write the categories. Without it, nothing is stored.')
        parser.add_argument('--all', action='store_true', dest='resort',
                            help='Re-consider every row except an owner one. Use after adding a '
                                 'keyword rule.')
        parser.add_argument('--no-ai', action='store_true',
                            help='Run rungs 1-3 only. No model call is made and nothing is billed.')
        parser.add_argument('--reask-version', default=None, metavar='VERSION',
                            help='Re-ask the model about every merchant whose stored AI answer came '
                                 'from another prompt. Must equal the current PROMPT_VERSION. Paid.')

    def handle(self, *args, **options):
        try:
            report = spend_category.sort_transactions(
                apply=options['apply'],
                resort=options['resort'],
                use_ai=not options['no_ai'],
                reask_version=options['reask_version'],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        mode = 'APPLIED' if options['apply'] else 'REPORT ONLY - nothing was written'
        self.stdout.write(f'--- sort_spending ({mode}) ---')
        for line in report.lines():
            self.stdout.write(line)
