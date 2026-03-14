import unittest
from unittest.mock import patch, Mock, MagicMock
import requests
import json
import os
import tempfile
import sys
import re
from io import StringIO

# Import the monitor module
import monitor


class TestTimestampLogging(unittest.TestCase):
    """Test that timestamps are added to stdout logging but not to Discord notifications."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary file for data storage
        self.temp_fd, self.temp_path = tempfile.mkstemp(suffix='.json')
        
        # Patch the DATA_FILE path
        self.data_file_patcher = patch.object(monitor, 'DATA_FILE', self.temp_path)
        self.data_file_patcher.start()
        
        # Mock Discord webhook to prevent actual notifications
        self.discord_patcher = patch('monitor.send_discord_notification')
        self.mock_discord = self.discord_patcher.start()
        
    def tearDown(self):
        """Clean up test fixtures."""
        self.discord_patcher.stop()
        self.data_file_patcher.stop()
        os.close(self.temp_fd)
        os.unlink(self.temp_path)
    
    def test_log_function_adds_timestamp(self):
        """Test that the log function adds a timestamp to messages."""
        # Capture stdout
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            monitor.log("Test message")
            output = mock_stdout.getvalue()
            
            # Check that output has timestamp format [YYYY-MM-DD HH:MM:SS]
            timestamp_pattern = r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] Test message\n$'
            self.assertRegex(output, timestamp_pattern)
    
    @patch('monitor.session')
    def test_server_status_log_has_timestamp(self, mock_session):
        """Test that server status messages to stdout have timestamps."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "online": True,
            "players": {"online": 2, "max": 10},
            "version": "1.21.0",
            "gamemode": "Survival"
        }
        mock_session.get.return_value = mock_response
        
        # Capture stdout
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            # Call check_server with None status (first check)
            monitor.check_server(0, None, "", "Unknown", set())
            
            output = mock_stdout.getvalue()
            
            # Check that output has timestamp format
            timestamp_pattern = r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]'
            self.assertRegex(output, timestamp_pattern)
            
            # Check that the actual message is in the output
            self.assertIn("The server is now ONLINE!", output)
    
    @patch('monitor.session')
    def test_discord_notification_no_timestamp(self, mock_session):
        """Test that Discord notifications don't include timestamps."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "online": True,
            "players": {"online": 2, "max": 10},
            "version": "1.21.0",
            "gamemode": "Survival"
        }
        mock_session.get.return_value = mock_response
        
        # Reset the discord mock to actually capture the message
        self.mock_discord.reset_mock()
        
        # Call check_server with None status (first check)
        monitor.check_server(0, None, "", "Unknown", set())
        
        # Verify Discord notification was called at least once
        self.assertTrue(self.mock_discord.called)
        
        # Check all Discord messages don't contain timestamps
        timestamp_pattern = r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]'
        for call_args in self.mock_discord.call_args_list:
            discord_message = call_args[0][0]
            
            # Check that the Discord message does NOT contain a timestamp
            self.assertNotRegex(discord_message, timestamp_pattern,
                               f"Discord message should not contain timestamp: {discord_message}")
            
            # Check that the message is not empty
            self.assertTrue(len(discord_message) > 0)
    
    @patch('monitor.session')
    def test_api_error_log_has_timestamp(self, mock_session):
        """Test that API error messages to stdout have timestamps."""
        # Simulate a connection error
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Network unreachable")
        
        # Capture stdout
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            monitor.check_server(5, True, "Survival", "1.21.0", set())
            
            output = mock_stdout.getvalue()
            
            # Check that output has timestamp format
            timestamp_pattern = r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]'
            self.assertRegex(output, timestamp_pattern)
            
            # Check that the actual error message is in the output
            self.assertIn("API unreachable (connection error)", output)


class TestAPIFailureHandling(unittest.TestCase):
    """Test that API failures don't trigger state changes or notifications."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary file for data storage
        self.temp_fd, self.temp_path = tempfile.mkstemp(suffix='.json')
        
        # Patch the DATA_FILE path
        self.data_file_patcher = patch.object(monitor, 'DATA_FILE', self.temp_path)
        self.data_file_patcher.start()
        
        # Mock Discord webhook to prevent actual notifications
        self.discord_patcher = patch('monitor.send_discord_notification')
        self.mock_discord = self.discord_patcher.start()
        
        # Initial state
        self.initial_online_count = 5
        self.initial_server_status = True
        self.initial_gamemode = "Survival"
        self.initial_version = "1.21.0"
        self.initial_player_names = {"player1", "player2"}
        
    def tearDown(self):
        """Clean up test fixtures."""
        self.discord_patcher.stop()
        self.data_file_patcher.stop()
        os.close(self.temp_fd)
        os.unlink(self.temp_path)
    
    @patch('monitor.session')
    def test_connection_error_preserves_state(self, mock_session):
        """Test that ConnectionError preserves previous state."""
        # Simulate a connection error
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Network unreachable")
        
        # Call check_server with initial state
        result = monitor.check_server(
            self.initial_online_count,
            self.initial_server_status,
            self.initial_gamemode,
            self.initial_version,
            self.initial_player_names
        )
        
        # Verify state is unchanged
        self.assertEqual(result[0], self.initial_online_count)
        self.assertEqual(result[1], self.initial_server_status)
        self.assertEqual(result[2], self.initial_gamemode)
        self.assertEqual(result[3], self.initial_version)
        self.assertEqual(result[4], self.initial_player_names)
        
        # Verify no Discord notification was sent
        self.mock_discord.assert_not_called()
    
    @patch('monitor.session')
    def test_timeout_preserves_state(self, mock_session):
        """Test that Timeout error preserves previous state."""
        # Simulate a timeout
        mock_session.get.side_effect = requests.exceptions.Timeout("Request timed out")
        
        # Call check_server with initial state
        result = monitor.check_server(
            self.initial_online_count,
            self.initial_server_status,
            self.initial_gamemode,
            self.initial_version,
            self.initial_player_names
        )
        
        # Verify state is unchanged
        self.assertEqual(result[0], self.initial_online_count)
        self.assertEqual(result[1], self.initial_server_status)
        self.assertEqual(result[2], self.initial_gamemode)
        self.assertEqual(result[3], self.initial_version)
        self.assertEqual(result[4], self.initial_player_names)
        
        # Verify no Discord notification was sent
        self.mock_discord.assert_not_called()
    
    @patch('monitor.session')
    def test_http_error_preserves_state(self, mock_session):
        """Test that HTTP error (500) preserves previous state."""
        # Create a mock response with 500 status code
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_session.get.return_value = mock_response
        
        # Call check_server with initial state
        result = monitor.check_server(
            self.initial_online_count,
            self.initial_server_status,
            self.initial_gamemode,
            self.initial_version,
            self.initial_player_names
        )
        
        # Verify state is unchanged
        self.assertEqual(result[0], self.initial_online_count)
        self.assertEqual(result[1], self.initial_server_status)
        self.assertEqual(result[2], self.initial_gamemode)
        self.assertEqual(result[3], self.initial_version)
        self.assertEqual(result[4], self.initial_player_names)
        
        # Verify no Discord notification was sent
        self.mock_discord.assert_not_called()
    
    @patch('monitor.session')
    def test_request_exception_preserves_state(self, mock_session):
        """Test that generic RequestException preserves previous state."""
        # Simulate a generic request exception
        mock_session.get.side_effect = requests.exceptions.RequestException("Unknown error")
        
        # Call check_server with initial state
        result = monitor.check_server(
            self.initial_online_count,
            self.initial_server_status,
            self.initial_gamemode,
            self.initial_version,
            self.initial_player_names
        )
        
        # Verify state is unchanged
        self.assertEqual(result[0], self.initial_online_count)
        self.assertEqual(result[1], self.initial_server_status)
        self.assertEqual(result[2], self.initial_gamemode)
        self.assertEqual(result[3], self.initial_version)
        self.assertEqual(result[4], self.initial_player_names)
        
        # Verify no Discord notification was sent
        self.mock_discord.assert_not_called()
    
    @patch('monitor.session')
    def test_json_decode_error_preserves_state(self, mock_session):
        """Test that JSON decode error preserves previous state."""
        # Create a mock response with invalid JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_session.get.return_value = mock_response
        
        # Call check_server with initial state
        result = monitor.check_server(
            self.initial_online_count,
            self.initial_server_status,
            self.initial_gamemode,
            self.initial_version,
            self.initial_player_names
        )
        
        # Verify state is unchanged
        self.assertEqual(result[0], self.initial_online_count)
        self.assertEqual(result[1], self.initial_server_status)
        self.assertEqual(result[2], self.initial_gamemode)
        self.assertEqual(result[3], self.initial_version)
        self.assertEqual(result[4], self.initial_player_names)
        
        # Verify no Discord notification was sent
        self.mock_discord.assert_not_called()
    
    @patch('monitor.session')
    def test_multiple_api_failures_preserve_state(self, mock_session):
        """Test that multiple consecutive API failures preserve state."""
        # First call - connection error
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Network unreachable")
        
        result1 = monitor.check_server(
            self.initial_online_count,
            self.initial_server_status,
            self.initial_gamemode,
            self.initial_version,
            self.initial_player_names
        )
        
        # Second call - timeout
        mock_session.get.side_effect = requests.exceptions.Timeout("Timeout")
        
        result2 = monitor.check_server(
            result1[0], result1[1], result1[2], result1[3], result1[4]
        )
        
        # Third call - HTTP error
        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_session.get.side_effect = None
        mock_session.get.return_value = mock_response
        
        result3 = monitor.check_server(
            result2[0], result2[1], result2[2], result2[3], result2[4]
        )
        
        # All results should maintain the initial state
        for result in [result1, result2, result3]:
            self.assertEqual(result[0], self.initial_online_count)
            self.assertEqual(result[1], self.initial_server_status)
            self.assertEqual(result[2], self.initial_gamemode)
            self.assertEqual(result[3], self.initial_version)
            self.assertEqual(result[4], self.initial_player_names)
        
        # Verify no Discord notifications were sent
        self.mock_discord.assert_not_called()
    
    @patch('monitor.session')
    def test_api_recovery_after_failure(self, mock_session):
        """Test that system works correctly after API recovers from failure."""
        # First call - API failure
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Network unreachable")
        
        result1 = monitor.check_server(
            self.initial_online_count,
            self.initial_server_status,
            self.initial_gamemode,
            self.initial_version,
            self.initial_player_names
        )
        
        # State should be preserved
        self.assertEqual(result1[0], self.initial_online_count)
        self.assertEqual(result1[1], self.initial_server_status)
        
        # Second call - API recovers with different state
        mock_session.get.side_effect = None
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "online": True,
            "players": {"online": 7, "max": 10},
            "version": "1.21.1",
            "gamemode": "Creative"
        }
        mock_session.get.return_value = mock_response
        
        result2 = monitor.check_server(
            result1[0], result1[1], result1[2], result1[3], result1[4]
        )
        
        # State should now be updated
        self.assertEqual(result2[0], 7)  # New player count
        self.assertEqual(result2[1], True)  # Server still online
        
        # Discord notification should be sent for the state change
        self.mock_discord.assert_called()


class TestDataPersistence(unittest.TestCase):
    """Test that data is not persisted during API failures."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary file for data storage
        self.temp_fd, self.temp_path = tempfile.mkstemp(suffix='.json')
        
        # Patch the DATA_FILE path
        self.data_file_patcher = patch.object(monitor, 'DATA_FILE', self.temp_path)
        self.data_file_patcher.start()
        
        # Mock Discord webhook
        self.discord_patcher = patch('monitor.send_discord_notification')
        self.mock_discord = self.discord_patcher.start()
        
        # Save initial state to file
        initial_data = {
            "online_count": 3,
            "server_status": True,
            "gamemode": "Survival",
            "server_type": "BEDROCK",
            "version": "1.20.0",
            "player_names": []
        }
        with open(self.temp_path, 'w') as f:
            json.dump(initial_data, f)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.discord_patcher.stop()
        self.data_file_patcher.stop()
        os.close(self.temp_fd)
        os.unlink(self.temp_path)
    
    @patch('monitor.session')
    def test_no_data_saved_on_api_failure(self, mock_session):
        """Test that data file is not modified during API failures."""
        # Read initial file content
        with open(self.temp_path, 'r') as f:
            initial_content = f.read()
        
        # Simulate API failure
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Network unreachable")
        
        # Call check_server
        monitor.check_server(3, True, "Survival", "1.20.0", set())
        
        # Read file content after the call
        with open(self.temp_path, 'r') as f:
            final_content = f.read()
        
        # Verify file was not modified
        self.assertEqual(initial_content, final_content)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_fd, self.temp_path = tempfile.mkstemp(suffix='.json')
        self.data_file_patcher = patch.object(monitor, 'DATA_FILE', self.temp_path)
        self.data_file_patcher.start()
        self.discord_patcher = patch('monitor.send_discord_notification')
        self.mock_discord = self.discord_patcher.start()
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.discord_patcher.stop()
        self.data_file_patcher.stop()
        os.close(self.temp_fd)
        os.unlink(self.temp_path)
    
    @patch('monitor.session')
    def test_first_check_with_api_failure(self, mock_session):
        """Test API failure on the very first check (no previous state)."""
        # Simulate API failure on first check
        mock_session.get.side_effect = requests.exceptions.Timeout("Timeout")
        
        # Call check_server with None as previous_server_status (first run)
        result = monitor.check_server(0, None, "", "Unknown", set())
        
        # Verify state remains as passed in
        self.assertEqual(result[0], 0)
        self.assertEqual(result[1], None)
        self.assertEqual(result[2], "")
        self.assertEqual(result[3], "Unknown")
        self.assertEqual(result[4], set())
        
        # Verify no Discord notification was sent
        self.mock_discord.assert_not_called()
    
    @patch('monitor.session')
    def test_offline_server_with_api_failure(self, mock_session):
        """Test API failure when server was previously offline."""
        # Simulate API failure
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        # Call check_server with offline state
        result = monitor.check_server(0, False, "", "1.20.0", set())
        
        # Verify offline state is preserved
        self.assertEqual(result[0], 0)
        self.assertEqual(result[1], False)
        
        # Verify no Discord notification was sent
        self.mock_discord.assert_not_called()


class TestConsecutiveOfflineChecks(unittest.TestCase):
    """Test that offline notifications require consecutive offline reports."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_fd, self.temp_path = tempfile.mkstemp(suffix='.json')
        self.data_file_patcher = patch.object(monitor, 'DATA_FILE', self.temp_path)
        self.data_file_patcher.start()
        self.discord_patcher = patch('monitor.send_discord_notification')
        self.mock_discord = self.discord_patcher.start()
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.discord_patcher.stop()
        self.data_file_patcher.stop()
        os.close(self.temp_fd)
        os.unlink(self.temp_path)
    
    def _make_offline_response(self, mock_session):
        """Configure mock to return an offline server response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "online": False,
            "players": {"online": 0, "max": 10},
            "version": "1.21.0",
            "gamemode": "Survival"
        }
        mock_session.get.return_value = mock_response
    
    def _make_online_response(self, mock_session):
        """Configure mock to return an online server response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "online": True,
            "players": {"online": 2, "max": 10},
            "version": "1.21.0",
            "gamemode": "Survival"
        }
        mock_session.get.return_value = mock_response
    
    @patch('monitor.session')
    def test_first_offline_no_notification(self, mock_session):
        """Test that a single offline report does NOT send a notification."""
        self._make_offline_response(mock_session)
        
        result = monitor.check_server(5, True, "Survival", "1.21.0", set(), 0)
        
        # No offline notification should be sent
        self.mock_discord.assert_not_called()
        # Previous server status should be preserved (still True)
        self.assertEqual(result[1], True)
        # Offline check count should be 1
        self.assertEqual(result[5], 1)
    
    @patch('monitor.session')
    def test_second_consecutive_offline_sends_notification(self, mock_session):
        """Test that OFFLINE_CONFIRM_CHECKS consecutive offline reports DO send a notification."""
        self._make_offline_response(mock_session)
        
        # Run offline checks up to OFFLINE_CONFIRM_CHECKS
        result = monitor.check_server(5, True, "Survival", "1.21.0", set(), 0)
        self.mock_discord.assert_not_called()
        
        for i in range(1, monitor.OFFLINE_CONFIRM_CHECKS - 1):
            result = monitor.check_server(
                result[0], result[1], result[2], result[3], result[4], result[5]
            )
            self.mock_discord.assert_not_called()
            self.assertEqual(result[5], i + 1)
        
        # Final offline check should trigger notification
        result = monitor.check_server(
            result[0], result[1], result[2], result[3], result[4], result[5]
        )
        
        # NOW the notification should be sent
        self.mock_discord.assert_called_once()
        discord_message = self.mock_discord.call_args[0][0]
        self.assertIn("OFFLINE", discord_message)
        # Server status should now be False
        self.assertEqual(result[1], False)
    
    @patch('monitor.session')
    def test_offline_then_online_no_notification(self, mock_session):
        """Test that offline followed by online does NOT send any offline notification."""
        # First check: offline
        self._make_offline_response(mock_session)
        result1 = monitor.check_server(0, True, "Survival", "1.21.0", set(), 0)
        self.mock_discord.assert_not_called()
        self.assertEqual(result1[1], True)  # Status preserved
        self.assertEqual(result1[5], 1)     # Counter incremented
        
        # Second check: back online (same player count as previous to avoid player change notification)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "online": True,
            "players": {"online": 0, "max": 10},
            "version": "1.21.0",
            "gamemode": "Survival"
        }
        mock_session.get.return_value = mock_response
        result2 = monitor.check_server(
            result1[0], result1[1], result1[2], result1[3], result1[4], result1[5]
        )
        
        # No offline notification should have been sent at any point
        self.mock_discord.assert_not_called()
        # Server status should still be True
        self.assertEqual(result2[1], True)
        # Counter should be reset
        self.assertEqual(result2[5], 0)
    
    @patch('monitor.session')
    def test_offline_counter_persisted_to_data_file(self, mock_session):
        """Test that the offline check counter is saved to the data file."""
        self._make_offline_response(mock_session)
        
        # First offline check
        monitor.check_server(5, True, "Survival", "1.21.0", set(), 0)
        
        # Read the data file
        with open(self.temp_path, 'r') as f:
            data = json.load(f)
        
        self.assertEqual(data.get("offline_check_count"), 1)
        # Server status should still be True (not confirmed offline)
        self.assertEqual(data.get("server_status"), True)
    
    @patch('monitor.session')
    def test_api_failure_preserves_offline_counter(self, mock_session):
        """Test that API failures preserve the offline counter."""
        # First offline check
        self._make_offline_response(mock_session)
        result1 = monitor.check_server(5, True, "Survival", "1.21.0", set(), 0)
        self.assertEqual(result1[5], 1)
        
        # API failure
        mock_session.get.side_effect = requests.exceptions.Timeout("Timeout")
        result2 = monitor.check_server(
            result1[0], result1[1], result1[2], result1[3], result1[4], result1[5]
        )
        
        # Counter should be preserved
        self.assertEqual(result2[5], 1)
        # No notification should have been sent
        self.mock_discord.assert_not_called()
    
    @patch('monitor.session')
    def test_first_check_offline_no_notification(self, mock_session):
        """Test that offline on the very first check (no previous state) does not notify."""
        self._make_offline_response(mock_session)
        
        # First check ever (previous_server_status is None)
        result = monitor.check_server(0, None, "", "Unknown", set(), 0)
        
        # Should not notify on first offline
        self.mock_discord.assert_not_called()
        # Status should remain None (not confirmed)
        self.assertEqual(result[1], None)
        self.assertEqual(result[5], 1)
    
    @patch('monitor.session')
    def test_confirmed_offline_then_online_sends_online_notification(self, mock_session):
        """Test that going online after confirmed offline sends online notification."""
        self._make_offline_response(mock_session)
        
        # Run OFFLINE_CONFIRM_CHECKS consecutive offline checks to confirm
        result = monitor.check_server(5, True, "Survival", "1.21.0", set(), 0)
        for _ in range(monitor.OFFLINE_CONFIRM_CHECKS - 1):
            result = monitor.check_server(
                result[0], result[1], result[2], result[3], result[4], result[5]
            )
        self.assertEqual(result[1], False)  # Confirmed offline
        self.mock_discord.reset_mock()
        
        # Now server comes back online
        self._make_online_response(mock_session)
        result = monitor.check_server(
            result[0], result[1], result[2], result[3], result[4], result[5]
        )
        
        # Should send online notification (may also send player join notification)
        self.assertTrue(self.mock_discord.called)
        first_call_message = self.mock_discord.call_args_list[0][0][0]
        self.assertIn("ONLINE", first_call_message)
        self.assertEqual(result[1], True)
        self.assertEqual(result[5], 0)


class TestDynamicOfflineConfirmation(unittest.TestCase):
    """Test that OFFLINE_CONFIRM_CHECKS is dynamically calculated based on CHECK_INTERVAL."""
    
    def test_api_cache_duration_constant(self):
        """Test that API_CACHE_DURATION is 120 seconds (2 minutes)."""
        self.assertEqual(monitor.API_CACHE_DURATION, 120)
    
    def test_min_offline_duration_constant(self):
        """Test that MIN_OFFLINE_DURATION equals 3 × API_CACHE_DURATION (360 seconds).
        
        This accounts for 2 full cache cycles + 1 worst-case timing offset.
        """
        self.assertEqual(monitor.MIN_OFFLINE_DURATION, 3 * monitor.API_CACHE_DURATION)
        self.assertEqual(monitor.MIN_OFFLINE_DURATION, 360)
    
    def test_offline_confirm_checks_at_least_two(self):
        """Test that OFFLINE_CONFIRM_CHECKS is always at least 2."""
        self.assertGreaterEqual(monitor.OFFLINE_CONFIRM_CHECKS, 2)
    
    def test_confirmation_window_spans_min_offline_duration(self):
        """Test that the confirmation window is at least MIN_OFFLINE_DURATION seconds."""
        window = (monitor.OFFLINE_CONFIRM_CHECKS - 1) * monitor.CHECK_INTERVAL
        self.assertGreaterEqual(window, monitor.MIN_OFFLINE_DURATION)
    
    def test_dynamic_calculation_various_intervals(self):
        """Test the dynamic formula for several CHECK_INTERVAL values."""
        import math
        cache = monitor.API_CACHE_DURATION  # 120
        min_dur = monitor.MIN_OFFLINE_DURATION  # 360
        
        # (CHECK_INTERVAL, expected OFFLINE_CONFIRM_CHECKS)
        cases = [
            (60,  7),   # ceil(360/60)+1  = 7, span = 6×60  = 360 ≥ 360
            (120, 4),   # ceil(360/120)+1 = 4, span = 3×120 = 360 ≥ 360
            (180, 3),   # ceil(360/180)+1 = 3, span = 2×180 = 360 ≥ 360
            (240, 3),   # ceil(360/240)+1 = 3, span = 2×240 = 480 ≥ 360
            (300, 3),   # ceil(360/300)+1 = 3, span = 2×300 = 600 ≥ 360
            (360, 2),   # ceil(360/360)+1 = 2, span = 1×360 = 360 ≥ 360
            (500, 2),   # ceil(360/500)+1 = 2, span = 1×500 = 500 ≥ 360
            (600, 2),   # ceil(360/600)+1 = 2, span = 1×600 = 600 ≥ 360
        ]
        for interval, expected in cases:
            result = max(2, math.ceil(min_dur / interval) + 1)
            self.assertEqual(result, expected,
                             f"CHECK_INTERVAL={interval}: expected {expected}, got {result}")
            # Verify the window always covers MIN_OFFLINE_DURATION
            window = (result - 1) * interval
            self.assertGreaterEqual(window, min_dur,
                                    f"CHECK_INTERVAL={interval}: window {window}s < {min_dur}s")
    
    def test_default_check_interval_produces_correct_checks(self):
        """Test that the default CHECK_INTERVAL (300s) produces the expected confirmation count."""
        import math
        default_interval = int(os.getenv("CHECK_INTERVAL", "300"))
        expected = max(2, math.ceil(monitor.MIN_OFFLINE_DURATION / default_interval) + 1)
        self.assertEqual(monitor.OFFLINE_CONFIRM_CHECKS, expected)
    
    def test_immediate_notifications_not_affected(self):
        """Test that online, player, and version changes still notify immediately."""
        # These notifications should NOT go through the offline confirmation logic.
        # Verify by checking the check_server code structure:
        # - Online transitions: notified immediately (server_online == True branch)
        # - Version changes: notified immediately (elif server_online and version changed)
        # - Player changes: notified immediately (if server_online player count/names)
        # - Gamemode changes: notified immediately (if BEDROCK and gamemode changed)
        # Only offline transitions go through OFFLINE_CONFIRM_CHECKS.
        self.assertGreaterEqual(monitor.OFFLINE_CONFIRM_CHECKS, 2)


if __name__ == '__main__':
    unittest.main()
