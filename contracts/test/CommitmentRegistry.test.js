const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("CommitmentRegistry", function () {
  let commitmentRegistry;
  let owner;
  let otherAccount;

  beforeEach(async function () {
    [owner, otherAccount] = await ethers.getSigners();
    const CommitmentRegistry = await ethers.getContractFactory("CommitmentRegistry");
    commitmentRegistry = await CommitmentRegistry.deploy();
    await commitmentRegistry.waitForDeployment();
  });

  describe("Deployment", function () {
    it("Should set the correct owner", async function () {
      expect(await commitmentRegistry.owner()).to.equal(owner.address);
    });
  });

  describe("Anchoring Commitments", function () {
    it("Should anchor a commitment with valid signature", async function () {
      const merkleRoot = ethers.keccak256(ethers.toUtf8Bytes("test-root"));
      const batchSize = 1000;

      // Create signature
      const messageHash = ethers.solidityPackedKeccak256(
        ["bytes32", "uint256"],
        [merkleRoot, batchSize]
      );
      const signature = await owner.signMessage(ethers.getBytes(messageHash));

      // Anchor commitment
      await expect(
        commitmentRegistry.anchorCommitment(merkleRoot, batchSize, signature)
      )
        .to.emit(commitmentRegistry, "CommitmentAnchored")
        .withArgs(merkleRoot, await ethers.provider.getBlock("latest").then(b => b.timestamp + 1), batchSize, owner.address);

      // Verify commitment exists
      const commitment = await commitmentRegistry.getCommitment(merkleRoot);
      expect(commitment.exists).to.be.true;
      expect(commitment.batchSize).to.equal(batchSize);
    });

    it("Should reject commitment with invalid batch size", async function () {
      const merkleRoot = ethers.keccak256(ethers.toUtf8Bytes("test-root"));
      const batchSize = 0;

      const messageHash = ethers.solidityPackedKeccak256(
        ["bytes32", "uint256"],
        [merkleRoot, batchSize]
      );
      const signature = await owner.signMessage(ethers.getBytes(messageHash));

      await expect(
        commitmentRegistry.anchorCommitment(merkleRoot, batchSize, signature)
      ).to.be.revertedWith("Invalid batch size");
    });

    it("Should reject duplicate Merkle root", async function () {
      const merkleRoot = ethers.keccak256(ethers.toUtf8Bytes("test-root"));
      const batchSize = 1000;

      const messageHash = ethers.solidityPackedKeccak256(
        ["bytes32", "uint256"],
        [merkleRoot, batchSize]
      );
      const signature = await owner.signMessage(ethers.getBytes(messageHash));

      // Anchor first time
      await commitmentRegistry.anchorCommitment(merkleRoot, batchSize, signature);

      // Try to anchor again
      await expect(
        commitmentRegistry.anchorCommitment(merkleRoot, batchSize, signature)
      ).to.be.revertedWith("Already anchored");
    });

    it("Should reject non-owner anchoring", async function () {
      const merkleRoot = ethers.keccak256(ethers.toUtf8Bytes("test-root"));
      const batchSize = 1000;

      const messageHash = ethers.solidityPackedKeccak256(
        ["bytes32", "uint256"],
        [merkleRoot, batchSize]
      );
      const signature = await owner.signMessage(ethers.getBytes(messageHash));

      await expect(
        commitmentRegistry.connect(otherAccount).anchorCommitment(merkleRoot, batchSize, signature)
      ).to.be.revertedWithCustomError(commitmentRegistry, "OwnableUnauthorizedAccount");
    });
  });

  describe("Merkle Proof Verification", function () {
    it("Should verify valid Merkle proof", async function () {
      // Simple Merkle tree with 2 leaves
      const leaf1 = ethers.keccak256(ethers.toUtf8Bytes("commitment1"));
      const leaf2 = ethers.keccak256(ethers.toUtf8Bytes("commitment2"));
      const merkleRoot = ethers.keccak256(
        ethers.solidityPacked(["bytes32", "bytes32"], [leaf1, leaf2])
      );

      // Anchor the commitment
      const batchSize = 2;
      const messageHash = ethers.solidityPackedKeccak256(
        ["bytes32", "uint256"],
        [merkleRoot, batchSize]
      );
      const signature = await owner.signMessage(ethers.getBytes(messageHash));
      await commitmentRegistry.anchorCommitment(merkleRoot, batchSize, signature);

      // Verify leaf1 with proof [leaf2]
      const proof = [leaf2];
      const isValid = await commitmentRegistry.verifyCommitment(merkleRoot, leaf1, proof);
      expect(isValid).to.be.true;
    });

    it("Should reject invalid Merkle proof", async function () {
      const leaf1 = ethers.keccak256(ethers.toUtf8Bytes("commitment1"));
      const leaf2 = ethers.keccak256(ethers.toUtf8Bytes("commitment2"));
      const merkleRoot = ethers.keccak256(
        ethers.solidityPacked(["bytes32", "bytes32"], [leaf1, leaf2])
      );

      const batchSize = 2;
      const messageHash = ethers.solidityPackedKeccak256(
        ["bytes32", "uint256"],
        [merkleRoot, batchSize]
      );
      const signature = await owner.signMessage(ethers.getBytes(messageHash));
      await commitmentRegistry.anchorCommitment(merkleRoot, batchSize, signature);

      // Try to verify with wrong proof
      const wrongLeaf = ethers.keccak256(ethers.toUtf8Bytes("wrong"));
      const proof = [leaf2];
      const isValid = await commitmentRegistry.verifyCommitment(merkleRoot, wrongLeaf, proof);
      expect(isValid).to.be.false;
    });
  });

  describe("Getter Functions", function () {
    it("Should get submitter commitments", async function () {
      const merkleRoot1 = ethers.keccak256(ethers.toUtf8Bytes("test-root-1"));
      const merkleRoot2 = ethers.keccak256(ethers.toUtf8Bytes("test-root-2"));
      const batchSize = 1000;

      // Anchor two commitments
      for (const merkleRoot of [merkleRoot1, merkleRoot2]) {
        const messageHash = ethers.solidityPackedKeccak256(
          ["bytes32", "uint256"],
          [merkleRoot, batchSize]
        );
        const signature = await owner.signMessage(ethers.getBytes(messageHash));
        await commitmentRegistry.anchorCommitment(merkleRoot, batchSize, signature);
      }

      const submitterCommitments = await commitmentRegistry.getSubmitterCommitments(owner.address);
      expect(submitterCommitments.length).to.equal(2);
      expect(submitterCommitments[0]).to.equal(merkleRoot1);
      expect(submitterCommitments[1]).to.equal(merkleRoot2);
    });

    it("Should get batch count", async function () {
      const merkleRoot = ethers.keccak256(ethers.toUtf8Bytes("test-root"));
      const batchSize = 1000;

      const messageHash = ethers.solidityPackedKeccak256(
        ["bytes32", "uint256"],
        [merkleRoot, batchSize]
      );
      const signature = await owner.signMessage(ethers.getBytes(messageHash));
      await commitmentRegistry.anchorCommitment(merkleRoot, batchSize, signature);

      const batchCount = await commitmentRegistry.getBatchCount(owner.address);
      expect(batchCount).to.equal(1);
    });
  });
});

