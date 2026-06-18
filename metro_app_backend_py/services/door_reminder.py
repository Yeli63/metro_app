"""
开门方向提醒服务 — 根据行驶方向+站台类型推断开门侧。
============================================================
原创代码 | 地铁智行课程项目
站台规则: 基于中国地铁靠右行驶的通用规则推导
  - 岛式站台(island): 上行→左侧, 下行→右侧
  - 侧式站台(side):   上行→右侧, 下行→左侧
依赖: Python stdlib (sqlite3, os)
============================================================
中国地铁靠右行驶，逻辑如下：
- 岛式站台 (island)：站台在中间，列车在两侧
  - 上行/往市区 → 开左侧门
  - 下行/往郊区 → 开右侧门
- 侧式站台 (side)：站台在外侧，列车在中间
  - 上行/往市区 → 开右侧门
  - 下行/往郊区 → 开左侧门
"""

import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

# 站台类型 → (上行开门侧, 下行开门侧)
PLATFORM_DOOR_MAP = {
    "island": {"up": "left", "down": "right"},
    "side":  {"up": "right", "down": "left"},
}


class DoorReminder:
    def __init__(self):
        self.db_path = os.environ.get("SQLITE_PATH", "./data/metro_network.sqlite")

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_door_side(self, line: str, station_name: str, direction: str) -> dict | None:
        """查询某站某方向的开门侧。

        Args:
            line: 线路名称
            station_name: 站名
            direction: 行驶方向 'up' | 'down'

        Returns:
            {"station": "复兴门", "line": "1号线", "direction": "up", "doorSide": "left"}
            或 None（站点不存在）
        """
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM stations WHERE name = ? AND line = ?",
                (station_name, line),
            ).fetchone()
            if not row:
                return None

            platform_type = row["platform_type"] or "island"
            door_rules = PLATFORM_DOOR_MAP.get(platform_type, PLATFORM_DOOR_MAP["island"])
            door_side = door_rules.get(direction, "unknown")

            return {
                "station": station_name,
                "line": line,
                "direction": direction,
                "doorSide": door_side,
                "platformType": platform_type,
            }
        finally:
            conn.close()

    def get_route_doors(self, station_ids: list) -> list:
        """获取一批站点的开门方向（按路径顺序）。

        Args:
            station_ids: 路径中的站点 ID 列表

        Returns:
            [{"station": "xx", "doorSide": "left"}, ...]
        """
        conn = self._get_conn()
        try:
            result = []
            for i, sid in enumerate(station_ids):
                row = conn.execute("SELECT * FROM stations WHERE id = ?", (sid,)).fetchone()
                if not row:
                    result.append({"station": sid, "doorSide": "unknown"})
                    continue

                platform = row["platform_type"] or "island"
                # 判断方向：查看从当前站到下一站的边方向
                direction = None
                if i < len(station_ids) - 1:
                    edge = conn.execute(
                        "SELECT direction FROM edges WHERE from_station = ? AND to_station = ?",
                        (sid, station_ids[i + 1]),
                    ).fetchone()
                    if edge:
                        direction = edge["direction"]

                if direction and platform in PLATFORM_DOOR_MAP:
                    door_side = PLATFORM_DOOR_MAP[platform].get(direction, "unknown")
                else:
                    door_side = "unknown"

                result.append({
                    "station": row["name"],
                    "line": row["line"],
                    "doorSide": door_side,
                    "platformType": platform,
                })

            return result
        finally:
            conn.close()


door_reminder = DoorReminder()
