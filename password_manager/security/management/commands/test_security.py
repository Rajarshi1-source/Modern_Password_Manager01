"""
Django Management Command: test_security
=========================================

This command provides an easy way to run manual security tests without needing
to enter the Django shell. It supports running individual scenarios or entire
test suites.

Usage Examples:
    # Run all tests
    python manage.py test_security --all
    
    # Run specific scenario
    python manage.py test_security --scenario normal_login
    
    # Run specific scenario with custom username
    python manage.py test_security --scenario new_device --username myuser
    
    # Run all tests without cleanup
    python manage.py test_security --all --no-cleanup
    
    # Run performance test
    python manage.py test_security --performance --requests 200
    
    # List available scenarios
    python manage.py test_security --list
    
    # Test social account locking
    python manage.py test_security --test-locking
    
    # Verify database state
    python manage.py test_security --verify-db
    
    # Clean up test data
    python manage.py test_security --cleanup

Author: Password Manager Security Team
Date: October 2025
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
import sys
import os

# Add tests directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../..'))

from tests.manual_security_tests import (
    SecurityTestRunner,
    TestScenarios,
    NotificationTestHelper,
    Colors
)


class Command(BaseCommand):
    help = 'Run manual security tests for the SecurityService'

    def add_arguments(self, parser):
        # Mode arguments (mutually exclusive)
        mode_group = parser.add_mutually_exclusive_group()
        mode_group.add_argument(
            '--all',
            action='store_true',
            help='Run all test scenarios'
        )
        mode_group.add_argument(
            '--scenario',
            type=str,
            help='Run a specific test scenario'
        )
        mode_group.add_argument(
            '--list',
            action='store_true',
            help='List all available test scenarios'
        )
        mode_group.add_argument(
            '--performance',
            action='store_true',
            help='Run performance test'
        )
        mode_group.add_argument(
            '--test-locking',
            action='store_true',
            help='Test social account auto-locking'
        )
        mode_group.add_argument(
            '--verify-db',
            action='store_true',
            help='Verify database state'
        )
        mode_group.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up test data'
        )
        mode_group.add_argument(
            '--test-notifications',
            action='store_true',
            help='Test notification services'
        )
        
        # Configuration arguments
        parser.add_argument(
            '--username',
            type=str,
            default='testuser',
            help='Username to use for testing (default: testuser)'
        )
        parser.add_argument(
            '--no-cleanup',
            action='store_true',
            help='Skip cleanup after running tests'
        )
        parser.add_argument(
            '--requests',
            type=int,
            default=100,
            help='Number of requests for performance test (default: 100)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )

    def handle(self, *args, **options):
        """Main command handler"""
        
        username = options['username']
        verbose = options['verbose']
        
        # Print header
        self.stdout.write(self.style.SUCCESS(
            '\n' + '='*70
        ))
        self.stdout.write(self.style.SUCCESS(
            '  PASSWORD MANAGER - MANUAL SECURITY TESTING'
        ))
        self.stdout.write(self.style.SUCCESS(
            '='*70 + '\n'
        ))
        
        try:
            # List scenarios
            if options['list']:
                self.list_scenarios()
                return
                
            # Initialize test runner
            if verbose:
                self.stdout.write(f"Initializing test runner for user: {username}...")
                
            runner = SecurityTestRunner(username=username)
            
            # Run all tests
            if options['all']:
                self.stdout.write(self.style.WARNING(
                    f"\nRunning all test scenarios for user: {username}\n"
                ))
                cleanup = not options['no_cleanup']
                results = runner.run_all_tests(cleanup=cleanup)
                self.print_final_results(results)
                return
                
            # Run specific scenario
            if options['scenario']:
                scenario_name = options['scenario']
                
                # Validate scenario exists
                scenarios = TestScenarios.get_all_scenarios()
                if scenario_name not in scenarios:
                    raise CommandError(
                        f"Scenario '{scenario_name}' not found. "
                        f"Use --list to see available scenarios."
                    )
                    
                self.stdout.write(self.style.WARNING(
                    f"\nRunning scenario: {scenario_name}\n"
                ))
                result = runner.test_scenario(scenario_name)
                
                if result and result.get('status') == 'passed':
                    self.stdout.write(self.style.SUCCESS('\n✓ Test PASSED\n'))
                elif result and result.get('status') == 'failed':
                    self.stdout.write(self.style.WARNING('\n⚠ Test FAILED\n'))
                else:
                    self.stdout.write(self.style.ERROR('\n✗ Test ERROR\n'))
                    
                return
                
            # Performance test
            if options['performance']:
                num_requests = options['requests']
                self.stdout.write(self.style.WARNING(
                    f"\nRunning performance test with {num_requests} requests...\n"
                ))
                metrics = runner.test_performance(num_requests=num_requests)
                self.stdout.write(self.style.SUCCESS(
                    f"\n✓ Performance test completed successfully\n"
                ))
                return
                
            # Test social account locking
            if options['test_locking']:
                self.stdout.write(self.style.WARNING(
                    "\nTesting social account auto-locking...\n"
                ))
                result = runner.test_social_account_locking()
                
                if result.get('account_locked'):
                    self.stdout.write(self.style.SUCCESS(
                        '\n✓ Account locking working correctly\n'
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        '\n⚠ Account was not locked\n'
                    ))
                return
                
            # Verify database
            if options['verify_db']:
                self.stdout.write(self.style.WARNING(
                    "\nVerifying database state...\n"
                ))
                stats = runner.verify_database_state()
                self.stdout.write(self.style.SUCCESS('\n✓ Database verification complete\n'))
                return
                
            # Cleanup
            if options['cleanup']:
                self.stdout.write(self.style.WARNING(
                    f"\nCleaning up test data for user: {username}...\n"
                ))
                counts = runner.cleanup_test_data()
                self.stdout.write(self.style.SUCCESS('\n✓ Cleanup completed\n'))
                return
                
            # Test notifications
            if options['test_notifications']:
                self.stdout.write(self.style.WARNING(
                    "\nTesting notification services...\n"
                ))
                user = User.objects.get(username=username)
                success = NotificationTestHelper.test_email_notification(user)
                
                if success:
                    self.stdout.write(self.style.SUCCESS(
                        '\n✓ Notification test completed\n'
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        '\n⚠ Notification not triggered (check settings)\n'
                    ))
                return
                
            # No arguments provided - show help
            self.stdout.write(self.style.WARNING(
                "No test mode specified. Use --help to see available options.\n"
            ))
            self.stdout.write(
                "Common commands:\n"
                "  --all                  Run all tests\n"
                "  --scenario <name>      Run specific test\n"
                "  --list                 List available scenarios\n"
                "  --performance          Run performance test\n"
            )
            
        except User.DoesNotExist:
            raise CommandError(
                f"User '{username}' not found. "
                f"The user will be created automatically when running tests."
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Error: {str(e)}\n'))
            if verbose:
                import traceback
                traceback.print_exc()
            raise CommandError(f'Test execution failed: {str(e)}')
            
    def list_scenarios(self):
        """List all available test scenarios"""
        scenarios = TestScenarios.get_all_scenarios()
        
        self.stdout.write(self.style.WARNING(
            f"Available Test Scenarios ({len(scenarios)}):\n"
        ))
        
        for name, scenario in scenarios.items():
            self.stdout.write(
                f"\n{self.style.SUCCESS(name)}:"
            )
            self.stdout.write(f"  {scenario['name']}")
            self.stdout.write(f"  {scenario['description']}")
            self.stdout.write(
                f"  Expected Risk: {scenario['expected_risk']}"
            )
            
        self.stdout.write(
            f"\n{self.style.WARNING('Usage:')}"
        )
        self.stdout.write(
            "  python manage.py test_security --scenario <scenario_name>\n"
        )
        
    def print_final_results(self, results):
        """Print final test results summary"""
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.WARNING('  FINAL RESULTS'))
        self.stdout.write('='*70 + '\n')
        
        total = results['total']
        passed = results['passed']
        failed = results['failed']
        errors = results['errors']
        
        self.stdout.write(f"Total Tests: {total}")
        
        if passed > 0:
            self.stdout.write(self.style.SUCCESS(f"Passed: {passed}"))
        if failed > 0:
            self.stdout.write(self.style.WARNING(f"Failed: {failed}"))
        if errors > 0:
            self.stdout.write(self.style.ERROR(f"Errors: {errors}"))
            
        # Overall status
        if passed == total:
            self.stdout.write(self.style.SUCCESS(
                '\n✓ ALL TESTS PASSED!\n'
            ))
        elif failed > 0:
            self.stdout.write(self.style.WARNING(
                f'\n⚠ {failed} TEST(S) FAILED\n'
            ))
        elif errors > 0:
            self.stdout.write(self.style.ERROR(
                f'\n✗ {errors} TEST(S) HAD ERRORS\n'
            ))

