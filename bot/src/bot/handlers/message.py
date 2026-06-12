import logging
import asyncio
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message

logger = logging.getLogger(__name__)
router = Router()

def truncate_output(text: str, max_chars: int = 3500) -> str:
    """Truncates output text to fit within Telegram's message limit, keeping the tail."""
    if len(text) <= max_chars:
        return text
    truncated_len = len(text) - max_chars
    return f"⚠️ [Вывод усечен на {truncated_len} символов]\n...\n" + text[-max_chars:]

async def run_command_async(cmd: str, cwd: str = "/opt", timeout: int = 30) -> str:
    """Asynchronously runs a shell command inside the directory with a timeout."""
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
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

@router.message(F.text)
async def handle_text_message(message: Message, db_user: dict):
    """Fallback text handler that runs general commands if prefixed with '$'."""
    text = message.text.strip()
    
    if text.startswith("$"):
        cmd = text[1:].strip()
        if not cmd:
            await message.reply("⚠️ Вы указали пустую команду после `$`")
            return
            
        status_msg = await message.reply("⏳ Выполняю команду на сервере...")
        
        result = await run_command_async(cmd)
        
        await status_msg.edit_text(result, parse_mode="HTML")
    else:
        # Ignore normal messages outside commands to prevent noise
        pass
