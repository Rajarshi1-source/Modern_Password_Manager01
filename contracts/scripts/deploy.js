/**
 * Deploy CommitmentRegistry to Arbitrum Sepolia or Mainnet
 *
 * Compatible with Hardhat 3.x. Mirrors the ESM `hre.network.connect()` pattern
 * used by deploy-vault-audit-log.js and deploy-timelocked-vault.js so all
 * three deploy scripts work under the `"type": "module"` package.
 *
 * Usage:
 *   npx hardhat run scripts/deploy.js --network arbitrumSepolia
 *   npx hardhat run scripts/deploy.js --network arbitrumOne
 */

import hre from "hardhat";
import { ethers } from "ethers";
import fs from "fs";

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
  // is a bigint under ethers v6. Coerce both sides to BigInt before comparing.
  const networkName = Object.keys(networkConfig).find(
    name => {
      const cfgId = networkConfig[name]?.chainId;
      if (cfgId == null) return false;
      return BigInt(cfgId) === currentNetwork.chainId;
    }
  ) || "unknown";

  console.log("=".repeat(60));
  console.log("CommitmentRegistry Deployment");
  console.log("=".repeat(60));
  console.log(`Network:  ${networkName}`);
  console.log(`Deployer: ${deployerAddress}`);

  const balance = await provider.getBalance(deployerAddress);
  console.log(`Balance:  ${ethers.formatEther(balance)} ETH`);
  console.log("-".repeat(60));

  const artifact = await hre.artifacts.readArtifact("CommitmentRegistry");

  if (!artifact.bytecode || artifact.bytecode === "0x") {
    throw new Error(
      "CommitmentRegistry bytecode is empty. Run `npx hardhat compile` first."
    );
  }

  console.log("\nDeploying CommitmentRegistry...");
  const factory = new ethers.ContractFactory(artifact.abi, artifact.bytecode, deployer);
  const commitmentRegistry = await factory.deploy();
  await commitmentRegistry.waitForDeployment();

  const contractAddress = await commitmentRegistry.getAddress();
  console.log(`✅ CommitmentRegistry deployed at: ${contractAddress}`);

  const deployTx = commitmentRegistry.deploymentTransaction();
  let txHash = null;
  let blockNumber = null;
  if (deployTx) {
    const receipt = await deployTx.wait();
    txHash = receipt.hash;
    blockNumber = receipt.blockNumber;
    console.log(`   Transaction hash: ${receipt.hash}`);
    console.log(`   Block number:     ${receipt.blockNumber}`);
    console.log(`   Gas used:         ${receipt.gasUsed.toString()}`);
  }

  const deploymentInfo = {
    network: networkName,
    contractAddress,
    deployer: deployerAddress,
    timestamp: new Date().toISOString(),
    chainId: currentNetwork.chainId.toString(),
    txHash,
    blockNumber,
  };

  const outputPath = `./deployments/${networkName}.json`;
  fs.mkdirSync("./deployments", { recursive: true });
  fs.writeFileSync(outputPath, JSON.stringify(deploymentInfo, null, 2));

  console.log(`\nDeployment info saved to: ${outputPath}`);

  if (networkName === "arbitrumSepolia") {
    console.log(`\nArbiscan: https://sepolia.arbiscan.io/address/${contractAddress}`);
    console.log(`Verify:   npx hardhat verify --network arbitrumSepolia ${contractAddress}`);
  } else if (networkName === "arbitrumOne") {
    console.log(`\nArbiscan: https://arbiscan.io/address/${contractAddress}`);
    console.log(`Verify:   npx hardhat verify --network arbitrumOne ${contractAddress}`);
  }

  console.log("\n" + "=".repeat(60));
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("Deployment failed:", error);
    process.exit(1);
  });
