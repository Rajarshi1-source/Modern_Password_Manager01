"""
Management Command: Upgrade to Quantum Encryption

Migrates existing behavioral commitments from classical to quantum-resistant encryption
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from behavioral_recovery.models import BehavioralCommitment
from behavioral_recovery.services.quantum_crypto_service import QuantumCryptoService
import logging
import base64
import json

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Upgrade existing behavioral commitments to quantum-resistant encryption (Kyber-768)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate migration without making changes'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of commitments to process per batch'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Migrate commitments for specific user only'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        user_id = options['user_id']
        
        self.stdout.write(self.style.MIGRATE_HEADING('Behavioral Commitment Quantum Migration'))
        self.stdout.write('=' * 70)
        
        # Get commitments to upgrade
        queryset = BehavioralCommitment.objects.filter(is_quantum_protected=False)
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
            self.stdout.write(f"Filtering for user ID: {user_id}")
        
        total = queryset.count()
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('✅ No commitments need upgrading'))
            return
        
        self.stdout.write(f"Found {total} commitments to upgrade")
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  DRY RUN MODE - No changes will be made\n'))
        
        # Initialize quantum crypto
        try:
            quantum_crypto = QuantumCryptoService()
            algo_info = quantum_crypto.get_algorithm_info()
            
            if not algo_info['quantum_resistant']:
                self.stdout.write(self.style.ERROR(
                    '❌ liboqs not available. Cannot perform quantum upgrade.'
                ))
                self.stdout.write('Install with: pip install liboqs-python')
                return
            
            self.stdout.write(self.style.SUCCESS(f"✅ Using {algo_info['algorithm']}"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Failed to initialize quantum crypto: {e}'))
            return
        
        # Process commitments
        upgraded = 0
        failed = 0
        skipped = 0
        
        for commitment in queryset.iterator(chunk_size=batch_size):
            try:
                # Skip if already quantum protected (safety check)
                if commitment.is_quantum_protected:
                    skipped += 1
                    continue
                
                # Decrypt old embedding (base64 format)
                try:
                    old_embedding = self._decrypt_legacy_embedding(commitment.encrypted_embedding)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(
                        f"⚠️  Could not decrypt commitment {commitment.commitment_id}: {e}"
                    ))
                    failed += 1
                    continue
                
                if not dry_run:
                    # Generate new Kyber keypair for this commitment
                    public_key, private_key = quantum_crypto.generate_keypair()
                    
                    # Encrypt with Kyber + AES
                    quantum_encrypted = quantum_crypto.encrypt_behavioral_embedding(
                        old_embedding,
                        public_key
                    )
                    
                    # Store original encrypted data as legacy
                    commitment.legacy_encrypted_embedding = commitment.encrypted_embedding
                    
                    # Update with quantum encryption
                    commitment.quantum_encrypted_embedding = quantum_encrypted
                    commitment.kyber_public_key = public_key
                    commitment.encryption_algorithm = 'kyber768-aes256gcm'
                    commitment.is_quantum_protected = True
                    commitment.migrated_to_quantum = timezone.now()
                    commitment.encrypted_embedding = b''  # Clear legacy field
                    
                    commitment.save()
                    
                    self.stdout.write('.', ending='')
                else:
                    self.stdout.write('.', ending='')
                
                upgraded += 1
                
                # Print progress every 10 commitments
                if upgraded % 10 == 0:
                    self.stdout.write(f' [{upgraded}/{total}]')
                
            except Exception as e:
                logger.error(f"Failed to upgrade commitment {commitment.id}: {e}", exc_info=True)
                self.stdout.write(self.style.ERROR(f'\n❌ Error on commitment {commitment.commitment_id}'))
                failed += 1
        
        # Summary
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS(f'\n✅ Migration {"simulated" if dry_run else "completed"}!'))
        self.stdout.write(f'\nTotal commitments: {total}')
        self.stdout.write(f'Upgraded: {upgraded}')
        if skipped > 0:
            self.stdout.write(f'Skipped (already quantum): {skipped}')
        if failed > 0:
            self.stdout.write(self.style.ERROR(f'Failed: {failed}'))
        
        if not dry_run and upgraded > 0:
            self.stdout.write(self.style.SUCCESS(
                f'\n🔐 {upgraded} commitments are now quantum-resistant!'
            ))
    
    def _decrypt_legacy_embedding(self, encrypted_embedding):
        """Decrypt legacy base64-encoded embedding"""
        decrypted_bytes = base64.b64decode(encrypted_embedding)
        decrypted_json = decrypted_bytes.decode('utf-8')
        embedding_data = json.loads(decrypted_json)
        return embedding_data

