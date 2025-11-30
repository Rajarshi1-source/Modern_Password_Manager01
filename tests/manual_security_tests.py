"""
Manual Security Testing Module
===============================

This module provides comprehensive manual testing utilities for the Security Service.
It includes test scenarios, helper functions, and integration tests that can be run
via Django shell or management commands.

Usage:
    # Via Django Shell
    python manage.py shell
    >>> from tests.manual_security_tests import SecurityTestRunner
    >>> runner = SecurityTestRunner()
    >>> runner.run_all_tests()
    
    # Via Management Command
    python manage.py test_security --scenario normal_login
    python manage.py test_security --all
    
Author: Password Manager Security Team
Date: October 2025
"""

import time
from datetime import timedelta
from django.test import RequestFactory
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Count
from unittest.mock import patch, Mock
import json

# Import security models and services
from security.models import (
    LoginAttempt, UserDevice, SocialMediaAccount, 
    SecurityAlert, AccountLockEvent, UserNotificationSettings
)
from security.services.security_service import SecurityService, NotificationService


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class TestScenarios:
    """
    Predefined test scenarios for manual security testing.
    Each scenario includes IP, user agent, device fingerprint, and expected risk level.
    """
    
    @staticmethod
    def get_all_scenarios():
        return {
            'normal_login': {
                'name': 'Normal Login from Known Device',
                'description': 'User logs in from their usual device and location',
                'ip': '192.168.1.100',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'device_fingerprint': 'known_device_123',
                'expected_risk': 'low',
                'expected_threat_score_range': (0, 30)
            },
            'new_device': {
                'name': 'Login from New Device',
                'description': 'User logs in from a new device but same location',
                'ip': '192.168.1.100',
                'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
                'device_fingerprint': 'new_device_456',
                'expected_risk': 'medium',
                'expected_threat_score_range': (30, 60)
            },
            'new_location': {
                'name': 'Login from New Location',
                'description': 'User logs in from an unusual geographic location',
                'ip': '203.0.113.1',  # Different country IP (example IP)
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'device_fingerprint': 'known_device_123',
                'expected_risk': 'medium',
                'expected_threat_score_range': (30, 60)
            },
            'suspicious_user_agent': {
                'name': 'Suspicious User Agent',
                'description': 'Login using automated tool or script',
                'ip': '192.168.1.100',
                'user_agent': 'curl/7.68.0',  # Command-line tool
                'device_fingerprint': 'suspicious_device_789',
                'expected_risk': 'high',
                'expected_threat_score_range': (60, 85)
            },
            'high_risk_combination': {
                'name': 'High Risk - Multiple Factors',
                'description': 'Combination of suspicious factors: new device, new location, suspicious UA',
                'ip': '198.51.100.1',  # Suspicious IP
                'user_agent': 'python-requests/2.28.1',  # Automated script
                'device_fingerprint': 'malicious_device_000',
                'expected_risk': 'high',
                'expected_threat_score_range': (70, 100)
            },
            'brute_force_attempt': {
                'name': 'Brute Force Attack',
                'description': 'Multiple failed login attempts from same IP',
                'ip': '10.0.0.1',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'device_fingerprint': 'attacker_device',
                'expected_risk': 'critical',
                'expected_threat_score_range': (80, 100),
                'is_failed_attempt': True,
                'repeat_count': 6  # Simulate 6 failed attempts
            },
            'impossible_travel': {
                'name': 'Impossible Travel Detection',
                'description': 'Login from geographically distant location in short time',
                'ip': '45.11.96.1',  # Asia IP
                'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                'device_fingerprint': 'new_device_999',
                'expected_risk': 'high',
                'expected_threat_score_range': (70, 90),
                'previous_location': {'ip': '192.168.1.100', 'time_ago_minutes': 5}
            }
        }


class SecurityTestRunner:
    """
    Main test runner for manual security testing.
    Provides methods to run individual tests or entire test suites.
    """
    
    def __init__(self, username='testuser'):
        """
        Initialize the test runner.
        
        Args:
            username (str): Username to use for testing. Will be created if doesn't exist.
        """
        self.factory = RequestFactory()
        self.security_service = SecurityService()
        self.username = username
        self.user = None
        self.test_results = []
        
        # Setup test user
        self._setup_test_user()
        
    def _setup_test_user(self):
        """Create or get the test user"""
        self.user, created = User.objects.get_or_create(
            username=self.username,
            defaults={
                'email': f'{self.username}@test.com',
                'password': 'testpassword123'
            }
        )
        
        if created:
            self.user.set_password('testpassword123')
            self.user.save()
            self._print_success(f"Created test user: {self.username}")
        else:
            self._print_info(f"Using existing test user: {self.username}")
            
    def _create_request(self, scenario_data, is_login=True):
        """
        Create a mock request based on scenario data.
        
        Args:
            scenario_data (dict): Scenario configuration
            is_login (bool): Whether this is a login request
            
        Returns:
            request: Mock Django request object
        """
        data = {
            'username': self.username,
            'password': 'testpassword123' if is_login else 'wrong_password',
            'device_fingerprint': scenario_data.get('device_fingerprint', 'default_device')
        }
        
        request = self.factory.post('/auth/login/', data)
        request.META['HTTP_USER_AGENT'] = scenario_data['user_agent']
        request.META['REMOTE_ADDR'] = scenario_data['ip']
        request.data = data
        
        return request
        
    def _print_header(self, text):
        """Print formatted header"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.ENDC}\n")
        
    def _print_success(self, text):
        """Print success message"""
        print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")
        
    def _print_error(self, text):
        """Print error message"""
        print(f"{Colors.RED}✗ {text}{Colors.ENDC}")
        
    def _print_warning(self, text):
        """Print warning message"""
        print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")
        
    def _print_info(self, text):
        """Print info message"""
        print(f"{Colors.CYAN}ℹ {text}{Colors.ENDC}")
        
    def test_scenario(self, scenario_name):
        """
        Run a specific test scenario.
        
        Args:
            scenario_name (str): Name of the scenario to run
            
        Returns:
            dict: Test results
        """
        scenarios = TestScenarios.get_all_scenarios()
        
        if scenario_name not in scenarios:
            self._print_error(f"Scenario '{scenario_name}' not found!")
            return None
            
        scenario = scenarios[scenario_name]
        
        self._print_header(f"Testing: {scenario['name']}")
        self._print_info(f"Description: {scenario['description']}")
        print()
        
        # Handle brute force scenario separately
        if scenario.get('is_failed_attempt') and scenario.get('repeat_count'):
            return self._test_brute_force(scenario)
        
        # Handle impossible travel scenario
        if 'previous_location' in scenario:
            return self._test_impossible_travel(scenario)
            
        # Standard scenario test
        request = self._create_request(scenario)
        
        try:
            # Analyze login attempt
            attempt = self.security_service.analyze_login_attempt(
                user=self.user,
                request=request,
                is_successful=not scenario.get('is_failed_attempt', False)
            )
            
            # Validate results
            result = self._validate_test_result(scenario, attempt)
            self.test_results.append(result)
            
            # Print results
            self._print_test_results(scenario, attempt, result)
            
            return result
            
        except Exception as e:
            self._print_error(f"Test failed with exception: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'status': 'error', 'error': str(e)}
            
    def _test_brute_force(self, scenario):
        """Test brute force attack scenario"""
        self._print_info(f"Simulating {scenario['repeat_count']} failed login attempts...")
        print()
        
        attempts = []
        for i in range(scenario['repeat_count']):
            request = self._create_request(scenario, is_login=False)
            
            try:
                attempt = self.security_service.analyze_login_attempt(
                    user=self.user,
                    request=request,
                    is_successful=False,
                    failure_reason='Invalid password'
                )
                
                attempts.append(attempt)
                
                print(f"  Attempt {i+1}/{scenario['repeat_count']}:")
                print(f"    Threat Score: {attempt.threat_score}")
                print(f"    Is Suspicious: {attempt.is_suspicious}")
                print(f"    Status: {attempt.status}")
                
                if i < scenario['repeat_count'] - 1:
                    time.sleep(0.5)  # Small delay between attempts
                    
            except Exception as e:
                self._print_error(f"  Attempt {i+1} failed: {str(e)}")
                
        print()
        
        # Check final attempt
        if attempts:
            final_attempt = attempts[-1]
            expected_min, expected_max = scenario['expected_threat_score_range']
            
            result = {
                'status': 'passed' if final_attempt.threat_score >= expected_min else 'failed',
                'scenario': scenario['name'],
                'attempt_count': len(attempts),
                'final_threat_score': final_attempt.threat_score,
                'expected_range': scenario['expected_threat_score_range'],
                'is_suspicious': final_attempt.is_suspicious,
                'suspicious_factors': final_attempt.suspicious_factors
            }
            
            if result['status'] == 'passed':
                self._print_success(f"Brute force detection working correctly")
                self._print_success(f"Final threat score: {final_attempt.threat_score}")
            else:
                self._print_warning(f"Threat score ({final_attempt.threat_score}) below expected minimum ({expected_min})")
                
            return result
            
        return {'status': 'error', 'error': 'No attempts recorded'}
        
    def _test_impossible_travel(self, scenario):
        """Test impossible travel scenario"""
        # Create a previous login from different location
        prev_loc = scenario['previous_location']
        prev_time = timezone.now() - timedelta(minutes=prev_loc['time_ago_minutes'])
        
        LoginAttempt.objects.create(
            user=self.user,
            username_attempted=self.username,
            ip_address=prev_loc['ip'],
            status='success',
            timestamp=prev_time,
            location='Los Angeles, US'
        )
        
        self._print_info(f"Created previous login from {prev_loc['ip']} {prev_loc['time_ago_minutes']} minutes ago")
        
        # Now test current login from distant location
        return self.test_scenario('new_location')  # Reuse new_location logic
        
    def _validate_test_result(self, scenario, attempt):
        """
        Validate test results against expected outcomes.
        
        Args:
            scenario (dict): Scenario configuration
            attempt (LoginAttempt): The login attempt result
            
        Returns:
            dict: Validation results
        """
        expected_min, expected_max = scenario['expected_threat_score_range']
        
        result = {
            'status': 'passed',
            'scenario': scenario['name'],
            'threat_score': attempt.threat_score,
            'expected_range': scenario['expected_threat_score_range'],
            'is_suspicious': attempt.is_suspicious,
            'suspicious_factors': attempt.suspicious_factors,
            'location': attempt.location,
            'ip_address': attempt.ip_address
        }
        
        # Validate threat score is in expected range
        if not (expected_min <= attempt.threat_score <= expected_max):
            result['status'] = 'failed'
            result['reason'] = f"Threat score {attempt.threat_score} outside expected range [{expected_min}, {expected_max}]"
            
        return result
        
    def _print_test_results(self, scenario, attempt, result):
        """Print formatted test results"""
        print(f"{Colors.BOLD}Test Results:{Colors.ENDC}")
        print(f"  IP Address: {attempt.ip_address}")
        print(f"  Location: {attempt.location or 'Unknown'}")
        print(f"  Threat Score: {Colors.BOLD}{attempt.threat_score}{Colors.ENDC}/100")
        print(f"  Expected Range: {scenario['expected_threat_score_range'][0]}-{scenario['expected_threat_score_range'][1]}")
        print(f"  Is Suspicious: {Colors.BOLD}{attempt.is_suspicious}{Colors.ENDC}")
        print(f"  Status: {attempt.status}")
        
        if attempt.suspicious_factors:
            print(f"\n  {Colors.YELLOW}Suspicious Factors:{Colors.ENDC}")
            for factor, value in attempt.suspicious_factors.items():
                print(f"    • {factor}: {value}")
                
        print()
        
        if result['status'] == 'passed':
            self._print_success(f"✓ Test PASSED - Threat detected correctly")
        else:
            self._print_warning(f"⚠ Test FAILED - {result.get('reason', 'Unknown reason')}")
            
    def run_all_tests(self, cleanup=True):
        """
        Run all predefined test scenarios.
        
        Args:
            cleanup (bool): Whether to cleanup test data after running
            
        Returns:
            dict: Summary of all test results
        """
        self._print_header("Running All Security Test Scenarios")
        
        scenarios = TestScenarios.get_all_scenarios()
        results = []
        
        for scenario_name in scenarios:
            result = self.test_scenario(scenario_name)
            if result:
                results.append(result)
            time.sleep(1)  # Pause between tests
            
        # Print summary
        self._print_summary(results)
        
        # Cleanup if requested
        if cleanup:
            self.cleanup_test_data()
            
        return {
            'total': len(results),
            'passed': sum(1 for r in results if r.get('status') == 'passed'),
            'failed': sum(1 for r in results if r.get('status') == 'failed'),
            'errors': sum(1 for r in results if r.get('status') == 'error'),
            'results': results
        }
        
    def _print_summary(self, results):
        """Print test summary"""
        self._print_header("Test Summary")
        
        total = len(results)
        passed = sum(1 for r in results if r.get('status') == 'passed')
        failed = sum(1 for r in results if r.get('status') == 'failed')
        errors = sum(1 for r in results if r.get('status') == 'error')
        
        print(f"Total Tests: {Colors.BOLD}{total}{Colors.ENDC}")
        print(f"Passed: {Colors.GREEN}{passed}{Colors.ENDC}")
        print(f"Failed: {Colors.YELLOW}{failed}{Colors.ENDC}")
        print(f"Errors: {Colors.RED}{errors}{Colors.ENDC}")
        print()
        
        if failed > 0:
            print(f"{Colors.YELLOW}Failed Tests:{Colors.ENDC}")
            for result in results:
                if result.get('status') == 'failed':
                    print(f"  • {result.get('scenario')}: {result.get('reason', 'Unknown')}")
                    
    def test_performance(self, num_requests=100):
        """
        Test performance of security analysis with multiple rapid requests.
        
        Args:
            num_requests (int): Number of requests to simulate
            
        Returns:
            dict: Performance metrics
        """
        self._print_header(f"Performance Test - {num_requests} Requests")
        
        scenario = TestScenarios.get_all_scenarios()['normal_login']
        
        start_time = time.time()
        
        for i in range(num_requests):
            # Vary IP slightly for each request
            scenario_copy = scenario.copy()
            scenario_copy['ip'] = f'192.168.1.{(i % 255) + 1}'
            scenario_copy['device_fingerprint'] = f'device_{i}'
            
            request = self._create_request(scenario_copy)
            
            try:
                self.security_service.analyze_login_attempt(
                    user=self.user,
                    request=request,
                    is_successful=True
                )
            except Exception as e:
                self._print_error(f"Request {i+1} failed: {str(e)}")
                
        end_time = time.time()
        total_time = end_time - start_time
        avg_time = total_time / num_requests
        
        self._print_success(f"Completed {num_requests} analyses in {total_time:.2f} seconds")
        self._print_info(f"Average time per analysis: {avg_time:.4f} seconds")
        self._print_info(f"Throughput: {num_requests/total_time:.2f} requests/second")
        
        return {
            'total_requests': num_requests,
            'total_time': total_time,
            'average_time': avg_time,
            'throughput': num_requests/total_time
        }
        
    def test_social_account_locking(self):
        """Test social account locking on high-risk login"""
        self._print_header("Testing Social Account Auto-Locking")
        
        # Create a social account for the user
        social_account, created = SocialMediaAccount.objects.get_or_create(
            user=self.user,
            platform='facebook',
            defaults={
                'username': f'{self.username}_fb',
                'status': 'active',
                'auto_lock_enabled': True
            }
        )
        
        if created:
            self._print_info("Created test social media account (Facebook)")
        else:
            # Reset to active if it exists
            social_account.status = 'active'
            social_account.auto_lock_enabled = True
            social_account.save()
            self._print_info("Using existing social media account")
            
        print(f"Initial Status: {social_account.status}")
        print()
        
        # Trigger high-risk login
        scenario = TestScenarios.get_all_scenarios()['high_risk_combination']
        request = self._create_request(scenario)
        
        # Mock high risk calculation
        with patch.object(self.security_service, '_calculate_risk_score') as mock_calc:
            mock_calc.return_value = {
                'risk_score': 85,
                'suspicious_factors': {
                    'new_device': True,
                    'suspicious_user_agent': True,
                    'blacklisted_ip': True
                }
            }
            
            attempt = self.security_service.analyze_login_attempt(
                user=self.user,
                request=request,
                is_successful=True
            )
            
        # Check if social account was locked
        social_account.refresh_from_db()
        
        print(f"Threat Score: {attempt.threat_score}")
        print(f"Social Account Status After Login: {Colors.BOLD}{social_account.status}{Colors.ENDC}")
        
        if social_account.status == 'locked':
            self._print_success("✓ Social account correctly locked due to high-risk login")
        else:
            self._print_warning("⚠ Social account was not locked (threshold may need adjustment)")
            
        # Check for security alerts
        alerts = SecurityAlert.objects.filter(user=self.user).order_by('-created_at')[:3]
        if alerts:
            print(f"\n{Colors.YELLOW}Recent Security Alerts:{Colors.ENDC}")
            for alert in alerts:
                print(f"  • {alert.title} - Severity: {alert.severity}")
        else:
            self._print_warning("No security alerts created")
            
        return {
            'threat_score': attempt.threat_score,
            'account_locked': social_account.status == 'locked',
            'alert_count': alerts.count() if alerts else 0
        }
        
    def verify_database_state(self):
        """Verify the state of security-related database records"""
        self._print_header("Database State Verification")
        
        stats = {
            'total_login_attempts': LoginAttempt.objects.count(),
            'suspicious_attempts': LoginAttempt.objects.filter(is_suspicious=True).count(),
            'user_attempts': LoginAttempt.objects.filter(user=self.user).count(),
            'registered_devices': UserDevice.objects.filter(user=self.user).count(),
            'security_alerts': SecurityAlert.objects.filter(user=self.user).count(),
            'account_lock_events': AccountLockEvent.objects.filter(user=self.user).count()
        }
        
        for key, value in stats.items():
            label = key.replace('_', ' ').title()
            print(f"{label}: {Colors.BOLD}{value}{Colors.ENDC}")
            
        # Show recent suspicious attempts
        print(f"\n{Colors.YELLOW}Recent Suspicious Attempts (Last 5):{Colors.ENDC}")
        suspicious_attempts = LoginAttempt.objects.filter(
            user=self.user, 
            is_suspicious=True
        ).order_by('-timestamp')[:5]
        
        if suspicious_attempts:
            for attempt in suspicious_attempts:
                print(f"  • {attempt.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - "
                      f"IP: {attempt.ip_address} - "
                      f"Score: {attempt.threat_score}")
        else:
            self._print_info("  No suspicious attempts found")
            
        return stats
        
    def cleanup_test_data(self):
        """Clean up all test data created during testing"""
        self._print_header("Cleaning Up Test Data")
        
        counts = {
            'login_attempts': LoginAttempt.objects.filter(user=self.user).delete()[0],
            'devices': UserDevice.objects.filter(user=self.user).delete()[0],
            'alerts': SecurityAlert.objects.filter(user=self.user).delete()[0],
            'lock_events': AccountLockEvent.objects.filter(user=self.user).delete()[0],
            'social_accounts': SocialMediaAccount.objects.filter(user=self.user).delete()[0]
        }
        
        for data_type, count in counts.items():
            if count > 0:
                self._print_info(f"Deleted {count} {data_type}")
                
        self._print_success("✓ Test data cleaned up successfully")
        
        return counts


class NotificationTestHelper:
    """Helper class for testing notification services"""
    
    @staticmethod
    def test_email_notification(user):
        """Test email notification for suspicious login"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}Testing Email Notifications{Colors.ENDC}\n")
        
        # Create a suspicious login attempt
        attempt = LoginAttempt.objects.create(
            user=user,
            username_attempted=user.username,
            ip_address='10.0.0.1',
            status='success',
            is_suspicious=True,
            threat_score=75,
            suspicious_factors={'new_device': True, 'new_location': 'Unknown, US'},
            location='Unknown, US'
        )
        
        with patch('security.services.security_service.send_mail') as mock_send:
            NotificationService.send_suspicious_login_alert(user, attempt)
            
            if mock_send.called:
                print(f"{Colors.GREEN}✓ Email notification triggered{Colors.ENDC}")
                call_args = mock_send.call_args[1]
                print(f"  Subject: {call_args.get('subject')}")
                print(f"  Recipient: {call_args.get('recipient_list')}")
                print(f"  From: {call_args.get('from_email')}")
                return True
            else:
                print(f"{Colors.YELLOW}⚠ No email sent (check threshold settings){Colors.ENDC}")
                return False


# Quick access functions for common operations
def quick_test(scenario_name='normal_login', username='testuser'):
    """
    Quick test function for running a single scenario.
    
    Args:
        scenario_name (str): Name of scenario to test
        username (str): Username to use for testing
    """
    runner = SecurityTestRunner(username=username)
    runner.test_scenario(scenario_name)
    runner.verify_database_state()


def run_all(username='testuser', cleanup=True):
    """
    Run all security tests.
    
    Args:
        username (str): Username to use for testing
        cleanup (bool): Whether to cleanup test data after running
    """
    runner = SecurityTestRunner(username=username)
    results = runner.run_all_tests(cleanup=cleanup)
    return results


def test_performance(num_requests=100, username='testuser'):
    """
    Run performance test.
    
    Args:
        num_requests (int): Number of requests to simulate
        username (str): Username to use for testing
    """
    runner = SecurityTestRunner(username=username)
    return runner.test_performance(num_requests=num_requests)


def cleanup(username='testuser'):
    """
    Clean up all test data.
    
    Args:
        username (str): Username whose data to cleanup
    """
    runner = SecurityTestRunner(username=username)
    runner.cleanup_test_data()


# For interactive shell usage
if __name__ == '__main__':
    print(f"""
{Colors.BOLD}{Colors.BLUE}Manual Security Testing Module{Colors.ENDC}

Quick Functions:
  quick_test(scenario_name, username='testuser')  - Run a single test
  run_all(username='testuser', cleanup=True)      - Run all tests
  test_performance(num_requests=100)              - Performance test
  cleanup(username='testuser')                    - Clean up test data

Example Usage:
  >>> from tests.manual_security_tests import *
  >>> quick_test('normal_login')
  >>> quick_test('high_risk_combination')
  >>> run_all()
  
For detailed usage, see tests/MANUAL_TESTING_GUIDE.md
    """)

