import os
import sys
import time
import json
from discord_webhook import DiscordWebhook

# Create a persistent session for connection pooling
import requests
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
                data.get("version", "Unknown")
            )
    except FileNotFoundError:
        return 0, None, "", SERVER_TYPE, "Unknown"  # Default values with current server type
    except json.JSONDecodeError:
        return 0, None, "", SERVER_TYPE, "Unknown"  # Default values with current server type

def save_current_data(online_count, server_status, gamemode, version):
    """Save current server and player data to a file."""
    # Create data directory if it doesn't exist
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump({
            "online_count": online_count,
            "server_status": server_status,
            "gamemode": gamemode,
            "server_type": SERVER_TYPE,
            "version": version
        }, f)

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

def check_server(previous_online_count, previous_server_status, previous_gamemode, previous_version):
    """Check the Minecraft server for status, player count, and server info."""
    try:
        # Add User-Agent header as required by the API
        headers = {
            "User-Agent": "MC-Server-Discord-Monitor (https://github.com/Philipovic/mc-bedrock-monitor)"
        }
        response = session.get(API_URL, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        server_online = data.get("online", False)
        online_count = data.get("players", {}).get("online", 0)
        max_players = data.get("players", {}).get("max", 0)
        current_version = data.get("version", "Unknown")
        
        # Handle server-type specific information
        motd = ""  # Initialize motd for all server types
        if SERVER_TYPE == "BEDROCK":
            gamemode = data.get("gamemode", "").strip()
            server_info = f"Version: {current_version}"
        else:  # JAVA
            gamemode = ""  # Java servers don't report gamemode
            software = data.get("software", "")
            motd = data.get("motd", {}).get("clean", [""])[0]
            plugins = data.get("plugins", [])
            mods = data.get("mods", [])
            
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
        
        # Notify if the server status changes or it's the first check
        if server_online != previous_server_status or previous_server_status is None:
            data_changed = True
            if server_online:
                message_parts = [f"✅ The server is now ONLINE!", server_info]
                if motd:
                    message_parts.append(f"📝 {motd}")
                message = "\n".join(message_parts)
                print(message)
                send_discord_notification(message)
            else:
                message = "❌ The server is now OFFLINE."
                print(message)
                send_discord_notification(message)
        
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

        # Notify if the player count changes (only if server is online)
        if server_online and online_count != previous_online_count:
            data_changed = True
            if online_count > previous_online_count:
                message_parts = [f"🎮 A player joined! {online_count}/{max_players} players online"]
                
                # Add player list for Java servers when available
                if SERVER_TYPE == "JAVA" and "list" in data.get("players", {}):
                    player_list = data["players"]["list"]
                    if player_list:
                        newest_player = player_list[-1]["name"]  # Get the last player in the list
                        message_parts.append(f"👋 Welcome, {newest_player}!")
                
                message = "\n".join(message_parts)
            elif online_count < previous_online_count:
                message = f"👋 A player left. {online_count}/{max_players} players online"
            
            print(message)
            send_discord_notification(message)

        # Save the updated server status, player count, gamemode and version only if data changed
        if data_changed:
            if server_online:  # Save gamemode and current version only if the server is online
                save_current_data(online_count, server_online, gamemode, current_version)
            else:
                save_current_data(online_count, server_online, previous_gamemode, previous_version)

        return (
            online_count,
            server_online,
            gamemode if server_online else previous_gamemode,
            current_version if server_online else previous_version
        )
    except Exception as e:
        print(f"Error while checking server: {e}")
        return previous_online_count, previous_server_status, previous_gamemode, previous_version

if __name__ == "__main__":
    print(f"Starting Minecraft {SERVER_TYPE} Server Monitor...")
    print(f"Monitoring server: {MC_SERVER}")
    print(f"Check interval: {CHECK_INTERVAL} seconds")
    
    # Load the last known server and player data
    previous_online_count, previous_server_status, previous_gamemode, stored_server_type, previous_version = load_previous_data()
    
    # Warn if server type has changed since last run
    if stored_server_type and stored_server_type != SERVER_TYPE:
        print(f"Warning: Server type has changed from {stored_server_type} to {SERVER_TYPE}")

    while True:
        previous_online_count, previous_server_status, previous_gamemode, previous_version = check_server(
            previous_online_count, previous_server_status, previous_gamemode, previous_version
        )
        time.sleep(CHECK_INTERVAL)
