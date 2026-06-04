"""站内设施查询服务。

优先从本地 SQLite 查询，未命中时通过高德 POI API 补充。
"""

import sqlite3
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

FACILITY_LABELS = {
    "restroom": "公共卫生间",
    "accessible_restroom": "无障碍卫生间",
    "nursing_room": "母婴室",
    "accessible_elevator": "无障碍电梯",
    "elevator": "直梯",
    "escalator": "扶梯",
    "ticket_machine": "售票机",
    "service_center": "客服中心",
}

FACILITY_ICONS = {
    "restroom": "WC",
    "accessible_restroom": "AWC",
    "nursing_room": "BABY",
    "accessible_elevator": "ELEV",
    "elevator": "ELEV",
    "escalator": "ESC",
    "ticket_machine": "TICKET",
    "service_center": "INFO",
}


class StationFacilities:
    def __init__(self):
        self.db_path = os.environ.get("SQLITE_PATH", "./data/metro_network.sqlite")
        self.amap_key = os.environ.get("AMAP_KEY", "")

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def query(self, station_name: str, line: str = "") -> dict:
        """查询某站的设施列表。

        Args:
            station_name: 站名
            line: 线路（可选，不传则返回所有线路的设施）

        Returns:
            {"station": "西直门", "facilities": [{"type": "restroom", "label": "公共卫生间", "icon": "WC", "floor": "B1", "location": "站厅层中部"}, ...]}
        """
        conn = self._get_conn()
        try:
            if line:
                rows = conn.execute(
                    "SELECT * FROM facilities WHERE station_name = ? AND line = ?",
                    (station_name, line),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM facilities WHERE station_name = ?",
                    (station_name,),
                ).fetchall()

            facilities = []
            for r in rows:
                facilities.append({
                    "type": r["facility_type"],
                    "label": FACILITY_LABELS.get(r["facility_type"], r["facility_type"]),
                    "icon": FACILITY_ICONS.get(r["facility_type"], "?"),
                    "floor": r["floor"],
                    "location": r["location_desc"],
                })

            # 本地有数据直接返回
            if facilities:
                return {"station": station_name, "line": line or "全部线路", "facilities": facilities, "source": "local"}

            # 本地无数据 → 尝试高德 API 兜底
            if self.amap_key:
                amap_result = self._query_amap(conn, station_name)
                if amap_result:
                    return {"station": station_name, "line": line or "全部线路", "facilities": amap_result, "source": "amap"}

            return {"station": station_name, "line": line or "全部线路", "facilities": [], "source": "none"}

        finally:
            conn.close()

    def _query_amap(self, conn, station_name: str) -> list:
        """调用高德 POI 周边搜索作为兜底。"""
        # 先查站坐标
        row = conn.execute(
            "SELECT lat, lng FROM stations WHERE name = ? LIMIT 1",
            (station_name,),
        ).fetchone()
        if not row:
            return []

        try:
            # 高德 POI 周边搜索（卫生间 + 无障碍设施 + 母婴室）
            resp = httpx.get("https://restapi.amap.com/v3/place/around", params={
                "key": self.amap_key,
                "location": f"{row['lng']},{row['lat']}",
                "types": "200300|200303|200304|991601",
                "radius": 300,
                "extensions": "all",
            }, timeout=5.0)
            data = resp.json()
            if data.get("status") != "1":
                return []

            facilities = []
            for poi in data.get("pois", []):
                poi_name = poi.get("name", "")
                poi_type = poi.get("typecode", "")
                floor = (poi.get("indoor_data", {}) or {}).get("floor", "")
                indoor = poi.get("indoor_map", "")

                ftype = self._map_amap_type(poi_type, poi_name)
                if ftype:
                    facilities.append({
                        "type": ftype,
                        "label": FACILITY_LABELS.get(ftype, poi_name),
                        "icon": FACILITY_ICONS.get(ftype, "?"),
                        "floor": floor or "",
                        "location": f"{'室内' if indoor == '1' else '站厅'} {poi_name}",
                    })

            # 去重
            seen = set()
            unique = []
            for f in facilities:
                key = (f["type"], f["floor"])
                if key not in seen:
                    seen.add(key)
                    unique.append(f)
            return unique

        except Exception:
            return []

    def _map_amap_type(self, typecode: str, name: str) -> str:
        """将高德 POI 类型映射到设施类型。"""
        tc = str(typecode)
        if tc.startswith("200300") or "厕所" in name or "卫生间" in name:
            if "无障碍" in name or tc == "200303":
                return "accessible_restroom"
            return "restroom"
        if tc == "200304" or "母婴" in name:
            return "nursing_room"
        if tc == "991601" or "无障碍电梯" in name:
            return "accessible_elevator"
        return ""


station_facilities = StationFacilities()
