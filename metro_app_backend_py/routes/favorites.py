"""收藏路线/站点 API。"""

import sqlite3
import os
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/favorites", tags=["收藏"])

DB_PATH = os.environ.get("SQLITE_PATH", "./data/metro_network.sqlite")


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class FavoriteCreate(BaseModel):
    fav_type: str  # "route" or "station"
    from_name: str = ""
    to_name: str = ""
    station_name: str = ""
    lines: str = ""


@router.get("")
def list_favorites(phone: str = Depends(get_current_user)):
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM favorites WHERE user_phone = ? ORDER BY created_at DESC",
        (phone,),
    ).fetchall()
    conn.close()
    return {"favorites": [dict(r) for r in rows]}


@router.post("")
def add_favorite(body: FavoriteCreate, phone: str = Depends(get_current_user)):
    if body.fav_type not in ("route", "station"):
        raise HTTPException(400, "fav_type must be 'route' or 'station'")
    conn = _get_db()
    conn.execute(
        "INSERT INTO favorites (user_phone, fav_type, from_name, to_name, station_name, lines) VALUES (?,?,?,?,?,?)",
        (phone, body.fav_type, body.from_name, body.to_name, body.station_name, body.lines),
    )
    conn.commit()
    fav_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return {"id": fav_id, "status": "ok"}


@router.delete("/{fav_id}")
def delete_favorite(fav_id: int, phone: str = Depends(get_current_user)):
    conn = _get_db()
    conn.execute("DELETE FROM favorites WHERE id = ? AND user_phone = ?", (fav_id, phone))
    deleted = conn.total_changes
    conn.commit()
    conn.close()
    if deleted == 0:
        raise HTTPException(404, "收藏不存在或无权删除")
    return {"status": "deleted"}
