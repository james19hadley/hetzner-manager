# Project Work Log

This file acts as a chronological developer journal and laboratory notebook. Record date, task description, and core results/conclusions for each working session.

---

## 2026-05-24: Onboarding & Core Alignment
**Author**: Agent & User

### Progress Summary
1. **Onboarding Alignment**: Reviewed system setup for `pulse-monolith-bot` and `ch_bot`. Both run inside Docker Compose on a remote Hetzner CX23 VPS.
2. **Core Vision Established**: Conducted the Project Alignment Interview. Decided to use a lightweight, ready-made solution (**Netdata**) for server resource tracking and email alerting (e.g. Gmail), without inventing a custom tool.
3. **Workspace Documents Updated**: Added project vision to [backlog.md](file:///home/ging/prog/hetzner-manager/notes/backlog.md) and updated status parameters in [status.json](file:///home/ging/prog/hetzner-manager/notes/status.json).

---

## 2026-05-24: Implementation of Netdata Monitoring & Firewall Security
**Author**: Agent & User

### Progress Summary
1. **Installed Netdata**: Successfully installed Netdata on the host remote Hetzner VPS (`100.103.212.83`).
2. **Secured Dashboard**: Configured host UFW to only allow port `19999` from the Tailscale interface (`tailscale0`). Public requests to `65.21.57.159:19999` are blocked.
3. **RAM & CPU Optimizations**: Configured `netdata.conf` to disable ML anomaly detection and set memory limits (reduced Netdata RAM footprint from 194MB to 103MB).
4. **Email / Telegram Setup**: Installed `msmtp` on the server and copied templates for `/etc/msmtprc` and `/etc/netdata/health_alarm_notify.conf`.
5. **Blog Setup Documented**: Added a walkthrough on how to mount static blog files and configure Caddy in the future.
6. **Task & Status Sync**: Updated [task.md](file:///home/ging/.gemini/antigravity/brain/43c057f8-6b17-44ba-ad02-d79f89aad5c5/task.md), [status.json](file:///home/ging/prog/hetzner-manager/notes/status.json), and [backlog.md](file:///home/ging/prog/hetzner-manager/notes/backlog.md).

---

## 2026-06-08: Fixed Alerting Permission & Verified Notifications
**Author**: Agent & User

### Progress Summary
1. **Discovered Permission Bug**: The Netdata test alert command failed with code `78` (`sendmail: account default not found`) because `/etc/msmtprc` was configured with owner `root:root` and permission `600`, preventing the `netdata` system user from reading it.
2. **Applied Fix**: Updated `/etc/msmtprc` to be owned by `root:msmtp` with permission `640` and added the `netdata` user to the `msmtp` system group. Also modified `scripts/setup_alerts.sh` to enforce this behavior automatically in the future.
3. **Successfully Verified Alerts**: Re-ran the Netdata alert-notify test command and verified that Warning, Critical, and Clear test alerts were successfully sent to `ivan.zharov.de@gmail.com`.
