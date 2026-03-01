# Veritas

Veritas monitors configured Discord channels for links to untrusted or low-reputation sources. Blocked sources have their message deleted and the author notified via DM. Warned sources receive a public quote-reply and a 🚩 reaction.

## Requirements

- Python 3.10+
- A Discord account with access to the [Discord Developer Portal](https://discord.com/developers/applications)

## Installation

```bash
sudo mkdir -p /opt/veritas
sudo chown ubuntu:ubuntu /opt/veritas
python3 -m venv /opt/veritas/env
/opt/veritas/env/bin/pip install -r requirements.txt
```

Copy `bot.py` and `config.yaml` into `/opt/veritas/`.

## Discord Setup

### 1. Create the application

Go to the [Discord Developer Portal](https://discord.com/developers/applications) and click **New Application**. Give it a name and accept the terms.

### 2. Create the bot and get a token

In the left sidebar, click **Bot**. Click **Reset Token**, copy the token immediately, and paste it into `config.yaml` as the `token` value. You will not be able to view the token again without resetting it, which will invalidate the previous one.

### 3. Enable the Message Content Intent

Still on the **Bot** page, scroll down to **Privileged Gateway Intents** and enable **Message Content Intent**. Without this, Discord will deliver message events to the bot but the content field will be empty, so no links will ever be matched.

### 4. Generate an invite link

Go to **OAuth2 → URL Generator** in the sidebar. Under **Scopes**, tick `bot`. A permissions panel will appear below — tick the following:

- Read Messages / View Channels
- Send Messages
- Manage Messages
- Add Reactions
- Read Message History

Copy the generated URL at the bottom of the page and open it in your browser to invite the bot to your server.

### 5. Restrict the bot to specific channels

Rather than relying solely on the channel list in `config.yaml`, it is recommended to restrict the bot at the Discord permission level so it only receives events from the channels it should be monitoring.

- Go to **Server Settings → Roles** and create a new role (e.g. `Veritas`)
- Assign that role to the bot via the member list
- Deny the role **View Channel** at the server level so it has no default access
- On each channel you want monitored, go to **Edit Channel → Permissions**, add the Veritas role, and explicitly allow: View Channel, Send Messages, Manage Messages, Add Reactions, Read Message History

This ensures Discord does not deliver events to the bot for channels it has no business monitoring.

## Configuration

All configuration lives in `config.yaml` alongside the bot script.

```yaml
token: "YOUR_BOT_TOKEN_HERE"

channels:
  - 1234567890123456789   # Right-click a channel → Copy Channel ID (requires Developer Mode)

blocklist:
  domains:
    - bit.ly
    - tinyurl.com
  twitter:
    - ArmchairW            # Handle only, no @ prefix
  telegram:
    - IntelSlava

warnlist:
  domains: []
  twitter: []
  telegram: []
```

To get channel IDs, enable **Developer Mode** in Discord under User Settings → Advanced, then right-click any channel and select **Copy Channel ID**.

Matching is case-insensitive throughout. Twitter/X and Telegram accounts are matched on the handle extracted from the URL path, so full URLs with status IDs, query strings, and so on are handled correctly. The blocklist is checked first — a URL that matches both lists will always result in a block, not a warning.

A community-maintained base blocklist covering known unreliable sources is available from [Project Owl](https://cryptpad.fr/sheet/#/2/sheet/view/IqFHSanAVHz7aMBX8jekHB9m7RXk+YUT8wHODELgTV4/). This has been used as the starting point for the `blocklist` and `warnlist` entries in the included config template.

## Running the bot

```bash
python bot.py
```

For persistent deployment on a Linux server, a systemd service is recommended.

Create `/etc/systemd/system/veritas.service`:

```ini
[Unit]
Description=Veritas
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/veritas
ExecStart=/opt/veritas/env/bin/python /opt/veritas/bot.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable veritas
sudo systemctl start veritas
sudo systemctl status veritas
```

Logs are written to stdout and captured by journald:

```bash
journalctl -u veritas -f
```