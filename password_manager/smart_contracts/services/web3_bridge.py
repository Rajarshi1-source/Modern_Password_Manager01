"""
Web3 Bridge for TimeLockedVault Smart Contract
================================================

Bridges the Django backend to the on-chain TimeLockedVault contract.
Extends the pattern from blockchain.services.blockchain_anchor_service.
"""

import logging
import os
import json
from typing import Dict, List, Optional, Any
from django.conf import settings

logger = logging.getLogger(__name__)


# TimeLockedVault ABI (simplified — key functions only)
TIMELOCKED_VAULT_ABI = [
    # createTimeLockVault
    {
        "inputs": [
            {"internalType": "bytes32", "name": "_passwordHash", "type": "bytes32"},
            {"internalType": "uint256", "name": "_unlockTime", "type": "uint256"}
        ],
        "name": "createTimeLockVault",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # createDeadMansSwitchVault
    {
        "inputs": [
            {"internalType": "bytes32", "name": "_passwordHash", "type": "bytes32"},
            {"internalType": "uint256", "name": "_checkInInterval", "type": "uint256"},
            {"internalType": "uint256", "name": "_gracePeriod", "type": "uint256"},
            {"internalType": "address", "name": "_beneficiary", "type": "address"}
        ],
        "name": "createDeadMansSwitchVault",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # createMultiSigVault
    {
        "inputs": [
            {"internalType": "bytes32", "name": "_passwordHash", "type": "bytes32"},
            {"internalType": "address[]", "name": "_signers", "type": "address[]"},
            {"internalType": "uint256", "name": "_requiredApprovals", "type": "uint256"}
        ],
        "name": "createMultiSigVault",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # createDAOVault
    {
        "inputs": [
            {"internalType": "bytes32", "name": "_passwordHash", "type": "bytes32"},
            {"internalType": "address[]", "name": "_voters", "type": "address[]"},
            {"internalType": "uint256", "name": "_votingDeadline", "type": "uint256"},
            {"internalType": "uint256", "name": "_quorumThreshold", "type": "uint256"}
        ],
        "name": "createDAOVault",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # createPriceOracleVault
    {
        "inputs": [
            {"internalType": "bytes32", "name": "_passwordHash", "type": "bytes32"},
            {"internalType": "address", "name": "_oracleAddress", "type": "address"},
            {"internalType": "uint256", "name": "_priceThreshold", "type": "uint256"},
            {"internalType": "bool", "name": "_priceAbove", "type": "bool"}
        ],
        "name": "createPriceOracleVault",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # createEscrowVault
    {
        "inputs": [
            {"internalType": "bytes32", "name": "_passwordHash", "type": "bytes32"},
            {"internalType": "address", "name": "_beneficiary", "type": "address"},
            {"internalType": "address", "name": "_arbitrator", "type": "address"}
        ],
        "name": "createEscrowVault",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # conditionalAccess (view)
    {
        "inputs": [{"internalType": "uint256", "name": "_vaultId", "type": "uint256"}],
        "name": "conditionalAccess",
        "outputs": [{"internalType": "bool", "name": "met", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    # unlockVault
    {
        "inputs": [{"internalType": "uint256", "name": "_vaultId", "type": "uint256"}],
        "name": "unlockVault",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # checkIn
    {
        "inputs": [{"internalType": "uint256", "name": "_vaultId", "type": "uint256"}],
        "name": "checkIn",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # approveAccess
    {
        "inputs": [{"internalType": "uint256", "name": "_vaultId", "type": "uint256"}],
        "name": "approveAccess",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # castVote
    {
        "inputs": [
            {"internalType": "uint256", "name": "_vaultId", "type": "uint256"},
            {"internalType": "bool", "name": "_approve", "type": "bool"}
        ],
        "name": "castVote",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # releaseEscrow
    {
        "inputs": [{"internalType": "uint256", "name": "_vaultId", "type": "uint256"}],
        "name": "releaseEscrow",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # cancelVault
    {
        "inputs": [{"internalType": "uint256", "name": "_vaultId", "type": "uint256"}],
        "name": "cancelVault",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # getVault (view)
    {
        "inputs": [{"internalType": "uint256", "name": "_vaultId", "type": "uint256"}],
        "name": "getVault",
        "outputs": [
            {
                "components": [
                    {"internalType": "uint256", "name": "id", "type": "uint256"},
                    {"internalType": "address", "name": "creator", "type": "address"},
                    {"internalType": "bytes32", "name": "passwordHash", "type": "bytes32"},
                    {"internalType": "uint8", "name": "conditionType", "type": "uint8"},
                    {"internalType": "uint8", "name": "status", "type": "uint8"},
                    {"internalType": "uint256", "name": "createdAt", "type": "uint256"},
                    {"internalType": "uint256", "name": "updatedAt", "type": "uint256"},
                    {"internalType": "uint256", "name": "unlockTime", "type": "uint256"},
                    {"internalType": "uint256", "name": "checkInInterval", "type": "uint256"},
                    {"internalType": "uint256", "name": "lastCheckIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "gracePeriod", "type": "uint256"},
                    {"internalType": "address", "name": "beneficiary", "type": "address"},
                    {"internalType": "uint256", "name": "requiredApprovals", "type": "uint256"},
                    {"internalType": "uint256", "name": "approvalCount", "type": "uint256"},
                    {"internalType": "uint256", "name": "votingDeadline", "type": "uint256"},
                    {"internalType": "uint256", "name": "quorumThreshold", "type": "uint256"},
                    {"internalType": "uint256", "name": "votesFor", "type": "uint256"},
                    {"internalType": "uint256", "name": "votesAgainst", "type": "uint256"},
                    {"internalType": "uint256", "name": "totalEligibleVoters", "type": "uint256"},
                    {"internalType": "uint256", "name": "priceThreshold", "type": "uint256"},
                    {"internalType": "bool", "name": "priceAbove", "type": "bool"},
                    {"internalType": "address", "name": "oracleAddress", "type": "address"},
                    {"internalType": "address", "name": "arbitrator", "type": "address"},
                    {"internalType": "bool", "name": "exists", "type": "bool"}
                ],
                "internalType": "struct TimeLockedVault.Vault",
                "name": "",
                "type": "tuple"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    # getVaultCount (view)
    {
        "inputs": [],
        "name": "getVaultCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    # getDeadMansSwitchStatus (view)
    {
        "inputs": [{"internalType": "uint256", "name": "_vaultId", "type": "uint256"}],
        "name": "getDeadMansSwitchStatus",
        "outputs": [
            {"internalType": "uint256", "name": "timeRemaining", "type": "uint256"},
            {"internalType": "bool", "name": "isTriggered", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    # getDAOVoteResults (view)
    {
        "inputs": [{"internalType": "uint256", "name": "_vaultId", "type": "uint256"}],
        "name": "getDAOVoteResults",
        "outputs": [
            {"internalType": "uint256", "name": "votesFor", "type": "uint256"},
            {"internalType": "uint256", "name": "votesAgainst", "type": "uint256"},
            {"internalType": "uint256", "name": "totalEligible", "type": "uint256"},
            {"internalType": "uint256", "name": "quorumThreshold", "type": "uint256"},
            {"internalType": "bool", "name": "votingEnded", "type": "bool"},
            {"internalType": "bool", "name": "conditionMet", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
]


# VaultAuditLog ABI — minimal on-chain audit trail for reveal events.
VAULT_AUDIT_LOG_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "submitter", "type": "address"},
            {"indexed": True, "internalType": "bytes32", "name": "commitmentHash", "type": "bytes32"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"},
        ],
        "name": "VaultUnlocked",
        "type": "event",
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "commitmentHash", "type": "bytes32"}],
        "name": "anchorUnlock",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "", "type": "address"}],
        "name": "unlockCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class SmartContractWeb3Bridge:
    """
    Singleton service bridging Django to the TimeLockedVault smart contract.
    Re-uses the existing BLOCKCHAIN_ANCHORING config for Web3 connection.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.config = getattr(settings, 'SMART_CONTRACT_AUTOMATION', {})
        self.blockchain_config = getattr(settings, 'BLOCKCHAIN_ANCHORING', {})
        self.enabled = self.config.get('ENABLED', False)

        if not self.enabled:
            logger.info("Smart contract automation is disabled")
            self._initialized = True
            self.w3 = None
            self.contract = None
            self.account = None
            return

        # Reuse blockchain RPC connection
        rpc_url = self.blockchain_config.get('RPC_URL')
        if not rpc_url:
            logger.warning("BLOCKCHAIN_ANCHORING.RPC_URL not configured")
            self._initialized = True
            self.w3 = None
            self.contract = None
            self.account = None
            return

        try:
            from web3 import Web3
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
            if self.w3.is_connected():
                logger.info(f"Smart contracts Web3 connected: {rpc_url}")
            else:
                logger.error("Smart contracts Web3 connection failed")
                self.w3 = None
        except Exception as e:
            logger.error(f"Smart contracts Web3 init error: {e}")
            self.w3 = None

        # Load contract
        contract_address = self.config.get('TIMELOCKED_VAULT_ADDRESS', '')
        if self.w3 and contract_address:
            try:
                from web3 import Web3
                self.contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(contract_address),
                    abi=TIMELOCKED_VAULT_ABI
                )
                logger.info(f"TimeLockedVault contract loaded at {contract_address}")
            except Exception as e:
                logger.error(f"Contract load error: {e}")
                self.contract = None
        else:
            self.contract = None

        # Load signing account
        private_key = os.environ.get('BLOCKCHAIN_PRIVATE_KEY')
        if private_key and self.w3:
            try:
                from eth_account import Account
                self.account = Account.from_key(private_key)
                self._private_key = private_key
                logger.info(f"Smart contract deployer: {self.account.address}")
            except Exception as e:
                logger.error(f"Account load error: {e}")
                self.account = None
                self._private_key = None
        else:
            self.account = None
            self._private_key = None

        # Load VaultAuditLog contract for the on-chain reveal anchor.
        # Falls back to the TimeLockedVault address so operators without a
        # separate deployment still get the feature gated off cleanly.
        audit_address = (
            self.config.get('VAULT_AUDIT_LOG_ADDRESS', '')
            or self.config.get('TIMELOCKED_VAULT_ADDRESS', '')
        )
        self.audit_contract = None
        if self.w3 and audit_address:
            try:
                from web3 import Web3
                self.audit_contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(audit_address),
                    abi=VAULT_AUDIT_LOG_ABI,
                )
                logger.info(f"VaultAuditLog contract loaded at {audit_address}")
            except Exception as e:
                logger.error(f"VaultAuditLog load error: {e}")
                self.audit_contract = None

        self._initialized = True

    def is_available(self) -> bool:
        """Check if the Web3 bridge is fully operational."""
        return self.enabled and self.w3 is not None and self.contract is not None

    def check_condition_onchain(self, vault_id_onchain: int) -> Optional[bool]:
        """
        Check if vault conditions are met on-chain.
        Returns None if unavailable.
        """
        if not self.is_available():
            return None
        try:
            result = self.contract.functions.conditionalAccess(vault_id_onchain).call()
            return result
        except Exception as e:
            logger.error(f"On-chain condition check failed for vault {vault_id_onchain}: {e}")
            return None

    def get_vault_onchain(self, vault_id_onchain: int) -> Optional[Dict]:
        """Fetch vault state from on-chain contract."""
        if not self.is_available():
            return None
        try:
            vault_data = self.contract.functions.getVault(vault_id_onchain).call()
            return {
                'id': vault_data[0],
                'creator': vault_data[1],
                'password_hash': vault_data[2].hex(),
                'condition_type': vault_data[3],
                'status': vault_data[4],
                'created_at': vault_data[5],
                'updated_at': vault_data[6],
                'unlock_time': vault_data[7],
                'check_in_interval': vault_data[8],
                'last_check_in': vault_data[9],
                'grace_period': vault_data[10],
                'beneficiary': vault_data[11],
                'required_approvals': vault_data[12],
                'approval_count': vault_data[13],
                'voting_deadline': vault_data[14],
                'quorum_threshold': vault_data[15],
                'votes_for': vault_data[16],
                'votes_against': vault_data[17],
                'total_eligible_voters': vault_data[18],
                'price_threshold': vault_data[19],
                'price_above': vault_data[20],
                'oracle_address': vault_data[21],
                'arbitrator': vault_data[22],
                'exists': vault_data[23],
            }
        except Exception as e:
            logger.error(f"On-chain vault fetch failed for {vault_id_onchain}: {e}")
            return None

    def get_dead_mans_switch_status(self, vault_id_onchain: int) -> Optional[Dict]:
        """Get dead man's switch status from on-chain."""
        if not self.is_available():
            return None
        try:
            result = self.contract.functions.getDeadMansSwitchStatus(vault_id_onchain).call()
            return {
                'time_remaining': result[0],
                'is_triggered': result[1],
            }
        except Exception as e:
            logger.error(f"DMS status check failed for {vault_id_onchain}: {e}")
            return None

    def get_dao_vote_results(self, vault_id_onchain: int) -> Optional[Dict]:
        """Get DAO voting results from on-chain."""
        if not self.is_available():
            return None
        try:
            result = self.contract.functions.getDAOVoteResults(vault_id_onchain).call()
            return {
                'votes_for': result[0],
                'votes_against': result[1],
                'total_eligible': result[2],
                'quorum_threshold': result[3],
                'voting_ended': result[4],
                'condition_met': result[5],
            }
        except Exception as e:
            logger.error(f"DAO results check failed for {vault_id_onchain}: {e}")
            return None

    def get_vault_count(self) -> Optional[int]:
        """Get total vault count from on-chain."""
        if not self.is_available():
            return None
        try:
            return self.contract.functions.getVaultCount().call()
        except Exception as e:
            logger.error(f"Vault count check failed: {e}")
            return None

    # =========================================================================
    # Write path (reveal anchor)
    # =========================================================================

    def _write_ready(self) -> bool:
        """True iff we can submit transactions."""
        return bool(self.enabled and self.w3 and self.account and self._private_key)

    def build_and_send(
        self,
        contract,
        function_name: str,
        *args,
        gas_limit: Optional[int] = None,
    ) -> Optional[str]:
        """
        Build, sign and broadcast a transaction against the given contract.

        Mirrors BlockchainAnchorService._sign_and_send pattern. Returns the
        0x-prefixed tx hash, or None if the bridge is disabled or broadcast
        fails (logged; never raises for the caller, which must treat a None
        response as "on-chain audit skipped — DB unlock still succeeded").
        """
        if not self._write_ready() or contract is None:
            logger.info("build_and_send skipped: bridge not write-ready")
            return None

        try:
            fn = getattr(contract.functions, function_name)(*args)
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            tx = fn.build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gas': gas_limit or 150_000,
                'gasPrice': self.w3.eth.gas_price,
            })
            signed = self.w3.eth.account.sign_transaction(tx, self._private_key)
            raw = getattr(signed, 'raw_transaction', None) or getattr(signed, 'rawTransaction', None)
            tx_hash = self.w3.eth.send_raw_transaction(raw)
            tx_hash_hex = self.w3.to_hex(tx_hash)
            logger.info(f"build_and_send {function_name}: {tx_hash_hex}")
            return tx_hash_hex
        except Exception as e:
            logger.error(f"build_and_send({function_name}) failed: {e}")
            return None

    def wait_for_receipt(
        self,
        tx_hash: str,
        timeout_s: int = 120,
    ) -> Optional[Dict[str, Any]]:
        """
        Poll for a transaction receipt. Returns a dict with block_number,
        gas_used, success (bool), or None on timeout / error.
        """
        if not self.w3 or not tx_hash:
            return None
        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout_s)
            return {
                'block_number': receipt.get('blockNumber'),
                'gas_used': receipt.get('gasUsed'),
                'success': receipt.get('status') == 1,
                'tx_hash': tx_hash,
            }
        except Exception as e:
            logger.warning(f"wait_for_receipt({tx_hash}) timeout/error: {e}")
            return None

    def explorer_url(self, tx_hash: str) -> str:
        """Human-readable link for the given tx hash."""
        if not tx_hash:
            return ''
        network = self.blockchain_config.get('NETWORK', 'testnet')
        base = 'https://arbiscan.io/tx/' if network == 'mainnet' else 'https://sepolia.arbiscan.io/tx/'
        return f"{base}{tx_hash}"
