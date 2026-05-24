#!/bin/bash
# install_netdata.sh - Installs Netdata on the remote VPS

set -e

echo "📥 Installing Netdata on the remote host..."
# Run the official kickstart script with non-interactive mode and telemetry disabled
curl https://get.netdata.cloud/kickstart.sh > /tmp/kickstart.sh
sh /tmp/kickstart.sh --non-interactive --disable-telemetry

echo "✅ Netdata installed successfully!"
systemctl status netdata --no-pager
