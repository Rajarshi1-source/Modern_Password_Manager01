// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title MockOracle
 * @dev Test-only Chainlink AggregatorV3-compatible mock with a
 *      controllable `updatedAt`. Used by the C4 oracle-staleness
 *      regression tests in `TimeLockedVault.test.js`.
 *
 *      This contract is intentionally NOT deployed to mainnet — Hardhat
 *      picks it up because it lives under `contracts/`, but the deploy
 *      scripts only target `CommitmentRegistry`, `TimeLockedVault`, and
 *      `VaultAuditLog`.
 */
contract MockOracle {
    uint80 public roundId = 1;
    int256 public answer = 2000_00000000; // $2000 in Chainlink 8-decimal format
    uint256 public startedAt;
    uint256 public updatedAt;
    uint80 public answeredInRound = 1;

    constructor() {
        updatedAt = block.timestamp;
        startedAt = block.timestamp;
    }

    /// @notice Set the answer and the (controllable) updatedAt.
    function set(int256 _answer, uint256 _updatedAt) external {
        answer = _answer;
        updatedAt = _updatedAt;
    }

    /// @notice Set the round IDs so we can exercise the
    ///         `answeredInRound < roundId` carry-over check.
    function setRounds(uint80 _roundId, uint80 _answeredInRound) external {
        roundId = _roundId;
        answeredInRound = _answeredInRound;
    }

    function latestRoundData()
        external
        view
        returns (uint80, int256, uint256, uint256, uint80)
    {
        return (roundId, answer, startedAt, updatedAt, answeredInRound);
    }
}
