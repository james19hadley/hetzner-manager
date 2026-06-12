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
        f"• /sysinfo — CPU, RAM, Uptime, Load Avg, Диск (через Netdata API)\n"
        f"• /daemons — Статус системных служб Systemd\n"
        f"• /docker — Статус Docker-контейнеров на хосте\n\n"
        f"⚙️ *Управление службами*:\n"
        f"• `/restart_daemon <имя>` — Безопасный перезапуск службы\n"
        f"• `/restart_container <имя>` — Перезапуск Docker-контейнера\n\n"
        f"💻 *Сессия шелла и команд*:\n"
        f"• Отправьте команду с префиксом `$` (например, `$ ls -la`), чтобы выполнить её на хосте.\n"
        f"• Сессия сохраняет рабочую директорию (`cd`) и пользователя!\n"
        f"• `/sh` — Войти в интерактивный режим шелла (сообщения выполняются без `$`)\n"
        f"• `/sh_exit` — Выйти из интерактивного режима шелла\n"
        f"• `/su <имя>` — Сменить активного пользователя сессии (например, `/su root`)\n"
        f"• `/sh_status` — Посмотреть статус текущей сессии шелла\n\n"
        f"🔑 *Управление пользователями и правами (Sudo)*:\n"
        f"• /sysusers — Список пользователей ОС, их шеллов и групп\n"
        f"• /sysgroups — Список групп ОС и их участников\n"
        f"• /syssudoers — Состояние правил sudoers бота\n"
        f"• `/syschmod <права> <путь>` — Изменить права (например, `/syschmod 755 /var/www`)\n"
        f"• `/syschown <пользователь:группа> <путь>` — Сменить владельца\n"
        f"• `/sysusermod <аргументы>` — Изменить пользователя\n"
        f"• `/sysuseradd <аргументы>` — Добавить нового пользователя\n"
        f"• `/sysuserdel <имя>` — Удалить пользователя ОС"
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

# --- System Management & Accounts ---

from src.bot.session import get_session

@router.message(Command("sysusers"))
async def cmd_sysusers(message: Message):
    try:
        gid_to_name = {}
        user_to_groups = {}
        with open("/etc/group", "r") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) >= 4:
                    gname = parts[0]
                    gid = int(parts[2])
                    gid_to_name[gid] = gname
                    members = parts[3].split(",") if parts[3] else []
                    for m in members:
                        if m:
                            user_to_groups.setdefault(m, []).append(gname)
        
        lines = ["👤 *Пользователи системы Hetzner*:\n"]
        with open("/etc/passwd", "r") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) >= 7:
                    uname = parts[0]
                    uid = int(parts[2])
                    gid = int(parts[3])
                    home = parts[5]
                    shell = parts[6]
                    
                    # Filter system accounts to display only relevant ones
                    if uid >= 1000 or uname in ['root', 'ag2r', 'antigravity', 'tg-monitor', 'netdata']:
                        p_group = gid_to_name.get(gid, str(gid))
                        sec_groups = user_to_groups.get(uname, [])
                        all_groups = sorted(list(set([p_group] + sec_groups)))
                        
                        lines.append(
                            f"• *{uname}* (UID: `{uid}`, GID: `{gid}`)\n"
                            f"  🏠 Home: `{home}`\n"
                            f"  🐚 Shell: `{shell}`\n"
                            f"  👥 Groups: `{', '.join(all_groups)}`\n"
                        )
        await message.answer("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Ошибка получения списка пользователей: `{e}`")

@router.message(Command("sysgroups"))
async def cmd_sysgroups(message: Message):
    try:
        lines = ["👥 *Группы системы Hetzner (несистемные и служебные)*:\n"]
        with open("/etc/group", "r") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) >= 4:
                    gname = parts[0]
                    gid = int(parts[2])
                    members = parts[3].strip()
                    
                    if gid >= 1000 or members or gname in ['root', 'docker', 'sudo', 'msmtp', 'tg-monitor', 'ag2r', 'antigravity']:
                        member_str = f" Members: `{members}`" if members else " _(No members)_"
                        lines.append(f"• *{gname}* (GID: `{gid}`):{member_str}")
        await message.answer("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Ошибка получения списка групп: `{e}`")

@router.message(Command("syssudoers"))
async def cmd_syssudoers(message: Message):
    status_msg = await message.answer("🔑 Читаю конфигурацию sudoers...")
    res = await run_shell("sudo ls -la /etc/sudoers.d")
    lines = [
        "🔑 *Файлы sudoers в `/etc/sudoers.d/`*:\n",
        f"<pre>{res}</pre>\n",
        "📄 *Содержимое `/etc/sudoers.d/tg-monitor`*:"
    ]
    content = await run_shell("sudo cat /etc/sudoers.d/tg-monitor")
    lines.append(f"<pre>{content}</pre>")
    await status_msg.edit_text("\n".join(lines), parse_mode="HTML")

@router.message(Command("syschmod"))
async def cmd_syschmod(message: Message):
    args = message.text.split()
    if len(args) < 3:
        await message.answer("⚠️ Использование: `/syschmod <права> <путь>`\nПример: `/syschmod 755 /var/www`")
        return
    mode = args[1]
    path = args[2]
    
    status_msg = await message.answer(f"⚙️ Выполняю `sudo chmod {mode} {path}`...")
    res = await run_shell(f"sudo chmod {mode} {path}")
    if not res:
        await status_msg.edit_text(f"✅ Права на `{path}` успешно изменены на `{mode}`!")
    else:
        await status_msg.edit_text(f"❌ Ошибка выполнения chmod:\n`{res}`")

@router.message(Command("syschown"))
async def cmd_syschown(message: Message):
    args = message.text.split()
    if len(args) < 3:
        await message.answer("⚠️ Использование: `/syschown <владелец:группа> <путь>`\nПример: `/syschown root:docker /var/run/docker.sock`")
        return
    owner_group = args[1]
    path = args[2]
    
    status_msg = await message.answer(f"⚙️ Выполняю `sudo chown {owner_group} {path}`...")
    res = await run_shell(f"sudo chown {owner_group} {path}")
    if not res:
        await status_msg.edit_text(f"✅ Владелец `{path}` успешно изменен на `{owner_group}`!")
    else:
        await status_msg.edit_text(f"❌ Ошибка выполнения chown:\n`{res}`")

@router.message(Command("sysusermod"))
async def cmd_sysusermod(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Использование: `/sysusermod <аргументы>`\nПример: `/sysusermod -aG docker tg-monitor`")
        return
    user_args = args[1]
    status_msg = await message.answer(f"⚙️ Выполняю `sudo usermod {user_args}`...")
    res = await run_shell(f"sudo usermod {user_args}")
    if not res:
        await status_msg.edit_text("✅ Пользователь успешно изменен!")
    else:
        await status_msg.edit_text(f"❌ Ошибка выполнения usermod:\n`{res}`")

@router.message(Command("sysuseradd"))
async def cmd_sysuseradd(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("⚠️ Использование: `/sysuseradd <аргументы_и_имя>`\nПример: `/sysuseradd -m -s /bin/bash testuser`")
        return
    user_args = args[1]
    status_msg = await message.answer(f"⚙️ Выполняю `sudo useradd {user_args}`...")
    res = await run_shell(f"sudo useradd {user_args}")
    if not res:
        await status_msg.edit_text("✅ Пользователь успешно добавлен!")
    else:
        await status_msg.edit_text(f"❌ Ошибка выполнения useradd:\n`{res}`")

@router.message(Command("sysuserdel"))
async def cmd_sysuserdel(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Использование: `/sysuserdel <имя_пользователя>`\nПример: `/sysuserdel testuser`")
        return
    username = args[1]
    status_msg = await message.answer(f"⚙️ Выполняю `sudo userdel -r {username}`...")
    res = await run_shell(f"sudo userdel -r {username}")
    if not res:
        await status_msg.edit_text(f"✅ Пользователь `{username}` успешно удален!")
    else:
        await status_msg.edit_text(f"❌ Ошибка выполнения userdel:\n`{res}`")

# --- Stateful Shell Session Management ---

@router.message(Command("su"))
async def cmd_su(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Использование: `/su <имя_пользователя>`\nПример: `/su root`")
        return
    username = args[1].strip()
    
    # Verify if user exists by running whoami as that user
    res = await run_shell(f"sudo -u {username} whoami")
    if username in res or "tg-monitor" in res or "root" in res:
        session = get_session(message.from_user.id)
        session["user"] = username
        await message.answer(f"👤 Пользователь сессии переключен на: `{username}`\nТеперь команды `$` выполняются от его имени.")
    else:
        await message.answer(f"❌ Не удалось войти под пользователем `{username}` (возможно, его нет в системе или нет прав):\n`{res}`")

@router.message(Command("sh_status"))
async def cmd_sh_status(message: Message):
    session = get_session(message.from_user.id)
    status_text = (
        f"💻 *Текущий статус сессии шелла*:\n\n"
        f"• *Пользователь*: `{session['user']}`\n"
        f"• *Директория (CWD)*: `{session['cwd']}`\n"
        f"• *Интерактивный режим*: `{'Включен 🟢' if session['interactive'] else 'Выключен 🔴'}`\n"
        f"• *Переменные окружения*: `{session['env']}`"
    )
    await message.answer(status_text, parse_mode="Markdown")

@router.message(Command("sh"))
async def cmd_sh(message: Message):
    args = message.text.split(maxsplit=1)
    session = get_session(message.from_user.id)
    
    if len(args) >= 2:
        # Execute one-off command statefully
        cmd = args[1].strip()
        from src.bot.handlers.message import run_command_async
        status_msg = await message.reply("⏳ Выполняю...")
        result = await run_command_async(
            cmd,
            username=session["user"],
            cwd=session["cwd"],
            env=session["env"]
        )
        await status_msg.edit_text(result, parse_mode="HTML")
    else:
        # Enter interactive mode
        session["interactive"] = True
        welcome = (
            f"🟢 *Интерактивный режим шелла активирован!*\n\n"
            f"Все ваши последующие текстовые сообщения (без знака `/` в начале) будут выполняться как терминальные команды.\n"
            f"Для выхода введите команду `/sh_exit`.\n\n"
            f"`[{session['user']}@{session['cwd']}]$`"
        )
        await message.answer(welcome, parse_mode="Markdown")

@router.message(Command("sh_exit"))
async def cmd_sh_exit(message: Message):
    session = get_session(message.from_user.id)
    session["interactive"] = False
    await message.answer("🔴 Интерактивный режим шелла выключен.")
