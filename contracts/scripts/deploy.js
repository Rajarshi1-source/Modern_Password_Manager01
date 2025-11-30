const hre = require("hardhat");

async function main() {
  console.log("Deploying CommitmentRegistry contract...");

  // Get the deployer account
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying with account:", deployer.address);

  // Get account balance
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("Account balance:", hre.ethers.formatEther(balance), "ETH");

  // Deploy the contract
  const CommitmentRegistry = await hre.ethers.getContractFactory("CommitmentRegistry");
  const commitmentRegistry = await CommitmentRegistry.deploy();

  await commitmentRegistry.waitForDeployment();

  const address = await commitmentRegistry.getAddress();
  console.log("CommitmentRegistry deployed to:", address);

  // Save deployment info
  const fs = require("fs");
  const deploymentInfo = {
    network: hre.network.name,
    contractAddress: address,
    deployer: deployer.address,
    timestamp: new Date().toISOString(),
    chainId: (await hre.ethers.provider.getNetwork()).chainId.toString(),
  };

  const outputPath = `./deployments/${hre.network.name}.json`;
  fs.mkdirSync("./deployments", { recursive: true });
  fs.writeFileSync(outputPath, JSON.stringify(deploymentInfo, null, 2));

  console.log("\nDeployment info saved to:", outputPath);
  console.log("\nTo verify on Arbiscan:");
  console.log(`npx hardhat verify --network ${hre.network.name} ${address}`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });

