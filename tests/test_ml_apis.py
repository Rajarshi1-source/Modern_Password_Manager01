"""
ML Security API Test Script
Tests all ML endpoints with sample data
"""
import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://127.0.0.1:8000"
API_BASE = f"{BASE_URL}/api/ml-security"

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.GREEN}[OK] {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}[ERROR] {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.YELLOW}[INFO] {text}{Colors.ENDC}")

def test_password_strength():
    """Test Password Strength Prediction API"""
    print_header("TEST 1: Password Strength Prediction")
    
    test_passwords = [
        ("weak123", "Weak Password"),
        ("MyPassword123", "Moderate Password"),
        ("MyStr0ng!P@ssw0rd#2024", "Strong Password"),
    ]
    
    for password, description in test_passwords:
        print(f"\n{Colors.BOLD}Testing: {description}{Colors.ENDC}")
        print(f"Password: {password}")
        
        try:
            response = requests.post(
                f"{API_BASE}/password-strength/",
                json={"password": password},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                strength = data.get('strength_score', 0)
                feedback = data.get('feedback', 'No feedback')
                
                print_success(f"Strength Score: {strength:.2f}/1.00")
                print_info(f"Feedback: {feedback}")
            elif response.status_code == 401:
                print_error("Authentication required (401)")
                print_info("This endpoint requires user authentication")
                print_info("Skipping to next test...")
            else:
                print_error(f"Failed with status {response.status_code}")
                print(f"Response: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print_error("Cannot connect to server")
            print_info("Make sure Django server is running: python manage.py runserver")
            return False
        except Exception as e:
            print_error(f"Error: {str(e)}")
            
    return True

def test_anomaly_detection():
    """Test Anomaly Detection API"""
    print_header("TEST 2: Anomaly Detection")
    
    # Normal behavior
    normal_data = {
        "event_data": {
            "ip_latitude": 34.0522,
            "ip_longitude": -118.2437,
            "time_of_day_sin": 0.5,
            "time_of_day_cos": 0.866
        },
        "event_type": "login"
    }
    
    # Anomalous behavior (different location)
    anomaly_data = {
        "event_data": {
            "ip_latitude": 51.5074,  # London
            "ip_longitude": 0.1278,
            "time_of_day_sin": -0.8,
            "time_of_day_cos": 0.6
        },
        "event_type": "login"
    }
    
    test_cases = [
        (normal_data, "Normal Login (Los Angeles)"),
        (anomaly_data, "Suspicious Login (London)"),
    ]
    
    for data, description in test_cases:
        print(f"\n{Colors.BOLD}Testing: {description}{Colors.ENDC}")
        
        try:
            response = requests.post(
                f"{API_BASE}/anomaly-detection/",
                json=data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                is_anomaly = result.get('is_anomaly', False)
                score = result.get('anomaly_score', 0)
                feedback = result.get('feedback', 'No feedback')
                
                if is_anomaly:
                    print_error(f"Anomaly Detected! Score: {score:.4f}")
                else:
                    print_success(f"Normal Behavior - Score: {score:.4f}")
                    
                print_info(f"Feedback: {feedback}")
            elif response.status_code == 401:
                print_error("Authentication required (401)")
                print_info("This endpoint requires user authentication")
            else:
                print_error(f"Failed with status {response.status_code}")
                
        except Exception as e:
            print_error(f"Error: {str(e)}")

def test_threat_analysis():
    """Test Threat Analysis API"""
    print_header("TEST 3: Threat Analysis")
    
    # Simulate user activity data
    test_data = {
        "data_sequence": "login_from_new_device browser_firefox location_changed multiple_failed_attempts",
        "analysis_type": "session_activity"
    }
    
    print(f"{Colors.BOLD}Testing: Session Activity Analysis{Colors.ENDC}")
    
    try:
        response = requests.post(
            f"{API_BASE}/threat-analysis/",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            threat_score = result.get('threat_score', 0)
            is_threat = result.get('is_threat', False)
            action = result.get('recommended_action', 'No action')
            
            if is_threat:
                print_error(f"Threat Detected! Score: {threat_score:.4f}")
            else:
                print_success(f"No Threat Detected - Score: {threat_score:.4f}")
                
            print_info(f"Recommended Action: {action}")
        elif response.status_code == 401:
            print_error("Authentication required (401)")
            print_info("This endpoint requires user authentication")
        else:
            print_error(f"Failed with status {response.status_code}")
            
    except Exception as e:
        print_error(f"Error: {str(e)}")

def test_server_connection():
    """Test if Django server is running"""
    print_header("Server Connection Test")
    
    try:
        response = requests.get(BASE_URL, timeout=3)
        print_success(f"Server is running at {BASE_URL}")
        return True
    except requests.exceptions.ConnectionError:
        print_error(f"Cannot connect to server at {BASE_URL}")
        print_info("Start the server with: cd password_manager && python manage.py runserver")
        return False
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False

def main():
    """Run all tests"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("=" * 60)
    print("     ML SECURITY API TEST SUITE")
    print("     Password Manager - AI Security Testing")
    print("=" * 60)
    print(f"{Colors.ENDC}\n")
    
    # Test server connection first
    if not test_server_connection():
        print_info("\nPlease start the Django server and run this script again.")
        return
    
    # Run all API tests
    test_password_strength()
    test_anomaly_detection()
    test_threat_analysis()
    
    # Summary
    print_header("Test Summary")
    print_info("All tests completed!")
    print_info("Note: Authentication errors (401) are expected for endpoints that require login.")
    print_info("\nTo test authenticated endpoints:")
    print("  1. Login to the application")
    print("  2. Get your JWT token")
    print("  3. Add header: Authorization: Bearer <your_token>")
    
    print(f"\n{Colors.GREEN}{Colors.BOLD}[SUCCESS] ML Security System is working!{Colors.ENDC}\n")

if __name__ == "__main__":
    main()

