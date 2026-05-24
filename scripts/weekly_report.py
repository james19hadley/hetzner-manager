#!/usr/bin/env python3
# scripts/weekly_report.py - Autonomous script to compile and send weekly server health report
# Run on the VPS as a cron job.

import json
import urllib.request
import subprocess
import sys
import re
from datetime import datetime, timezone

import time

NETDATA_URL = "http://127.0.0.1:19999/api/v1"

def get_json(endpoint):
    url = f"{NETDATA_URL}/{endpoint}"
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'HetznerManagerReport/1.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            if attempt < 4:
                print(f"Netdata API not ready yet (attempt {attempt+1}/5). Retrying in 2s...", file=sys.stderr)
                time.sleep(2)
            else:
                print(f"Error fetching data from Netdata API: {e}", file=sys.stderr)
                return None

def get_recipient_email():
    # Attempt to read recipient from health_alarm_notify.conf
    try:
        with open("/etc/netdata/health_alarm_notify.conf", "r") as f:
            content = f.read()
            match = re.search(r'DEFAULT_RECIPIENT_EMAIL="([^"]+)"', content)
            if match:
                return match.group(1)
    except Exception:
        pass
    
    # Fallback to reading from msmtprc
    try:
        with open("/etc/msmtprc", "r") as f:
            content = f.read()
            match = re.search(r'from\s+([^\s\n]+)', content)
            if match:
                return match.group(1)
    except Exception:
        pass
        
    return None

def get_sys_data():
    # 1. Fetch system CPU chart details to get first/last entries
    cpu_chart = get_json("chart?chart=system.cpu")
    if not cpu_chart:
        return None
        
    first_entry = cpu_chart.get("first_entry", 0)
    last_entry = cpu_chart.get("last_entry", 0)
    now_ts = int(datetime.now(timezone.utc).timestamp())
    
    # Calculate query range (7 days = 604800 seconds, or maximum available)
    range_seconds = 604800
    if last_entry - first_entry < range_seconds:
        range_seconds = last_entry - first_entry
        
    after_ts = last_entry - range_seconds
    hours_collected = range_seconds / 3600
    
    # 2. Query average CPU usage over range
    cpu_data = get_json(f"data?chart=system.cpu&after={after_ts}&points=1&group=average")
    # 3. Query average RAM usage over range
    ram_data = get_json(f"data?chart=system.ram&after={after_ts}&points=1&group=average")
    
    # 4. Fetch alarms
    alarms = get_json("alarms?active")
    
    return {
        "hours_collected": hours_collected,
        "cpu": cpu_data,
        "ram": ram_data,
        "alarms": alarms
    }

def get_disk_usage():
    try:
        res = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
        lines = res.stdout.strip().split('\n')
        if len(lines) >= 2:
            parts = re.split(r'\s+', lines[1])
            if len(parts) >= 5:
                return f"{parts[2]} used out of {parts[1]} ({parts[4]} occupied)"
    except Exception:
        pass
    return "Unknown"

def send_email(recipient, subject, body):
    msg = f"Subject: {subject}\nTo: {recipient}\nContent-Type: text/plain; charset=UTF-8\n\n{body}"
    try:
        p = subprocess.Popen(["/usr/sbin/sendmail", "-t", "-i"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate(msg.encode('utf-8'))
        if p.returncode != 0:
            print(f"sendmail failed: {stderr.decode()}", file=sys.stderr)
            return False
        return True
    except Exception as e:
        print(f"Error executing sendmail: {e}", file=sys.stderr)
        return False

def generate_report():
    recipient = get_recipient_email()
    if not recipient:
        print("Error: Could not determine recipient email address. Please configure it in /etc/netdata/health_alarm_notify.conf.", file=sys.stderr)
        sys.exit(1)
        
    sys_data = get_sys_data()
    if not sys_data:
        print("Error: Could not retrieve metrics from Netdata API.", file=sys.stderr)
        sys.exit(1)
        
    # Calculate CPU stats
    cpu_metrics = sys_data["cpu"]
    avg_cpu_idle = 0.0
    if cpu_metrics and "data" in cpu_metrics and len(cpu_metrics["data"]) > 0:
        labels = cpu_metrics["labels"]
        values = cpu_metrics["data"][0]
        # Sum of non-idle elements
        for label, val in zip(labels, values):
            if label not in ["time", "guest_nice", "guest", "steal", "softirq", "irq", "user", "system", "nice", "iowait"]:
                continue
            # Netdata CPU totals represent percentage. Let's calculate busy CPU
            if label in ["user", "system", "softirq", "irq", "steal", "nice"]:
                avg_cpu_idle += val if val else 0.0
    
    avg_cpu_busy = min(avg_cpu_idle, 100.0)
    
    # Calculate RAM stats
    ram_metrics = sys_data["ram"]
    ram_used_pct = 0.0
    ram_used_mib = 0.0
    ram_total_mib = 0.0
    if ram_metrics and "data" in ram_metrics and len(ram_metrics["data"]) > 0:
        labels = ram_metrics["labels"]
        values = ram_metrics["data"][0]
        ram_dict = dict(zip(labels, values))
        
        used = ram_dict.get("used", 0)
        free = ram_dict.get("free", 0)
        cached = ram_dict.get("cached", 0)
        buffers = ram_dict.get("buffers", 0)
        
        ram_total_mib = used + free + cached + buffers
        if ram_total_mib > 0:
            ram_used_mib = used
            ram_used_pct = (used / ram_total_mib) * 100
            
    # Format alarms
    active_alarms = sys_data["alarms"].get("alarms", {})
    alarm_summary = ""
    if not active_alarms:
        alarm_summary = "✅ All system alarms are clean. No warnings or critical issues detected!"
    else:
        for idx, (alarm_id, data) in enumerate(active_alarms.items(), 1):
            alarm_summary += f"{idx}. [{data.get('status')}] {data.get('name')}: {data.get('summary')} (Chart: {data.get('chart')})\n"
            
    # Build report body
    report_body = f"""Hello!

Here is your weekly server health report for Hetzner VPS (ubuntu-4gb-hel1-1).

==================================================
📊 REPORT PERIOD & OVERALL METRICS
==================================================
Report Period:  Last {sys_data['hours_collected']:.1f} hours of data collection
Average CPU:    {avg_cpu_busy:.2f}% active usage
Average RAM:    {ram_used_pct:.2f}% used ({ram_used_mib:.0f} MB / {ram_total_mib:.0f} MB)
Disk Space:     {get_disk_usage()}
Date generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

==================================================
🚨 ACTIVE SYSTEM ALARMS
==================================================
{alarm_summary}

==================================================
💡 RECOMMENDATIONS
==================================================
"""
    if avg_cpu_busy > 80.0:
        report_body += "- ⚠️ High CPU load average detected. Consider optimizing background bot worker processes.\n"
    if ram_used_pct > 85.0:
        report_body += "- ⚠️ Memory usage is running high. Consider adding swap space or upgrading VPS tier.\n"
    if "reboot" in alarm_summary:
        report_body += "- ℹ️ A system reboot is pending. Run 'ssh root@100.103.212.83 \"reboot\"' to apply updates.\n"
    
    if avg_cpu_busy <= 80.0 and ram_used_pct <= 85.0 and "reboot" not in alarm_summary:
        report_body += "👍 Server health is excellent! No action required.\n"
        
    report_body += """
Best regards,
Hetzner Server Manager Agent
"""

    subject = f"Weekly Server Health Report: {avg_cpu_busy:.1f}% CPU, {ram_used_pct:.1f}% RAM"
    print(f"Sending report to {recipient}...")
    
    if send_email(recipient, subject, report_body):
        print("✅ Report sent successfully!")
    else:
        print("❌ Failed to send report.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    generate_report()
