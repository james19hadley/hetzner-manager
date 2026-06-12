# Hetzner Manager Telegram Bot

A lightweight, secure Telegram Bot for remote monitoring and administration of Hetzner VPS servers and [Antigravity](https://antigravity.dev) AI coding sessions.

## 🚀 Key Features

* **🖥️ Real-time Server Metrics**: Gather CPU, RAM, disk space, load average, and uptime metrics directly from the local **Netdata API** on the VPS.
* **⚙️ Daemon & Docker Control**: Check status and restart whitelisted systemd services (`ag2r`, `antigravity-gui`, `xvfb`, etc.) and Docker containers securely.
* **💻 Stateful Shell Sessions**: Execute terminal commands directly from Telegram. Sessions maintain the working directory (`cd`), active user context (`su`), and custom environment variables. Supports entering interactive shell mode where every message is executed as a command.
* **🛡️ Antigravity Suite**: 
  * Monitor active CDP targets and Electron logs.
  * Capture screenshots of the headless display (`:99`) using `scrot`.
  * Manage Electron GUI lifecycles (restart, sleep, wake up).
  * Handle headless **Google OAuth Sign-In** flows: triggers auth URLs, accepts pasted localhost OAuth callbacks, and forwards them to the AG2R local server.
  * Dynamically generate direct password-authenticated dashboard links for both secure Tailscale VPN and public tunnel hosts.
* **🔑 Secure Architecture**: Runs under a dedicated, unprivileged system user (`tg-monitor`) and accesses administrative actions dynamically via strict, passwordless `sudo` rules. Only whitelisted Telegram Account IDs configured in the database can interact with the bot.

---

## 🛠️ Architecture & Security Model

The bot follows the principle of least privilege:
1. **Privilege Demotion**: The bot's systemd daemon runs as user `tg-monitor`, which belongs to the `docker` group but otherwise has no root access.
2. **Restricted Sudo Rules**: Sudo elevations are restricted via `/etc/sudoers.d/tg-monitor` to allow executing `systemctl restart` only for whitelisted services, plus stateful user switching (`sudo -u <username>`).
3. **Admin Whitelisting**: The SQLite database (`data/bot_state.db`) stores authorized Telegram user IDs. Incoming messages are filtered via an authentication middleware. Unknown IDs are ignored.

---

## 📁 Repository Structure

```
├── bot/
│   ├── src/
│   │   ├── main.py                # Bot entry point and command registration
│   │   ├── bot/
│   │   │   ├── handlers/
│   │   │   │   ├── base.py        # Base admin & Antigravity command handlers
│   │   │   │   └── message.py     # Stateful shell runner and callback URL interceptor
│   │   │   ├── middleware/
│   │   │   │   └── auth.py        # Access control whitelisting middleware
│   │   │   ├── alerts.py          # Netdata background alarm monitoring thread
│   │   │   └── session.py         # Shell session context manager
│   │   └── database/
│   │       └── db.py              # SQLite storage wrapper (users, chat mappings)
│   ├── requirements.txt           # Python dependencies
│   └── .env.example               # Template environment configuration
└── README.md                      # This document
```

---

## ⚙️ Setup & Installation

### Prerequisites
* Python 3.10+
* A Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### Configuration
1. Copy the example configuration:
   ```bash
   cp bot/.env.example bot/.env
   ```
2. Open `bot/.env` and configure your credentials:
   ```env
   TELEGRAM_BOT_TOKEN="your-bot-token-here"
   DATABASE_PATH="data/bot_state.db"
   ADMIN_TELEGRAM_ID="your-telegram-id-here" # Automatically whitelisted on first startup
   ```

### Installation & Deployment

#### Option 1: Production Deployment (Systemd + Privilege Demotion)

This is the recommended deployment method for production servers. It runs the bot under a dedicated low-privilege system user with restricted sudo permissions to interact with host daemons.

1. **Create the `tg-monitor` System User**:
   ```bash
   sudo useradd -r -s /bin/false -U tg-monitor
   sudo usermod -aG docker tg-monitor
   ```

2. **Configure Sudo Rules**:
   Create `/etc/sudoers.d/tg-monitor` to allow passwordless user switching and service management:
   ```bash
   sudo bash -c "echo 'tg-monitor ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/tg-monitor"
   sudo chmod 0440 /etc/sudoers.d/tg-monitor
   ```

3. **Install dependencies**:
   ```bash
   cd /opt/hetzner-manager
   sudo python3 -m venv bot/.venv
   sudo bot/.venv/bin/pip install --upgrade pip
   sudo bot/.venv/bin/pip install -r bot/requirements.txt
   sudo chown -R tg-monitor:tg-monitor /opt/hetzner-manager
   ```

4. **Install and Start the Systemd Service**:
   Create the systemd unit file at `/etc/systemd/system/hetzner-bot.service`:
   ```ini
   [Unit]
   Description=Hetzner Manager Telegram Bot
   After=network.target

   [Service]
   User=tg-monitor
   Group=tg-monitor
   WorkingDirectory=/opt/hetzner-manager/bot
   ExecStart=/opt/hetzner-manager/bot/.venv/bin/python3 -m src.main
   Restart=always
   RestartSec=5
   StandardOutput=journal
   StandardError=journal

   [Install]
   WantedBy=multi-user.target
   ```
   Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable hetzner-bot.service
   sudo systemctl start hetzner-bot.service
   ```

#### Option 2: Local Development (Manual Run)

For debugging or development purposes, you can run the bot manually:

1. Initialize a Python virtual environment:
   ```bash
   python3 -m venv bot/.venv
   source bot/.venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r bot/requirements.txt
   ```
3. Run the bot:
   ```bash
   python3 -m bot.src.main
   ```

---

## 📖 Bot Commands Reference

### System Metrics & Services
* `/sysinfo` — Fetch CPU, RAM, disk usage, load average, and uptime metrics.
* `/daemons` — View status of configured systemd services.
* `/docker` — List active Docker containers.
* `/restart_container <name>` — Restart a Docker container.
* `/restart_daemon <name>` — Safe restart of system services.

### Antigravity Management
* `/agy_status` — Query Electron GUI / CDP targets and send a screenshot of the virtual display.
* `/agy_restart` — Restart the Antigravity Electron GUI service.
* `/agy_sleep` — Put Antigravity GUI to sleep (stops service).
* `/agy_wakeup` — Wake up Antigravity GUI (starts service).
* `/agy_logs` — View last 15 log lines for Antigravity GUI and AG2R.
* `/agy_login` — Initiate Google OAuth login for the headless browser.
* `/agy_callback <url>` — Pass a localhost OAuth callback redirect to complete sign-in.
* `/agy_link` — Get direct, password-authenticated links for Tailscale VPN or public tunnels to open the AG2R remote control dashboard.

### Stateful Shell Sessions
* `$ <command>` — Run a shell command statefully.
* `/sh` — Enter interactive shell mode (all messages are executed as commands).
* `/sh_exit` — Exit interactive shell mode.
* `/sh_status` — View active session state (current directory, active user, environment).
* `/su <username>` — Switch active user context of the shell session.

### OS Accounts & Permissions (Sudoers required)
* `/sysusers` — List OS users, home directories, and groups.
* `/sysgroups` — List OS groups.
* `/syssudoers` — Read active sudo rules.
* `/syschmod <mode> <path>` — Change file permissions on the host.
* `/syschown <user:group> <path>` — Change file ownership on the host.
* `/sysuseradd <args>` — Create a new OS user.
* `/sysusermod <args>` — Modify an existing OS user.
* `/sysuserdel <name>` — Delete an OS user.

---

## 📝 License
This project is open-source and available under the [MIT License](LICENSE).
