from datetime import date, datetime

import aiosqlite

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    sex TEXT,
    age INTEGER,
    height REAL,
    weight REAL,
    activity TEXT,
    goal TEXT,
    remind_on INTEGER DEFAULT 0,
    remind_time TEXT DEFAULT '19:00',
    remind_days TEXT DEFAULT '0,1,3,4',
    last_remind TEXT,
    cycle_start TEXT,
    cycle_len INTEGER DEFAULT 28,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS weight_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    weight REAL NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    exercise_id TEXT NOT NULL,
    file_id TEXT,
    url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

EXTRA_COLS = {
    "remind_on": "INTEGER DEFAULT 0",
    "remind_time": "TEXT DEFAULT '19:00'",
    "remind_days": "TEXT DEFAULT '0,1,3,4'",
    "last_remind": "TEXT",
    "cycle_start": "TEXT",
    "cycle_len": "INTEGER DEFAULT 28",
}


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        cur = await db.execute("PRAGMA table_info(users)")
        have = {row[1] for row in await cur.fetchall()}
        for col, typ in EXTRA_COLS.items():
            if col not in have:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {typ}")
        await db.commit()


async def upsert_user(user_id: int, **fields) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        if fields:
            sets = ", ".join(f"{k} = ?" for k in fields)
            vals = list(fields.values()) + [user_id]
            await db.execute(f"UPDATE users SET {sets} WHERE user_id = ?", vals)
        await db.commit()


async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cur.fetchone()


async def users_with_reminders():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE remind_on = 1")
        return await cur.fetchall()


async def add_weight(user_id: int, weight: float, day: str | None = None) -> None:
    day = day or date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO weight_log (user_id, day, weight) VALUES (?, ?, ?)",
            (user_id, day, weight),
        )
        await db.execute("UPDATE users SET weight = ? WHERE user_id = ?", (weight, user_id))
        await db.commit()


async def list_weight(user_id: int, limit: int = 14):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT day, weight FROM weight_log WHERE user_id = ? ORDER BY day DESC, id DESC LIMIT ?",
            (user_id, limit),
        )
        return await cur.fetchall()


async def save_video(owner_id: int, exercise_id: str, file_id: str | None, url: str | None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO videos (owner_id, exercise_id, file_id, url) VALUES (?, ?, ?, ?)",
            (owner_id, exercise_id, file_id, url),
        )
        await db.commit()


async def get_videos(exercise_id: str, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT * FROM videos
            WHERE exercise_id = ? AND owner_id IN (0, ?)
            ORDER BY CASE WHEN owner_id = 0 THEN 0 ELSE 1 END, id DESC
            LIMIT 8
            """,
            (exercise_id, user_id),
        )
        return await cur.fetchall()


async def count_videos(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM videos WHERE owner_id IN (0, ?)", (user_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else 0
