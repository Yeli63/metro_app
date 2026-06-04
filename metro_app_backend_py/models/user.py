"""用户模型 — Pydantic 请求/响应模型 + MongoDB 操作。"""

import os
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from config.db import mongo_client


# ── 请求模型 ──

class RegisterRequest(BaseModel):
    phone: str = Field(..., min_length=11, max_length=11, pattern=r"^1[3-9]\d{9}$")
    password: str = Field(..., min_length=6, max_length=128)
    nickname: str = Field(default="", max_length=32)


class LoginRequest(BaseModel):
    phone: str = Field(..., min_length=11, max_length=11)
    password: str = Field(..., min_length=1)


# ── 响应模型 ──

class UserResponse(BaseModel):
    phone: str
    nickname: str
    created_at: datetime


# ── MongoDB 操作 ──

def _get_users_collection():
    client: AsyncIOMotorClient = mongo_client
    if client is None:
        raise RuntimeError("MongoDB 未连接")
    db = client[os.environ.get("MONGO_DB", "metro_app")]
    return db["users"]


async def create_user(phone: str, hashed_password: str, nickname: str = "") -> dict:
    col = _get_users_collection()
    existing = await col.find_one({"phone": phone})
    if existing:
        return None
    doc = {
        "phone": phone,
        "hashed_password": hashed_password,
        "nickname": nickname or phone,
        "created_at": datetime.now(timezone.utc),
    }
    await col.insert_one(doc)
    return doc


async def find_user_by_phone(phone: str) -> dict | None:
    col = _get_users_collection()
    return await col.find_one({"phone": phone})
