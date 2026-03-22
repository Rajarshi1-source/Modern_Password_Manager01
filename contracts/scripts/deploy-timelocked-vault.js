/**
 * Deploy TimeLockedVault to Arbitrum Sepolia or Mainnet
 * 
 * Compatible with Hardhat 3.x
 *
 * Usage:
 *   npx hardhat run scripts/deploy-timelocked-vault.js --network arbitrumSepolia
 *   npx hardhat run scripts/deploy-timelocked-vault.js --network arbitrumOne
 */

import hre from "hardhat";
import { ethers } from "ethers";

async function main() {
  // Hardhat 3 uses hre.network.connect() to get a provider connection
  const connection = await hre.network.connect();
  
  // Wrap the Hardhat 3 connection provider for ethers v6
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
  const networkName = Object.keys(networkConfig).find(
    name => networkConfig[name]?.chainId === currentNetwork.chainId
  ) || "unknown";

  console.log("=".repeat(60));
  console.log("TimeLockedVault Deployment");
  console.log("=".repeat(60));
  console.log(`Network:  ${networkName}`);
  console.log(`Deployer: ${deployerAddress}`);

  const balance = await provider.getBalance(deployerAddress);
  console.log(`Balance:  ${ethers.formatEther(balance)} ETH`);
  console.log("-".repeat(60));

  // Read the compiled artifact
  const artifact = await hre.artifacts.readArtifact("TimeLockedVault");

  // Deploy TimeLockedVault
  console.log("\nDeploying TimeLockedVault...");
  const factory = new ethers.ContractFactory(artifact.abi, artifact.bytecode, deployer);
  const vault = await factory.deploy();
  await vault.waitForDeployment();

  const contractAddress = await vault.getAddress();
  console.log(`✅ TimeLockedVault deployed at: ${contractAddress}`);

  // Get deployment receipt
  const deployTx = vault.deploymentTransaction();
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
  console.log(`TIMELOCKED_VAULT_ADDRESS=${contractAddress}`);

  // Arbiscan URLs
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
