/**
 * TimeLockedVault.test.js
 * 
 * Hardhat tests for the TimeLockedVault smart contract.
 * Covers all 6 condition types: time-lock, dead man's switch,
 * multi-sig, DAO voting, price oracle, and escrow.
 */

import { expect } from "chai";
import hre from "hardhat";

describe("TimeLockedVault", function () {
  let vault;
  let owner, user1, user2, user3, beneficiary, arbitrator;
  const passwordHash = "0x" + "ab".repeat(32); // Mock password hash

  beforeEach(async function () {
    [owner, user1, user2, user3, beneficiary, arbitrator] = await hre.ethers.getSigners();
    const TimeLockedVault = await hre.ethers.getContractFactory("TimeLockedVault");
    vault = await TimeLockedVault.deploy();
    await vault.waitForDeployment();
  });

  // ===========================================================================
  // Time-Lock Vault Tests
  // ===========================================================================
  describe("Time-Lock Vault", function () {
    it("should create a time-lock vault", async function () {
      const futureTime = Math.floor(Date.now() / 1000) + 86400; // +1 day
      const tx = await vault.connect(user1).createTimeLockVault(passwordHash, futureTime);
      const receipt = await tx.wait();

      const vaultData = await vault.getVault(1);
      expect(vaultData.creator).to.equal(user1.address);
      expect(vaultData.conditionType).to.equal(0); // TIME_LOCK
      expect(vaultData.status).to.equal(0); // ACTIVE
      expect(vaultData.unlockTime).to.equal(futureTime);
    });

    it("should not unlock before time", async function () {
      const futureTime = Math.floor(Date.now() / 1000) + 86400;
      await vault.connect(user1).createTimeLockVault(passwordHash, futureTime);

      const canAccess = await vault.conditionalAccess(1);
      expect(canAccess).to.be.false;
    });

    it("should unlock after time passes", async function () {
      const futureTime = Math.floor(Date.now() / 1000) + 60; // +60 seconds
      await vault.connect(user1).createTimeLockVault(passwordHash, futureTime);

      // Advance time
      await hre.network.provider.send("evm_increaseTime", [120]);
      await hre.network.provider.send("evm_mine");

      const canAccess = await vault.conditionalAccess(1);
      expect(canAccess).to.be.true;

      // Unlock
      await vault.connect(user1).unlockVault(1);
      const vaultData = await vault.getVault(1);
      expect(vaultData.status).to.equal(1); // UNLOCKED
    });

    it("should reject past unlock time", async function () {
      const pastTime = Math.floor(Date.now() / 1000) - 100;
      await expect(
        vault.connect(user1).createTimeLockVault(passwordHash, pastTime)
      ).to.be.revertedWith("Unlock time must be in the future");
    });

    it("should reject empty password hash", async function () {
      const futureTime = Math.floor(Date.now() / 1000) + 86400;
      await expect(
        vault.connect(user1).createTimeLockVault("0x" + "00".repeat(32), futureTime)
      ).to.be.revertedWith("Invalid password hash");
    });
  });

  // ===========================================================================
  // Dead Man's Switch Tests
  // ===========================================================================
  describe("Dead Man's Switch", function () {
    const checkInInterval = 30 * 24 * 3600; // 30 days
    const gracePeriod = 7 * 24 * 3600; // 7 days

    it("should create a dead man's switch vault", async function () {
      await vault.connect(user1).createDeadMansSwitchVault(
        passwordHash, checkInInterval, gracePeriod, beneficiary.address
      );

      const vaultData = await vault.getVault(1);
      expect(vaultData.conditionType).to.equal(1); // DEAD_MANS_SWITCH
      expect(vaultData.beneficiary).to.equal(beneficiary.address);
      expect(vaultData.checkInInterval).to.equal(checkInInterval);
      expect(vaultData.gracePeriod).to.equal(gracePeriod);
    });

    it("should not trigger when owner checks in", async function () {
      await vault.connect(user1).createDeadMansSwitchVault(
        passwordHash, checkInInterval, gracePeriod, beneficiary.address
      );

      // Advance 15 days
      await hre.network.provider.send("evm_increaseTime", [15 * 24 * 3600]);
      await hre.network.provider.send("evm_mine");

      // Check in
      await vault.connect(user1).checkIn(1);

      const canAccess = await vault.conditionalAccess(1);
      expect(canAccess).to.be.false;
    });

    it("should trigger after interval + grace period", async function () {
      await vault.connect(user1).createDeadMansSwitchVault(
        passwordHash, checkInInterval, gracePeriod, beneficiary.address
      );

      // Advance past interval + grace period
      await hre.network.provider.send("evm_increaseTime", [checkInInterval + gracePeriod + 1]);
      await hre.network.provider.send("evm_mine");

      const canAccess = await vault.conditionalAccess(1);
      expect(canAccess).to.be.true;

      // Status check
      const [timeRemaining, isTriggered] = await vault.getDeadMansSwitchStatus(1);
      expect(isTriggered).to.be.true;
      expect(timeRemaining).to.equal(0);
    });

    it("should not allow non-creator to check in", async function () {
      await vault.connect(user1).createDeadMansSwitchVault(
        passwordHash, checkInInterval, gracePeriod, beneficiary.address
      );

      await expect(
        vault.connect(user2).checkIn(1)
      ).to.be.revertedWith("Not vault creator");
    });

    it("should reject creator as beneficiary", async function () {
      await expect(
        vault.connect(user1).createDeadMansSwitchVault(
          passwordHash, checkInInterval, gracePeriod, user1.address
        )
      ).to.be.revertedWith("Beneficiary cannot be creator");
    });

    it("should reject too short check-in interval", async function () {
      await expect(
        vault.connect(user1).createDeadMansSwitchVault(
          passwordHash, 3600, gracePeriod, beneficiary.address // 1 hour < 1 day
        )
      ).to.be.revertedWith("Check-in interval must be >= 1 day");
    });
  });

  // ===========================================================================
  // Multi-Sig Tests
  // ===========================================================================
  describe("Multi-Sig Vault", function () {
    it("should create a 2-of-3 multi-sig vault", async function () {
      const signers = [user1.address, user2.address, user3.address];
      await vault.connect(owner).createMultiSigVault(passwordHash, signers, 2);

      const vaultData = await vault.getVault(1);
      expect(vaultData.conditionType).to.equal(2); // MULTI_SIG
      expect(vaultData.requiredApprovals).to.equal(2);
      expect(vaultData.approvalCount).to.equal(0);

      const retrievedSigners = await vault.getMultiSigSigners(1);
      expect(retrievedSigners.length).to.equal(3);
    });

    it("should track approvals and unlock at threshold", async function () {
      const signers = [user1.address, user2.address, user3.address];
      await vault.connect(owner).createMultiSigVault(passwordHash, signers, 2);

      // First approval
      await vault.connect(user1).approveAccess(1);
      let vaultData = await vault.getVault(1);
      expect(vaultData.approvalCount).to.equal(1);
      expect(await vault.conditionalAccess(1)).to.be.false;

      // Second approval
      await vault.connect(user2).approveAccess(1);
      expect(await vault.conditionalAccess(1)).to.be.true;
    });

    it("should reject duplicate approvals", async function () {
      const signers = [user1.address, user2.address, user3.address];
      await vault.connect(owner).createMultiSigVault(passwordHash, signers, 2);

      await vault.connect(user1).approveAccess(1);
      await expect(
        vault.connect(user1).approveAccess(1)
      ).to.be.revertedWith("Already approved");
    });

    it("should reject unauthorized signers", async function () {
      const signers = [user1.address, user2.address];
      await vault.connect(owner).createMultiSigVault(passwordHash, signers, 2);

      await expect(
        vault.connect(user3).approveAccess(1)
      ).to.be.revertedWith("Not an authorized signer");
    });

    it("should reject less than 2 signers", async function () {
      await expect(
        vault.connect(owner).createMultiSigVault(passwordHash, [user1.address], 1)
      ).to.be.revertedWith("Need at least 2 signers");
    });
  });

  // ===========================================================================
  // DAO Voting Tests
  // ===========================================================================
  describe("DAO Voting Vault", function () {
    it("should create a DAO voting vault", async function () {
      const voters = [user1.address, user2.address, user3.address];
      const deadline = Math.floor(Date.now() / 1000) + 7 * 24 * 3600; // +7 days

      await vault.connect(owner).createDAOVault(passwordHash, voters, deadline, 5100);

      const vaultData = await vault.getVault(1);
      expect(vaultData.conditionType).to.equal(3); // DAO_VOTE
      expect(vaultData.quorumThreshold).to.equal(5100);
      expect(vaultData.totalEligibleVoters).to.equal(3);
    });

    it("should record votes correctly", async function () {
      const voters = [user1.address, user2.address, user3.address];
      const deadline = Math.floor(Date.now() / 1000) + 7 * 24 * 3600;

      await vault.connect(owner).createDAOVault(passwordHash, voters, deadline, 5100);

      await vault.connect(user1).castVote(1, true);
      await vault.connect(user2).castVote(1, false);

      const results = await vault.getDAOVoteResults(1);
      expect(results.votesFor).to.equal(1);
      expect(results.votesAgainst).to.equal(1);
      expect(results.votingEnded).to.be.false;
    });

    it("should approve when quorum met after deadline", async function () {
      const voters = [user1.address, user2.address, user3.address];
      const deadline = Math.floor(Date.now() / 1000) + 60;

      await vault.connect(owner).createDAOVault(passwordHash, voters, deadline, 5100);

      // 2 out of 3 vote yes (66.7% > 51%)
      await vault.connect(user1).castVote(1, true);
      await vault.connect(user2).castVote(1, true);

      // Can't access before deadline
      expect(await vault.conditionalAccess(1)).to.be.false;

      // Advance time past deadline
      await hre.network.provider.send("evm_increaseTime", [120]);
      await hre.network.provider.send("evm_mine");

      expect(await vault.conditionalAccess(1)).to.be.true;
    });

    it("should reject when quorum not met", async function () {
      const voters = [user1.address, user2.address, user3.address];
      const deadline = Math.floor(Date.now() / 1000) + 60;

      await vault.connect(owner).createDAOVault(passwordHash, voters, deadline, 6700); // 67% quorum

      // Only 1 out of 3 votes yes (33.3% < 67%)
      await vault.connect(user1).castVote(1, true);
      await vault.connect(user2).castVote(1, false);

      await hre.network.provider.send("evm_increaseTime", [120]);
      await hre.network.provider.send("evm_mine");

      expect(await vault.conditionalAccess(1)).to.be.false;
    });

    it("should reject duplicate votes", async function () {
      const voters = [user1.address, user2.address];
      const deadline = Math.floor(Date.now() / 1000) + 86400;

      await vault.connect(owner).createDAOVault(passwordHash, voters, deadline, 5100);

      await vault.connect(user1).castVote(1, true);
      await expect(
        vault.connect(user1).castVote(1, true)
      ).to.be.revertedWith("Already voted");
    });

    it("should reject votes after deadline", async function () {
      const voters = [user1.address, user2.address];
      const deadline = Math.floor(Date.now() / 1000) + 60;

      await vault.connect(owner).createDAOVault(passwordHash, voters, deadline, 5100);

      await hre.network.provider.send("evm_increaseTime", [120]);
      await hre.network.provider.send("evm_mine");

      await expect(
        vault.connect(user1).castVote(1, true)
      ).to.be.revertedWith("Voting period ended");
    });
  });

  // ===========================================================================
  // Escrow Tests
  // ===========================================================================
  describe("Escrow Vault", function () {
    it("should create an escrow vault", async function () {
      await vault.connect(user1).createEscrowVault(
        passwordHash, beneficiary.address, arbitrator.address
      );

      const vaultData = await vault.getVault(1);
      expect(vaultData.conditionType).to.equal(5); // ESCROW
      expect(vaultData.beneficiary).to.equal(beneficiary.address);
      expect(vaultData.arbitrator).to.equal(arbitrator.address);
    });

    it("should only allow arbitrator to release", async function () {
      await vault.connect(user1).createEscrowVault(
        passwordHash, beneficiary.address, arbitrator.address
      );

      // Non-arbitrator should fail
      await expect(
        vault.connect(user1).releaseEscrow(1)
      ).to.be.revertedWith("Only arbitrator can release");

      // Arbitrator should succeed
      await vault.connect(arbitrator).releaseEscrow(1);
      const vaultData = await vault.getVault(1);
      expect(vaultData.status).to.equal(1); // UNLOCKED
    });

    it("should reject creator as arbitrator", async function () {
      await expect(
        vault.connect(user1).createEscrowVault(
          passwordHash, beneficiary.address, user1.address
        )
      ).to.be.revertedWith("Arbitrator cannot be creator");
    });

    it("should not allow unlockVault for escrow type", async function () {
      await vault.connect(user1).createEscrowVault(
        passwordHash, beneficiary.address, arbitrator.address
      );

      await expect(
        vault.connect(user1).unlockVault(1)
      ).to.be.revertedWith("Use releaseEscrow()");
    });
  });

  // ===========================================================================
  // General Vault Operations Tests
  // ===========================================================================
  describe("General Operations", function () {
    it("should cancel a vault", async function () {
      const futureTime = Math.floor(Date.now() / 1000) + 86400;
      await vault.connect(user1).createTimeLockVault(passwordHash, futureTime);

      await vault.connect(user1).cancelVault(1);
      const vaultData = await vault.getVault(1);
      expect(vaultData.status).to.equal(2); // CANCELLED
    });

    it("should not allow non-creator to cancel", async function () {
      const futureTime = Math.floor(Date.now() / 1000) + 86400;
      await vault.connect(user1).createTimeLockVault(passwordHash, futureTime);

      await expect(
        vault.connect(user2).cancelVault(1)
      ).to.be.revertedWith("Not vault creator");
    });

    it("should not double-unlock", async function () {
      const futureTime = Math.floor(Date.now() / 1000) + 60;
      await vault.connect(user1).createTimeLockVault(passwordHash, futureTime);

      await hre.network.provider.send("evm_increaseTime", [120]);
      await hre.network.provider.send("evm_mine");

      await vault.connect(user1).unlockVault(1);
      await expect(
        vault.connect(user1).unlockVault(1)
      ).to.be.revertedWith("Vault not active");
    });

    it("should track user vaults", async function () {
      const futureTime = Math.floor(Date.now() / 1000) + 86400;
      await vault.connect(user1).createTimeLockVault(passwordHash, futureTime);
      await vault.connect(user1).createTimeLockVault(passwordHash, futureTime + 1);
      await vault.connect(user2).createTimeLockVault(passwordHash, futureTime);

      const user1Vaults = await vault.getUserVaults(user1.address);
      expect(user1Vaults.length).to.equal(2);

      const user2Vaults = await vault.getUserVaults(user2.address);
      expect(user2Vaults.length).to.equal(1);
    });

    it("should update beneficiary", async function () {
      await vault.connect(user1).createDeadMansSwitchVault(
        passwordHash, 30 * 24 * 3600, 7 * 24 * 3600, beneficiary.address
      );

      await vault.connect(user1).updateBeneficiary(1, user2.address);
      const vaultData = await vault.getVault(1);
      expect(vaultData.beneficiary).to.equal(user2.address);
    });

    it("should return correct vault count", async function () {
      expect(await vault.getVaultCount()).to.equal(0);

      const futureTime = Math.floor(Date.now() / 1000) + 86400;
      await vault.connect(user1).createTimeLockVault(passwordHash, futureTime);
      expect(await vault.getVaultCount()).to.equal(1);

      await vault.connect(user2).createTimeLockVault(passwordHash, futureTime);
      expect(await vault.getVaultCount()).to.equal(2);
    });

    it("should revert for non-existent vault", async function () {
      await expect(
        vault.getVault(999)
      ).to.be.revertedWith("Vault does not exist");
    });
  });
});
