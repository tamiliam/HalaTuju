"""
Derive and populate institution modifiers (urban, cultural_safety_net)
from state and address data. W8 Part 1.

Usage:
    python manage.py derive_institution_modifiers          # dry run
    python manage.py derive_institution_modifiers --apply  # write to DB
"""
from django.core.management.base import BaseCommand

from apps.courses.models import Institution


# States that are predominantly urban
URBAN_STATES = {
    'WP Kuala Lumpur',
    'WP Putrajaya',
    'Pulau Pinang',  # Penang is fully urbanised (island + mainland Seberang Perai)
}

# Major cities — if address contains any of these, institution is urban.
# Used for states that aren't fully urban but have urban centres.
URBAN_CITIES = [
    # Selangor
    'Shah Alam', 'Petaling Jaya', 'Subang', 'Cyberjaya', 'Putrajaya',
    'Klang', 'Kajang', 'Bangi', 'Serdang', 'Puchong', 'Damansara',
    'Gombak', 'Rawang', 'Ampang', 'Cheras',
    # Penang
    'George Town', 'Georgetown', 'Gelugor', 'Bayan Lepas', 'Nibong Tebal',
    'Bukit Mertajam', 'Butterworth', 'Seberang Perai',
    # Johor
    'Johor Bahru', 'Johor Baru', 'Skudai', 'Iskandar',
    'Batu Pahat', 'Pasir Gudang',
    # Perak
    'Ipoh', 'Seri Iskandar',
    # Negeri Sembilan
    'Seremban', 'Nilai',
    # Kedah
    'Alor Setar', 'Sungai Petani',
    # Melaka
    'Melaka', 'Malacca',
    # Pahang
    'Kuantan',
    # Terengganu
    'Kuala Terengganu',
    # Kelantan
    'Kota Bharu',
    # Sabah
    'Kota Kinabalu',
    # Sarawak
    'Kuching', 'Miri', 'Sibu',
    # Labuan
    'Labuan',
]

# States with significant Indian community presence.
# Based on Department of Statistics Malaysia ethnic composition data.
HIGH_SAFETY_NET_STATES = {
    'WP Kuala Lumpur',
    'WP Putrajaya',
    'Selangor',
    'Perak',
    'Pulau Pinang',
    'Negeri Sembilan',
    'Johor',
    'Melaka',
    'Kedah',
}

# Everything else defaults to "low".


def derive_urban(institution):
    """Determine if an institution is in an urban area."""
    if institution.state in URBAN_STATES:
        return True

    address = (institution.address or '').lower()
    name = institution.institution_name.lower()
    combined = f"{address} {name}"

    for city in URBAN_CITIES:
        if city.lower() in combined:
            return True

    return False


def derive_cultural_safety_net(institution):
    """Determine cultural safety net level from state."""
    if institution.state in HIGH_SAFETY_NET_STATES:
        return 'high'
    return 'low'


class Command(BaseCommand):
    help = 'Derive institution modifiers (urban, cultural_safety_net) from state/address data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Write modifiers to database (default is dry run)',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        institutions = Institution.objects.all()
        total = institutions.count()

        urban_count = 0
        high_safety_count = 0
        updated = 0

        type_stats = {}

        for inst in institutions:
            urban = derive_urban(inst)
            safety_net = derive_cultural_safety_net(inst)

            new_modifiers = {
                'urban': urban,
                'cultural_safety_net': safety_net,
            }

            if urban:
                urban_count += 1
            if safety_net == 'high':
                high_safety_count += 1

            # Track by type
            t = inst.type
            if t not in type_stats:
                type_stats[t] = {'total': 0, 'urban': 0, 'high': 0}
            type_stats[t]['total'] += 1
            if urban:
                type_stats[t]['urban'] += 1
            if safety_net == 'high':
                type_stats[t]['high'] += 1

            if inst.modifiers != new_modifiers:
                updated += 1
                if apply:
                    inst.modifiers = new_modifiers
                    inst.save(update_fields=['modifiers'])

        # Report
        self.stdout.write(f"\n{'Type':<25} {'Total':>6} {'Urban':>6} {'High SN':>8}")
        self.stdout.write('-' * 50)
        for t, stats in sorted(type_stats.items()):
            self.stdout.write(
                f"{t:<25} {stats['total']:>6} {stats['urban']:>6} {stats['high']:>8}"
            )
        self.stdout.write('-' * 50)
        self.stdout.write(
            f"{'TOTAL':<25} {total:>6} {urban_count:>6} {high_safety_count:>8}"
        )
        self.stdout.write(f"\nWould update: {updated} institutions")

        if apply:
            self.stdout.write(self.style.SUCCESS(f'\nApplied modifiers to {updated} institutions.'))
        else:
            self.stdout.write(self.style.WARNING('\nDry run — use --apply to write to database.'))
