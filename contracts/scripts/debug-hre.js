import hre from "hardhat";

console.log("hre keys:", Object.keys(hre));
console.log("hre.network:", hre.network);
console.log("hre.network keys:", hre.network ? Object.keys(hre.network) : "undefined");

if (hre.network && hre.network.provider) {
  console.log("provider keys:", Object.keys(hre.network.provider));
} else {
  console.log("No hre.network.provider");
}

// Check if config has network info
console.log("hre.config.networks keys:", Object.keys(hre.config?.networks || {}));
console.log("Network name:", hre.network?.name);
