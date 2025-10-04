import os
import sys
import requests
import time
import json
from discord_webhook import DiscordWebhook

# Configuration from environment variables
MC_SERVER = os.getenv("MC_SERVER")
if not MC_SERVER:
    # Fail fast if the required MC_SERVER variable isn't provided. This avoids
    # accidentally shipping a hardcoded third-party server in your repository.
    print("Error: environment variable MC_SERVER is not set.\n" \
          "Please set MC_SERVER (for example: play.example.com:19132) " \
          "in your environment or .env file.")
    sys.exit(1)

API_URL = f"https://api.mcsrvstat.us/bedrock/3/{MC_SERVER}"
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))  # Default: 60 seconds
DATA_FILE = os.getenv("DATA_FILE", "server_data.json")  # Default file name
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

def load_previous_data():
    """Load previous server and player data from a file."""
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            return data.get("online_count", 0), data.get("server_status", None), data.get("gamemode", "")
    except FileNotFoundError:
        return 0, None, ""  # Default to 0 players, server status unknown, no gamemode
    except json.JSONDecodeError:
        return 0, None, ""  # Default to 0 players, server status unknown, no gamemode

def save_current_data(online_count, server_status, gamemode):
    """Save current server and player data to a file."""
    with open(DATA_FILE, "w") as f:
        json.dump({
            "online_count": online_count,
            "server_status": server_status,
            "gamemode": gamemode
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

def check_server(previous_online_count, previous_server_status, previous_gamemode):
    """Check the Minecraft Bedrock server for status, player count, and server info."""
    try:
        response = requests.get(API_URL).json()
        server_online = response.get("online", False)
        online_count = response.get("players", {}).get("online", 0)
        max_players = response.get("players", {}).get("max", 0)
        gamemode = response.get("gamemode", "").strip()

        # Notify if the server status changes or it's the first check
        if server_online != previous_server_status or previous_server_status is None:
            if server_online:
                version = response.get("version", "Unknown")
                message = f"✅ The server is now ONLINE! (Version: {version})"
                print(message)
                send_discord_notification(message)
            else:
                message = "❌ The server is now OFFLINE."
                print(message)
                send_discord_notification(message)

        # Notify if the gamemode changes (only when server is online)
        if server_online and gamemode != previous_gamemode:
            message = f"ℹ️ Gamemode changed to: {gamemode}"
            print(message)
            send_discord_notification(message)

        # Notify if the player count changes (only if server is online)
        if server_online and online_count != previous_online_count:
            if online_count > previous_online_count:
                message = f"🎮 A player joined! {online_count}/{max_players} players online."
            elif online_count < previous_online_count:
                message = f"👋 A player left. {online_count}/{max_players} players online."
            print(message)
            send_discord_notification(message)

        # Save the updated server status, player count, and gamemode
        if server_online:  # Save gamemode only if the server is online
            save_current_data(online_count, server_online, gamemode)
        else:
            save_current_data(online_count, server_online, previous_gamemode)

        return online_count, server_online, gamemode if server_online else previous_gamemode
    except Exception as e:
        print(f"Error while checking server: {e}")
        return previous_online_count, previous_server_status, previous_gamemode

if __name__ == "__main__":
    # Load the last known server and player data
    previous_online_count, previous_server_status, previous_gamemode = load_previous_data()

    while True:
        previous_online_count, previous_server_status, previous_gamemode = check_server(
            previous_online_count, previous_server_status, previous_gamemode
        )
        time.sleep(CHECK_INTERVAL)
