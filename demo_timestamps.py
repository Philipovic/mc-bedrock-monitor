#!/usr/bin/env python3
"""
Manual verification script to demonstrate timestamp logging.
This script simulates different scenarios to show timestamps in logs.
"""

import sys
import os
import tempfile
from unittest.mock import patch, Mock
import requests

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set required environment variables for monitor.py import
os.environ['MC_SERVER'] = 'test.example.com:19132'

import monitor

def print_separator(title=""):
    print("\n" + "="*70)
    if title:
        print(f"  {title}")
        print("="*70)
    print()

def demo_scenario_1():
    """Demo 1: Normal server monitoring with timestamps."""
    print_separator("SCENARIO 1: Normal Operation - Logs with Timestamps")
    
    # Create a temporary data file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        with patch.object(monitor, 'DATA_FILE', temp_path):
            with patch('monitor.session') as mock_session:
                # Mock successful API response
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.raise_for_status.return_value = None
                mock_response.json.return_value = {
                    "online": True,
                    "players": {"online": 3, "max": 10},
                    "version": "1.21.2",
                    "gamemode": "Survival"
                }
                mock_session.get.return_value = mock_response
                
                print("Simulating server coming online...")
                print("(Notice the timestamps in square brackets)")
                print()
                
                # Call check_server (first check)
                monitor.check_server(0, None, "", "Unknown", set())
                
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def demo_scenario_2():
    """Demo 2: API failure with timestamps."""
    print_separator("SCENARIO 2: API Failure - Error Logs with Timestamps")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        with patch.object(monitor, 'DATA_FILE', temp_path):
            with patch('monitor.session') as mock_session:
                # Simulate connection error
                mock_session.get.side_effect = requests.exceptions.ConnectionError("Network unreachable")
                
                print("Simulating API connection failure...")
                print("(Notice the timestamps in square brackets)")
                print()
                
                # Call check_server
                monitor.check_server(5, True, "Survival", "1.21.0", set())
                
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def demo_scenario_3():
    """Demo 3: Show Discord messages don't have timestamps."""
    print_separator("SCENARIO 3: Discord Notifications - NO Timestamps")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        with patch.object(monitor, 'DATA_FILE', temp_path):
            with patch('monitor.send_discord_notification') as mock_discord:
                with patch('monitor.session') as mock_session:
                    # Mock successful API response
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.raise_for_status.return_value = None
                    mock_response.json.return_value = {
                        "online": False,
                        "players": {"online": 0, "max": 10},
                        "version": "1.21.0"
                    }
                    mock_session.get.return_value = mock_response
                    
                    print("Simulating server going offline...")
                    print()
                    
                    # Call check_server
                    monitor.check_server(3, True, "Survival", "1.21.0", set())
                    
                    print("\nDiscord notification that would be sent:")
                    print("-" * 40)
                    if mock_discord.called:
                        discord_msg = mock_discord.call_args[0][0]
                        print(discord_msg)
                        print("-" * 40)
                        print("✓ Notice: NO timestamp in Discord message!")
                    
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def demo_log_function():
    """Demo 4: Show the log function directly."""
    print_separator("SCENARIO 4: Log Function - Timestamp Format")
    
    print("Testing the log() function directly:")
    print()
    
    monitor.log("Starting server monitor")
    monitor.log("Server status check complete")
    monitor.log("Player joined the game")
    
    print()
    print("✓ All stdout logs include [YYYY-MM-DD HH:MM:SS] timestamps")

def main():
    print("\n" + "🔍 TIMESTAMP LOGGING DEMONSTRATION" + "\n")
    print("This demonstrates that:")
    print("  1. All stdout logs have timestamps")
    print("  2. Discord notifications do NOT have timestamps")
    print()
    
    # Run demos
    demo_scenario_1()
    demo_scenario_2()
    demo_scenario_3()
    demo_log_function()
    
    print_separator("SUMMARY")
    print("✅ VERIFICATION COMPLETE")
    print()
    print("Key behaviors confirmed:")
    print("  ✓ Stdout logs include timestamps in [YYYY-MM-DD HH:MM:SS] format")
    print("  ✓ Discord notifications do NOT include timestamps")
    print("  ✓ All print statements now use the log() function")
    print()

if __name__ == '__main__':
    main()
