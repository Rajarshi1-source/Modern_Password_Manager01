/**
 * VaultAuditLog.test.js
 *
 * Audit-fix M9 (2026-05) regressions: authorised-anchorer access
 * control + brick-resistance + idempotent anchoring.
 */

import { expect } from "chai";
import { network } from "hardhat";

let ethers;
before(async function () {
  const connection = await network.create();
  ethers = connection.ethers;
});

describe("VaultAuditLog", function () {
  let log;
  let owner, hotKey, attacker;

  beforeEach(async function () {
    [owner, hotKey, attacker] = await ethers.getSigners();
    const VaultAuditLog = await ethers.getContractFactory("VaultAuditLog");
    log = await VaultAuditLog.deploy();
    await log.waitForDeployment();
  });

  it("seeds the deployer as the initial anchorer", async function () {
    expect(await log.owner()).to.equal(owner.address);
    expect(await log.authorizedAnchorers(owner.address)).to.equal(true);
    expect(await log.authorizedAnchorerCount()).to.equal(1n);
  });

  it("rejects unauthorised anchorUnlock callers", async function () {
    const commitment = "0x" + "ab".repeat(32);
    await expect(
      log.connect(attacker).anchorUnlock(commitment)
    ).to.be.revertedWith("VaultAuditLog: unauthorized anchorer");
  });

  it("accepts authorised anchorers and emits VaultUnlocked", async function () {
    const commitment = "0x" + "11".repeat(32);
    await expect(log.connect(owner).anchorUnlock(commitment))
      .to.emit(log, "VaultUnlocked")
      .withArgs(owner.address, commitment, /* timestamp */ (n) => true);

    expect(await log.anchoredCommitments(commitment)).to.equal(true);
    expect(await log.unlockCount(owner.address)).to.equal(1n);
  });

  it("rejects double-anchor of the same commitment hash", async function () {
    const commitment = "0x" + "22".repeat(32);
    await log.connect(owner).anchorUnlock(commitment);
    await expect(
      log.connect(owner).anchorUnlock(commitment)
    ).to.be.revertedWith("VaultAuditLog: already anchored");
  });

  it("rejects the zero commitment", async function () {
    await expect(
      log.connect(owner).anchorUnlock("0x" + "00".repeat(32))
    ).to.be.revertedWith("VaultAuditLog: zero commitment");
  });

  describe("anchorer rotation", function () {
    it("owner can add and remove anchorers", async function () {
      await expect(log.addAuthorizedAnchorer(hotKey.address))
        .to.emit(log, "AnchorerAuthorized")
        .withArgs(hotKey.address);
      expect(await log.authorizedAnchorers(hotKey.address)).to.equal(true);
      expect(await log.authorizedAnchorerCount()).to.equal(2n);

      // Newly authorised key can anchor.
      const commit = "0x" + "33".repeat(32);
      await expect(log.connect(hotKey).anchorUnlock(commit))
        .to.emit(log, "VaultUnlocked");

      // Now we can safely revoke the deployer (count > 1).
      await expect(log.removeAuthorizedAnchorer(owner.address))
        .to.emit(log, "AnchorerRevoked")
        .withArgs(owner.address);
      expect(await log.authorizedAnchorers(owner.address)).to.equal(false);
      expect(await log.authorizedAnchorerCount()).to.equal(1n);
    });

    it("non-owner cannot add an anchorer", async function () {
      await expect(
        log.connect(attacker).addAuthorizedAnchorer(attacker.address)
      ).to.be.revertedWithCustomError(log, "OwnableUnauthorizedAccount");
    });

    it("refuses to remove the last anchorer (brick-resistance)", async function () {
      // Constructor seeds exactly one — try to remove it.
      await expect(
        log.removeAuthorizedAnchorer(owner.address)
      ).to.be.revertedWith("Cannot remove last anchorer");
      // Set must be unchanged.
      expect(await log.authorizedAnchorers(owner.address)).to.equal(true);
      expect(await log.authorizedAnchorerCount()).to.equal(1n);
    });

    it("disables renouncing ownership", async function () {
      await expect(log.renounceOwnership()).to.be.revertedWith(
        "Renounce disabled"
      );
      expect(await log.owner()).to.equal(owner.address);
    });
  });
});
