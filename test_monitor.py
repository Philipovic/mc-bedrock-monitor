import unittest
from unittest.mock import patch, Mock, MagicMock
import requests
import json
import os
import tempfile
import sys

# Import the monitor module
import monitor


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


if __name__ == '__main__':
    unittest.main()
