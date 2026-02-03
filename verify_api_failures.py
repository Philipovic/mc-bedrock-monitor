#!/usr/bin/env python3
"""
Manual verification script to test API failure handling.
This script simulates different API failure scenarios and shows the behavior.
"""

import sys
import os
import tempfile
import json
from unittest.mock import patch, Mock
import requests

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set required environment variables for monitor.py import
os.environ['MC_SERVER'] = 'test.example.com:19132'

import monitor

def print_separator():
    print("\n" + "="*70 + "\n")

def test_scenario(scenario_name, mock_behavior, initial_state):
    """Test a specific failure scenario."""
    print(f"🧪 Testing: {scenario_name}")
    print(f"   Initial state: online={initial_state['online']}, players={initial_state['count']}")
    
    # Create a temporary data file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        # Patch the data file path
        with patch.object(monitor, 'DATA_FILE', temp_path):
            # Patch Discord notifications
            with patch('monitor.send_discord_notification') as mock_discord:
                # Patch the session
                with patch('monitor.session') as mock_session:
                    # Apply the mock behavior
                    mock_behavior(mock_session)
                    
                    # Call check_server
                    result = monitor.check_server(
                        initial_state['count'],
                        initial_state['online'],
                        initial_state['gamemode'],
                        initial_state['version'],
                        set()
                    )
                    
                    # Check results
                    state_unchanged = (
                        result[0] == initial_state['count'] and
                        result[1] == initial_state['online'] and
                        result[2] == initial_state['gamemode'] and
                        result[3] == initial_state['version']
                    )
                    
                    discord_not_called = not mock_discord.called
                    
                    if state_unchanged and discord_not_called:
                        print(f"   ✅ PASS: State preserved, no notifications sent")
                    else:
                        print(f"   ❌ FAIL:")
                        if not state_unchanged:
                            print(f"      - State was changed!")
                            print(f"        Before: {initial_state}")
                            print(f"        After: count={result[0]}, online={result[1]}, gamemode={result[2]}, version={result[3]}")
                        if not discord_not_called:
                            print(f"      - Discord notification was sent!")
                    
                    return state_unchanged and discord_not_called
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def main():
    print("🚀 Manual Verification: API Failure Handling")
    print("=" * 70)
    print("This script tests that API failures don't trigger state changes")
    print("or Discord notifications.")
    print_separator()
    
    # Define initial state
    initial_state = {
        'count': 5,
        'online': True,
        'gamemode': 'Survival',
        'version': '1.21.0'
    }
    
    test_results = []
    
    # Test 1: Connection Error
    def mock_connection_error(mock_session):
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Network unreachable")
    
    test_results.append(test_scenario(
        "Connection Error (Network unreachable)",
        mock_connection_error,
        initial_state
    ))
    print_separator()
    
    # Test 2: Timeout
    def mock_timeout(mock_session):
        mock_session.get.side_effect = requests.exceptions.Timeout("Request timed out")
    
    test_results.append(test_scenario(
        "Timeout Error",
        mock_timeout,
        initial_state
    ))
    print_separator()
    
    # Test 3: HTTP 500 Error
    def mock_http_error(mock_session):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_session.get.return_value = mock_response
    
    test_results.append(test_scenario(
        "HTTP 500 Server Error",
        mock_http_error,
        initial_state
    ))
    print_separator()
    
    # Test 4: Invalid JSON Response
    def mock_invalid_json(mock_session):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_session.get.return_value = mock_response
    
    test_results.append(test_scenario(
        "Invalid JSON Response",
        mock_invalid_json,
        initial_state
    ))
    print_separator()
    
    # Test 5: Offline server with API failure
    offline_state = {
        'count': 0,
        'online': False,
        'gamemode': '',
        'version': '1.20.0'
    }
    
    test_results.append(test_scenario(
        "Connection Error (Server was offline)",
        mock_connection_error,
        offline_state
    ))
    print_separator()
    
    # Summary
    passed = sum(test_results)
    total = len(test_results)
    
    print("📊 SUMMARY")
    print("=" * 70)
    print(f"Total tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    
    if passed == total:
        print("\n✅ All tests passed! API failure handling is working correctly.")
        print("   - State is preserved during API failures")
        print("   - No Discord notifications are sent during API failures")
        return 0
    else:
        print("\n❌ Some tests failed. Please review the implementation.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
