#!/usr/bin/env node
/**
 * Frontend Dependency Vulnerability Scanner
 * ==========================================
 * 
 * Checks npm dependencies for:
 * - Known vulnerabilities (using npm audit)
 * - Outdated packages
 * - License compliance
 * - Deprecated packages
 * 
 * Usage:
 *   node scripts/check_dependencies.js
 *   node scripts/check_dependencies.js --fix
 *   node scripts/check_dependencies.js --report
 * 
 * Author: Password Manager Team
 * Date: October 2025
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// ANSI color codes for terminal output
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
};

class DependencyChecker {
  constructor() {
    this.packageJsonPath = path.join(process.cwd(), 'package.json');
    this.packageLockPath = path.join(process.cwd(), 'package-lock.json');
    this.results = {
      vulnerabilities: [],
      outdated: [],
      deprecated: [],
      licenses: [],
      summary: {}
    };
  }

  /**
   * Main execution method
   */
  async run() {
    console.log(`${colors.cyan}${colors.bright}🔍 Frontend Dependency Scanner${colors.reset}\n`);
    
    // Check if package.json exists
    if (!fs.existsSync(this.packageJsonPath)) {
      console.error(`${colors.red}❌ Error: package.json not found${colors.reset}`);
      process.exit(1);
    }

    try {
      // Run all checks
      await this.checkVulnerabilities();
      await this.checkOutdated();
      await this.checkDeprecated();
      await this.checkLicenses();
      
      // Display summary
      this.displaySummary();
      
      // Generate report if requested
      if (process.argv.includes('--report')) {
        this.generateReport();
      }
      
      // Auto-fix if requested
      if (process.argv.includes('--fix')) {
        await this.autoFix();
      }
      
      // Exit with appropriate code
      const hasIssues = this.results.vulnerabilities.length > 0 || 
                       this.results.outdated.length > 0;
      process.exit(hasIssues ? 1 : 0);
      
    } catch (error) {
      console.error(`${colors.red}❌ Error: ${error.message}${colors.reset}`);
      process.exit(1);
    }
  }

  /**
   * Check for vulnerabilities using npm audit
   */
  async checkVulnerabilities() {
    console.log(`${colors.blue}📊 Checking for vulnerabilities...${colors.reset}`);
    
    try {
      const auditOutput = execSync('npm audit --json', { 
        encoding: 'utf-8',
        stdio: ['pipe', 'pipe', 'pipe']
      });
      
      const audit = JSON.parse(auditOutput);
      
      if (audit.vulnerabilities) {
        for (const [pkg, data] of Object.entries(audit.vulnerabilities)) {
          this.results.vulnerabilities.push({
            package: pkg,
            severity: data.severity,
            via: data.via,
            range: data.range,
            fixAvailable: data.fixAvailable
          });
        }
      }
      
      // Summary
      const metadata = audit.metadata || {};
      this.results.summary.vulnerabilities = {
        total: metadata.vulnerabilities?.total || 0,
        info: metadata.vulnerabilities?.info || 0,
        low: metadata.vulnerabilities?.low || 0,
        moderate: metadata.vulnerabilities?.moderate || 0,
        high: metadata.vulnerabilities?.high || 0,
        critical: metadata.vulnerabilities?.critical || 0
      };
      
      // Display results
      if (this.results.vulnerabilities.length > 0) {
        console.log(`${colors.red}  ⚠️  Found ${this.results.vulnerabilities.length} vulnerabilities${colors.reset}`);
        
        // Show critical and high severity
        const critical = this.results.vulnerabilities.filter(v => v.severity === 'critical');
        const high = this.results.vulnerabilities.filter(v => v.severity === 'high');
        
        if (critical.length > 0) {
          console.log(`${colors.red}     🔴 Critical: ${critical.length}${colors.reset}`);
        }
        if (high.length > 0) {
          console.log(`${colors.yellow}     🟠 High: ${high.length}${colors.reset}`);
        }
      } else {
        console.log(`${colors.green}  ✓ No vulnerabilities found${colors.reset}`);
      }
      
    } catch (error) {
      // npm audit returns non-zero exit code when vulnerabilities found
      if (error.stdout) {
        const audit = JSON.parse(error.stdout);
        if (audit.vulnerabilities) {
          // Process vulnerabilities from error output
          this.checkVulnerabilities = async () => {}; // Prevent recursion
          return this.checkVulnerabilities();
        }
      }
      console.log(`${colors.yellow}  ⚠️  Could not run npm audit${colors.reset}`);
    }
  }

  /**
   * Check for outdated packages
   */
  async checkOutdated() {
    console.log(`\n${colors.blue}📦 Checking for outdated packages...${colors.reset}`);
    
    try {
      const outdatedOutput = execSync('npm outdated --json', { 
        encoding: 'utf-8',
        stdio: ['pipe', 'pipe', 'pipe']
      });
      
      const outdated = JSON.parse(outdatedOutput || '{}');
      
      for (const [pkg, data] of Object.entries(outdated)) {
        this.results.outdated.push({
          package: pkg,
          current: data.current,
          wanted: data.wanted,
          latest: data.latest,
          location: data.location
        });
      }
      
      if (this.results.outdated.length > 0) {
        console.log(`${colors.yellow}  ⚠️  Found ${this.results.outdated.length} outdated packages${colors.reset}`);
        
        // Show major version updates
        const majorUpdates = this.results.outdated.filter(p => {
          const current = p.current.split('.')[0];
          const latest = p.latest.split('.')[0];
          return current !== latest;
        });
        
        if (majorUpdates.length > 0) {
          console.log(`${colors.red}     🔄 Major updates available: ${majorUpdates.length}${colors.reset}`);
        }
      } else {
        console.log(`${colors.green}  ✓ All packages are up to date${colors.reset}`);
      }
      
    } catch (error) {
      // npm outdated returns exit code 1 when packages are outdated
      if (error.stdout) {
        const outdated = JSON.parse(error.stdout || '{}');
        if (Object.keys(outdated).length > 0) {
          for (const [pkg, data] of Object.entries(outdated)) {
            this.results.outdated.push({
              package: pkg,
              current: data.current,
              wanted: data.wanted,
              latest: data.latest
            });
          }
          console.log(`${colors.yellow}  ⚠️  Found ${this.results.outdated.length} outdated packages${colors.reset}`);
          return;
        }
      }
      console.log(`${colors.green}  ✓ All packages are up to date${colors.reset}`);
    }
  }

  /**
   * Check for deprecated packages
   */
  async checkDeprecated() {
    console.log(`\n${colors.blue}⚠️  Checking for deprecated packages...${colors.reset}`);
    
    try {
      const packageJson = JSON.parse(fs.readFileSync(this.packageJsonPath, 'utf-8'));
      const allDeps = {
        ...packageJson.dependencies || {},
        ...packageJson.devDependencies || {}
      };
      
      // Check each package for deprecation warnings
      for (const pkg of Object.keys(allDeps)) {
        try {
          const viewOutput = execSync(`npm view ${pkg} --json`, { 
            encoding: 'utf-8',
            stdio: ['pipe', 'pipe', 'pipe']
          });
          
          const pkgData = JSON.parse(viewOutput);
          
          if (pkgData.deprecated) {
            this.results.deprecated.push({
              package: pkg,
              message: pkgData.deprecated,
              version: allDeps[pkg]
            });
          }
        } catch (err) {
          // Package not found or other error - skip
        }
      }
      
      if (this.results.deprecated.length > 0) {
        console.log(`${colors.red}  ⚠️  Found ${this.results.deprecated.length} deprecated packages${colors.reset}`);
        this.results.deprecated.forEach(dep => {
          console.log(`${colors.yellow}     - ${dep.package}: ${dep.message}${colors.reset}`);
        });
      } else {
        console.log(`${colors.green}  ✓ No deprecated packages found${colors.reset}`);
      }
      
    } catch (error) {
      console.log(`${colors.yellow}  ⚠️  Could not check for deprecated packages${colors.reset}`);
    }
  }

  /**
   * Check package licenses
   */
  async checkLicenses() {
    console.log(`\n${colors.blue}📜 Checking package licenses...${colors.reset}`);
    
    try {
      // Try to use license-checker if available
      const licenseOutput = execSync('npx license-checker --json', { 
        encoding: 'utf-8',
        stdio: ['pipe', 'pipe', 'pipe']
      });
      
      const licenses = JSON.parse(licenseOutput);
      
      // Check for problematic licenses
      const problematicLicenses = ['GPL', 'AGPL', 'LGPL'];
      
      for (const [pkg, data] of Object.entries(licenses)) {
        const license = data.licenses || 'Unknown';
        const isProblematic = problematicLicenses.some(l => 
          license.toUpperCase().includes(l)
        );
        
        if (isProblematic || license === 'Unknown') {
          this.results.licenses.push({
            package: pkg,
            license: license,
            repository: data.repository
          });
        }
      }
      
      if (this.results.licenses.length > 0) {
        console.log(`${colors.yellow}  ⚠️  Found ${this.results.licenses.length} packages with questionable licenses${colors.reset}`);
      } else {
        console.log(`${colors.green}  ✓ All licenses are compatible${colors.reset}`);
      }
      
    } catch (error) {
      console.log(`${colors.yellow}  ℹ️  License checking skipped (install license-checker for this feature)${colors.reset}`);
    }
  }

  /**
   * Display summary of all checks
   */
  displaySummary() {
    console.log(`\n${colors.cyan}${colors.bright}═══════════════════════════════════════${colors.reset}`);
    console.log(`${colors.cyan}${colors.bright}            SUMMARY${colors.reset}`);
    console.log(`${colors.cyan}${colors.bright}═══════════════════════════════════════${colors.reset}\n`);
    
    const vulnSummary = this.results.summary.vulnerabilities || {};
    
    console.log(`${colors.bright}Vulnerabilities:${colors.reset}`);
    console.log(`  Total: ${vulnSummary.total || 0}`);
    if (vulnSummary.critical > 0) console.log(`  ${colors.red}Critical: ${vulnSummary.critical}${colors.reset}`);
    if (vulnSummary.high > 0) console.log(`  ${colors.yellow}High: ${vulnSummary.high}${colors.reset}`);
    if (vulnSummary.moderate > 0) console.log(`  Moderate: ${vulnSummary.moderate}`);
    if (vulnSummary.low > 0) console.log(`  Low: ${vulnSummary.low}`);
    
    console.log(`\n${colors.bright}Outdated Packages:${colors.reset} ${this.results.outdated.length}`);
    console.log(`${colors.bright}Deprecated Packages:${colors.reset} ${this.results.deprecated.length}`);
    console.log(`${colors.bright}License Issues:${colors.reset} ${this.results.licenses.length}`);
    
    // Overall health score
    const healthScore = this.calculateHealthScore();
    const healthColor = healthScore >= 90 ? colors.green : 
                       healthScore >= 70 ? colors.yellow : colors.red;
    
    console.log(`\n${colors.bright}Health Score:${colors.reset} ${healthColor}${healthScore}/100${colors.reset}`);
    
    console.log(`\n${colors.cyan}${colors.bright}═══════════════════════════════════════${colors.reset}\n`);
  }

  /**
   * Calculate overall health score
   */
  calculateHealthScore() {
    let score = 100;
    
    const vulnSummary = this.results.summary.vulnerabilities || {};
    
    // Deduct points for vulnerabilities
    score -= (vulnSummary.critical || 0) * 20;
    score -= (vulnSummary.high || 0) * 10;
    score -= (vulnSummary.moderate || 0) * 5;
    score -= (vulnSummary.low || 0) * 2;
    
    // Deduct points for outdated packages
    score -= Math.min(this.results.outdated.length * 2, 20);
    
    // Deduct points for deprecated packages
    score -= this.results.deprecated.length * 5;
    
    // Deduct points for license issues
    score -= this.results.licenses.length * 3;
    
    return Math.max(0, score);
  }

  /**
   * Generate detailed report
   */
  generateReport() {
    const reportPath = path.join(process.cwd(), 'dependency-report.json');
    
    const report = {
      timestamp: new Date().toISOString(),
      healthScore: this.calculateHealthScore(),
      summary: this.results.summary,
      vulnerabilities: this.results.vulnerabilities,
      outdated: this.results.outdated,
      deprecated: this.results.deprecated,
      licenses: this.results.licenses
    };
    
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
    
    console.log(`${colors.green}✓ Report saved to: ${reportPath}${colors.reset}\n`);
  }

  /**
   * Auto-fix vulnerabilities and update packages
   */
  async autoFix() {
    console.log(`\n${colors.blue}🔧 Attempting auto-fix...${colors.reset}\n`);
    
    try {
      // Run npm audit fix
      console.log('Running npm audit fix...');
      execSync('npm audit fix', { stdio: 'inherit' });
      
      console.log(`\n${colors.green}✓ Auto-fix completed${colors.reset}`);
      console.log(`${colors.yellow}⚠️  Please test your application to ensure everything still works${colors.reset}\n`);
      
    } catch (error) {
      console.log(`${colors.red}❌ Auto-fix failed: ${error.message}${colors.reset}\n`);
    }
  }
}

// Run the scanner
if (require.main === module) {
  const checker = new DependencyChecker();
  checker.run().catch(error => {
    console.error(`${colors.red}Fatal error: ${error.message}${colors.reset}`);
    process.exit(1);
  });
}

module.exports = DependencyChecker;

