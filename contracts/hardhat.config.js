// Hardhat 3.x uses split plugins instead of the toolbox bundle.
// `hardhat-ethers` exposes `hre.ethers`; `hardhat-mocha` registers the
// JS test runner so the Mocha files under `test/` are discovered by
// `npx hardhat test`. Toolbox bundle is intentionally not used — it
// pulls in Hardhat 2 deps that conflict with Hardhat 3.
import hardhatEthers from "@nomicfoundation/hardhat-ethers";
import hardhatMocha from "@nomicfoundation/hardhat-mocha";
// NOTE: `@nomicfoundation/hardhat-chai-matchers` is loaded directly by
// each test file via `import "@nomicfoundation/hardhat-chai-matchers"`,
// not as a Hardhat plugin. The current published versions don't ship a
// Hardhat 3-compatible plugin entrypoint; the package's chai-side
// `use(...)` registration works fine when imported for side effects.

import { config as dotenvConfig } from "dotenv";
dotenvConfig({ path: "../password_manager/.env" });

/** @type import('hardhat/config').HardhatUserConfig */
export default {
  plugins: [hardhatEthers, hardhatMocha],
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

