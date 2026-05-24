#!/bin/bash
# deploy.sh - Deploy hetzner-manager scripts and configurations to the remote VPS
# Run this script locally from your laptop to deploy.

set -e

VPS_IP="100.103.212.83"
TARGET_DIR="/opt/hetzner-manager"

echo "🚀 Deploying hetzner-manager to remote VPS ($VPS_IP)..."

# 1. Ensure target directories exist on VPS
ssh root@$VPS_IP "mkdir -p $TARGET_DIR/scripts $TARGET_DIR/configs"

# 2. Sync files via rsync (excludes local files, notes history and system logs)
rsync -avz --delete \
  --exclude '.git/' \
  --exclude '.gitignore' \
  --exclude 'venv/' \
  --exclude '__pycache__/' \
  --exclude 'notes/status.json' \
  --exclude 'notes/work_log.md' \
  ./ root@$VPS_IP:$TARGET_DIR/

# 3. Apply configurations on the server
echo "⚙️ Applying Netdata configurations..."
ssh root@$VPS_IP "
  # Copy Netdata configs to their system locations if they exist in configs/
  [ -f $TARGET_DIR/configs/netdata.conf ] && cp $TARGET_DIR/configs/netdata.conf /etc/netdata/netdata.conf
  [ -f $TARGET_DIR/configs/docker.conf ] && cp $TARGET_DIR/configs/docker.conf /etc/netdata/go.d/docker.conf
  
  # Set correct permissions
  chown -R root:netdata /etc/netdata
  chmod 644 /etc/netdata/netdata.conf /etc/netdata/go.d/docker.conf 2>/dev/null || true
  
  # Restart Netdata to apply changes
  systemctl restart netdata
"

# 4. Configure weekly stats cron job
echo "⏰ Configuring weekly status report cron job..."
ssh root@$VPS_IP "
  # Make sure the weekly stats script is executable
  chmod +x $TARGET_DIR/scripts/weekly_report.py 2>/dev/null || true
  
  # Register the cron job in crontab (runs every Sunday at 18:00)
  # We read existing crontab, remove any existing weekly_report.py entry, and append the new one
  CRON_CMD=\"0 18 * * 0 python3 $TARGET_DIR/scripts/weekly_report.py >> /var/log/weekly_report.log 2>&1\"
  (crontab -l 2>/dev/null | grep -v \"weekly_report.py\" ; echo \"\$CRON_CMD\") | crontab -
"

echo "✅ Deployment completed successfully!"
