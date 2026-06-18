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
                  strategy: str = "time", city: str = "北京",
                  from_name: str = "", to_name: str = "") -> dict | None:
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

            # 过滤：丢弃终点不是目标站的路线
            if to_name:
                routes = [r for r in routes
                          if r["details"]["stations"] and r["details"]["stations"][-1] == to_name]
            if not routes:
                return None

            # 排序：优先起止站名匹配，其次按策略排
            def route_score(r):
                st = r["details"]["stations"]
                match_bonus = 0
                if from_name and st and st[0] == from_name:
                    match_bonus -= 1000
                if to_name and st and st[-1] == to_name:
                    match_bonus -= 1000
                if strategy == "transfers":
                    return (match_bonus, r["transfers"], r["totalTime"])
                elif strategy == "price":
                    return (match_bonus, r["price"], r["totalTime"])
                return (match_bonus, r["totalTime"], r["transfers"])

            routes.sort(key=route_score)

            # 过滤：最佳方案至少起止一站匹配，否则弃用高德、走本地
            best = routes[0]
            best_st = best["details"]["stations"]
            from_ok = from_name and best_st and best_st[0] == from_name
            to_ok = to_name and best_st and best_st[-1] == to_name
            if not from_ok or not to_ok:
                return None  # 触发本地 RAPTOR 兜底

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
        """将高德公交方案转为统一格式(仅保留地铁段)。"""
        segments = transit.get("segments", [])
        if not segments:
            return None

        total_time = 0
        metro_segments = []  # 收集所有地铁段: [(line_name, stations, duration_min), ...]
        pending_walk = 0     # 当前累积的步行时间(用于换乘)
        price = float(transit.get("cost", 0))

        for seg in segments:
            bus = seg.get("bus", {})
            buslines = bus.get("buslines", [])
            walking = seg.get("walking", {})

            # 步行时间：作为下一次换乘的步行成本
            if walking:
                walk_sec = int(walking.get("duration", 0))
                walk_time = max(1, walk_sec // 60)
                total_time += walk_time
                pending_walk += walk_time

            if buslines:
                for bl in buslines:
                    line_name = bl.get("name", "")
                    if not self._is_metro(line_name):
                        continue

                    seg_sec = int(bl.get("duration", 0))
                    seg_time = max(1, seg_sec // 60)
                    total_time += seg_time

                    # 站点解析
                    stops = bl.get("via_stops", [])
                    departure = bl.get("departure_stop", {})
                    arrival = bl.get("arrival_stop", {})

                    dep_name = self._clean_station(departure.get("name", ""))
                    arr_name = self._clean_station(arrival.get("name", ""))

                    full_stops = []
                    if dep_name:
                        full_stops.append(dep_name)
                    for s in stops:
                        n = self._clean_station(s.get("name", ""))
                        if n:
                            full_stops.append(n)
                    if arr_name and (not full_stops or arr_name != full_stops[-1]):
                        full_stops.append(arr_name)

                    # 裁剪到实际乘坐区间
                    start_idx = full_stops.index(dep_name) if dep_name in full_stops else 0
                    end_idx = full_stops.index(arr_name) if arr_name in full_stops else len(full_stops) - 1
                    seg_stations = full_stops[start_idx:end_idx + 1]

                    metro_segments.append((line_name, seg_stations, seg_time, pending_walk))
                    pending_walk = 0  # 步行已关联到这段

        if not metro_segments:
            return None

        # 拼接站点列表并生成换乘信息
        all_stations = []
        lines = []
        transfer_list = []

        for i, (line, stns, dur, walk) in enumerate(metro_segments):
            # 去重首站(与前一段末站相同)
            if all_stations and stns and stns[0] == all_stations[-1]:
                stns = stns[1:]

            all_stations.extend(stns)
            lines.append(line)

            # 换乘=上一段末站是当前段首站的同名站
            if i > 0:
                prev_last = metro_segments[i - 1][1][-1] if metro_segments[i - 1][1] else ""
                curr_first = metro_segments[i][1][0] if metro_segments[i][1] else ""
                transfer_station = prev_last if prev_last == curr_first else metro_segments[i][1][0]
                transfer_list.append({
                    "station": transfer_station,
                    "fromLine": metro_segments[i - 1][0],
                    "toLine": line,
                    "walkTime": walk,
                })

        return {
            "totalTime": total_time,
            "transfers": len(transfer_list),
            "price": price if price > 0 else 3.0,
            "lines": lines,
            "details": {
                "stations": all_stations,
                "transfers": transfer_list,
            },
        }

    @staticmethod
    def _clean_station(name: str) -> str:
        """清理站名（去掉高德返回的'地铁站'多余后缀）。"""
        for suffix in ["地铁站", "(地铁)"]:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        return name


amap_planner = AmapPlanner()
