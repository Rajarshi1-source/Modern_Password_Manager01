// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title VaultAuditLog
 * @notice Append-only on-chain audit trail for SmartContractVault reveals.
 *
 * @dev The password plaintext never touches the chain. The Django backend
 *      decrypts off-chain after evaluating off-chain conditions, then calls
 *      anchorUnlock(commitmentHash) to leave a tamper-evident, timestamped
 *      breadcrumb. The commitment is keccak256(vaultId || userId || nonce).
 *
 *      Audit-fix M9 (2026-05): the contract now restricts `anchorUnlock` to
 *      addresses in the `authorizedAnchorers` map, mirroring the
 *      `authorizedSigners` pattern shipped for `CommitmentRegistry` in
 *      PR #262 (C8). Previously, anyone could call `anchorUnlock` with any
 *      32-byte non-zero value, which let an attacker spam the event log
 *      with junk reveals indistinguishable from real ones (the off-chain
 *      Django side does have the preimage, but an external auditor reading
 *      Arbiscan does not). The hot-key model also pairs cleanly with the
 *      `KeyProvider` abstraction so a future KMS rotation just calls
 *      `addAuthorizedAnchorer(new) + removeAuthorizedAnchorer(old)` without
 *      a redeploy.
 *
 *      The brick-resistance guards (cannot remove the last anchorer,
 *      cannot renounceOwnership) mirror the `CommitmentRegistry` invariants
 *      so the operational story is identical.
 */
contract VaultAuditLog is Ownable {
    /// @dev Emitted once per vault reveal.
    event VaultUnlocked(
        address indexed submitter,
        bytes32 indexed commitmentHash,
        uint256 timestamp
    );

    event AnchorerAuthorized(address indexed anchorer);
    event AnchorerRevoked(address indexed anchorer);

    /// @dev Running count of reveals submitted by each address. Not
    ///      strictly needed for the audit trail (events are authoritative),
    ///      but useful for dashboards that don't run an archive node.
    mapping(address => uint256) public unlockCount;

    /// @dev Tracks which commitment hashes have already been anchored.
    ///      The Django side persists a single `reveal_nonce` / `reveal_commitment`
    ///      per vault for idempotent retries; if a retry races and the same
    ///      commitment is re-broadcast, the chain still emits exactly one
    ///      `VaultUnlocked` because the second transaction reverts here.
    mapping(bytes32 => bool) public anchoredCommitments;

    /// @dev Hot keys allowed to call `anchorUnlock`. The deployer is
    ///      seeded; `owner()` can rotate. Mirrors `CommitmentRegistry.
    ///      authorizedSigners`.
    mapping(address => bool) public authorizedAnchorers;

    /// @dev Number of currently-authorised anchorers. Maintained alongside
    ///      `authorizedAnchorers` so `removeAuthorizedAnchorer` can refuse
    ///      to revoke the last one (otherwise the log would be bricked).
    uint256 public authorizedAnchorerCount;

    constructor() Ownable(msg.sender) {
        authorizedAnchorers[msg.sender] = true;
        authorizedAnchorerCount = 1;
        emit AnchorerAuthorized(msg.sender);
    }

    /**
     * @notice Authorise a new anchor-submitting hot key.
     */
    function addAuthorizedAnchorer(address anchorer) external onlyOwner {
        require(anchorer != address(0), "Invalid anchorer");
        require(!authorizedAnchorers[anchorer], "Already authorized");
        authorizedAnchorers[anchorer] = true;
        authorizedAnchorerCount += 1;
        emit AnchorerAuthorized(anchorer);
    }

    /**
     * @notice Revoke a hot key. Refuses to remove the last anchorer so a
     *         rotation mistake cannot brick the contract. To wind it down
     *         deliberately, transfer ownership first.
     */
    function removeAuthorizedAnchorer(address anchorer) external onlyOwner {
        require(authorizedAnchorers[anchorer], "Not authorized");
        require(authorizedAnchorerCount > 1, "Cannot remove last anchorer");
        authorizedAnchorers[anchorer] = false;
        authorizedAnchorerCount -= 1;
        emit AnchorerRevoked(anchorer);
    }

    /**
     * @notice Renouncing ownership is disabled (mirrors
     *         CommitmentRegistry). Always transfer ownership to a multisig
     *         instead so the anchorer set remains rotatable.
     */
    function renounceOwnership() public view override onlyOwner {
        revert("Renounce disabled");
    }

    /**
     * @notice Anchor an off-chain unlock decision.
     * @param commitmentHash keccak256(vaultId || userId || nonce)
     *        Must be non-zero so we fail closed on misconfigured callers
     *        and must not have been anchored before, so reveal anchoring
     *        is end-to-end idempotent (matches the C11 DB invariant).
     */
    function anchorUnlock(bytes32 commitmentHash) external {
        require(
            authorizedAnchorers[msg.sender],
            "VaultAuditLog: unauthorized anchorer"
        );
        require(commitmentHash != bytes32(0), "VaultAuditLog: zero commitment");
        require(
            !anchoredCommitments[commitmentHash],
            "VaultAuditLog: already anchored"
        );
        anchoredCommitments[commitmentHash] = true;
        unlockCount[msg.sender] += 1;
        emit VaultUnlocked(msg.sender, commitmentHash, block.timestamp);
    }
}
