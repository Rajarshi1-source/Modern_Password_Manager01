// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";

/**
 * @title CommitmentRegistry
 * @dev Registry for anchoring behavioral commitment batches to Arbitrum blockchain
 * @notice Uses Merkle tree batching to reduce gas costs (1000 commitments per batch)
 *
 * Security model (post-audit):
 *   - `verifyCommitment` is a free, private `view`. It does NOT emit an event
 *     so external indexers cannot learn which leaves are being probed.
 *   - `anchorCommitment` is permissionless at the transaction level; the
 *     batch is only accepted if it is signed by an address recorded in
 *     `authorizedSigners`. This separates the broadcaster (any address
 *     holding gas) from the authorization key, allowing the latter to live
 *     in a KMS/HSM while the former is a hot wallet.
 *   - `owner()` administers the `authorizedSigners` set and otherwise has no
 *     write authority over anchored data.
 */
contract CommitmentRegistry is Ownable {
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;

    /// @dev Commitment structure for batch anchoring
    struct Commitment {
        bytes32 merkleRoot;      // Root of Merkle tree batch
        uint256 timestamp;        // Block timestamp when anchored
        uint256 batchSize;        // Number of commitments in batch
        address submitter;        // Address that submitted the batch
        bool exists;              // Existence flag
    }

    /// @dev Mapping from Merkle root to commitment details
    mapping(bytes32 => Commitment) public commitments;

    /// @dev Mapping from submitter address to their Merkle roots
    mapping(address => bytes32[]) public submitterCommitments;

    /// @dev Addresses authorized to sign anchor requests. Independent of
    ///      `owner()` so the contract owner can rotate the hot signer
    ///      without redeployment.
    mapping(address => bool) public authorizedSigners;

    /// @dev Number of currently-authorized signers. Maintained alongside
    ///      `authorizedSigners` so `removeAuthorizedSigner` can refuse to
    ///      remove the last one (otherwise the registry would be bricked:
    ///      no signer could anchor and `owner()` is not itself authorized
    ///      to sign unless explicitly added). Added per CodeRabbit review.
    uint256 public authorizedSignerCount;

    /// @dev Events
    event CommitmentAnchored(
        bytes32 indexed merkleRoot,
        uint256 timestamp,
        uint256 batchSize,
        address indexed submitter
    );

    event SignerAuthorized(address indexed signer);
    event SignerRevoked(address indexed signer);

    /**
     * @dev Constructor - initializes contract with owner; the deployer
     *      becomes both `owner()` and an initial authorized signer.
     */
    constructor() Ownable(msg.sender) {
        authorizedSigners[msg.sender] = true;
        authorizedSignerCount = 1;
        emit SignerAuthorized(msg.sender);
    }

    /**
     * @notice Authorize a new anchor-signing key.
     */
    function addAuthorizedSigner(address signer) external onlyOwner {
        require(signer != address(0), "Invalid signer");
        require(!authorizedSigners[signer], "Already authorized");
        authorizedSigners[signer] = true;
        authorizedSignerCount += 1;
        emit SignerAuthorized(signer);
    }

    /**
     * @notice Revoke an existing anchor-signing key.
     * @dev Refuses to remove the last signer so a key rotation mistake
     *      cannot brick anchoring. To wind the contract down deliberately,
     *      transfer ownership first; do not use this function.
     */
    function removeAuthorizedSigner(address signer) external onlyOwner {
        require(authorizedSigners[signer], "Not authorized");
        require(authorizedSignerCount > 1, "Cannot remove last signer");
        authorizedSigners[signer] = false;
        authorizedSignerCount -= 1;
        emit SignerRevoked(signer);
    }

    /**
     * @notice Renouncing ownership is disabled.
     * @dev If ownership were renounced, no one could ever rotate
     *      `authorizedSigners` again — meaning a compromised hot key
     *      could not be revoked. Always transfer ownership to a multisig
     *      instead of renouncing.
     */
    function renounceOwnership() public view override onlyOwner {
        revert("Renounce disabled");
    }

    /**
     * @notice Anchor a batch of commitments to the blockchain
     * @param merkleRoot Root hash of the Merkle tree containing all commitments
     * @param batchSize Number of commitments in the batch
     * @param signature ECDSA signature over `keccak256(merkleRoot, batchSize)`
     *        produced by an address present in `authorizedSigners`.
     *
     *        The transaction sender (`msg.sender`) is recorded as the
     *        submitter but is NOT required to be authorized. This lets a
     *        gas-funded relayer broadcast on behalf of a KMS-held signer.
     */
    function anchorCommitment(
        bytes32 merkleRoot,
        uint256 batchSize,
        bytes calldata signature
    ) external {
        require(batchSize > 0 && batchSize <= 10000, "Invalid batch size");
        require(!commitments[merkleRoot].exists, "Already anchored");

        // Recover signer and require it is in the authorized set.
        // Bind the signed payload to (chainId, contract address) so a
        // signature minted for one CommitmentRegistry deployment cannot
        // be replayed against another deployment or on a different chain
        // — added per CodeRabbit review. Using `abi.encodePacked` over a
        // fixed-arity set of fixed-size types so the off-chain `solidityKeccak`
        // helper produces the same digest byte-for-byte.
        bytes32 messageHash = keccak256(
            abi.encodePacked(block.chainid, address(this), merkleRoot, batchSize)
        );
        address signer = ECDSA.recover(
            MessageHashUtils.toEthSignedMessageHash(messageHash),
            signature
        );
        require(authorizedSigners[signer], "Unauthorized signer");

        // Store commitment
        commitments[merkleRoot] = Commitment({
            merkleRoot: merkleRoot,
            timestamp: block.timestamp,
            batchSize: batchSize,
            submitter: msg.sender,
            exists: true
        });

        submitterCommitments[msg.sender].push(merkleRoot);

        emit CommitmentAnchored(
            merkleRoot,
            block.timestamp,
            batchSize,
            msg.sender
        );
    }

    /**
     * @notice Verify that a specific commitment exists in a Merkle tree batch.
     * @dev `view` — no state change, no event. Free to call, and external
     *      observers cannot tell which leaves were probed.
     * @param merkleRoot The root of the Merkle tree
     * @param leafHash Hash of the specific commitment to verify
     * @param proof Array of sibling hashes needed for verification
     * @return bool True if the commitment is valid, false otherwise
     */
    function verifyCommitment(
        bytes32 merkleRoot,
        bytes32 leafHash,
        bytes32[] calldata proof
    ) external view returns (bool) {
        require(commitments[merkleRoot].exists, "Root not found");

        bytes32 computedHash = leafHash;

        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 proofElement = proof[i];

            if (computedHash <= proofElement) {
                computedHash = keccak256(
                    abi.encodePacked(computedHash, proofElement)
                );
            } else {
                computedHash = keccak256(
                    abi.encodePacked(proofElement, computedHash)
                );
            }
        }

        return computedHash == merkleRoot;
    }

    /**
     * @notice Get commitment details by Merkle root
     * @param merkleRoot The Merkle root to query
     * @return Commitment structure
     */
    function getCommitment(bytes32 merkleRoot)
        external
        view
        returns (Commitment memory)
    {
        require(commitments[merkleRoot].exists, "Commitment not found");
        return commitments[merkleRoot];
    }

    /**
     * @notice Get all Merkle roots submitted by an address
     * @param submitter The address to query
     * @return Array of Merkle roots
     */
    function getSubmitterCommitments(address submitter)
        external
        view
        returns (bytes32[] memory)
    {
        return submitterCommitments[submitter];
    }

    /**
     * @notice Get total number of batches anchored
     * @param submitter The address to query
     * @return Number of batches
     */
    function getBatchCount(address submitter) external view returns (uint256) {
        return submitterCommitments[submitter].length;
    }
}
