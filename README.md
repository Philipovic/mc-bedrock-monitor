# Minecraft Bedrock Server Status Monitor (Discord notifications)

A lightweight and small monitor for a **Minecraft Bedrock server** that checks the server status and player counts periodically and sends notifications to a Discord channel via webhook.

What it does:
- Periodically queries the [Minecraft Server Status API](https://mcsrvstat.us/) for a configured bedrock server.
- Detects server ONLINE/OFFLINE transitions
- Detects gamemode changes
- Detects player join/leave events (only player count changes)

Key configuration (environment variables):
- `SERVER_TYPE` (optional): set to `BEDROCK` for Bedrock servers. (If not set, defaults to BEDROCK)
- `MC_SERVER` (required): host[:port] of the Bedrock server to monitor (example: `play.example.com:19132`).
- `DISCORD_WEBHOOK_URL` (optional): Discord webhook URL to post notifications. If not set, notifications are skipped and messages are printed only to stdout.
- `CHECK_INTERVAL` (optional): seconds between checks (default: `300`). Keep in mind that the API is currently free to use and consider donating to keep it online.

Example outputs:
- Server went online:
    - `✅ The server is now ONLINE! (Version: 1.21.2)`
- Server went offline:
    - `❌ The server is now OFFLINE.`
- Gamemode changed (while online):
    - `ℹ️ Gamemode changed to: Survival`
- Player joined/left (while online):
    - `🎮 A player joined! 3/10 players online.`
    - `👋 A player left. 1/10 players online.`
- Server updates its version (while online):
    - `🔄 Server version changed: 1.21.1 → 1.21.2`

## Run with Docker Compose (recommended)

See the `example.docker-compose.yml` for reference.  

## Run container directly

Pull and run the published image with all required settings inline:

```bash
docker pull ghcr.io/philipovic/mc-bedrock-monitor:latest
```

Run the container (adjust environment variables as needed):
```bash
docker run -d \
  --name mc-bedrock-monitor \
  -e SERVER_TYPE=BEDROCK \
  -e MC_SERVER=play.example.com:19132 \
  -e DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..." \
  -e CHECK_INTERVAL=300 \
  -v mc_data:/app/data \
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

