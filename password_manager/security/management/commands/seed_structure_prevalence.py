"""
Seed the dark-web structural-prevalence table.

Populates :class:`security.models.PasswordStructurePrevalence` with curated
estimates of how common each password *structure* (character-class transition
signature + length bucket) is in public breach corpora (RockYou and breach
compilations). These are coarse, irreversible structural statistics — no
passwords or words — and form the zero-knowledge "dark-web monitoring" signal.

Idempotent: re-running updates existing rows. The internal dark-web threat
feed can refresh these over time; this command provides the baseline.

Usage:
    python manage.py seed_structure_prevalence
    python manage.py seed_structure_prevalence --clear
"""

from django.core.management.base import BaseCommand

# Curated prevalence estimates derived from public breach-corpus analyses.
# Signature = char-class transition pattern (runs collapsed), e.g. 'ULD' is
# "Uppercase + lowercase run + digit run" (the classic Word+year-suffix shape).
# (char_class_pattern, length_bucket, prevalence)
SEED_DATA = [
    # word + digit suffix — the single most common shape in dumps
    ('LD', 'short', 0.14),
    ('LD', 'medium', 0.18),
    ('LD', 'long', 0.06),
    ('LD', '', 0.12),          # any-length fallback
    # all lowercase
    ('L', 'short', 0.10),
    ('L', 'medium', 0.08),
    ('L', '', 0.08),
    # all digits (PINs / numeric)
    ('D', 'very_short', 0.05),
    ('D', 'short', 0.07),
    ('D', '', 0.05),
    # Capitalised word + digits (e.g. Summer2024, Password1)
    ('ULD', 'medium', 0.09),
    ('ULD', 'long', 0.04),
    ('ULD', '', 0.06),
    # Capitalised word, no digits
    ('UL', 'short', 0.03),
    ('UL', 'medium', 0.03),
    # word + digits + trailing symbol
    ('LDS', 'medium', 0.04),
    ('LDS', 'long', 0.03),
    ('ULDS', 'medium', 0.03),
    ('ULDS', 'long', 0.03),
    # digit prefix then word
    ('DL', 'short', 0.02),
]

# Representative corpus size the estimates are scaled against.
SEED_SAMPLE_SIZE = 1_000_000


class Command(BaseCommand):
    help = "Seed curated dark-web password-structure prevalence statistics."

    def add_arguments(self, parser):
        """Register the optional ``--clear`` flag."""
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete existing curated_seed rows before seeding.',
        )

    def handle(self, *args, **options):
        """Upsert the curated prevalence rows (idempotent)."""
        from security.models import PasswordStructurePrevalence

        if options['clear']:
            deleted, _ = PasswordStructurePrevalence.objects.filter(
                source='curated_seed'
            ).delete()
            self.stdout.write(f"Cleared {deleted} existing curated rows.")

        created = updated = 0
        for pattern, bucket, prevalence in SEED_DATA:
            # source is part of the key, so this only ever upserts the curated
            # baseline row and never overwrites a feed-sourced row.
            _, was_created = PasswordStructurePrevalence.objects.update_or_create(
                char_class_pattern=pattern,
                length_bucket=bucket,
                source='curated_seed',
                defaults={
                    'prevalence': prevalence,
                    'occurrence_count': int(prevalence * SEED_SAMPLE_SIZE),
                    'sample_size': SEED_SAMPLE_SIZE,
                },
            )
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(self.style.SUCCESS(
            f"Structure prevalence seeded: {created} created, {updated} updated "
            f"({len(SEED_DATA)} total)."
        ))
