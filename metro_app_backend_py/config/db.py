import os
import sqlite3
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

mongo_client: AsyncIOMotorClient | None = None


async def connect_mongo() -> AsyncIOMotorClient | None:
    global mongo_client
    try:
        mongo_client = AsyncIOMotorClient(os.environ["MONGO_URI"])
        await mongo_client.admin.command("ping")
        print("MongoDB connected")
        return mongo_client
    except Exception as e:
        print(f"MongoDB unavailable (non-critical): {e}")
        return None


async def close_mongo():
    global mongo_client
    if mongo_client:
        mongo_client.close()
        print("MongoDB disconnected")


def get_sqlite_db() -> sqlite3.Connection:
    db_path = os.environ.get("SQLITE_PATH", "./data/metro_network.sqlite")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
