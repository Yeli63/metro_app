"""票价计算服务。

基于距离的阶梯票价，使用 Haversine 公式估算距离。
"""

import math
import os
from dotenv import load_dotenv

load_dotenv()


class FareCalculator:
    db_path: str

    def __init__(self):
        self.db_path = os.environ.get("SQLITE_PATH", "./data/metro_network.sqlite")

    def calculate(self, conn, from_station_id: str, to_station_id: str) -> float:
        """根据起止站 ID 计算票价。"""
        distance = self._estimate_distance(conn, from_station_id, to_station_id)
        return self._get_fare_by_distance(conn, distance)

    def calculate_multi_segment(self, conn, segments: list) -> float:
        """计算多段行程总票价。"""
        return sum(self.calculate(conn, seg["from"], seg["to"]) for seg in segments)

    def _estimate_distance(self, conn, from_id: str, to_id: str) -> float:
        from_row = conn.execute("SELECT lat, lng FROM stations WHERE id = ?", (from_id,)).fetchone()
        to_row = conn.execute("SELECT lat, lng FROM stations WHERE id = ?", (to_id,)).fetchone()
        if not from_row or not to_row:
            return 0.0
        return self._haversine(from_row["lat"], from_row["lng"], to_row["lat"], to_row["lng"])

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """计算两点间的大圆距离（km）。"""
        R = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(d_lon / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _get_fare_by_distance(self, conn, distance: float) -> float:
        row = conn.execute(
            "SELECT price FROM fare_rules WHERE ? >= start_km AND ? < end_km",
            (distance, distance),
        ).fetchone()
        return row["price"] if row else 0.0


fare_calculator = FareCalculator()
