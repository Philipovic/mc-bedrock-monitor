# Minecraft Server Status - Discord Monitor

A lightweight and small monitor for **Minecraft servers** (both Java and Bedrock) that checks the server status and player counts periodically and sends notifications to a Discord channel via webhook.

What it does:
- Periodically queries the [Minecraft Server Status API](https://mcsrvstat.us/) for the configured server
- Detects server ONLINE/OFFLINE transitions
- Monitors server version changes
- Detects player join/leave events
- For Bedrock servers:
  - Detects gamemode changes
  - Shows player count updates
- For Java servers:
  - Shows player names when they join
  - Displays server software and MOTD
  - Reports plugin and mod counts

### Key configuration (environment variables):
- `SERVER_TYPE` (optional): set to `JAVA` or `BEDROCK`. If not set, defaults to `BEDROCK`
- `MC_SERVER` (required): host[:port] of the server to monitor
  - For Bedrock servers: `play.example.com:19132`
  - For Java servers: `play.example.com:25565` (25565 is default Java port)
- `DISCORD_WEBHOOK_URL` (optional): Discord webhook URL to post notifications. If not set, notifications are skipped and messages are printed only to stdout
- `CHECK_INTERVAL` (optional): seconds between checks (default: `300`). Keep in mind that the API is currently free to use and consider donating to keep it online
- `OFFLINE_THRESHOLD` (optional): number of consecutive offline checks required before marking server as offline (default: `2`). This prevents false offline notifications due to transient network issues or API timeouts

### Example outputs:

Common notifications:
- Server status changes:
    - `✅ The server is now ONLINE!`
    - `❌ The server is now OFFLINE.`
- Version updates:
    - `🔄 Server version changed: 1.21.1 → 1.21.2`

Bedrock server notifications:
- Server startup:
    - `✅ The server is now ONLINE!`
    - `Version: 1.21.2`
- Gamemode changes:
    - `ℹ️ Gamemode changed to: Survival`
- Player count updates:
    - `🎮 A player joined!`
    - `📊 3/10 players online`
- Multiple players:
    - `🎮 3 players joined!`
    - `📊 5/10 players online`

Java server notifications:
- Server startup with plugins/mods:
    - `✅ The server is now ONLINE!`
    - `Version: 1.20.1 (Paper) | 15 plugins | 3 mods`
    - `📝 Message of the Day: A Minecraft Server`
- Player joins with names:
    - `🎮 Notch joined!`
    - `🎮 Steve joined!`
    - `📊 2/20 players online`
- Player leaves:
    - `👋 Notch left.`
    - `📊 1/20 players online`

## Run with Docker Compose (recommended)

See the `example.docker-compose.yml` for reference.  

## Run container directly

Pull and run the published image with all required settings inline:

```bash
docker pull ghcr.io/philipovic/mc-bedrock-monitor:latest
```

Run the container (adjust environment variables as needed):
```bash
# For Bedrock servers (default)
docker run -d \
  --name mc-monitor \
  -e MC_SERVER=play.example.com:19132 \
  -e DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..." \
  -e CHECK_INTERVAL=300 \
  -v mc_monitor_data:/app/data \
  ghcr.io/philipovic/mc-bedrock-monitor:latest
```
```bash
# For Java servers
docker run -d \
  --name mc-monitor \
  -e SERVER_TYPE=JAVA \
  -e MC_SERVER=play.example.com:25565 \
  -e DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..." \
  -e CHECK_INTERVAL=300 \
  -v mc_monitor_data:/app/data \
  ghcr.io/philipovic/mc-bedrock-monitor:latest
```

View logs of the running container

```bash
docker logs -f mc-bedrock-monitor
```
## Stop and remove the container

```bash
docker stop mc-bedrock-monitor
docker rm mc-bedrock-monitor
```

