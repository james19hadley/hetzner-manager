import os
import asyncio
import logging
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
    
    # Gather system info
    uptime = await run_shell("uptime -p")
    loadavg = await run_shell("cat /proc/loadavg | awk '{print $1 \", \" $2 \", \" $3}'")
    
    cpu_idle = await run_shell("top -bn1 | grep 'Cpu(s)' | sed 's/.*, *\\([0-9.]*\\)%* id.*/\\1/'")
    try:
        cpu_busy = f"{100 - float(cpu_idle):.1f}%"
    except ValueError:
        cpu_busy = "Unknown"
        
    ram = await run_shell("free -m | awk 'NR==2{printf \"%s MB / %s MB (%.1f%%)\", $3, $2, $3*100/$2}'")
    disk = await run_shell("df -h / | awk 'NR==2{printf \"%s / %s (%s)\", $3, $2, $5}'")
    
    lines = [
        "🖥️ *Текущие показатели сервера Hetzner*:\n",
        f"• *Uptime*: `{uptime}`",
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
