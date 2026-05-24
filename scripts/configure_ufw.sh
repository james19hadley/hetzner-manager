#!/bin/bash
# configure_ufw.sh - Configures UFW firewall for Netdata on Tailscale

set -e

echo "🔒 Configuring UFW rules for Netdata..."

# Allow port 19999 on the tailscale0 interface only
ufw allow in on tailscale0 to any port 19999 proto tcp comment 'Netdata GUI via Tailscale'

# Reload firewall
ufw reload

echo "✅ UFW configured successfully!"
ufw status verbose
