import os
import sys
import requests
import time
import json
from discord_webhook import DiscordWebhook

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
        response = requests.get(API_URL, headers=headers).json()
        
        server_online = response.get("online", False)
        online_count = response.get("players", {}).get("online", 0)
        max_players = response.get("players", {}).get("max", 0)
        current_version = response.get("version", "Unknown")
        
        # Handle server-type specific information
        if SERVER_TYPE == "BEDROCK":
            gamemode = response.get("gamemode", "").strip()
            server_info = f"Version: {current_version}"
        else:  # JAVA
            gamemode = ""  # Java servers don't report gamemode
            software = response.get("software", "")
            motd = response.get("motd", {}).get("clean", [""])[0]
            plugins = response.get("plugins", [])
            mods = response.get("mods", [])
            
            # Build server info string
            server_info = f"Version: {current_version}"
            if software:
                server_info += f" ({software})"
            if plugins:
                plugin_count = len(plugins)
                server_info += f" | {plugin_count} plugin{'s' if plugin_count != 1 else ''}"
            if mods:
                mod_count = len(mods)
                server_info += f" | {mod_count} mod{'s' if mod_count != 1 else ''}"

        # Notify if the server status changes or it's the first check
        if server_online != previous_server_status or previous_server_status is None:
            if server_online:
                message = f"✅ The server is now ONLINE!\n{server_info}"
                if motd:
                    message += f"\n📝 {motd}"
                print(message)
                send_discord_notification(message)
            else:
                message = f"❌ The server is now OFFLINE."
                print(message)
                send_discord_notification(message)
        
        # Notify if server version changes while online
        elif server_online and current_version != previous_version and current_version != "Unknown":
            message = f"🔄 Server version changed: {previous_version} → {current_version}"
            print(message)
            send_discord_notification(message)

        # Notify if the gamemode changes (only for Bedrock servers and when server is online)
        if SERVER_TYPE == "BEDROCK" and server_online and gamemode != previous_gamemode:
            message = f"ℹ️ Gamemode changed to: {gamemode}"
            print(message)
            send_discord_notification(message)

        # Notify if the player count changes (only if server is online)
        if server_online and online_count != previous_online_count:
            if online_count > previous_online_count:
                message = f"🎮 A player joined! {online_count}/{max_players} players online"
                
                # Add player list for Java servers when available
                if SERVER_TYPE == "JAVA" and "list" in response.get("players", {}):
                    player_list = response["players"]["list"]
                    if player_list:
                        newest_player = player_list[-1]["name"]  # Get the last player in the list
                        message += f"\n👋 Welcome, {newest_player}!"
            elif online_count < previous_online_count:
                message = f"👋 A player left. {online_count}/{max_players} players online"
            
            print(message)
            send_discord_notification(message)

        # Save the updated server status, player count, gamemode and version
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
