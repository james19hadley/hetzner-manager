#!/usr/bin/env python3
# scripts/server_status.py - Fetch and analyze real-time metrics from the remote VPS via Netdata API

import json
import urllib.request
import sys
from datetime import timedelta

NETDATA_IP = "100.103.212.83"
NETDATA_PORT = 19999
BASE_URL = f"http://{NETDATA_IP}:{NETDATA_PORT}/api/v1"

def get_json(endpoint):
    url = f"{BASE_URL}/{endpoint}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'HetznerManagerAgent/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode())
    except urllib.error.URLError as e:
        print(f"❌ Error connecting to Netdata at {url}. Is Tailscale connected?")
        print(f"Details: {e}")
        sys.exit(1)

def format_bytes(bytes_num):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_num < 1024:
            return f"{bytes_num:.2f} {unit}"
        bytes_num /= 1024
    return f"{bytes_num:.2f} PB"

def print_status():
    print("☁️  Fetching real-time server metrics from Hetzner VPS...")
    
    # 1. Fetch system info
    info = get_json("info")
    alarms = get_json("alarms?active")
    
    hostname = info.get("hostname", "unknown")
    os_name = info.get("os_name", "unknown")
    os_version = info.get("os_version", "unknown")
    uptime_sec = info.get("uptime", 0)
    
    print("\n🖥️  --- SYSTEM INFO ---")
    print(f"Host:      {hostname}")
    print(f"OS:        {os_name} {os_version}")
    print(f"Uptime:    {timedelta(seconds=uptime_sec)}")
    print(f"Metrics:   {info.get('metrics-count', 0)} active gauges collected")
    
    # 2. Fetch active alarms
    active_alarms = alarms.get("alarms", {})
    print("\n🚨 --- ACTIVE ALARMS ---")
    if not active_alarms:
        print("✅ No active alarms. Everything is healthy!")
    else:
        for alarm_id, alarm_data in active_alarms.items():
            status = alarm_data.get("status", "WARNING")
            summary = alarm_data.get("summary", "No details")
            chart = alarm_data.get("chart", "unknown")
            color = "🔴" if status == "CRITICAL" else "🟡"
            print(f"{color} [{status}] {alarm_data.get('name')}: {summary} (Chart: {chart})")

    # 3. Fetch current system resources (CPU, RAM, Network)
    # We can get a quick summary from the info output or query specific charts
    print("\n📊 --- ENGINE & HEALTH STATUS ---")
    print(f"Memory Mode:        {info.get('memory-mode', 'unknown')}")
    print(f"Cloud Connection:   {'Connected' if info.get('aclk-available') else 'Offline (Local Only)'}")

    print("\n💡 Tip: Run 'ssh root@100.103.212.83 \"docker ps\"' to check running containers, or look at the web GUI at http://100.103.212.83:19999/ for interactive charts.")

if __name__ == "__main__":
    print_status()
