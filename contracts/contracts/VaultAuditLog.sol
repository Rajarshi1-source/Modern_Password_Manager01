// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title VaultAuditLog
 * @notice Append-only on-chain audit trail for SmartContractVault reveals.
 *
 * @dev The password plaintext never touches the chain. The Django backend
 *      decrypts off-chain after evaluating off-chain conditions, then calls
 *      anchorUnlock(commitmentHash) to leave a tamper-evident, timestamped
 *      breadcrumb. The commitment is keccak256(vaultId || userId || nonce).
 *
 *      This contract deliberately has zero privileged functions: anyone can
 *      anchor (msg.sender is recorded in the event) and nothing is stored
 *      in contract storage aside from a per-sender counter, keeping gas low.
 */
contract VaultAuditLog {
    /// @dev Emitted once per vault reveal.
    event VaultUnlocked(
        address indexed submitter,
        bytes32 indexed commitmentHash,
        uint256 timestamp
    );

    /// @dev Running count of reveals submitted by each address. Not
    ///      strictly needed for the audit trail (events are authoritative),
    ///      but useful for dashboards that don't run an archive node.
    mapping(address => uint256) public unlockCount;

    /**
     * @notice Anchor an off-chain unlock decision.
     * @param commitmentHash keccak256(vaultId || userId || nonce)
     *        Must be non-zero so we fail closed on misconfigured callers.
     */
    function anchorUnlock(bytes32 commitmentHash) external {
        require(commitmentHash != bytes32(0), "VaultAuditLog: zero commitment");
        unlockCount[msg.sender] += 1;
        emit VaultUnlocked(msg.sender, commitmentHash, block.timestamp);
    }
}
