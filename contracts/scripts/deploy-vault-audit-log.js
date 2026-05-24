/**
 * Deploy VaultAuditLog to Arbitrum Sepolia or Mainnet
 *
 * Compatible with Hardhat 3.x
 *
 * The VaultAuditLog contract is an append-only on-chain audit trail for
 * SmartContractVault reveals. The plaintext password never touches the
 * chain — only a commitment hash is anchored.
 *
 * Usage:
 *   npx hardhat run scripts/deploy-vault-audit-log.js --network arbitrumSepolia
 *   npx hardhat run scripts/deploy-vault-audit-log.js --network arbitrumOne
 */

import hre from "hardhat";
import { ethers } from "ethers";

async function main() {
  const connection = await hre.network.connect();
  const provider = new ethers.BrowserProvider(connection.provider);
  const accounts = await provider.listAccounts();

  if (accounts.length === 0) {
    throw new Error(
      "No accounts configured. Set BLOCKCHAIN_PRIVATE_KEY in your .env file.\n" +
      "Get Arbitrum Sepolia ETH from https://www.alchemy.com/faucets/arbitrum-sepolia"
    );
  }

  const deployer = accounts[0];
  const deployerAddress = await deployer.getAddress();
  const networkConfig = hre.config.networks;
  const currentNetwork = await provider.getNetwork();
  // `hre.config.networks[*].chainId` is a JS number; `provider.getNetwork().chainId`
  // is a bigint under ethers v6. Strict-equals never matches, so we coerce
  // both sides to BigInt before comparing (per CodeRabbit review).
  const networkName = Object.keys(networkConfig).find(
    name => {
      const cfgId = networkConfig[name]?.chainId;
      if (cfgId == null) return false;
      return BigInt(cfgId) === currentNetwork.chainId;
    }
  ) || "unknown";

  console.log("=".repeat(60));
  console.log("VaultAuditLog Deployment");
  console.log("=".repeat(60));
  console.log(`Network:  ${networkName}`);
  console.log(`Deployer: ${deployerAddress}`);

  const balance = await provider.getBalance(deployerAddress);
  console.log(`Balance:  ${ethers.formatEther(balance)} ETH`);
  console.log("-".repeat(60));

  const artifact = await hre.artifacts.readArtifact("VaultAuditLog");

  if (!artifact.bytecode || artifact.bytecode === "0x") {
    throw new Error(
      "VaultAuditLog bytecode is empty. Run `npx hardhat compile` first."
    );
  }

  console.log("\nDeploying VaultAuditLog...");
  const factory = new ethers.ContractFactory(artifact.abi, artifact.bytecode, deployer);
  const auditLog = await factory.deploy();
  await auditLog.waitForDeployment();

  const contractAddress = await auditLog.getAddress();
  console.log(`✅ VaultAuditLog deployed at: ${contractAddress}`);

  const deployTx = auditLog.deploymentTransaction();
  if (deployTx) {
    const receipt = await deployTx.wait();
    console.log(`   Transaction hash: ${receipt.hash}`);
    console.log(`   Block number:     ${receipt.blockNumber}`);
    console.log(`   Gas used:         ${receipt.gasUsed.toString()}`);
  }

  console.log("\n" + "=".repeat(60));
  console.log("CONFIGURATION");
  console.log("=".repeat(60));
  console.log("\nAdd to your .env file:");
  console.log(`VAULT_AUDIT_LOG_ADDRESS=${contractAddress}`);
  console.log("\nThis is REQUIRED — the Django backend no longer falls back");
  console.log("to TIMELOCKED_VAULT_ADDRESS when VAULT_AUDIT_LOG_ADDRESS is unset.");

  console.log("\n" + "=".repeat(60));
  console.log("POST-DEPLOY: authorise the production hot key (M9 audit fix)");
  console.log("=".repeat(60));
  console.log(`
After audit fix M9 the contract requires anchorers to be on an
allowlist. The deployer is seeded as the initial anchorer. If your
production Django process uses a different signing key (KMS-backed
or rotated), you MUST call addAuthorizedAnchorer(prod_signer) before
the first reveal — otherwise OnchainUnlockService.submit_unlock_anchor
will revert with "VaultAuditLog: unauthorized anchorer".

  npx hardhat console --network ${networkName}
  > const log = await ethers.getContractAt("VaultAuditLog", "${contractAddress}")
  > await log.addAuthorizedAnchorer("<PROD_SIGNER_ADDR>")
  > // Optional: revoke the deployer once the prod signer is in
  > await log.removeAuthorizedAnchorer("${deployerAddress}")
`);

  if (networkName === "arbitrumSepolia") {
    console.log(`\nArbiscan: https://sepolia.arbiscan.io/address/${contractAddress}`);
  } else if (networkName === "arbitrumOne") {
    console.log(`\nArbiscan: https://arbiscan.io/address/${contractAddress}`);
  }

  console.log("\n" + "=".repeat(60));
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("Deployment failed:", error);
    process.exit(1);
  });
