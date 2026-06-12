import os
import asyncio
import logging
import json
import urllib.request
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

logger = logging.getLogger(__name__)
router = Router()

async def run_shell(cmd: str) -> str:
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            return stdout.decode().strip()
        else:
            return f"Error (code {proc.returncode}): " + stderr.decode().strip()
    except Exception as e:
        return f"Exception: {str(e)}"

async def get_netdata_json(endpoint: str) -> dict:
    url = f"http://localhost:19999/api/v1/{endpoint}"
    def _fetch():
        req = urllib.request.Request(url, headers={'User-Agent': 'HetznerManagerBot/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode())
    return await asyncio.to_thread(_fetch)

async def get_cpu_usage() -> str:
    try:
        data = await get_netdata_json("data?chart=system.cpu&after=-10&points=1&group=average")
        if data and "data" in data and len(data["data"]) > 0:
            labels = data["labels"]
            values = data["data"][0]
            metrics_dict = dict(zip(labels, values))
            busy_sum = sum(metrics_dict[k] for k in metrics_dict if k != "time" and metrics_dict[k] is not None)
            return f"{busy_sum:.1f}%"
    except Exception as e:
        logger.error(f"Error fetching CPU from Netdata: {e}")
    return "Unknown"

async def get_ram_usage() -> str:
    try:
        data = await get_netdata_json("data?chart=system.ram&after=-10&points=1&group=average")
        if data and "data" in data and len(data["data"]) > 0:
            labels = data["labels"]
            values = data["data"][0]
            ram_dict = dict(zip(labels, values))
            used = ram_dict.get("used", 0) or 0
            free = ram_dict.get("free", 0) or 0
            cached = ram_dict.get("cached", 0) or 0
            buffers = ram_dict.get("buffers", 0) or 0
            
            total = used + free + cached + buffers
            if total > 0:
                used_pct = (used / total) * 100
                return f"{used:.0f} MB / {total:.0f} MB ({used_pct:.1f}%)"
    except Exception as e:
        logger.error(f"Error fetching RAM from Netdata: {e}")
    return "Unknown"

async def get_disk_usage() -> str:
    try:
        data = await get_netdata_json("data?chart=disk_space./&after=-10&points=1&group=average")
        if data and "data" in data and len(data["data"]) > 0:
            labels = data["labels"]
            values = data["data"][0]
            disk_dict = dict(zip(labels, values))
            used = disk_dict.get("used", 0) or 0
            avail = disk_dict.get("avail", 0) or 0
            reserved = disk_dict.get("reserved for root", 0) or 0
            
            total = used + avail + reserved
            if total > 0:
                used_pct = (used / total) * 100
                return f"{used:.1f} GB / {total:.1f} GB ({used_pct:.1f}%)"
    except Exception as e:
        logger.error(f"Error fetching Disk from Netdata: {e}")
    return "Unknown"

async def get_load_average() -> str:
    try:
        data = await get_netdata_json("data?chart=system.load&after=-10&points=1&group=average")
        if data and "data" in data and len(data["data"]) > 0:
            labels = data["labels"]
            values = data["data"][0]
            load_dict = dict(zip(labels, values))
            l1 = load_dict.get("load1", 0)
            l5 = load_dict.get("load5", 0)
            l15 = load_dict.get("load15", 0)
            return f"{l1:.2f}, {l5:.2f}, {l15:.2f}"
    except Exception as e:
        logger.error(f"Error fetching load average from Netdata: {e}")
    return "Unknown"

async def get_system_info() -> dict:
    try:
        info = await get_netdata_json("info")
        uptime_sec = info.get("uptime", 0)
        days = int(uptime_sec // 86400)
        hours = int((uptime_sec % 86400) // 3600)
        minutes = int((uptime_sec % 3600) // 60)
        uptime_parts = []
        if days > 0:
            uptime_parts.append(f"{days}d")
        if hours > 0:
            uptime_parts.append(f"{hours}h")
        uptime_parts.append(f"{minutes}m")
        uptime = " ".join(uptime_parts) if uptime_parts else "0m"
        
        return {
            "uptime": uptime,
            "os_name": info.get("os_name", "Unknown"),
            "os_version": info.get("os_version", "Unknown")
        }
    except Exception as e:
        logger.error(f"Error fetching system info from Netdata: {e}")
        return {
            "uptime": "Unknown",
            "os_name": "Unknown",
            "os_version": "Unknown"
        }

@router.message(CommandStart())
async def cmd_start(message: Message, db_user: dict):
    welcome_text = (
        f"👋 Привет, {db_user['name']}!\n\n"
        f"Вы авторизованы как: `{db_user['description']}`\n\n"
        f"🖥️ *Мониторинг сервера Hetzner*:\n"
        f"• /sysinfo — Состояние CPU, оперативной памяти и диска\n"
        f"• /daemons — Статус служб Systemd\n"
        f"• /docker — Список и статус Docker-контейнеров\n\n"
        f"⚙️ *Управление*:\n"
        f"• `/restart_daemon <имя>` — Перезапустить системную службу\n"
        f"• `/restart_container <имя>` — Перезапустить Docker-контейнер\n\n"
        f"💻 *Выполнение шелл-команд*:\n"
        f"Отправьте сообщение с префиксом `$` (например, `$ free -m`), чтобы выполнить команду на сервере."
    )
    await message.answer(welcome_text, parse_mode="Markdown")

@router.message(Command("sysinfo", "status"))
async def cmd_sysinfo(message: Message):
    status_msg = await message.answer("📊 Считываю метрики системы...")
    
    # Gather system info via Netdata API
    sys_info = await get_system_info()
    loadavg = await get_load_average()
    cpu_busy = await get_cpu_usage()
    ram = await get_ram_usage()
    disk = await get_disk_usage()
    
    lines = [
        "🖥️ *Текущие показатели сервера Hetzner* (через Netdata API):\n",
        f"• *OS*: `{sys_info['os_name']} {sys_info['os_version']}`",
        f"• *Uptime*: `{sys_info['uptime']}`",
        f"• *Load Average*: `{loadavg}`",
        f"• *Загрузка CPU*: `{cpu_busy}`",
        f"• *Использование RAM*: `{ram}`",
        f"• *Дисковое пространство (`/`)*: `{disk}`"
    ]
    await status_msg.edit_text("\n".join(lines), parse_mode="Markdown")

@router.message(Command("daemons", "services"))
async def cmd_daemons(message: Message):
    status_msg = await message.answer("🔍 Опрашиваю состояние служб Systemd...")
    
    services = {
        "ag2r": "AG2R Remote Client UI",
        "antigravity-gui": "Antigravity GUI (Electron)",
        "xvfb": "Virtual Display Xvfb",
        "hetzner-bot": "Telegram Monitor Bot"
    }
    
    lines = ["⚙️ *Статус системных служб (Systemd)*:\n"]
    
    for s_name, desc in services.items():
        state = await run_shell(f"systemctl is-active {s_name}.service")
        icon = "🟢" if state == "active" else "🔴"
        lines.append(f"{icon} *{s_name}* ({desc}): `{state}`")
        
    await status_msg.edit_text("\n".join(lines), parse_mode="Markdown")

@router.message(Command("docker", "containers"))
async def cmd_docker(message: Message):
    status_msg = await message.answer("🐳 Получаю список Docker-контейнеров...")
    
    raw_containers = await run_shell("docker ps -a --format '{{.Names}}\t{{.Status}}'")
    if raw_containers.startswith("Error") or raw_containers.startswith("Exception"):
        await status_msg.edit_text(f"❌ Ошибка опроса Docker: `{raw_containers}`")
        return
        
    lines = ["🐳 *Статус Docker-контейнеров на сервере*:\n"]
    
    if not raw_containers.strip():
        lines.append("📭 Нет активных Docker-контейнеров.")
    else:
        for line in raw_containers.strip().split("\n"):
            if "\t" in line:
                name, status = line.split("\t", 1)
                icon = "🟢" if "Up" in status else "🔴"
                lines.append(f"{icon} `{name}`: _{status}_")
            else:
                lines.append(f"• `{line}`")
                
    await status_msg.edit_text("\n".join(lines), parse_mode="Markdown")

@router.message(Command("restart_daemon"))
async def cmd_restart_daemon(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Использование: `/restart_daemon <имя_службы>`\nПример: `/restart_daemon ag2r`")
        return
        
    service_name = args[1].lower().replace(".service", "")
    allowed_services = ["ag2r", "antigravity-gui", "xvfb", "hetzner-bot"]
    
    if service_name not in allowed_services:
        await message.answer(f"❌ Перезапуск службы `{service_name}` запрещен. Разрешенные службы: {', '.join(allowed_services)}")
        return
        
    status_msg = await message.answer(f"🔄 Выполняю перезапуск службы `{service_name}.service`...")
    
    res = await run_shell(f"sudo systemctl restart {service_name}.service")
    
    if res == "" or "Error" not in res:
        await status_msg.edit_text(f"✅ Служба `{service_name}.service` успешно перезапущена!")
    else:
        await status_msg.edit_text(f"❌ Ошибка перезапуска службы:\n`{res}`")

@router.message(Command("restart_container"))
async def cmd_restart_container(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Использование: `/restart_container <имя_контейнера>`\nПример: `/restart_container pulse_bot`")
        return
        
    container_name = args[1].strip()
    status_msg = await message.answer(f"🐳 Выполняю перезапуск контейнера `{container_name}`...")
    
    res = await run_shell(f"docker restart {container_name}")
    
    if "Error" not in res and "Exception" not in res:
        await status_msg.edit_text(f"✅ Контейнер `{container_name}` успешно перезапущен!")
    else:
        await status_msg.edit_text(f"❌ Ошибка перезапуска контейнера:\n`{res}`")
