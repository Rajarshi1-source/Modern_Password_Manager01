// import "@nomicfoundation/hardhat-toolbox"; // Incompatible with Hardhat 3.x
import { config as dotenvConfig } from "dotenv";
dotenvConfig({ path: "../password_manager/.env" });

/** @type import('hardhat/config').HardhatUserConfig */
export default {
  solidity: {
    version: "0.8.28",
    settings: {
      viaIR: true,
      optimizer: {
        enabled: true,
        runs: 200,
      },
    },
  },
  networks: {
    // Arbitrum Sepolia Testnet
    arbitrumSepolia: {
      type: "http",
      url: process.env.ARBITRUM_TESTNET_RPC_URL || "https://sepolia-rollup.arbitrum.io/rpc",
      accounts: process.env.BLOCKCHAIN_PRIVATE_KEY ? [process.env.BLOCKCHAIN_PRIVATE_KEY] : [],
      chainId: 421614,
    },
    // Arbitrum One Mainnet
    arbitrumOne: {
      type: "http",
      url: process.env.ARBITRUM_MAINNET_RPC_URL || "https://arb1.arbitrum.io/rpc",
      accounts: process.env.BLOCKCHAIN_PRIVATE_KEY ? [process.env.BLOCKCHAIN_PRIVATE_KEY] : [],
      chainId: 42161,
    },
    // Hardhat local network for testing
    hardhat: {
      type: "edr-simulated",
      chainId: 31337,
    },
  },
  etherscan: {
    apiKey: {
      arbitrumSepolia: process.env.ARBISCAN_API_KEY || "",
      arbitrumOne: process.env.ARBISCAN_API_KEY || "",
    },
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
};

