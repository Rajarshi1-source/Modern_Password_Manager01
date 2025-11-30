// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

/**
 * @title CommitmentRegistry
 * @dev Registry for anchoring behavioral commitment batches to Arbitrum blockchain
 * @notice Uses Merkle tree batching to reduce gas costs (1000 commitments per batch)
 */
contract CommitmentRegistry is Ownable {
    using ECDSA for bytes32;

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

    /// @dev Events
    event CommitmentAnchored(
        bytes32 indexed merkleRoot,
        uint256 timestamp,
        uint256 batchSize,
        address indexed submitter
    );

    event CommitmentVerified(
        bytes32 indexed merkleRoot,
        bytes32 indexed leafHash,
        bool valid
    );

    /**
     * @dev Constructor - initializes contract with owner
     */
    constructor() Ownable(msg.sender) {}

    /**
     * @notice Anchor a batch of commitments to the blockchain
     * @param merkleRoot Root hash of the Merkle tree containing all commitments
     * @param batchSize Number of commitments in the batch
     * @param signature ECDSA signature for anti-spam protection
     */
    function anchorCommitment(
        bytes32 merkleRoot,
        uint256 batchSize,
        bytes calldata signature
    ) external onlyOwner {
        require(batchSize > 0 && batchSize <= 10000, "Invalid batch size");
        require(!commitments[merkleRoot].exists, "Already anchored");

        // Verify signature (additional security layer)
        bytes32 messageHash = keccak256(
            abi.encodePacked(merkleRoot, batchSize)
        );
        address signer = messageHash.toEthSignedMessageHash().recover(signature);
        require(signer == owner(), "Invalid signature");

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
     * @notice Verify that a specific commitment exists in a Merkle tree batch
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

        bool isValid = computedHash == merkleRoot;

        emit CommitmentVerified(merkleRoot, leafHash, isValid);

        return isValid;
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

