"""
Dependency Vulnerability Scanner
=================================
Checks Python dependencies for known vulnerabilities and outdated versions.

Usage:
    python manage.py check_dependencies

Author: Password Manager Team
Date: October 2025
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
import subprocess
import json
import re
from packaging import version as pkg_version
from shared.models import DependencyVersion
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check dependencies for vulnerabilities and updates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Automatically update vulnerable dependencies (use with caution)',
        )
        parser.add_argument(
            '--save',
            action='store_true',
            help='Save results to database',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔍 Checking Python dependencies...'))
        
        # Run checks
        vulnerabilities = self.check_vulnerabilities()
        outdated = self.check_outdated_packages()
        
        # Display results
        self.display_results(vulnerabilities, outdated)
        
        # Save to database if requested
        if options['save']:
            self.save_results(vulnerabilities, outdated)
        
        # Auto-fix if requested
        if options['fix']:
            self.fix_vulnerabilities(vulnerabilities)
    
    def check_vulnerabilities(self):
        """Check for known vulnerabilities using pip-audit."""
        self.stdout.write('Running pip-audit...')
        
        vulnerabilities = []
        
        try:
            # Try pip-audit first (recommended)
            result = subprocess.run(
                ['pip-audit', '--format', 'json'],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                for vuln in data.get('vulnerabilities', []):
                    vulnerabilities.append({
                        'package': vuln['name'],
                        'current_version': vuln['version'],
                        'vulnerability_id': vuln.get('id', 'Unknown'),
                        'description': vuln.get('description', 'No description'),
                        'fixed_versions': vuln.get('fixed_versions', []),
                        'severity': self._determine_severity(vuln.get('description', ''))
                    })
                
                self.stdout.write(self.style.SUCCESS(f'✅ Found {len(vulnerabilities)} vulnerabilities with pip-audit'))
            else:
                self.stdout.write(self.style.WARNING('⚠ pip-audit not available, trying safety...'))
                vulnerabilities = self.check_with_safety()
        
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING('⚠ pip-audit not installed, trying safety...'))
            vulnerabilities = self.check_with_safety()
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error running pip-audit: {e}'))
            vulnerabilities = self.check_with_safety()
        
        return vulnerabilities
    
    def check_with_safety(self):
        """Check for vulnerabilities using safety (fallback)."""
        vulnerabilities = []
        
        try:
            result = subprocess.run(
                ['safety', 'check', '--json'],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.stdout:
                data = json.loads(result.stdout)
                
                for vuln in data:
                    vulnerabilities.append({
                        'package': vuln[0],
                        'current_version': vuln[2],
                        'vulnerability_id': vuln[3],
                        'description': vuln[4],
                        'fixed_versions': [vuln[1]],
                        'severity': self._determine_severity(vuln[4])
                    })
                
                self.stdout.write(self.style.SUCCESS(f'✅ Found {len(vulnerabilities)} vulnerabilities with safety'))
        
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('❌ Neither pip-audit nor safety is installed'))
            self.stdout.write(self.style.WARNING('Install with: pip install pip-audit safety'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error running safety: {e}'))
        
        return vulnerabilities
    
    def check_outdated_packages(self):
        """Check for outdated packages."""
        self.stdout.write('Checking for outdated packages...')
        
        outdated = []
        
        try:
            result = subprocess.run(
                ['pip', 'list', '--outdated', '--format', 'json'],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                
                for package in data:
                    outdated.append({
                        'package': package['name'],
                        'current_version': package['version'],
                        'latest_version': package['latest_version'],
                        'update_type': self._determine_update_type(
                            package['version'],
                            package['latest_version']
                        )
                    })
                
                self.stdout.write(self.style.SUCCESS(f'✅ Found {len(outdated)} outdated packages'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error checking outdated packages: {e}'))
        
        return outdated
    
    def display_results(self, vulnerabilities, outdated):
        """Display check results in a formatted manner."""
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.HTTP_INFO('VULNERABILITY REPORT'))
        self.stdout.write('='*80 + '\n')
        
        if vulnerabilities:
            self.stdout.write(self.style.ERROR(f'❌ Found {len(vulnerabilities)} VULNERABILITIES:\n'))
            
            for vuln in vulnerabilities:
                severity_style = self._get_severity_style(vuln['severity'])
                
                self.stdout.write(severity_style(f"[{vuln['severity']}] {vuln['package']} {vuln['current_version']}"))
                self.stdout.write(f"  ID: {vuln['vulnerability_id']}")
                self.stdout.write(f"  Description: {vuln['description'][:100]}...")
                
                if vuln['fixed_versions']:
                    self.stdout.write(self.style.SUCCESS(f"  Fixed in: {', '.join(vuln['fixed_versions'])}"))
                
                self.stdout.write('')
        else:
            self.stdout.write(self.style.SUCCESS('✅ No vulnerabilities found!\n'))
        
        self.stdout.write('='*80)
        self.stdout.write(self.style.HTTP_INFO('OUTDATED PACKAGES'))
        self.stdout.write('='*80 + '\n')
        
        if outdated:
            self.stdout.write(self.style.WARNING(f'⚠ Found {len(outdated)} OUTDATED packages:\n'))
            
            # Group by update type
            major = [p for p in outdated if p['update_type'] == 'MAJOR']
            minor = [p for p in outdated if p['update_type'] == 'MINOR']
            patch = [p for p in outdated if p['update_type'] == 'PATCH']
            
            if major:
                self.stdout.write(self.style.ERROR(f'\n🔴 MAJOR updates ({len(major)}):'))
                for pkg in major:
                    self.stdout.write(f"  {pkg['package']}: {pkg['current_version']} → {pkg['latest_version']}")
            
            if minor:
                self.stdout.write(self.style.WARNING(f'\n🟡 MINOR updates ({len(minor)}):'))
                for pkg in minor:
                    self.stdout.write(f"  {pkg['package']}: {pkg['current_version']} → {pkg['latest_version']}")
            
            if patch:
                self.stdout.write(self.style.SUCCESS(f'\n🟢 PATCH updates ({len(patch)}):'))
                for pkg in patch:
                    self.stdout.write(f"  {pkg['package']}: {pkg['current_version']} → {pkg['latest_version']}")
            
            self.stdout.write('')
        else:
            self.stdout.write(self.style.SUCCESS('✅ All packages are up to date!\n'))
        
        self.stdout.write('='*80 + '\n')
    
    def save_results(self, vulnerabilities, outdated):
        """Save results to database."""
        self.stdout.write('Saving results to database...')
        
        saved_count = 0
        
        try:
            # Save vulnerabilities
            for vuln in vulnerabilities:
                DependencyVersion.objects.update_or_create(
                    package_name=vuln['package'],
                    defaults={
                        'current_version': vuln['current_version'],
                        'latest_version': vuln['fixed_versions'][0] if vuln['fixed_versions'] else None,
                        'has_vulnerability': True,
                        'vulnerability_id': vuln['vulnerability_id'],
                        'vulnerability_severity': vuln['severity'],
                        'last_checked': timezone.now()
                    }
                )
                saved_count += 1
            
            # Save outdated packages
            for pkg in outdated:
                DependencyVersion.objects.update_or_create(
                    package_name=pkg['package'],
                    defaults={
                        'current_version': pkg['current_version'],
                        'latest_version': pkg['latest_version'],
                        'has_vulnerability': False,
                        'last_checked': timezone.now()
                    }
                )
                saved_count += 1
            
            self.stdout.write(self.style.SUCCESS(f'✅ Saved {saved_count} dependency records'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error saving results: {e}'))
    
    def fix_vulnerabilities(self, vulnerabilities):
        """Automatically update vulnerable dependencies."""
        if not vulnerabilities:
            self.stdout.write(self.style.SUCCESS('✅ Nothing to fix!'))
            return
        
        self.stdout.write(self.style.WARNING('\n⚠ AUTO-FIX MODE - Updating vulnerable packages...'))
        
        for vuln in vulnerabilities:
            if vuln['fixed_versions']:
                package = vuln['package']
                fixed_version = vuln['fixed_versions'][0]
                
                self.stdout.write(f"Updating {package} to {fixed_version}...")
                
                try:
                    result = subprocess.run(
                        ['pip', 'install', '--upgrade', f"{package}=={fixed_version}"],
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    
                    if result.returncode == 0:
                        self.stdout.write(self.style.SUCCESS(f'✅ Updated {package}'))
                    else:
                        self.stdout.write(self.style.ERROR(f'❌ Failed to update {package}: {result.stderr}'))
                
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'❌ Error updating {package}: {e}'))
        
        self.stdout.write(self.style.WARNING('\n⚠ Please test your application after updates!'))
    
    def _determine_severity(self, description):
        """Determine severity level from description."""
        description_lower = description.lower()
        
        if any(word in description_lower for word in ['critical', 'remote code execution', 'rce', 'arbitrary code']):
            return 'CRITICAL'
        elif any(word in description_lower for word in ['high', 'sql injection', 'xss', 'csrf']):
            return 'HIGH'
        elif any(word in description_lower for word in ['medium', 'moderate', 'denial of service', 'dos']):
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _determine_update_type(self, current, latest):
        """Determine if update is MAJOR, MINOR, or PATCH."""
        try:
            current_ver = pkg_version.parse(current)
            latest_ver = pkg_version.parse(latest)
            
            current_parts = str(current_ver).split('.')
            latest_parts = str(latest_ver).split('.')
            
            if current_parts[0] != latest_parts[0]:
                return 'MAJOR'
            elif len(current_parts) > 1 and len(latest_parts) > 1 and current_parts[1] != latest_parts[1]:
                return 'MINOR'
            else:
                return 'PATCH'
        except:
            return 'UNKNOWN'
    
    def _get_severity_style(self, severity):
        """Get appropriate style for severity level."""
        if severity == 'CRITICAL':
            return self.style.ERROR
        elif severity == 'HIGH':
            return self.style.WARNING
        elif severity == 'MEDIUM':
            return self.style.HTTP_INFO
        else:
            return self.style.SUCCESS

