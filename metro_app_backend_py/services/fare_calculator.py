"""票价计算服务。

按路径实际距离（edges 表面累计）计算阶梯票价。
"""

import os
from dotenv import load_dotenv

load_dotenv()


class FareCalculator:
    db_path: str

    def __init__(self):
        self.db_path = os.environ.get("SQLITE_PATH", "./data/metro_network.sqlite")

    def calculate(self, conn, from_station_id: str, to_station_id: str) -> float:
        """根据起止站 ID 计算票价（Haversine 直线距离兜底）。"""
        # 优先用路径边距累加（由 raptor_engine 传入完整路径的起止站）
        from_row = conn.execute("SELECT lat, lng FROM stations WHERE id = ?", (from_station_id,)).fetchone()
        to_row = conn.execute("SELECT lat, lng FROM stations WHERE id = ?", (to_station_id,)).fetchone()
        if not from_row or not to_row:
            return 0.0
        import math
        R = 6371
        dlat = math.radians(to_row["lat"] - from_row["lat"])
        dlng = math.radians(to_row["lng"] - from_row["lng"])
        a = math.sin(dlat/2)**2 + math.cos(math.radians(from_row["lat"]))*math.cos(math.radians(to_row["lat"]))*math.sin(dlng/2)**2
        dist = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return self._get_fare_by_distance(conn, dist)

    def calculate_path_distance(self, conn, station_ids: list) -> (float, float):
        """按路径中的站点 ID 序列，逐段累加 edges 表中的 distance_km 和时间。

        Returns: (total_distance_km, total_time_min)
        """
        total_dist = 0.0
        total_time = 0.0
        for i in range(len(station_ids) - 1):
            edge = conn.execute(
                "SELECT distance_km, travel_time FROM edges WHERE from_station = ? AND to_station = ?",
                (station_ids[i], station_ids[i + 1]),
            ).fetchone()
            if edge:
                total_dist += edge["distance_km"] or 0
                total_time += edge["travel_time"] or 0
        return total_dist, total_time

    def _get_fare_by_distance(self, conn, distance: float) -> float:
        row = conn.execute(
            "SELECT price FROM fare_rules WHERE ? >= start_km AND ? < end_km",
            (distance, distance),
        ).fetchone()
        return row["price"] if row else 0.0


fare_calculator = FareCalculator()
