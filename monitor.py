import os
import sys
import requests
import time
import json
from discord_webhook import DiscordWebhook

# Create a persistent session for connection pooling
session = requests.Session()

# Configuration from environment variables
MC_SERVER = os.getenv("MC_SERVER")
SERVER_TYPE = os.getenv("SERVER_TYPE", "BEDROCK").upper()  # Default to BEDROCK, but prepare for JAVA

if not MC_SERVER:
    # Fail fast if the required MC_SERVER variable isn't provided. This avoids
    # accidentally shipping a hardcoded third-party server in your repository.
    print("Error: environment variable MC_SERVER is not set.\n" \
          "Please set MC_SERVER (for example: play.example.com:19132) " \
          "in your environment or .env file.")
    sys.exit(1)

if SERVER_TYPE not in ["BEDROCK", "JAVA"]:
    print("Error: SERVER_TYPE must be either 'BEDROCK' or 'JAVA'")
    sys.exit(1)

# API Configuration
API_BASE_URL = "https://api.mcsrvstat.us"
API_VERSION = "3"
API_URL = f"{API_BASE_URL}/{'bedrock/' if SERVER_TYPE == 'BEDROCK' else ''}{API_VERSION}/{MC_SERVER}"
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))  # Default: 5 minutes
DATA_FILE = "/app/data/server_data.json"  # Fixed path for data storage
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
REQUEST_TIMEOUT = 10  # Timeout for API requests in seconds
OFFLINE_THRESHOLD = int(os.getenv("OFFLINE_THRESHOLD", "2"))  # Number of consecutive offline checks before marking as offline

def load_previous_data():
    """Load previous server and player data from a file."""
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            return (
                data.get("online_count", 0),
                data.get("server_status", None),
                data.get("gamemode", ""),
                data.get("server_type", SERVER_TYPE),
                data.get("version", "Unknown"),
                set(data.get("player_names", [])),  # Load player names as a set
                data.get("consecutive_offline_checks", 0)  # Load consecutive offline check count
            )
    except FileNotFoundError:
        return 0, None, "", SERVER_TYPE, "Unknown", set(), 0  # Default values with current server type
    except json.JSONDecodeError:
        return 0, None, "", SERVER_TYPE, "Unknown", set(), 0  # Default values with current server type

def save_current_data(online_count, server_status, gamemode, version, player_names=None, consecutive_offline_checks=0):
    """Save current server and player data to a file."""
    # Create data directory if it doesn't exist
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    data_to_save = {
        "online_count": online_count,
        "server_status": server_status,
        "gamemode": gamemode,
        "server_type": SERVER_TYPE,
        "version": version,
        "consecutive_offline_checks": consecutive_offline_checks
    }
    # Save player names if provided (convert set to list for JSON serialization)
    if player_names is not None:
        data_to_save["player_names"] = list(player_names)
    
    with open(DATA_FILE, "w") as f:
        json.dump(data_to_save, f)

def send_discord_notification(message):
    """Send a notification to Discord using a webhook."""
    if not DISCORD_WEBHOOK_URL:
        print("Discord Webhook URL not set. Skipping notification.")
        return
    try:
        webhook = DiscordWebhook(url=DISCORD_WEBHOOK_URL, content=message)
        response = webhook.execute()
        if response.status_code == 200:
            print("Notification sent to Discord.")
        else:
            print(f"Failed to send Discord notification. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error sending Discord notification: {e}")

def check_server(previous_online_count, previous_server_status, previous_gamemode, previous_version, previous_player_names, consecutive_offline_checks):
    """Check the Minecraft server for status, player count, and server info."""
    
    try:
        # Add User-Agent header as required by the API
        headers = {
            "User-Agent": "MC-Server-Discord-Monitor (https://github.com/Philipovic/mc-bedrock-monitor)"
        }
        response = session.get(API_URL, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
    except requests.exceptions.ConnectionError as e:
        # Network is down, DNS failure, or API server unreachable
        print(f"API unreachable (connection error): {e}")
        return previous_online_count, previous_server_status, previous_gamemode, previous_version, previous_player_names, consecutive_offline_checks
    except requests.exceptions.Timeout as e:
        # Request timed out
        print(f"API unreachable (timeout): {e}")
        return previous_online_count, previous_server_status, previous_gamemode, previous_version, previous_player_names, consecutive_offline_checks
    except requests.exceptions.HTTPError as e:
        # Server returned an error status code
        status_code = e.response.status_code if e.response is not None else "unknown"
        print(f"API error (HTTP {status_code}): {e}")
        return previous_online_count, previous_server_status, previous_gamemode, previous_version, previous_player_names, consecutive_offline_checks
    except requests.exceptions.RequestException as e:
        # Any other request-related error
        print(f"API unreachable (request error): {e}")
        return previous_online_count, previous_server_status, previous_gamemode, previous_version, previous_player_names, consecutive_offline_checks
    except json.JSONDecodeError as e:
        # Invalid JSON response from API
        print(f"API returned invalid JSON: {e}")
        return previous_online_count, previous_server_status, previous_gamemode, previous_version, previous_player_names, consecutive_offline_checks
    
    server_online = data.get("online", False)
    online_count = data.get("players", {}).get("online", 0)
    max_players = data.get("players", {}).get("max", 0)
    current_version = data.get("version", "Unknown")
    
    # Handle offline detection with threshold to prevent false positives
    # If server appears offline, increment counter; if online, reset counter
    if not server_online:
        consecutive_offline_checks += 1
        # Only consider server truly offline after reaching threshold
        is_truly_offline = consecutive_offline_checks >= OFFLINE_THRESHOLD
    else:
        consecutive_offline_checks = 0
        is_truly_offline = False
    
    # Initialize variables that may be used later
    motd = ""
    gamemode = ""
    current_player_names = set()
    
    # Handle server-type specific information
    if SERVER_TYPE == "BEDROCK":
        gamemode = data.get("gamemode", "").strip()
        server_info = f"Version: {current_version}"
        # Bedrock API doesn't provide individual player names
    else:  # JAVA
        # Java servers don't report gamemode, but do have MOTD
        software = data.get("software", "")
        motd = data.get("motd", {}).get("clean", [""])[0] if data.get("motd") else ""
        plugins = data.get("plugins", [])
        mods = data.get("mods", [])
        
        # Get current player names for Java servers
        if "list" in data.get("players", {}):
            player_list = data["players"]["list"]
            current_player_names = set(player["name"] for player in player_list)
        
        # Build server info string using list for efficient concatenation
        info_parts = [f"Version: {current_version}"]
        if software:
            info_parts.append(f"({software})")
        if plugins:
            plugin_count = len(plugins)
            info_parts.append(f"{plugin_count} plugin{'s' if plugin_count != 1 else ''}")
        if mods:
            mod_count = len(mods)
            info_parts.append(f"{mod_count} mod{'s' if mod_count != 1 else ''}")
        
        server_info = " | ".join(info_parts)

    # Track if we need to save data
    data_changed = False
    
    # Determine the effective server status for notifications
    # When server appears offline but hasn't reached threshold, keep previous status
    effective_server_status = server_online if server_online else (False if is_truly_offline else previous_server_status)
    
    # Notify if the server status changes or it's the first check
    # Only notify about offline status if we've confirmed it with multiple checks
    if effective_server_status != previous_server_status or previous_server_status is None:
        data_changed = True
        if effective_server_status:
            # Format version in parentheses on the same line as ONLINE message
            version_str = f" ({current_version})" if current_version and current_version != "Unknown" else ""
            message_parts = [f"✅ The server is now ONLINE!{version_str}"]
            # Add additional server info (software, plugins, mods) for Java servers
            if SERVER_TYPE == "JAVA":
                extra_info = []
                software = data.get("software", "")
                plugins = data.get("plugins", [])
                mods = data.get("mods", [])
                if software:
                    extra_info.append(software)
                if plugins:
                    plugin_count = len(plugins)
                    extra_info.append(f"{plugin_count} plugin{'s' if plugin_count != 1 else ''}")
                if mods:
                    mod_count = len(mods)
                    extra_info.append(f"{mod_count} mod{'s' if mod_count != 1 else ''}")
                if extra_info:
                    message_parts.append(" | ".join(extra_info))
            if motd:
                message_parts.append(f"📝 {motd}")
            message = "\n".join(message_parts)
            print(message)
            send_discord_notification(message)
        else:
            message = "❌ The server is now OFFLINE."
            print(message)
            send_discord_notification(message)
    elif not server_online and consecutive_offline_checks < OFFLINE_THRESHOLD:
        # Log when we detect potential offline state but waiting for confirmation
        print(f"⚠️  Server appears offline (check {consecutive_offline_checks}/{OFFLINE_THRESHOLD}). Waiting for confirmation...")
    
    # Notify if server version changes while online
    elif server_online and current_version != previous_version and current_version != "Unknown":
        data_changed = True
        message = f"🔄 Server version changed: {previous_version} → {current_version}"
        print(message)
        send_discord_notification(message)

    # Notify if the gamemode changes (only for Bedrock servers and when server is online)
    if SERVER_TYPE == "BEDROCK" and server_online and gamemode != previous_gamemode:
        data_changed = True
        message = f"ℹ️ Gamemode changed to: {gamemode}"
        print(message)
        send_discord_notification(message)

    # Handle player join/leave events
    if server_online:
        if SERVER_TYPE == "JAVA" and (current_player_names or previous_player_names):
            # For Java servers, we can track individual players
            joined_players = current_player_names - previous_player_names
            left_players = previous_player_names - current_player_names
            
            # Build message parts for joins and leaves
            message_parts = []
            
            # Add join notifications
            if joined_players:
                data_changed = True
                for player_name in sorted(joined_players):  # Sort for consistent ordering
                    message_parts.append(f"🎮 {player_name} joined!")
            
            # Add leave notifications
            if left_players:
                data_changed = True
                for player_name in sorted(left_players):  # Sort for consistent ordering
                    message_parts.append(f"👋 {player_name} left.")
            
            # Add player count once at the end if there were any changes
            if message_parts:
                message_parts.append(f"📊 {online_count}/{max_players} players online")
                message = "\n".join(message_parts)
                print(message)
                send_discord_notification(message)
                
        elif online_count != previous_online_count:
            # For Bedrock servers or when player names aren't available, fall back to count-based detection
            data_changed = True
            player_diff = online_count - previous_online_count
            
            if player_diff > 0:
                if player_diff == 1:
                    message = f"🎮 A player joined!\n📊 {online_count}/{max_players} players online"
                else:
                    message = f"🎮 {player_diff} players joined!\n📊 {online_count}/{max_players} players online"
            else:  # player_diff < 0
                player_diff = abs(player_diff)
                if player_diff == 1:
                    message = f"👋 A player left.\n📊 {online_count}/{max_players} players online"
                else:
                    message = f"👋 {player_diff} players left.\n📊 {online_count}/{max_players} players online"
            
            print(message)
            send_discord_notification(message)

    # Save the updated server status, player count, gamemode, version and player names
    # Always save to persist consecutive_offline_checks counter
    if data_changed or consecutive_offline_checks > 0:
        if server_online:  # Save gamemode, current version and player names only if the server is online
            save_current_data(online_count, effective_server_status, gamemode, current_version, current_player_names, consecutive_offline_checks)
        else:
            save_current_data(online_count, effective_server_status, previous_gamemode, previous_version, set(), consecutive_offline_checks)

    return (
        online_count,
        effective_server_status,
        gamemode if server_online else previous_gamemode,
        current_version if server_online else previous_version,
        current_player_names if server_online else set(),
        consecutive_offline_checks
    )

if __name__ == "__main__":
    print(f"Starting Minecraft {SERVER_TYPE} Server Monitor...")
    print(f"Monitoring server: {MC_SERVER}")
    print(f"Check interval: {CHECK_INTERVAL} seconds")
    print(f"Offline threshold: {OFFLINE_THRESHOLD} consecutive checks")
    
    # Load the last known server and player data
    previous_online_count, previous_server_status, previous_gamemode, stored_server_type, previous_version, previous_player_names, consecutive_offline_checks = load_previous_data()
    
    # Warn if server type has changed since last run
    if stored_server_type and stored_server_type != SERVER_TYPE:
        print(f"Warning: Server type has changed from {stored_server_type} to {SERVER_TYPE}")

    while True:
        previous_online_count, previous_server_status, previous_gamemode, previous_version, previous_player_names, consecutive_offline_checks = check_server(
            previous_online_count, previous_server_status, previous_gamemode, previous_version, previous_player_names, consecutive_offline_checks
        )
        time.sleep(CHECK_INTERVAL)
