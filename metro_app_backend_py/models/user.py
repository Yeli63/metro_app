"""用户模型 — Pydantic 请求/响应模型 + SQLite 存储（MongoDB 可选）。"""

import sqlite3
import os
from datetime import datetime, timezone
from pydantic import BaseModel, Field


# ── 请求模型 ──

class RegisterRequest(BaseModel):
    phone: str = Field(..., min_length=11, max_length=11, pattern=r"^1[3-9]\d{9}$")
    password: str = Field(..., min_length=6, max_length=128)
    nickname: str = Field(default="", max_length=32)


class LoginRequest(BaseModel):
    phone: str = Field(..., min_length=11, max_length=11)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    phone: str
    nickname: str
    created_at: datetime


# ── SQLite 存储 ──

def _get_db():
    db_path = os.environ.get("SQLITE_PATH", "./data/metro_network.sqlite")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # 确保 users 表存在
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        phone TEXT PRIMARY KEY,
        hashed_password TEXT NOT NULL,
        nickname TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    return conn


async def create_user(phone: str, hashed_password: str, nickname: str = "") -> dict:
    conn = _get_db()
    try:
        existing = conn.execute("SELECT phone FROM users WHERE phone = ?", (phone,)).fetchone()
        if existing:
            return None
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO users (phone, hashed_password, nickname, created_at) VALUES (?,?,?,?)",
            (phone, hashed_password, nickname or phone, now),
        )
        conn.commit()
        return {"phone": phone, "hashed_password": hashed_password, "nickname": nickname or phone, "created_at": now}
    finally:
        conn.close()


async def find_user_by_phone(phone: str) -> dict | None:
    conn = _get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
