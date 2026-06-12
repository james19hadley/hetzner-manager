import os
import aiosqlite
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def initialize(self):
        """Creates tables and schema if they do not exist."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            
            # 1. Users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 2. Telegram accounts whitelisting table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS telegram_accounts (
                    telegram_id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    description TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)
            await db.commit()
        logger.info(f"Database initialized at {self.db_path}")

    async def add_user(self, name: str) -> int:
        """Adds a user and returns their ID."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "INSERT INTO users (name) VALUES (?) RETURNING id;", (name,)
            ) as cursor:
                row = await cursor.fetchone()
                await db.commit()
                return row[0] if row else None

    async def register_telegram_account(self, telegram_id: int, user_id: int, description: str = None):
        """Maps a Telegram ID to a whitelisted user."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO telegram_accounts (telegram_id, user_id, description) VALUES (?, ?, ?);",
                (telegram_id, user_id, description)
            )
            await db.commit()

    async def get_user_by_telegram_id(self, telegram_id: int) -> dict:
        """Returns user info if Telegram ID is whitelisted, otherwise None."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT u.id, u.name, ta.description 
                FROM users u
                JOIN telegram_accounts ta ON u.id = ta.user_id
                WHERE ta.telegram_id = ?;
                """,
                (telegram_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_all_telegram_accounts(self) -> list:
        """Gets all whitelisted Telegram IDs."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT telegram_id FROM telegram_accounts;") as cursor:
                rows = await cursor.fetchall()
                return [row["telegram_id"] for row in rows]
