"""高德地图公交路径规划 → 本地 RAPTOR 兜底。

优先调用高德公交路径规划 API（实时数据、真实耗时），
配额不足或调用失败时自动降级到本地 RAPTOR 引擎。
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

AMAP_KEY = os.environ.get("AMAP_KEY", "")
AMAP_DIRECTION_URL = "https://restapi.amap.com/v3/direction/transit/integrated"

# 策略映射: 我们的 strategy → 高德 strategy 参数
STRATEGY_MAP = {
    "time": 0,       # 最快
    "price": 1,      # 最经济
    "transfers": 2,  # 最少换乘
}


class AmapPlanner:
    def __init__(self):
        self.quota_exhausted = False

    def find_path(self, from_lat: float, from_lng: float,
                  to_lat: float, to_lng: float,
                  strategy: str = "time", city: str = "北京") -> dict | None:
        """调用高德公交路径规划 API。

        Returns:
            成功 → {"routes": [...], "source": "amap"}
            失败/配额不足 → None（触发本地兜底）
        """
        if not AMAP_KEY or self.quota_exhausted:
            return None

        amap_strategy = STRATEGY_MAP.get(strategy, 0)

        try:
            resp = httpx.get(AMAP_DIRECTION_URL, params={
                "key": AMAP_KEY,
                "origin": f"{from_lng},{from_lat}",
                "destination": f"{to_lng},{to_lat}",
                "city": city,
                "strategy": amap_strategy,
                "extensions": "all",
            }, timeout=6.0)

            data = resp.json()
            if data.get("status") != "1":
                info = data.get("info", "")
                # 配额耗尽特征
                if "DAILY_QUERY_OVER" in info or "OVER_QUOTA" in info or "LIMIT" in info.upper() or "限" in info:
                    self.quota_exhausted = True
                return None

            route = data.get("route", {})
            transits = route.get("transits", [])
            if not transits:
                return None

            routes = []
            for t in transits:
                r = self._parse_transit(t)
                if r:
                    routes.append(r)

            if not routes:
                return None

            # 排序
            key_map = {
                "time": lambda r: (r["totalTime"], r["transfers"]),
                "transfers": lambda r: (r["transfers"], r["totalTime"]),
                "price": lambda r: (r["price"], r["totalTime"]),
            }
            routes.sort(key=key_map.get(strategy, key_map["time"]))

            return {"routes": routes[:10], "source": "amap"}

        except Exception:
            return None

    @staticmethod
    def _is_metro(line_name: str) -> bool:
        """判断是否为地铁线路（过滤掉公交）。"""
        import re
        if not line_name:
            return False
        # 公交特征优先排除: 数字+路(如"1路""822路") 或 字母+数字+路(如"T58路")
        if re.search(r'\d+路', line_name) or re.search(r'[A-Z]\d+路', line_name):
            return False
        # 地铁特征: X号线 或 地铁X号线
        if re.search(r'\d+号线', line_name) or '地铁' in line_name.split('(')[0]:
            return True
        # 特殊线路名
        if re.match(r'^(S1|首都机场|大兴机场|燕房|西郊|亦庄|昌平|房山)', line_name):
            return True
        return False

    def _parse_transit(self, transit: dict) -> dict | None:
        """将高德公交方案转为我们的统一格式(仅保留地铁段)。"""
        segments = transit.get("segments", [])
        if not segments:
            return None

        total_time = 0
        lines = []
        all_stations = []
        transfer_list = []
        transfer_count = 0
        total_walk = 0
        price = float(transit.get("cost", 0))
        has_metro = False

        for seg in segments:
            bus = seg.get("bus", {})
            buslines = bus.get("buslines", [])
            walking = seg.get("walking", {})

            if walking:
                walk_sec = int(walking.get("duration", 0))
                walk_time = max(1, walk_sec // 60)
                total_time += walk_time
                total_walk += walk_time

            if buslines:
                for bl in buslines:
                    line_name = bl.get("name", "")
                    if not self._is_metro(line_name):
                        continue  # 跳过公交段
                    has_metro = True
                    seg_sec = int(bl.get("duration", 0))
                    seg_time = max(1, seg_sec // 60)
                    total_time += seg_time

                    # 途经站点 — 裁剪到实际起止站之间
                    stops = bl.get("via_stops", [])
                    departure = bl.get("departure_stop", {})
                    arrival = bl.get("arrival_stop", {})

                    dep_name = self._clean_station(departure.get("name", ""))
                    arr_name = self._clean_station(arrival.get("name", ""))

                    # 构建完整站序: departure + via_stops + arrival
                    full_stops = []
                    if dep_name:
                        full_stops.append(dep_name)
                    for s in stops:
                        n = self._clean_station(s.get("name", ""))
                        if n:
                            full_stops.append(n)
                    if arr_name and arr_name != full_stops[-1] if full_stops else True:
                        full_stops.append(arr_name)

                    # 裁剪: 找到 departure 和 arrival 在列表中的位置
                    start_idx = 0
                    end_idx = len(full_stops) - 1
                    if dep_name in full_stops:
                        start_idx = full_stops.index(dep_name)
                    if arr_name in full_stops:
                        end_idx = full_stops.index(arr_name)

                    seg_stations = full_stops[start_idx:end_idx + 1]

                    if seg_stations:
                        all_stations.extend(seg_stations)
                    if line_name:
                        lines.append(line_name)

            # 换乘检测
            if len(lines) > len(transfer_list) + 1:
                transfer_count += 1
                prev_line = lines[-2] if len(lines) >= 2 else ""
                curr_line = lines[-1] if lines else ""
                # 在 all_stations 中找连接点
                if all_stations:
                    transfer_list.append({
                        "station": all_stations[-1] if all_stations else "换乘站",
                        "fromLine": prev_line,
                        "toLine": curr_line,
                        "walkTime": total_walk,
                    })
                total_walk = 0

        if not has_metro or not all_stations:
            return None

        return {
            "totalTime": total_time,
            "transfers": transfer_count,
            "price": price if price > 0 else 3.0,
            "lines": list(dict.fromkeys(lines)),  # 去重保序
            "details": {
                "stations": all_stations,
                "transfers": transfer_list,
            },
        }

    @staticmethod
    def _clean_station(name: str) -> str:
        """清理站名（去掉'地铁站'后缀等）。"""
        for suffix in ["地铁站", "(地铁)", "站"]:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        return name


amap_planner = AmapPlanner()
