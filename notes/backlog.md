# Project Alignment & Core Vision

- **Core Vision**: Configure a lightweight, ready-made server monitoring system (Netdata) on the Hetzner CX23 VPS to track CPU, RAM, disk, network, and Docker container performance in real-time.
- **Definition of Done**: 
  - Netdata is running on the VPS, monitoring system resources and Docker containers.
  - Real-time dashboard is accessible securely (e.g., via Tailscale VPN or basic auth through Caddy).
  - Alerting is configured to send email notifications to the user's Gmail when critical thresholds (CPU, RAM, disk, server unreachable) are breached.
  - Setup is documented and reproducible.
- **Materials & Starting Point**: 
  - Hetzner VPS (2 vCPUs, 4 GB RAM, Ubuntu).
  - Already running services: `pulse-monolith-bot` (Caddy, Postgres, Redis, Celery, Bot) and `ch_bot`.
  - No active domains yet; Tailscale VPN is configured and can be used for secure private dashboard access.
- **Current Blockers/Unknowns**: 
  - Configuring Netdata to use minimal resources (adjust database retention and tiering).
  - Configuring Netdata alerts to send to Gmail via an SMTP provider (e.g. Gmail App Password or free SMTP relay).

---

# Project Backlog & Roadmap

This file tracks overall goals, milestones, and task checklists for the project.

## Milestone Roadmap

| Milestone | Target Date | Description | Status |
| :--- | :--- | :--- | :--- |
| **M1** | 2026-06-01 | Setup & Initial Research | Completed |
| **M2** | 2026-07-01 | Core Development / Work | Completed |
| **M3** | 2026-08-01 | Final Deliverable / Exam | Pending |

---

## Task Checklist

### Phase 1: Setup & Initialization
- [x] **Task 1.1**: Connect to remote resources and clone code.
- [x] **Task 1.2**: Set up environment and local variables.
- [x] **Task 1.4**: Install Netdata on the remote VPS.
- [x] **Task 1.5**: Secure Netdata dashboard via Tailscale.

### Phase 2: Core execution
- [x] **Task 2.1**: Configure Netdata email alerts using SMTP (Gmail/Brevo) - Verified and working.
- [x] **Task 2.2**: Optimize Netdata for low memory usage (minimal footprint).
- [ ] **Task 2.3**: Test alerts by simulating high CPU load.
- [x] **Task 2.4**: Setup skeleton configuration for the future Blog website in Caddy.

### Phase 3: Reporting & Submission
- [ ] **Task 3.1**: Draft the report/paper.
- [ ] **Task 3.2**: Final review and submit.
