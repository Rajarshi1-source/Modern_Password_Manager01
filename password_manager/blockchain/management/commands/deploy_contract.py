"""
Management Command to Deploy CommitmentRegistry Smart Contract

Usage:
    python manage.py deploy_contract --network testnet
    python manage.py deploy_contract --network mainnet --confirm
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import sys


class Command(BaseCommand):
    help = 'Deploy CommitmentRegistry smart contract to Arbitrum'

    def add_arguments(self, parser):
        parser.add_argument(
            '--network',
            type=str,
            choices=['testnet', 'mainnet'],
            default='testnet',
            help='Network to deploy to (testnet or mainnet)'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deployment to mainnet (required for mainnet)'
        )

    def handle(self, *args, **options):
        network = options['network']
        
        # Safety check for mainnet
        if network == 'mainnet' and not options['confirm']:
            raise CommandError(
                "❌ Mainnet deployment requires --confirm flag. "
                "This will deploy to Arbitrum mainnet and use real ETH!"
            )
        
        self.stdout.write(self.style.WARNING(
            f"\n{'='*80}\n"
            f"🚀 Deploying CommitmentRegistry Contract to Arbitrum {network.title()}\n"
            f"{'='*80}\n"
        ))
        
        # Check configuration
        if not settings.BLOCKCHAIN_ANCHORING.get('ENABLED'):
            raise CommandError("❌ Blockchain anchoring is disabled in settings")
        
        private_key = settings.BLOCKCHAIN_ANCHORING.get('PRIVATE_KEY')
        if not private_key:
            raise CommandError(
                "❌ BLOCKCHAIN_PRIVATE_KEY not set in environment. "
                "Add it to your .env file."
            )
        
        # Instructions for manual deployment
        self.stdout.write(self.style.SUCCESS(
            "\n📝 Manual Deployment Instructions:\n"
            "=================================="
        ))
        
        self.stdout.write(
            "\n1. Navigate to the contracts directory:\n"
            "   cd ../contracts\n"
        )
        
        self.stdout.write(
            "\n2. Install dependencies (if not already installed):\n"
            "   npm install\n"
        )
        
        self.stdout.write(
            "\n3. Ensure you have test ETH on Arbitrum Sepolia:\n"
            f"   Network: {network}\n"
            f"   RPC URL: {settings.BLOCKCHAIN_ANCHORING['RPC_URL']}\n"
            "   Get test ETH: https://faucet.quicknode.com/arbitrum/sepolia\n"
        )
        
        self.stdout.write(
            "\n4. Deploy the contract:\n"
            f"   npx hardhat run scripts/deploy.js --network arbitrum{'Sepolia' if network == 'testnet' else 'One'}\n"
        )
        
        self.stdout.write(
            "\n5. Copy the deployed contract address and update your .env file:\n"
            f"   COMMITMENT_REGISTRY_ADDRESS_{'TESTNET' if network == 'testnet' else 'MAINNET'}=<contract_address>\n"
        )
        
        self.stdout.write(
            "\n6. Verify the contract on Arbiscan (optional but recommended):\n"
            f"   npx hardhat verify --network arbitrum{'Sepolia' if network == 'testnet' else 'One'} <contract_address>\n"
        )
        
        self.stdout.write(self.style.SUCCESS(
            "\n✅ Follow the steps above to deploy the contract.\n"
            f"{'='*80}\n"
        ))
        
        # Show estimated costs
        if network == 'mainnet':
            self.stdout.write(self.style.WARNING(
                "\n💰 Estimated Costs (Arbitrum Mainnet):\n"
                "======================================"
                "\n- Deployment: ~$2-5 USD"
                "\n- Per batch anchor (1000 commitments): ~$0.02 USD"
                "\n- Monthly (1 anchor/day): ~$0.60 USD"
                "\n"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\n✅ Testnet deployment is FREE (uses test ETH)\n"
            ))

