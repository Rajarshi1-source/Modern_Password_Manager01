// Hardhat 3.x uses split plugins instead of the toolbox bundle.
// `hardhat-ethers` exposes `hre.ethers`; `hardhat-mocha` registers the
// JS test runner so the Mocha files under `test/` are discovered by
// `npx hardhat test`. Toolbox bundle is intentionally not used — it
// pulls in Hardhat 2 deps that conflict with Hardhat 3.
import hardhatEthers from "@nomicfoundation/hardhat-ethers";
import hardhatMocha from "@nomicfoundation/hardhat-mocha";
// `hardhat-ethers-chai-matchers` is the Hardhat 3 plugin that adds
// `.to.emit()`, `.to.be.revertedWith()` etc. to chai. Without it those
// properties do not exist, so `expect(tx).to.emit(...)` throws before
// the transaction promise is awaited, and a reverting transaction then
// surfaces as an unhandled rejection that aborts the whole mocha run.
import hardhatEthersChaiMatchers from "@nomicfoundation/hardhat-ethers-chai-matchers";

import { config as dotenvConfig } from "dotenv";
dotenvConfig({ path: "../password_manager/.env" });

/** @type import('hardhat/config').HardhatUserConfig */
export default {
  plugins: [hardhatEthers, hardhatMocha, hardhatEthersChaiMatchers],
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

