"""
Run All Tests Script
====================

Comprehensive test runner for Password Manager.
Runs unit tests, functional tests, and integration tests.

Usage:
    python tests/run_all_tests.py
    python tests/run_all_tests.py --unit-only
    python tests/run_all_tests.py --functional-only
    python tests/run_all_tests.py --integration-only
    python tests/run_all_tests.py --coverage
    python tests/run_all_tests.py --verbose
"""

import sys
import os
import subprocess
import argparse
from datetime import datetime
import time

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.ENDC}\n")


def print_section(text):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'-'*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'-'*70}{Colors.ENDC}\n")


def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ {text}{Colors.ENDC}")


def run_command(command, cwd=None, description=""):
    """
    Run a shell command and return result.
    
    Args:
        command (str or list): Command to run
        cwd (str, optional): Working directory
        description (str): Description of what's being run
        
    Returns:
        tuple: (success, output, error)
    """
    if description:
        print_info(f"Running: {description}")
    
    try:
        if isinstance(command, str):
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
        else:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300
            )
        
        if result.returncode == 0:
            return True, result.stdout, result.stderr
        else:
            return False, result.stdout, result.stderr
    
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out after 5 minutes"
    except Exception as e:
        return False, "", str(e)


def run_unit_tests(verbose=False, coverage=False):
    """Run Django unit tests"""
    print_section("Running Unit Tests")
    
    # Navigate to password_manager directory
    password_manager_dir = os.path.join(os.path.dirname(__file__), '..', 'password_manager')
    
    if coverage:
        command = f"coverage run --source='.' manage.py test"
        description = "Unit tests with coverage"
    else:
        command = "python manage.py test"
        description = "Unit tests"
    
    if verbose:
        command += " --verbosity=2"
    
    success, stdout, stderr = run_command(
        command,
        cwd=password_manager_dir,
        description=description
    )
    
    if success:
        print_success("Unit tests passed")
        if stdout:
            print(stdout)
        return True
    else:
        print_error("Unit tests failed")
        if stderr:
            print(stderr)
        if stdout:
            print(stdout)
        return False


def run_functional_tests(verbose=False):
    """Run functional tests"""
    print_section("Running Functional Tests")
    
    # Try pytest first, fall back to unittest
    try:
        import pytest
        
        functional_dir = os.path.join(os.path.dirname(__file__), 'functional')
        
        command = ["pytest", functional_dir]
        if verbose:
            command.append("-v")
        
        success, stdout, stderr = run_command(
            command,
            description="Functional tests (pytest)"
        )
        
        if success:
            print_success("Functional tests passed")
            if stdout:
                print(stdout)
            return True
        else:
            print_error("Functional tests failed")
            if stderr:
                print(stderr)
            if stdout:
                print(stdout)
            return False
    
    except ImportError:
        # Fallback to running as Python scripts
        print_info("pytest not found, running as Python scripts")
        
        functional_tests = [
            'functional/test_user_workflows.py',
            'functional/test_vault_operations.py'
        ]
        
        all_passed = True
        for test_file in functional_tests:
            test_path = os.path.join(os.path.dirname(__file__), test_file)
            
            if os.path.exists(test_path):
                success, stdout, stderr = run_command(
                    f"python {test_path}",
                    description=f"Running {test_file}"
                )
                
                if success:
                    print_success(f"{test_file} passed")
                else:
                    print_error(f"{test_file} failed")
                    all_passed = False
        
        return all_passed


def run_integration_tests(verbose=False):
    """Run integration tests"""
    print_section("Running Integration Tests")
    
    # Check if Django server is running
    print_info("Checking if Django server is running...")
    
    import requests
    try:
        response = requests.get("http://127.0.0.1:8000", timeout=2)
        print_success("Django server is running")
    except:
        print_warning("Django server is not running. Integration tests may fail.")
        print_info("Start the server with: cd password_manager && python manage.py runserver")
    
    # Run ML API tests
    test_ml_apis = os.path.join(os.path.dirname(__file__), 'test_ml_apis.py')
    
    if os.path.exists(test_ml_apis):
        success, stdout, stderr = run_command(
            f"python {test_ml_apis}",
            description="ML API Integration Tests"
        )
        
        if success:
            print_success("Integration tests passed")
            if stdout:
                print(stdout)
            return True
        else:
            print_error("Integration tests failed")
            if stderr:
                print(stderr)
            if stdout:
                print(stdout)
            return False
    else:
        print_warning("Integration test file not found")
        return True


def run_coverage_report():
    """Generate and display coverage report"""
    print_section("Generating Coverage Report")
    
    password_manager_dir = os.path.join(os.path.dirname(__file__), '..', 'password_manager')
    
    # Generate text report
    success, stdout, stderr = run_command(
        "coverage report",
        cwd=password_manager_dir,
        description="Coverage report"
    )
    
    if success and stdout:
        print(stdout)
    
    # Generate HTML report
    print_info("Generating HTML coverage report...")
    success, stdout, stderr = run_command(
        "coverage html",
        cwd=password_manager_dir,
        description="HTML coverage report"
    )
    
    if success:
        html_path = os.path.join(password_manager_dir, 'htmlcov', 'index.html')
        print_success(f"HTML report generated: {html_path}")
        print_info(f"Open with: open {html_path}")


def run_manual_security_tests():
    """Run manual security tests"""
    print_section("Running Manual Security Tests")
    
    password_manager_dir = os.path.join(os.path.dirname(__file__), '..', 'password_manager')
    
    success, stdout, stderr = run_command(
        "python manage.py test_security --all",
        cwd=password_manager_dir,
        description="Manual security tests"
    )
    
    if success:
        print_success("Manual security tests passed")
        if stdout:
            print(stdout)
        return True
    else:
        print_error("Manual security tests failed")
        if stderr:
            print(stderr)
        return False


def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(
        description="Run all Password Manager tests"
    )
    
    parser.add_argument(
        '--unit-only',
        action='store_true',
        help='Run only unit tests'
    )
    
    parser.add_argument(
        '--functional-only',
        action='store_true',
        help='Run only functional tests'
    )
    
    parser.add_argument(
        '--integration-only',
        action='store_true',
        help='Run only integration tests'
    )
    
    parser.add_argument(
        '--manual-security',
        action='store_true',
        help='Run manual security tests'
    )
    
    parser.add_argument(
        '--coverage',
        action='store_true',
        help='Run with coverage measurement'
    )
    
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Verbose output'
    )
    
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Run quick tests only (skip integration tests)'
    )
    
    args = parser.parse_args()
    
    # Print header
    print_header("PASSWORD MANAGER TEST SUITE")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    start_time = time.time()
    
    results = {
        'unit': None,
        'functional': None,
        'integration': None,
        'manual_security': None
    }
    
    # Run selected tests
    if args.unit_only:
        results['unit'] = run_unit_tests(verbose=args.verbose, coverage=args.coverage)
    elif args.functional_only:
        results['functional'] = run_functional_tests(verbose=args.verbose)
    elif args.integration_only:
        results['integration'] = run_integration_tests(verbose=args.verbose)
    elif args.manual_security:
        results['manual_security'] = run_manual_security_tests()
    else:
        # Run all tests
        results['unit'] = run_unit_tests(verbose=args.verbose, coverage=args.coverage)
        results['functional'] = run_functional_tests(verbose=args.verbose)
        
        if not args.quick:
            results['integration'] = run_integration_tests(verbose=args.verbose)
    
    # Generate coverage report if requested
    if args.coverage:
        run_coverage_report()
    
    # Calculate elapsed time
    elapsed_time = time.time() - start_time
    
    # Print summary
    print_section("Test Summary")
    
    total_tests = 0
    passed_tests = 0
    
    for test_type, result in results.items():
        if result is not None:
            total_tests += 1
            if result:
                passed_tests += 1
                print_success(f"{test_type.replace('_', ' ').title()}: PASSED")
            else:
                print_error(f"{test_type.replace('_', ' ').title()}: FAILED")
    
    print()
    print(f"Tests Run: {total_tests}")
    print(f"Passed: {Colors.GREEN}{passed_tests}{Colors.ENDC}")
    print(f"Failed: {Colors.RED}{total_tests - passed_tests}{Colors.ENDC}")
    print(f"Time Elapsed: {elapsed_time:.2f} seconds")
    
    print(f"\nFinished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Exit with appropriate code
    if total_tests == passed_tests:
        print_header("ALL TESTS PASSED! ✅")
        sys.exit(0)
    else:
        print_header("SOME TESTS FAILED! ❌")
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"\n\nUnexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

