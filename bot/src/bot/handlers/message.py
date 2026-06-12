import logging
import asyncio
import shlex
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message
from src.bot.session import get_session

logger = logging.getLogger(__name__)
router = Router()

def truncate_output(text: str, max_chars: int = 3500) -> str:
    """Truncates output text to fit within Telegram's message limit, keeping the tail."""
    if len(text) <= max_chars:
        return text
    truncated_len = len(text) - max_chars
    return f"⚠️ [Вывод усечен на {truncated_len} символов]\n...\n" + text[-max_chars:]

async def run_command_async(cmd: str, username: str = "tg-monitor", cwd: str = "/opt", env: dict = None, timeout: int = 30) -> str:
    """Asynchronously runs a shell command under the specified user and environment with a timeout."""
    try:
        # Construct environment string
        env_parts = []
        if env:
            for k, v in env.items():
                env_parts.append(f"{k}={shlex.quote(str(v))}")
        env_prefix = " ".join(env_parts) + " " if env_parts else ""
        
        # Build command invocation
        if username == "tg-monitor":
            # Run directly as current bot user (or with sudo prefix if explicitly typed by the user)
            full_cmd = cmd
        else:
            # Run via sudo as target user
            quoted_cmd = shlex.quote(cmd)
            if env_prefix:
                full_cmd = f"sudo -u {username} env {env_prefix} bash -c {quoted_cmd}"
            else:
                full_cmd = f"sudo -u {username} bash -c {quoted_cmd}"
                
        proc = await asyncio.create_subprocess_shell(
            full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                proc.terminate()
                await asyncio.sleep(0.5)
                proc.kill()
            except Exception:
                pass
            
            stdout, stderr = await proc.communicate()
            out_str = stdout.decode('utf-8', errors='ignore')
            err_str = stderr.decode('utf-8', errors='ignore')
            
            return (
                f"⏳ Превышено время ожидания ({timeout} сек.). Процесс принудительно остановлен.\n\n"
                f"📟 Частичный вывод:\n<pre>{truncate_output(out_str, 1500)}</pre>\n\n"
                f"⚠️ Ошибки:\n<pre>{truncate_output(err_str, 1000)}</pre>"
            )
            
        out_str = stdout.decode('utf-8', errors='ignore')
        err_str = stderr.decode('utf-8', errors='ignore')
        
        output_parts = []
        if out_str.strip():
            output_parts.append(f"📟 *Stdout*:\n<pre>{truncate_output(out_str)}</pre>")
        if err_str.strip():
            output_parts.append(f"⚠️ *Stderr*:\n<pre>{truncate_output(err_str)}</pre>")
            
        if not output_parts:
            output_parts.append(f"✅ Команда выполнена с кодом `{proc.returncode}` (вывод пуст).")
            
        return "\n\n".join(output_parts)
        
    except Exception as e:
        return f"❌ Ошибка запуска команды: `{str(e)}`"

async def change_directory(cmd_text: str, current_cwd: str, username: str) -> tuple[str, str]:
    """Resolves relative directory transitions via shell execution on the host."""
    target_dir = cmd_text[3:].strip()
    if not target_dir:
        target_dir = "~"
        
    # We resolve the path by running pwd as the session user
    sub_cmd = f"cd {shlex.quote(current_cwd)} && cd {target_dir} && pwd"
    
    # We execute this small path resolution command
    try:
        if username == "tg-monitor":
            full_cmd = sub_cmd
        else:
            full_cmd = f"sudo -u {username} bash -c {shlex.quote(sub_cmd)}"
            
        proc = await asyncio.create_subprocess_shell(
            full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode == 0:
            new_cwd = stdout.decode().strip().split("\n")[-1]
            return new_cwd, f"📁 Перешли в `{new_cwd}`"
        else:
            err_msg = stderr.decode().strip()
            return current_cwd, f"❌ Не удалось перейти в директорию:\n`{err_msg}`"
    except Exception as e:
        return current_cwd, f"❌ Ошибка разрешения пути: `{str(e)}`"

@router.message(F.text)
async def handle_text_message(message: Message, db_user: dict):
    """Fallback handler that intercepts command lines starting with '$' or during interactive session."""
    text = message.text.strip()
    
    # Bypass bot command commands starting with /
    if text.startswith("/"):
        return
        
    # Intercept plain text login shortcuts
    if text.lower() in ["login", "логин"]:
        from src.bot.handlers.base import cmd_agy_login
        await cmd_agy_login(message)
        return
        
    # Intercept Google Auth callback URL (starts with http://localhost or http://127.0.0.1 and contains auth/callback)
    if ("localhost:" in text or "127.0.0.1:" in text) and "auth/callback" in text:
        status_msg = await message.reply("⚙️ Обнаружена ссылка авторизации. Передаю в Antigravity...")
        try:
            from src.bot.handlers.base import ag2r_post_authenticated
            res = await ag2r_post_authenticated("auth/callback-proxy", {"url": text})
            if res.get("ok"):
                await status_msg.edit_text("✅ Ссылка авторизации успешно передана! Antigravity авторизован в Google.")
            else:
                await status_msg.edit_text(f"❌ Сервер отклонил ссылку: `{res.get('error', 'unknown error')}`")
        except Exception as e:
            await status_msg.edit_text(f"❌ Ошибка отправки ссылки авторизации:\n`{str(e)}`")
        return
        
    session = get_session(message.from_user.id)
    is_cmd = text.startswith("$")
    
    if is_cmd or session.get("interactive", False):
        cmd = text[1:].strip() if is_cmd else text
        if not cmd:
            await message.reply("⚠️ Вы указали пустую команду.")
            return
            
        # Parse CD command statefully
        if cmd.startswith("cd ") or cmd == "cd":
            new_cwd, msg_text = await change_directory(cmd, session["cwd"], session["user"])
            session["cwd"] = new_cwd
            
            # If in interactive mode, format prompt prefix
            if session.get("interactive", False):
                await message.reply(f"{msg_text}\n\n`[{session['user']}@{session['cwd']}]$`", parse_mode="Markdown")
            else:
                await message.reply(msg_text, parse_mode="Markdown")
            return
            
        # Format waiting response depending on mode
        status_msg = await message.reply("⏳ Выполняю команду...")
        
        # Run generic command
        result = await run_command_async(
            cmd,
            username=session["user"],
            cwd=session["cwd"],
            env=session["env"]
        )
        
        # If in interactive mode, append prompt prefix to output
        if session.get("interactive", False):
            result += f"\n\n`[{session['user']}@{session['cwd']}]$`"
            
        await status_msg.edit_text(result, parse_mode="HTML")
    else:
        # Ignore regular text chatter outside command execution
        pass

