#!/bin/bash
# deploy.sh - Deploy hetzner-manager scripts, configurations, and the Telegram bot to the remote VPS
# Run this script locally from your laptop to deploy.

set -e

VPS_IP="65.21.57.159"
TARGET_DIR="/opt/hetzner-manager"

echo "🚀 Deploying hetzner-manager and Telegram Bot to remote VPS ($VPS_IP)..."

# 1. Ensure target directories exist on VPS
ssh root@$VPS_IP "mkdir -p $TARGET_DIR/scripts $TARGET_DIR/configs $TARGET_DIR/bot/data"

# 2. Sync files via rsync (excludes local virtualenv, databases, git metadata)
rsync -avz --delete \
  --exclude '.git/' \
  --exclude '.gitignore' \
  --exclude 'venv/' \
  --exclude 'bot/.venv/' \
  --exclude 'bot/data/' \
  --exclude 'bot/.env' \
  --exclude '__pycache__/' \
  --exclude 'notes/status.json' \
  --exclude 'notes/work_log.md' \
  ./ root@$VPS_IP:$TARGET_DIR/

# 3. Apply configurations and install service on the server
echo "⚙️ Setting up Telegram Bot and system configurations on the server..."
ssh root@$VPS_IP "
  # Copy Netdata configs to their system locations if they exist in configs/
  [ -f $TARGET_DIR/configs/netdata.conf ] && cp $TARGET_DIR/configs/netdata.conf /etc/netdata/netdata.conf
  [ -f $TARGET_DIR/configs/docker.conf ] && cp $TARGET_DIR/configs/docker.conf /etc/netdata/go.d/docker.conf
  
  # Set correct permissions for Netdata
  chown -R root:netdata /etc/netdata 2>/dev/null || true
  chmod 644 /etc/netdata/netdata.conf /etc/netdata/go.d/docker.conf 2>/dev/null || true
  
  # Restart Netdata to apply changes
  systemctl restart netdata
  
  # Migrate database and env from old tg-agy-client if available
  [ ! -f $TARGET_DIR/bot/data/bot_state.db ] && [ -f /opt/tg-agy-client/data/bot_state.db ] && cp -a /opt/tg-agy-client/data/bot_state.db $TARGET_DIR/bot/data/bot_state.db && echo 'Migrated SQLite database'
  [ ! -f $TARGET_DIR/bot/.env ] && [ -f /opt/tg-agy-client/.env ] && cp /opt/tg-agy-client/.env $TARGET_DIR/bot/.env && echo 'Migrated .env config'
  
  # Create tg-monitor user and configure docker group
  id -u tg-monitor &>/dev/null || useradd -r -s /bin/false -U tg-monitor
  usermod -aG docker tg-monitor
  
  # Ensure Python virtual environment and dependencies are set up
  if [ ! -d $TARGET_DIR/bot/.venv ]; then
    python3 -m venv $TARGET_DIR/bot/.venv
  fi
  $TARGET_DIR/bot/.venv/bin/pip install --upgrade pip
  $TARGET_DIR/bot/.venv/bin/pip install -r $TARGET_DIR/bot/requirements.txt
  
  # Fix directory ownership
  chown -R tg-monitor:tg-monitor $TARGET_DIR
  
  # Install sudoers rule for tg-monitor
  echo 'tg-monitor ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/tg-monitor
  chmod 0440 /etc/sudoers.d/tg-monitor
  
  # Install Systemd Service for Bot
  cat << 'EOF' > /etc/systemd/system/hetzner-bot.service
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
EOF

  # Reload and restart systemd service
  systemctl daemon-reload
  systemctl enable hetzner-bot.service
  systemctl restart hetzner-bot.service
  echo 'Bot service started'
"

# 4. Configure weekly stats cron job
echo "⏰ Configuring weekly status report cron job..."
ssh root@$VPS_IP "
  # Make sure the weekly stats script is executable
  chmod +x $TARGET_DIR/scripts/weekly_report.py 2>/dev/null || true
  
  # Register the cron job in crontab (runs every Sunday at 18:00)
  CRON_CMD=\"0 18 * * 0 python3 $TARGET_DIR/scripts/weekly_report.py >> /var/log/weekly_report.log 2>&1\"
  (crontab -l 2>/dev/null | grep -v \"weekly_report.py\" ; echo \"\$CRON_CMD\") | crontab -
"

echo "✅ Deployment completed successfully!"
