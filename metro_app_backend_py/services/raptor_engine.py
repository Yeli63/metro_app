"""RAPTOR 路径规划引擎。

迭代式实现：支持 0~N 次换乘的路径搜索。
"""

import sqlite3
import os
from collections import defaultdict
from heapq import heappush, heappop
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
        conn = self._get_conn()
        try:
            origin_stations = self._get_station_by_name(conn, origin_name)
            dest_stations = self._get_station_by_name(conn, dest_name)

            if not origin_stations or not dest_stations:
                return {"error": "站点不存在"}

            dest_ids = {d["id"] for d in dest_stations}

            routes = []
            for origin in origin_stations:
                results = self._multi_transfer_search(conn, origin["id"], dest_ids, strategy)
                routes.extend(results)

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

    # ── 多次换乘搜索 ──

    def _multi_transfer_search(self, conn, origin_id: str, dest_ids: set, strategy: str) -> list:
        """迭代式 RAPTOR：每轮沿线路扩展，换乘站进入下一轮。"""
        # 预加载线路站点顺序
        line_stations = self._load_line_stations(conn)

        # 起点信息
        origin_line = self._get_station_line(conn, origin_id)

        # best[station_id] = (time, transfers, path_stations, path_lines, transfer_list)
        best = {}

        # 第 0 轮：沿起点线路双向探索
        for dir in ("up", "down"):
            self._explore_line(conn, origin_id, origin_line, dir,
                               [], [origin_line], [],
                               0, 0, best, line_stations, dest_ids)

        solutions = []
        for sid, (time, transfers, path_stations, path_lines, transfer_list) in best.items():
            if sid in dest_ids:
                solutions.append(self._build_result(conn, sid, time, transfers,
                                                     path_stations, path_lines, transfer_list, strategy))

        # 第 1~max_transfers 轮：从上一轮到达的站点出发，尝试换乘
        for round_num in range(1, self.max_transfers + 1):
            # 收集上一轮到达的站点（恰好 round_num-1 次换乘）
            frontier = [(sid, data) for sid, data in best.items() if data[1] == round_num - 1]

            if not frontier:
                break

            for station_id, (time, transfers, path, lines, tlist) in frontier:
                station_name = self._get_station_name(conn, station_id)
                current_line = lines[-1] if lines else self._get_station_line(conn, station_id)

                # 查找从当前线路出发的所有换乘
                transfer_rows = conn.execute(
                    "SELECT to_line, walk_time FROM transfers WHERE station_id = ? AND from_line = ?",
                    (station_id, current_line),
                ).fetchall()

                for tr in transfer_rows:
                    new_line = tr["to_line"]
                    if new_line in lines:
                        continue  # 避免回环

                    walk_time = tr["walk_time"]
                    # 找到同名站在新线路上的 ID
                    dest_transfer = conn.execute(
                        "SELECT id FROM stations WHERE name = ? AND line = ?",
                        (station_name, new_line),
                    ).fetchone()
                    if not dest_transfer:
                        continue

                    new_tid = dest_transfer["id"]
                    new_time = time + walk_time
                    new_transfers = transfers + 1
                    new_lines = lines + [new_line]
                    new_tlist = tlist + [{
                        "station": station_name,
                        "fromLine": current_line,
                        "toLine": new_line,
                        "walkTime": walk_time,
                    }]

                    for dir in ("up", "down"):
                        self._explore_line(conn, new_tid, new_line, dir,
                                           path, new_lines, new_tlist,
                                           new_time, new_transfers,
                                           best, line_stations, dest_ids)

        # 从 best 中收集到达目标的方案
        for sid, (time, transfers, path_stations, path_lines, transfer_list) in best.items():
            if sid in dest_ids:
                solutions.append(self._build_result(conn, sid, time, transfers,
                                                     path_stations, path_lines, transfer_list, strategy))

        return solutions

    def _explore_line(self, conn, start_id: str, line: str, direction: str,
                      prefix_path: list, prefix_lines: list, prefix_transfers: list,
                      base_time: float, base_transfers: int,
                      best: dict, line_stations: dict, dest_ids: set):
        """沿线路朝某个方向扩展，将到达的站点更新到 best 中。"""
        if line not in line_stations:
            return

        stations_in_order = line_stations[line][direction]
        try:
            start_idx = stations_in_order.index(start_id)
        except ValueError:
            return

        acc_time = base_time
        # 从起点站（含）开始，沿方向逐个遍历
        for i in range(start_idx, len(stations_in_order)):
            sid = stations_in_order[i]
            if i > start_idx:
                # 查边耗时
                edge = conn.execute(
                    "SELECT travel_time FROM edges WHERE from_station = ? AND to_station = ?",
                    (stations_in_order[i - 1], sid),
                ).fetchone()
                if not edge:
                    break
                acc_time += edge["travel_time"]

            path = prefix_path + stations_in_order[start_idx:i + 1]

            # 更新 best
            key = (acc_time, base_transfers)
            if sid not in best or key < (best[sid][0], best[sid][1]):
                # 合并路径：如果 prefix_path 的最后一个站与当前路径首站相同则去重
                best[sid] = (acc_time, base_transfers, path, list(prefix_lines), list(prefix_transfers))

    def _load_line_stations(self, conn) -> dict:
        """预加载每条线路在两个方向上的站点序列。

        Returns: {line: {"up": [id1, id2, ...], "down": [idN, ..., id1]}}
        """
        line_stations = defaultdict(lambda: {"up": [], "down": []})

        stations = conn.execute("SELECT id, line FROM stations ORDER BY id").fetchall()
        for s in stations:
            line_stations[s["line"]]["up"].append(s["id"])

        # 下行是上行的反向
        for line in line_stations:
            line_stations[line]["down"] = list(reversed(line_stations[line]["up"]))

        return dict(line_stations)

    # ── 结果构建 ──

    def _build_result(self, conn, dest_id: str, total_time: float, transfers: int,
                      path: list, lines: list, tlist: list, strategy: str) -> dict:
        from services.fare_calculator import fare_calculator

        price = fare_calculator.calculate(conn, path[0], path[-1])

        return {
            "totalTime": round(total_time, 1),
            "transfers": transfers,
            "price": price,
            "lines": lines,
            "details": {
                "stations": [self._get_station_name(conn, sid) for sid in path],
                "transfers": tlist,
            },
        }

    # ── 辅助查询 ──

    def _get_station_by_name(self, conn, name: str):
        return conn.execute("SELECT * FROM stations WHERE name = ?", (name,)).fetchall()

    def _get_station_line(self, conn, station_id: str) -> str | None:
        row = conn.execute("SELECT line FROM stations WHERE id = ?", (station_id,)).fetchone()
        return row["line"] if row else None

    def _get_station_name(self, conn, station_id: str) -> str:
        row = conn.execute("SELECT name FROM stations WHERE id = ?", (station_id,)).fetchone()
        return row["name"] if row else station_id


raptor_engine = RaptorEngine()
