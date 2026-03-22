// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title TimeLockedVault
 * @dev Smart contract for conditional password access automation
 * @notice Supports time-locks, dead man's switch, multi-sig, DAO voting,
 *         oracle price conditions, and escrow-based password release.
 *
 * Use Cases:
 *   - Dead man's switch (blockchain-verified)
 *   - Time-locked inheritance
 *   - Escrow passwords with trusted arbitrator
 *   - Multi-sig password access (M-of-N)
 *   - DAO governance voting for access
 *   - Oracle-driven conditional access (e.g., ETH price threshold)
 */
contract TimeLockedVault is Ownable, ReentrancyGuard {

    // =========================================================================
    // Enums
    // =========================================================================

    enum ConditionType {
        TIME_LOCK,          // Unlock after a specific timestamp
        DEAD_MANS_SWITCH,   // Unlock if owner doesn't check in within interval
        MULTI_SIG,          // M-of-N approvals required
        DAO_VOTE,           // Community voting approval
        PRICE_ORACLE,       // Unlock when asset price crosses threshold
        ESCROW              // Arbitrator-controlled release
    }

    enum VaultStatus {
        ACTIVE,
        UNLOCKED,
        CANCELLED,
        EXPIRED
    }

    enum VoteChoice {
        NONE,
        APPROVE,
        REJECT
    }

    // =========================================================================
    // Structs
    // =========================================================================

    struct Vault {
        uint256 id;
        address creator;
        bytes32 passwordHash;       // Keccak256 hash of encrypted password
        ConditionType conditionType;
        VaultStatus status;
        uint256 createdAt;
        uint256 updatedAt;
        // Time-lock fields
        uint256 unlockTime;
        // Dead man's switch fields
        uint256 checkInInterval;    // Seconds between required check-ins
        uint256 lastCheckIn;
        uint256 gracePeriod;        // Extra seconds after missed check-in
        address beneficiary;
        // Multi-sig fields
        uint256 requiredApprovals;
        uint256 approvalCount;
        // DAO voting fields
        uint256 votingDeadline;
        uint256 quorumThreshold;    // Basis points (e.g., 5100 = 51%)
        uint256 votesFor;
        uint256 votesAgainst;
        uint256 totalEligibleVoters;
        // Price oracle fields
        uint256 priceThreshold;     // Price in 8 decimals (Chainlink format)
        bool priceAbove;            // true = unlock when price > threshold
        address oracleAddress;
        // Escrow fields
        address arbitrator;
        bool exists;
    }

    // =========================================================================
    // State Variables
    // =========================================================================

    uint256 public nextVaultId;
    mapping(uint256 => Vault) public vaults;

    // Multi-sig: vaultId => signer => approved
    mapping(uint256 => mapping(address => bool)) public multiSigApprovals;
    // Multi-sig: vaultId => array of authorized signers
    mapping(uint256 => address[]) public multiSigSigners;

    // DAO: vaultId => voter => vote choice
    mapping(uint256 => mapping(address => VoteChoice)) public daoVotes;
    // DAO: vaultId => array of eligible voters
    mapping(uint256 => address[]) public daoVoters;

    // User => array of vault IDs they created
    mapping(address => uint256[]) public userVaults;

    // =========================================================================
    // Events
    // =========================================================================

    event VaultCreated(
        uint256 indexed vaultId,
        address indexed creator,
        ConditionType conditionType,
        uint256 createdAt
    );

    event VaultUnlocked(
        uint256 indexed vaultId,
        address indexed unlockedBy,
        uint256 unlockedAt
    );

    event VaultCancelled(
        uint256 indexed vaultId,
        address indexed cancelledBy,
        uint256 cancelledAt
    );

    event CheckIn(
        uint256 indexed vaultId,
        address indexed owner,
        uint256 checkedInAt,
        uint256 nextDeadline
    );

    event MultiSigApproval(
        uint256 indexed vaultId,
        address indexed signer,
        uint256 currentApprovals,
        uint256 requiredApprovals
    );

    event DAOVoteCast(
        uint256 indexed vaultId,
        address indexed voter,
        VoteChoice choice,
        uint256 votesFor,
        uint256 votesAgainst
    );

    event EscrowReleased(
        uint256 indexed vaultId,
        address indexed arbitrator,
        address indexed beneficiary,
        uint256 releasedAt
    );

    event BeneficiaryUpdated(
        uint256 indexed vaultId,
        address indexed oldBeneficiary,
        address indexed newBeneficiary
    );

    // =========================================================================
    // Modifiers
    // =========================================================================

    modifier vaultExists(uint256 _vaultId) {
        require(vaults[_vaultId].exists, "Vault does not exist");
        _;
    }

    modifier onlyVaultCreator(uint256 _vaultId) {
        require(vaults[_vaultId].creator == msg.sender, "Not vault creator");
        _;
    }

    modifier vaultActive(uint256 _vaultId) {
        require(vaults[_vaultId].status == VaultStatus.ACTIVE, "Vault not active");
        _;
    }

    // =========================================================================
    // Constructor
    // =========================================================================

    constructor() Ownable(msg.sender) {
        nextVaultId = 1;
    }

    // =========================================================================
    // Vault Creation Functions
    // =========================================================================

    /**
     * @notice Create a time-locked vault that unlocks after a specific timestamp
     * @param _passwordHash Hash of the encrypted password
     * @param _unlockTime Unix timestamp when the vault unlocks
     */
    function createTimeLockVault(
        bytes32 _passwordHash,
        uint256 _unlockTime
    ) external returns (uint256) {
        require(_unlockTime > block.timestamp, "Unlock time must be in the future");
        require(_passwordHash != bytes32(0), "Invalid password hash");

        uint256 vaultId = nextVaultId++;
        Vault storage v = vaults[vaultId];

        v.id = vaultId;
        v.creator = msg.sender;
        v.passwordHash = _passwordHash;
        v.conditionType = ConditionType.TIME_LOCK;
        v.status = VaultStatus.ACTIVE;
        v.createdAt = block.timestamp;
        v.updatedAt = block.timestamp;
        v.unlockTime = _unlockTime;
        v.exists = true;

        userVaults[msg.sender].push(vaultId);

        emit VaultCreated(vaultId, msg.sender, ConditionType.TIME_LOCK, block.timestamp);
        return vaultId;
    }

    /**
     * @notice Create a dead man's switch vault
     * @param _passwordHash Hash of the encrypted password
     * @param _checkInInterval Seconds between required check-ins
     * @param _gracePeriod Extra seconds after a missed check-in before release
     * @param _beneficiary Address that receives access on switch trigger
     */
    function createDeadMansSwitchVault(
        bytes32 _passwordHash,
        uint256 _checkInInterval,
        uint256 _gracePeriod,
        address _beneficiary
    ) external returns (uint256) {
        require(_checkInInterval >= 1 days, "Check-in interval must be >= 1 day");
        require(_gracePeriod >= 1 hours, "Grace period must be >= 1 hour");
        require(_beneficiary != address(0), "Invalid beneficiary");
        require(_beneficiary != msg.sender, "Beneficiary cannot be creator");
        require(_passwordHash != bytes32(0), "Invalid password hash");

        uint256 vaultId = nextVaultId++;
        Vault storage v = vaults[vaultId];

        v.id = vaultId;
        v.creator = msg.sender;
        v.passwordHash = _passwordHash;
        v.conditionType = ConditionType.DEAD_MANS_SWITCH;
        v.status = VaultStatus.ACTIVE;
        v.createdAt = block.timestamp;
        v.updatedAt = block.timestamp;
        v.checkInInterval = _checkInInterval;
        v.lastCheckIn = block.timestamp;
        v.gracePeriod = _gracePeriod;
        v.beneficiary = _beneficiary;
        v.exists = true;

        userVaults[msg.sender].push(vaultId);

        emit VaultCreated(vaultId, msg.sender, ConditionType.DEAD_MANS_SWITCH, block.timestamp);
        return vaultId;
    }

    /**
     * @notice Create a multi-sig vault requiring M-of-N approvals
     * @param _passwordHash Hash of the encrypted password
     * @param _signers Array of authorized signer addresses
     * @param _requiredApprovals Number of approvals needed (M)
     */
    function createMultiSigVault(
        bytes32 _passwordHash,
        address[] calldata _signers,
        uint256 _requiredApprovals
    ) external returns (uint256) {
        require(_signers.length >= 2, "Need at least 2 signers");
        require(_signers.length <= 10, "Max 10 signers");
        require(_requiredApprovals >= 1, "Need at least 1 approval");
        require(_requiredApprovals <= _signers.length, "Required > total signers");
        require(_passwordHash != bytes32(0), "Invalid password hash");

        uint256 vaultId = nextVaultId++;
        Vault storage v = vaults[vaultId];

        v.id = vaultId;
        v.creator = msg.sender;
        v.passwordHash = _passwordHash;
        v.conditionType = ConditionType.MULTI_SIG;
        v.status = VaultStatus.ACTIVE;
        v.createdAt = block.timestamp;
        v.updatedAt = block.timestamp;
        v.requiredApprovals = _requiredApprovals;
        v.approvalCount = 0;
        v.exists = true;

        multiSigSigners[vaultId] = _signers;
        userVaults[msg.sender].push(vaultId);

        emit VaultCreated(vaultId, msg.sender, ConditionType.MULTI_SIG, block.timestamp);
        return vaultId;
    }

    /**
     * @notice Create a DAO voting vault
     * @param _passwordHash Hash of the encrypted password
     * @param _voters Array of eligible voter addresses
     * @param _votingDeadline Unix timestamp when voting ends
     * @param _quorumThreshold Quorum in basis points (5100 = 51%)
     */
    function createDAOVault(
        bytes32 _passwordHash,
        address[] calldata _voters,
        uint256 _votingDeadline,
        uint256 _quorumThreshold
    ) external returns (uint256) {
        require(_voters.length >= 1, "Need at least 1 voter");
        require(_votingDeadline > block.timestamp, "Deadline must be in the future");
        require(_quorumThreshold > 0 && _quorumThreshold <= 10000, "Quorum: 1-10000 bps");
        require(_passwordHash != bytes32(0), "Invalid password hash");

        uint256 vaultId = nextVaultId++;
        Vault storage v = vaults[vaultId];

        v.id = vaultId;
        v.creator = msg.sender;
        v.passwordHash = _passwordHash;
        v.conditionType = ConditionType.DAO_VOTE;
        v.status = VaultStatus.ACTIVE;
        v.createdAt = block.timestamp;
        v.updatedAt = block.timestamp;
        v.votingDeadline = _votingDeadline;
        v.quorumThreshold = _quorumThreshold;
        v.votesFor = 0;
        v.votesAgainst = 0;
        v.totalEligibleVoters = _voters.length;
        v.exists = true;

        daoVoters[vaultId] = _voters;
        userVaults[msg.sender].push(vaultId);

        emit VaultCreated(vaultId, msg.sender, ConditionType.DAO_VOTE, block.timestamp);
        return vaultId;
    }

    /**
     * @notice Create a price oracle vault that unlocks based on asset price
     * @param _passwordHash Hash of the encrypted password
     * @param _oracleAddress Chainlink price feed contract address
     * @param _priceThreshold Price threshold (8 decimals, Chainlink format)
     * @param _priceAbove true = unlock when price > threshold; false = price < threshold
     */
    function createPriceOracleVault(
        bytes32 _passwordHash,
        address _oracleAddress,
        uint256 _priceThreshold,
        bool _priceAbove
    ) external returns (uint256) {
        require(_oracleAddress != address(0), "Invalid oracle address");
        require(_priceThreshold > 0, "Price threshold must be > 0");
        require(_passwordHash != bytes32(0), "Invalid password hash");

        uint256 vaultId = nextVaultId++;
        Vault storage v = vaults[vaultId];

        v.id = vaultId;
        v.creator = msg.sender;
        v.passwordHash = _passwordHash;
        v.conditionType = ConditionType.PRICE_ORACLE;
        v.status = VaultStatus.ACTIVE;
        v.createdAt = block.timestamp;
        v.updatedAt = block.timestamp;
        v.priceThreshold = _priceThreshold;
        v.priceAbove = _priceAbove;
        v.oracleAddress = _oracleAddress;
        v.exists = true;

        userVaults[msg.sender].push(vaultId);

        emit VaultCreated(vaultId, msg.sender, ConditionType.PRICE_ORACLE, block.timestamp);
        return vaultId;
    }

    /**
     * @notice Create an escrow vault with a trusted arbitrator
     * @param _passwordHash Hash of the encrypted password
     * @param _beneficiary Beneficiary who receives access
     * @param _arbitrator Trusted arbitrator who can release the vault
     */
    function createEscrowVault(
        bytes32 _passwordHash,
        address _beneficiary,
        address _arbitrator
    ) external returns (uint256) {
        require(_beneficiary != address(0), "Invalid beneficiary");
        require(_arbitrator != address(0), "Invalid arbitrator");
        require(_arbitrator != msg.sender, "Arbitrator cannot be creator");
        require(_beneficiary != _arbitrator, "Beneficiary cannot be arbitrator");
        require(_passwordHash != bytes32(0), "Invalid password hash");

        uint256 vaultId = nextVaultId++;
        Vault storage v = vaults[vaultId];

        v.id = vaultId;
        v.creator = msg.sender;
        v.passwordHash = _passwordHash;
        v.conditionType = ConditionType.ESCROW;
        v.status = VaultStatus.ACTIVE;
        v.createdAt = block.timestamp;
        v.updatedAt = block.timestamp;
        v.beneficiary = _beneficiary;
        v.arbitrator = _arbitrator;
        v.exists = true;

        userVaults[msg.sender].push(vaultId);

        emit VaultCreated(vaultId, msg.sender, ConditionType.ESCROW, block.timestamp);
        return vaultId;
    }

    // =========================================================================
    // Condition Evaluation
    // =========================================================================

    /**
     * @notice Evaluate whether a vault's conditions are met
     * @param _vaultId Vault ID to evaluate
     * @return met Whether the condition is satisfied
     */
    function conditionalAccess(uint256 _vaultId)
        public
        view
        vaultExists(_vaultId)
        returns (bool met)
    {
        Vault storage v = vaults[_vaultId];

        if (v.status != VaultStatus.ACTIVE) {
            return v.status == VaultStatus.UNLOCKED;
        }

        if (v.conditionType == ConditionType.TIME_LOCK) {
            return block.timestamp >= v.unlockTime;
        }

        if (v.conditionType == ConditionType.DEAD_MANS_SWITCH) {
            uint256 deadline = v.lastCheckIn + v.checkInInterval + v.gracePeriod;
            return block.timestamp > deadline;
        }

        if (v.conditionType == ConditionType.MULTI_SIG) {
            return v.approvalCount >= v.requiredApprovals;
        }

        if (v.conditionType == ConditionType.DAO_VOTE) {
            if (block.timestamp < v.votingDeadline) return false;
            uint256 totalVotes = v.votesFor + v.votesAgainst;
            if (totalVotes == 0) return false;
            // Check quorum: (votesFor / totalEligible) >= quorum
            // Using basis points to avoid decimals
            uint256 approvalBps = (v.votesFor * 10000) / v.totalEligibleVoters;
            return approvalBps >= v.quorumThreshold;
        }

        if (v.conditionType == ConditionType.PRICE_ORACLE) {
            return _checkOraclePrice(v.oracleAddress, v.priceThreshold, v.priceAbove);
        }

        // ESCROW: only arbitrator can release (handled in releaseEscrow)
        return false;
    }

    // =========================================================================
    // Action Functions
    // =========================================================================

    /**
     * @notice Attempt to unlock a vault (evaluates conditions on-chain)
     * @param _vaultId Vault ID to unlock
     */
    function unlockVault(uint256 _vaultId)
        external
        nonReentrant
        vaultExists(_vaultId)
        vaultActive(_vaultId)
    {
        Vault storage v = vaults[_vaultId];

        // Escrow vaults can only be unlocked by the arbitrator
        require(v.conditionType != ConditionType.ESCROW, "Use releaseEscrow()");

        require(conditionalAccess(_vaultId), "Conditions not met");

        v.status = VaultStatus.UNLOCKED;
        v.updatedAt = block.timestamp;

        emit VaultUnlocked(_vaultId, msg.sender, block.timestamp);
    }

    /**
     * @notice Dead man's switch check-in (resets the countdown)
     * @param _vaultId Vault ID to check in for
     */
    function checkIn(uint256 _vaultId)
        external
        vaultExists(_vaultId)
        onlyVaultCreator(_vaultId)
        vaultActive(_vaultId)
    {
        Vault storage v = vaults[_vaultId];
        require(v.conditionType == ConditionType.DEAD_MANS_SWITCH, "Not a dead man's switch vault");

        v.lastCheckIn = block.timestamp;
        v.updatedAt = block.timestamp;

        uint256 nextDeadline = block.timestamp + v.checkInInterval;
        emit CheckIn(_vaultId, msg.sender, block.timestamp, nextDeadline);
    }

    /**
     * @notice Multi-sig approval from an authorized signer
     * @param _vaultId Vault ID to approve
     */
    function approveAccess(uint256 _vaultId)
        external
        vaultExists(_vaultId)
        vaultActive(_vaultId)
    {
        Vault storage v = vaults[_vaultId];
        require(v.conditionType == ConditionType.MULTI_SIG, "Not a multi-sig vault");
        require(!multiSigApprovals[_vaultId][msg.sender], "Already approved");
        require(_isAuthorizedSigner(_vaultId, msg.sender), "Not an authorized signer");

        multiSigApprovals[_vaultId][msg.sender] = true;
        v.approvalCount++;
        v.updatedAt = block.timestamp;

        emit MultiSigApproval(_vaultId, msg.sender, v.approvalCount, v.requiredApprovals);
    }

    /**
     * @notice Cast a DAO vote on a vault proposal
     * @param _vaultId Vault ID to vote on
     * @param _approve true = vote to approve, false = vote to reject
     */
    function castVote(uint256 _vaultId, bool _approve)
        external
        vaultExists(_vaultId)
        vaultActive(_vaultId)
    {
        Vault storage v = vaults[_vaultId];
        require(v.conditionType == ConditionType.DAO_VOTE, "Not a DAO vote vault");
        require(block.timestamp < v.votingDeadline, "Voting period ended");
        require(daoVotes[_vaultId][msg.sender] == VoteChoice.NONE, "Already voted");
        require(_isEligibleVoter(_vaultId, msg.sender), "Not an eligible voter");

        if (_approve) {
            daoVotes[_vaultId][msg.sender] = VoteChoice.APPROVE;
            v.votesFor++;
        } else {
            daoVotes[_vaultId][msg.sender] = VoteChoice.REJECT;
            v.votesAgainst++;
        }
        v.updatedAt = block.timestamp;

        emit DAOVoteCast(_vaultId, msg.sender, _approve ? VoteChoice.APPROVE : VoteChoice.REJECT, v.votesFor, v.votesAgainst);
    }

    /**
     * @notice Release an escrow vault (arbitrator only)
     * @param _vaultId Vault ID to release
     */
    function releaseEscrow(uint256 _vaultId)
        external
        nonReentrant
        vaultExists(_vaultId)
        vaultActive(_vaultId)
    {
        Vault storage v = vaults[_vaultId];
        require(v.conditionType == ConditionType.ESCROW, "Not an escrow vault");
        require(msg.sender == v.arbitrator, "Only arbitrator can release");

        v.status = VaultStatus.UNLOCKED;
        v.updatedAt = block.timestamp;

        emit EscrowReleased(_vaultId, msg.sender, v.beneficiary, block.timestamp);
        emit VaultUnlocked(_vaultId, msg.sender, block.timestamp);
    }

    /**
     * @notice Cancel a vault (creator only, vault must be active)
     * @param _vaultId Vault ID to cancel
     */
    function cancelVault(uint256 _vaultId)
        external
        vaultExists(_vaultId)
        onlyVaultCreator(_vaultId)
        vaultActive(_vaultId)
    {
        Vault storage v = vaults[_vaultId];
        v.status = VaultStatus.CANCELLED;
        v.updatedAt = block.timestamp;

        emit VaultCancelled(_vaultId, msg.sender, block.timestamp);
    }

    /**
     * @notice Update beneficiary for dead man's switch or escrow vault
     * @param _vaultId Vault ID
     * @param _newBeneficiary New beneficiary address
     */
    function updateBeneficiary(uint256 _vaultId, address _newBeneficiary)
        external
        vaultExists(_vaultId)
        onlyVaultCreator(_vaultId)
        vaultActive(_vaultId)
    {
        require(_newBeneficiary != address(0), "Invalid beneficiary");
        require(_newBeneficiary != msg.sender, "Beneficiary cannot be creator");

        Vault storage v = vaults[_vaultId];
        require(
            v.conditionType == ConditionType.DEAD_MANS_SWITCH ||
            v.conditionType == ConditionType.ESCROW,
            "Vault type does not have beneficiary"
        );

        address old = v.beneficiary;
        v.beneficiary = _newBeneficiary;
        v.updatedAt = block.timestamp;

        emit BeneficiaryUpdated(_vaultId, old, _newBeneficiary);
    }

    // =========================================================================
    // View Functions
    // =========================================================================

    /**
     * @notice Get vault details
     */
    function getVault(uint256 _vaultId)
        external
        view
        vaultExists(_vaultId)
        returns (Vault memory)
    {
        return vaults[_vaultId];
    }

    /**
     * @notice Get all vault IDs for a user
     */
    function getUserVaults(address _user) external view returns (uint256[] memory) {
        return userVaults[_user];
    }

    /**
     * @notice Get multi-sig signers for a vault
     */
    function getMultiSigSigners(uint256 _vaultId) external view returns (address[] memory) {
        return multiSigSigners[_vaultId];
    }

    /**
     * @notice Get DAO voters for a vault
     */
    function getDAOVoters(uint256 _vaultId) external view returns (address[] memory) {
        return daoVoters[_vaultId];
    }

    /**
     * @notice Get dead man's switch time remaining
     * @return timeRemaining Seconds until switch triggers (0 if already triggered)
     * @return isTriggered Whether the switch has been triggered
     */
    function getDeadMansSwitchStatus(uint256 _vaultId)
        external
        view
        vaultExists(_vaultId)
        returns (uint256 timeRemaining, bool isTriggered)
    {
        Vault storage v = vaults[_vaultId];
        require(v.conditionType == ConditionType.DEAD_MANS_SWITCH, "Not a DMS vault");

        uint256 deadline = v.lastCheckIn + v.checkInInterval + v.gracePeriod;
        if (block.timestamp > deadline) {
            return (0, true);
        }
        return (deadline - block.timestamp, false);
    }

    /**
     * @notice Get DAO voting results
     */
    function getDAOVoteResults(uint256 _vaultId)
        external
        view
        vaultExists(_vaultId)
        returns (
            uint256 votesFor,
            uint256 votesAgainst,
            uint256 totalEligible,
            uint256 quorumThreshold,
            bool votingEnded,
            bool conditionMet
        )
    {
        Vault storage v = vaults[_vaultId];
        require(v.conditionType == ConditionType.DAO_VOTE, "Not a DAO vault");

        votesFor = v.votesFor;
        votesAgainst = v.votesAgainst;
        totalEligible = v.totalEligibleVoters;
        quorumThreshold = v.quorumThreshold;
        votingEnded = block.timestamp >= v.votingDeadline;

        if (votingEnded && v.totalEligibleVoters > 0) {
            uint256 approvalBps = (v.votesFor * 10000) / v.totalEligibleVoters;
            conditionMet = approvalBps >= v.quorumThreshold;
        }
    }

    /**
     * @notice Get total vault count
     */
    function getVaultCount() external view returns (uint256) {
        return nextVaultId - 1;
    }

    // =========================================================================
    // Internal Functions
    // =========================================================================

    /**
     * @dev Check if an address is an authorized multi-sig signer
     */
    function _isAuthorizedSigner(uint256 _vaultId, address _signer)
        internal
        view
        returns (bool)
    {
        address[] storage signers = multiSigSigners[_vaultId];
        for (uint256 i = 0; i < signers.length; i++) {
            if (signers[i] == _signer) return true;
        }
        return false;
    }

    /**
     * @dev Check if an address is an eligible DAO voter
     */
    function _isEligibleVoter(uint256 _vaultId, address _voter)
        internal
        view
        returns (bool)
    {
        address[] storage voters = daoVoters[_vaultId];
        for (uint256 i = 0; i < voters.length; i++) {
            if (voters[i] == _voter) return true;
        }
        return false;
    }

    /**
     * @dev Check Chainlink oracle price against threshold
     * @notice Uses a static call to the Chainlink AggregatorV3 interface
     */
    function _checkOraclePrice(
        address _oracle,
        uint256 _threshold,
        bool _above
    ) internal view returns (bool) {
        // Chainlink AggregatorV3Interface.latestRoundData() selector
        // Returns: (roundId, answer, startedAt, updatedAt, answeredInRound)
        (bool success, bytes memory data) = _oracle.staticcall(
            abi.encodeWithSignature("latestRoundData()")
        );

        if (!success || data.length < 160) {
            return false; // Oracle call failed, condition not met
        }

        // Decode the answer (2nd return value)
        (, int256 answer,,,) = abi.decode(data, (uint80, int256, uint256, uint256, uint80));

        if (answer <= 0) return false;

        uint256 price = uint256(answer);

        if (_above) {
            return price > _threshold;
        } else {
            return price < _threshold;
        }
    }
}
