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

    it("C8: allows a non-owner relayer when signed by an authorized signer", async function () {
      // After audit fix C8, anchorCommitment is permissionless at the tx
      // level. Authorization comes from the ECDSA signature recovering
      // to an address in `authorizedSigners` (owner is seeded as one).
      const merkleRoot = ethers.keccak256(ethers.toUtf8Bytes("test-root"));
      const batchSize = 1000;

      const messageHash = ethers.solidityPackedKeccak256(
        ["bytes32", "uint256"],
        [merkleRoot, batchSize]
      );
      const signature = await owner.signMessage(ethers.getBytes(messageHash));

      // otherAccount has no gas-funded relayer privilege restrictions:
      // the signature is owner's, so the contract accepts it.
      await expect(
        commitmentRegistry.connect(otherAccount).anchorCommitment(
          merkleRoot, batchSize, signature
        )
      ).to.emit(commitmentRegistry, "CommitmentAnchored");
    });

    it("C8: rejects when the signer is not authorized", async function () {
      const merkleRoot = ethers.keccak256(ethers.toUtf8Bytes("test-root-2"));
      const batchSize = 1000;

      const messageHash = ethers.solidityPackedKeccak256(
        ["bytes32", "uint256"],
        [merkleRoot, batchSize]
      );
      // Sign with otherAccount; it is NOT in authorizedSigners by default.
      const signature = await otherAccount.signMessage(ethers.getBytes(messageHash));

      await expect(
        commitmentRegistry.anchorCommitment(merkleRoot, batchSize, signature)
      ).to.be.revertedWith("Unauthorized signer");
    });
  });

  describe("C8: signer rotation", function () {
    it("owner can add and remove authorized signers", async function () {
      // Add otherAccount as a signer.
      await expect(commitmentRegistry.addAuthorizedSigner(otherAccount.address))
        .to.emit(commitmentRegistry, "SignerAuthorized")
        .withArgs(otherAccount.address);
      expect(await commitmentRegistry.authorizedSigners(otherAccount.address)).to.be.true;

      // Now otherAccount can sign anchors.
      const merkleRoot = ethers.keccak256(ethers.toUtf8Bytes("rotated"));
      const batchSize = 5;
      const messageHash = ethers.solidityPackedKeccak256(
        ["bytes32", "uint256"], [merkleRoot, batchSize]
      );
      const signature = await otherAccount.signMessage(ethers.getBytes(messageHash));
      await expect(
        commitmentRegistry.anchorCommitment(merkleRoot, batchSize, signature)
      ).to.emit(commitmentRegistry, "CommitmentAnchored");

      // Revoke.
      await expect(commitmentRegistry.removeAuthorizedSigner(otherAccount.address))
        .to.emit(commitmentRegistry, "SignerRevoked");
      expect(await commitmentRegistry.authorizedSigners(otherAccount.address)).to.be.false;
    });

    it("non-owner cannot add a signer", async function () {
      await expect(
        commitmentRegistry.connect(otherAccount).addAuthorizedSigner(otherAccount.address)
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

    it("C2: verifyCommitment is view (callable without a tx) and emits NO event", async function () {
      const leaf1 = ethers.keccak256(ethers.toUtf8Bytes("c2-leaf-1"));
      const leaf2 = ethers.keccak256(ethers.toUtf8Bytes("c2-leaf-2"));
      const merkleRoot = ethers.keccak256(
        ethers.solidityPacked(["bytes32", "bytes32"], [leaf1, leaf2])
      );

      const batchSize = 2;
      const messageHash = ethers.solidityPackedKeccak256(
        ["bytes32", "uint256"], [merkleRoot, batchSize]
      );
      const signature = await owner.signMessage(ethers.getBytes(messageHash));
      await commitmentRegistry.anchorCommitment(merkleRoot, batchSize, signature);

      // .staticCall confirms the function is `view` — would fail
      // (no return data from a non-view function) if C2 regressed.
      const result = await commitmentRegistry.verifyCommitment.staticCall(
        merkleRoot, leaf1, [leaf2]
      );
      expect(result).to.be.true;

      // The `CommitmentVerified` event was deleted in the C2 fix. Calling
      // verifyCommitment must not emit anything. We assert by checking
      // the contract has no such event in its ABI.
      const ev = commitmentRegistry.interface.fragments.find(
        f => f.type === 'event' && f.name === 'CommitmentVerified'
      );
      expect(ev, 'CommitmentVerified event must not exist').to.be.undefined;
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

