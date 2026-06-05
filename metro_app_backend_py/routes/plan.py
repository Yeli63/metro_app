"""路径规划、开门提醒与站内设施 API 路由。"""

import sqlite3
import os
from fastapi import APIRouter, Query, Request
from dotenv import load_dotenv
from services.raptor_engine import raptor_engine
from services.amap_planner import amap_planner, AMAP_KEY
from services.door_reminder import door_reminder
from services.station_facilities import station_facilities
from middleware.rate_limiter import limiter, PLAN_LIMIT

load_dotenv()
router = APIRouter()


def _get_station_coords(name: str) -> tuple | None:
    """从本地 SQLite 获取站点坐标。"""
    db_path = os.environ.get("SQLITE_PATH", "./data/metro_network.sqlite")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT lat, lng FROM stations WHERE name = ? LIMIT 1", (name,)).fetchone()
    conn.close()
    if row:
        return (row["lat"], row["lng"])
    return None


@router.get("/api/plan")
@limiter.limit(PLAN_LIMIT)
def plan_route(
    request: Request,
    from_: str = Query(..., alias="from", description="起点站名称"),
    to: str = Query(..., description="终点站名称"),
    strategy: str = Query("time", description="排序策略: time | transfers | price"),
):
    # ① 先获取坐标
    from_coords = _get_station_coords(from_)
    to_coords = _get_station_coords(to)

    # ② 高德 API 优先（需配置 AMAP_KEY 且站名能在本地库里找到坐标）
    if AMAP_KEY and from_coords and to_coords:
        amap_result = amap_planner.find_path(
            from_coords[0], from_coords[1],
            to_coords[0], to_coords[1],
            strategy, from_name=from_, to_name=to,
        )
        if amap_result and amap_result.get("routes"):
            return amap_result

    # ③ 高德不可用 → 本地 RAPTOR 兜底
    result = raptor_engine.find_path(from_, to, strategy)
    if "error" in result:
        return {"error": result["error"]}
    result["source"] = "local"
    return result


@router.get("/api/door")
def door_side(
    line: str = Query(..., description="线路名称"),
    station: str = Query(..., description="站名"),
    direction: str = Query(..., description="行驶方向: up | down"),
):
    result = door_reminder.get_door_side(line, station, direction)
    if result is None:
        return {"error": "站点不存在"}
    return result


@router.get("/api/facilities")
def get_facilities(
    station: str = Query(..., description="站名"),
    line: str = Query("", description="线路（可选）"),
):
    return station_facilities.query(station, line)


@router.get("/api/stations")
def get_stations():
    """返回所有站点坐标，供地图渲染。"""
    db_path = os.environ.get("SQLITE_PATH", "./data/metro_network.sqlite")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, name, line, lat, lng, platform_type FROM stations ORDER BY line, id"
    ).fetchall()
    conn.close()
    return {"stations": [dict(r) for r in rows]}


@router.get("/api/line_edges")
def get_line_edges():
    """返回所有线路边坐标，供地图绘制。"""
    db_path = os.environ.get("SQLITE_PATH", "./data/metro_network.sqlite")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT e.from_station, e.to_station, e.line, e.direction,
               s1.lat as from_lat, s1.lng as from_lng,
               s2.lat as to_lat, s2.lng as to_lng
        FROM edges e
        JOIN stations s1 ON e.from_station = s1.id
        JOIN stations s2 ON e.to_station = s2.id
        ORDER BY e.line, e.direction
    """).fetchall()
    conn.close()
    return {"edges": [dict(r) for r in rows]}
