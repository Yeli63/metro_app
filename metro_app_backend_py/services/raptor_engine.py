"""RAPTOR 路径规划引擎。

简化版实现：支持同线路直达和一次换乘的路径搜索。
"""

import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()


class RaptorEngine:
    def __init__(self):
        self.db_path = os.environ.get("SQLITE_PATH", "./data/metro_network.sqlite")
        self.max_transfers = 5

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def find_path(self, origin_name: str, dest_name: str, strategy: str = "time") -> dict:
        """查询行程方案。

        Args:
            origin_name: 起点站名称
            dest_name: 终点站名称
            strategy: 排序策略 'time' | 'transfers' | 'price'

        Returns:
            dict: {"routes": [...]} 或 {"error": "..."}
        """
        conn = self._get_conn()
        try:
            origin_stations = self._get_station_by_name(conn, origin_name)
            dest_stations = self._get_station_by_name(conn, dest_name)

            if not origin_stations or not dest_stations:
                return {"error": "站点不存在"}

            routes = []
            for origin in origin_stations:
                for dest in dest_stations:
                    result = self._single_pair_search(conn, origin["id"], dest["id"], strategy)
                    if result:
                        routes.append(result)

            # 按策略排序
            key_map = {
                "time": lambda r: (r["totalTime"], r["transfers"]),
                "transfers": lambda r: (r["transfers"], r["totalTime"]),
                "price": lambda r: (r["price"], r["totalTime"]),
            }
            sort_key = key_map.get(strategy, key_map["time"])
            routes.sort(key=sort_key)

            return {"routes": routes[:10]}
        finally:
            conn.close()

    def _single_pair_search(self, conn, origin_id: str, dest_id: str, strategy: str) -> dict | None:
        # 同线路直达
        direct = self._direct_route(conn, origin_id, dest_id)
        if direct:
            return self._build_solution(conn, direct["stations"], direct["line"], [], strategy)

        # 一次换乘
        origin_line = self._get_station_line(conn, origin_id)
        dest_line = self._get_station_line(conn, dest_id)
        if origin_line == dest_line:
            return None

        transfer_rows = conn.execute(
            "SELECT station_id FROM transfers WHERE from_line = ? AND to_line = ?",
            (origin_line, dest_line),
        ).fetchall()

        for transfer in transfer_rows:
            tid = transfer["station_id"]
            transfer_name = self._get_station_name(conn, tid)
            # 找到换乘站对应目标线路上的同名站
            dest_transfer = conn.execute(
                "SELECT id FROM stations WHERE name = ? AND line = ?",
                (transfer_name, dest_line),
            ).fetchone()
            if not dest_transfer:
                continue
            dest_tid = dest_transfer["id"]

            first_leg = self._direct_route(conn, origin_id, tid)
            second_leg = self._direct_route(conn, dest_tid, dest_id)
            if first_leg and second_leg:
                walk_time = self._get_transfer_walk_time(conn, tid, origin_line, dest_line)
                transfer_info = [{
                    "station": self._get_station_name(conn, tid),
                    "fromLine": origin_line,
                    "toLine": dest_line,
                    "walkTime": walk_time,
                }]
                # 拼接两段路径（换乘站保留两个线路版本）
                combined_stations = first_leg["stations"] + second_leg["stations"]
                return self._build_solution(
                    conn, combined_stations,
                    [first_leg["line"], second_leg["line"]],
                    transfer_info, strategy,
                )

        return None

    def _direct_route(self, conn, from_id: str, to_id: str) -> dict | None:
        from_row = conn.execute("SELECT * FROM stations WHERE id = ?", (from_id,)).fetchone()
        to_row = conn.execute("SELECT * FROM stations WHERE id = ?", (to_id,)).fetchone()
        if not from_row or not to_row or from_row["line"] != to_row["line"]:
            return None

        line = from_row["line"]
        for direction in ("up", "down"):
            path = self._traverse_line(conn, from_id, to_id, line, direction)
            if path:
                return {"stations": path, "line": line}
        return None

    def _traverse_line(self, conn, from_id: str, to_id: str, line: str, direction: str) -> list | None:
        """BFS 沿线路边搜索路径。"""
        visited = set()
        queue = [(from_id, [from_id])]

        while queue:
            current_id, path = queue.pop(0)
            if current_id == to_id:
                return path
            if current_id in visited:
                continue
            visited.add(current_id)

            edges = conn.execute(
                "SELECT to_station FROM edges WHERE from_station = ? AND line = ? AND direction = ?",
                (current_id, line, direction),
            ).fetchall()

            for edge in edges:
                if edge["to_station"] not in visited:
                    queue.append((edge["to_station"], path + [edge["to_station"]]))

        return None

    def _build_solution(self, conn, station_ids: list, lines, transfers: list, strategy: str) -> dict:
        """构建路径方案。

        Args:
            lines: 单线路字符串（直达场景）或多线路列表（换乘场景）
        """
        line_list = lines if isinstance(lines, list) else [lines]

        # 边查询不限定线路也能唯一确定（同站对之间不会有多条线路的边）
        segment_time = 0
        for i in range(len(station_ids) - 1):
            edge = conn.execute(
                "SELECT travel_time FROM edges WHERE from_station = ? AND to_station = ?",
                (station_ids[i], station_ids[i + 1]),
            ).fetchone()
            if edge:
                segment_time += edge["travel_time"]

        total_time = segment_time
        for t in transfers:
            total_time += t["walkTime"]

        from services.fare_calculator import fare_calculator

        price = fare_calculator.calculate(conn, station_ids[0], station_ids[-1])

        return {
            "totalTime": total_time,
            "transfers": len(transfers),
            "price": price,
            "lines": line_list,
            "details": {
                "stations": [self._get_station_name(conn, sid) for sid in station_ids],
                "transfers": transfers,
            },
        }

    # --- 辅助查询 ---
    def _get_station_by_name(self, conn, name: str):
        return conn.execute("SELECT * FROM stations WHERE name = ?", (name,)).fetchall()

    def _get_station_line(self, conn, station_id: str) -> str | None:
        row = conn.execute("SELECT line FROM stations WHERE id = ?", (station_id,)).fetchone()
        return row["line"] if row else None

    def _get_station_name(self, conn, station_id: str) -> str:
        row = conn.execute("SELECT name FROM stations WHERE id = ?", (station_id,)).fetchone()
        return row["name"] if row else station_id

    def _get_transfer_walk_time(self, conn, station_id: str, from_line: str, to_line: str) -> int:
        row = conn.execute(
            "SELECT walk_time FROM transfers WHERE station_id = ? AND from_line = ? AND to_line = ?",
            (station_id, from_line, to_line),
        ).fetchone()
        return row["walk_time"] if row else 5


raptor_engine = RaptorEngine()
