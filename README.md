# mc_bedrock_monitor

A small monitor for a **Minecraft Bedrock server** that checks server status and player counts periodically and sends notifications to a Discord channel via webhook.

What it does
- Periodically queries the mcsrvstat Bedrock API for a configured server.
- Detects server ONLINE/OFFLINE transitions and notifies Discord
- Detects gamemode changes and notifies when the server is online.
- Detects player join/leave events (player count changes)
- Persists last-known state (online count, server status, gamemode) 

Key configuration (environment variables)
- `MC_SERVER` (required): host[:port] of the Bedrock server to monitor (example: `play.example.com:19132`). The script exits if this is not set.
- `DISCORD_WEBHOOK_URL` (optional): Discord webhook URL to post notifications. If not set, notifications are skipped and messages are printed only to stdout.
- `CHECK_INTERVAL` (optional): seconds between checks (default: `60`).
- `DATA_FILE` (optional): path inside the container where state is stored (default: `/app/server_data.json` or the value passed in compose). Use a volume to persist it across restarts.

Example outputs
- Server went online:
	- stdout: `✅ The server is now ONLINE! (Version: 1.19.x)`
	- Discord message: `✅ The server is now ONLINE! (Version: 1.19.x)`
- Server went offline:
	- stdout/Discord: `❌ The server is now OFFLINE.`
- Gamemode changed (while online):
	- `ℹ️ Gamemode changed to: survival`
- Player joined/left (while online):
	- `🎮 A player joined! 3/10 players online.`
	- `👋 A player left. 1/10 players online.`

Run with Docker Compose (recommended)
1. Make sure `docker-compose.yml` is configured (it contains placeholders) and create a local override `docker-compose.local.yml` with your real values (do not commit that file). Example:

```bash
cp docker-compose.local.yml.example docker-compose.local.yml
# edit docker-compose.local.yml to add your MC_SERVER and DISCORD_WEBHOOK_URL
```

2. Start the container (build + detach):

```bash
docker compose -f docker-compose.yml up -d --build
```

3. Follow logs:

```bash
docker compose -f docker-compose.yml logs -f
```

4. Stop:

```bash
docker compose -f docker-compose.yml down
```

Or run directly with docker (one-off)

```bash
docker build -t mc-bedrock-monitor .
docker run --env MC_SERVER=play.example.com:19132 \
	--env DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/.." \
	--rm -v mc_data:/app/data mc-bedrock-monitor
```

- The data file stores last-known `online_count`, `server_status`, and `gamemode`. You can inspect or back it up from a named volume if needed.