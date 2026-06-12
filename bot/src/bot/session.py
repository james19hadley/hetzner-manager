# session.py - Stateful shell session manager for Telegram users

shell_sessions = {}

def get_session(user_id: int) -> dict:
    if user_id not in shell_sessions:
        shell_sessions[user_id] = {
            "cwd": "/opt",
            "user": "tg-monitor",
            "env": {},
            "interactive": False
        }
    return shell_sessions[user_id]
