import asyncio
import logging
import json
import urllib.request
from aiogram import Bot
from src.database.db import Database

logger = logging.getLogger("hetzner_bot.alerts")

async def get_active_alarms() -> dict:
    url = "http://localhost:19999/api/v1/alarms?active"
    def _fetch():
        req = urllib.request.Request(url, headers={'User-Agent': 'HetznerManagerBot/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode())
    
    # Run the blocking fetch in an executor thread
    data = await asyncio.to_thread(_fetch)
    return data.get("alarms", {})

async def monitor_alerts(bot: Bot, db: Database, check_interval: int = 30):
    logger.info("Starting Netdata background alerts monitor task...")
    
    # Initialize cached active alarms on startup silently
    try:
        cached_alarms = await get_active_alarms()
        logger.info(f"Initialized alerts cache with {len(cached_alarms)} currently active alarms.")
    except Exception as e:
        cached_alarms = {}
        logger.error(f"Failed to initialize active alarms cache: {e}. Will retry in loop.")

    while True:
        await asyncio.sleep(check_interval)
        try:
            current_alarms = await get_active_alarms()
            
            # Find new or changed alerts
            for alarm_key, alarm_info in current_alarms.items():
                name = alarm_info.get("name", alarm_key)
                status = alarm_info.get("status", "WARNING")
                summary = alarm_info.get("summary", "No details available")
                chart = alarm_info.get("chart", "unknown")
                value = alarm_info.get("value_string", "unknown")
                
                # If it's a new alarm or the status changed (e.g. WARNING -> CRITICAL)
                cached_alarm = cached_alarms.get(alarm_key)
                if not cached_alarm or cached_alarm.get("status") != status:
                    icon = "🔴" if status == "CRITICAL" else "🟡"
                    msg = (
                        f"{icon} *[NETDATA ALERT - {status}]*\n\n"
                        f"• *Имя*: `{name}`\n"
                        f"• *Компонент*: `{chart}`\n"
                        f"• *Показатель*: `{value}`\n"
                        f"• *Описание*: {summary}\n"
                    )
                    
                    # Send alert to all whitelisted admins
                    admin_ids = await db.get_all_telegram_accounts()
                    for admin_id in admin_ids:
                        try:
                            await bot.send_message(admin_id, msg, parse_mode="Markdown")
                        except Exception as send_err:
                            logger.error(f"Failed to send alert to user {admin_id}: {send_err}")
            
            # Find resolved alerts (present in cache but not in current_alarms)
            for alarm_key, cached_info in list(cached_alarms.items()):
                if alarm_key not in current_alarms:
                    name = cached_info.get("name", alarm_key)
                    chart = cached_info.get("chart", "unknown")
                    summary = cached_info.get("summary", "")
                    
                    msg = (
                        f"🟢 *[ALERT RESOLVED]*\n\n"
                        f"• *Имя*: `{name}`\n"
                        f"• *Компонент*: `{chart}`\n"
                        f"• *Описание*: {summary}\n"
                        f"Восстановлен нормальный рабочий режим."
                    )
                    
                    admin_ids = await db.get_all_telegram_accounts()
                    for admin_id in admin_ids:
                        try:
                            await bot.send_message(admin_id, msg, parse_mode="Markdown")
                        except Exception as send_err:
                            logger.error(f"Failed to send resolution message to user {admin_id}: {send_err}")
            
            # Update cache
            cached_alarms = current_alarms
            
        except Exception as e:
            logger.error(f"Error in background alerts monitor loop: {e}")
