"""初始化 SQLite 离线路网数据库，包含建表和种子数据。"""

import sqlite3
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

DB_PATH = os.environ.get("SQLITE_PATH", "./data/metro_network.sqlite")

# 确保 data 目录存在
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA foreign_keys=ON")

# 建表
conn.executescript("""
    CREATE TABLE IF NOT EXISTS stations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        line TEXT NOT NULL,
        lat REAL,
        lng REAL,
        platform_type TEXT DEFAULT 'island'
    );

    CREATE TABLE IF NOT EXISTS edges (
        from_station TEXT NOT NULL,
        to_station TEXT NOT NULL,
        line TEXT NOT NULL,
        direction TEXT NOT NULL CHECK(direction IN ('up','down')),
        travel_time INT NOT NULL,
        distance_km REAL,
        PRIMARY KEY (from_station, to_station, line)
    );

    CREATE TABLE IF NOT EXISTS transfers (
        station_id TEXT NOT NULL,
        from_line TEXT NOT NULL,
        to_line TEXT NOT NULL,
        walk_time INT DEFAULT 5,
        is_cross_platform INT DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS fare_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city TEXT DEFAULT 'default',
        fare_type TEXT CHECK(fare_type IN ('distance','section')),
        start_km REAL,
        end_km REAL,
        price REAL
    );

    CREATE TABLE IF NOT EXISTS facilities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        station_name TEXT NOT NULL,
        line TEXT NOT NULL,
        facility_type TEXT NOT NULL CHECK(facility_type IN ('restroom','accessible_restroom','nursing_room','accessible_elevator','elevator','escalator','ticket_machine','service_center')),
        floor TEXT DEFAULT '',
        location_desc TEXT DEFAULT '',
        source TEXT DEFAULT 'manual'
    );
""")

# 插入种子数据
# ═══ 种子数据辅助函数 ═══
def seed_data():
    import math
    def haversine_km(lat1, lng1, lat2, lng2):
        R = 6371; dlat = math.radians(lat2-lat1); dlng = math.radians(lng2-lng1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlng/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    SPEED_KPH = 35  # 地铁平均时速 km/h

    sid_map = {}

    def add_line(line_name, stations):
        """添加一条完整线路。stations: [(name, lat, lng, platform_type), ...]"""
        ids = []
        for i, (name, lat, lng, ptype) in enumerate(stations):
            sid = f"{line_name}_{i+1:03d}"
            ids.append(sid)
            sid_map[(name, line_name)] = sid
            conn.execute(
                "INSERT OR IGNORE INTO stations (id, name, line, lat, lng, platform_type) VALUES (?, ?, ?, ?, ?, ?)",
                (sid, name, line_name, lat, lng, ptype),
            )
        for i in range(len(ids) - 1):
            _, lat1, lng1, _ = stations[i]
            _, lat2, lng2, _ = stations[i+1]
            dist = round(haversine_km(lat1, lng1, lat2, lng2), 2)
            time_min = max(1, round(dist / SPEED_KPH * 60))
            conn.execute(
                "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
                (ids[i], ids[i+1], line_name, "up", time_min, dist),
            )
            conn.execute(
                "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
                (ids[i+1], ids[i], line_name, "down", time_min, dist),
            )
        # 环线闭合边（仅限2号线）
        if line_name == "2号线" and len(ids) > 1:
            conn.execute(
                "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
                (ids[-1], ids[0], line_name, "up", 2, 1.1),
            )
            conn.execute(
                "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
                (ids[0], ids[-1], line_name, "down", 2, 1.1),
            )

    def add_transfer(name, line_a, line_b, walk=5):
        """添加双向换乘关系。"""
        a = sid_map.get((name, line_a))
        b = sid_map.get((name, line_b))
        if a and b:
            conn.execute("INSERT OR IGNORE INTO transfers (station_id, from_line, to_line, walk_time, is_cross_platform) VALUES (?,?,?,?,?)", (a, line_a, line_b, walk, 0))
            conn.execute("INSERT OR IGNORE INTO transfers (station_id, from_line, to_line, walk_time, is_cross_platform) VALUES (?,?,?,?,?)", (b, line_b, line_a, walk, 0))

    def add_facilities(fac_list):
        """批量添加设施。fac_list: [(name, line, type, floor, desc), ...]"""
        conn.executemany(
            "INSERT OR IGNORE INTO facilities (station_name, line, facility_type, floor, location_desc) VALUES (?,?,?,?,?)",
            fac_list,
        )

    # ═══════════════════════════════════════════
    # 北京地铁 1号线 · 八通线（苹果园 → 环球度假区，36站）
    # ═══════════════════════════════════════════
    add_line("1号线", [
        ("苹果园",   39.926, 116.178, "side"),
        ("古城",     39.920, 116.192, "island"),
        ("八角游乐园", 39.917, 116.205, "island"),
        ("八宝山",   39.914, 116.218, "island"),
        ("玉泉路",   39.911, 116.231, "island"),
        ("五棵松",   39.909, 116.244, "island"),
        ("万寿路",   39.907, 116.258, "island"),
        ("公主坟",   39.908, 116.310, "island"),
        ("军事博物馆", 39.908, 116.327, "island"),
        ("木樨地",   39.907, 116.340, "island"),
        ("南礼士路", 39.906, 116.350, "island"),
        ("复兴门",   39.908, 116.357, "island"),
        ("西单",     39.913, 116.374, "island"),
        ("天安门西", 39.913, 116.388, "island"),
        ("天安门东", 39.914, 116.401, "island"),
        ("王府井",   39.916, 116.414, "island"),
        ("东单",     39.915, 116.422, "island"),
        ("建国门",   39.909, 116.436, "island"),
        ("永安里",   39.909, 116.448, "island"),
        ("国贸",     39.909, 116.461, "island"),
        ("大望路",   39.908, 116.475, "island"),
        ("四惠",     39.909, 116.496, "side"),
        ("四惠东",   39.907, 116.510, "side"),
        # ── 八通线段 ──
        ("高碑店",   39.908, 116.525, "island"),
        ("传媒大学", 39.909, 116.545, "island"),
        ("双桥",     39.910, 116.565, "side"),
        ("管庄",     39.910, 116.585, "island"),
        ("八里桥",   39.908, 116.605, "side"),
        ("通州北苑", 39.907, 116.625, "island"),
        ("果园",     39.905, 116.640, "island"),
        ("九棵树",   39.903, 116.655, "island"),
        ("梨园",     39.902, 116.668, "side"),
        ("临河里",   39.900, 116.680, "island"),
        ("土桥",     39.898, 116.695, "island"),
        ("花庄",     39.886, 116.710, "side"),
        ("环球度假区", 39.880, 116.725, "island"),
    ])

    # ═══════════════════════════════════════════
    # 北京地铁 2号线（环线，18站）
    # ═══════════════════════════════════════════
    add_line("2号线", [
        ("西直门",   39.940, 116.355, "island"),
        ("积水潭",   39.948, 116.373, "island"),
        ("鼓楼大街", 39.950, 116.393, "island"),
        ("安定门",   39.949, 116.408, "island"),
        ("雍和宫",   39.948, 116.417, "island"),
        ("东直门",   39.941, 116.435, "island"),
        ("东四十条", 39.934, 116.433, "island"),
        ("朝阳门",   39.926, 116.435, "island"),
        ("建国门",   39.909, 116.436, "island"),
        ("北京站",   39.904, 116.428, "island"),
        ("崇文门",   39.901, 116.418, "island"),
        ("前门",     39.900, 116.398, "island"),
        ("和平门",   39.900, 116.384, "island"),
        ("宣武门",   39.899, 116.376, "island"),
        ("长椿街",   39.900, 116.364, "island"),
        ("复兴门",   39.908, 116.357, "island"),
        ("阜成门",   39.923, 116.356, "island"),
        ("车公庄",   39.932, 116.355, "island"),
    ])

    # ═══════════════════════════════════════════
    # 北京地铁 3号线（东四十条 → 东坝北，10站）
    # ═══════════════════════════════════════════
    add_line("3号线", [
        ("东四十条",   39.934, 116.433, "island"),
        ("工人体育场", 39.938, 116.445, "island"),
        ("团结湖",     39.936, 116.461, "island"),
        ("朝阳公园",   39.938, 116.475, "island"),
        ("石佛营",     39.940, 116.490, "side"),
        ("北京朝阳站", 39.942, 116.505, "island"),
        ("姚家园",     39.944, 116.520, "side"),
        ("东坝南",     39.950, 116.540, "island"),
        ("东坝",       39.955, 116.555, "island"),
        ("东坝北",     39.960, 116.570, "side"),
    ])

    # ═══ 换乘关系 ═══
    add_transfer("复兴门", "1号线", "2号线", 4)
    add_transfer("建国门", "1号线", "2号线", 5)
    add_transfer("东四十条", "2号线", "3号线", 5)

    # ═══ 北京地铁阶梯票价 ═══
    conn.executemany(
        "INSERT OR IGNORE INTO fare_rules (start_km, end_km, price) VALUES (?, ?, ?)",
        [(0,6,3),(6,12,4),(12,22,5),(22,32,6),(32,52,7),(52,72,8),(72,92,9),(92,999,10)],
    )

    # ═══ 站内设施（换乘大站+热门站） ═══
    add_facilities([
        ("复兴门","1号线","restroom","B1","站厅层中部"),
        ("复兴门","1号线","accessible_elevator","B1","换乘通道南侧"),
        ("复兴门","1号线","nursing_room","B1","无障碍卫生间旁"),
        ("西单","1号线","restroom","B1","站厅层东侧"),
        ("西单","1号线","accessible_elevator","B1","F口附近"),
        ("西单","1号线","nursing_room","B1","站厅层中部"),
        ("天安门东","1号线","restroom","B1","站厅层中部"),
        ("天安门东","1号线","accessible_elevator","B1","B口附近"),
        ("王府井","1号线","restroom","B1","站厅层中部"),
        ("建国门","1号线","restroom","B1","站厅层西侧"),
        ("建国门","1号线","accessible_elevator","B1","换乘通道东侧"),
        ("建国门","1号线","nursing_room","B1","站厅层中部"),
        ("国贸","1号线","restroom","B1","C口附近"),
        ("国贸","1号线","accessible_elevator","B1","C口附近"),
        ("国贸","1号线","nursing_room","B1","站厅层中部"),
        ("四惠","1号线","restroom","B1","站厅层西侧"),
        ("西直门","2号线","restroom","B1","站厅层中部"),
        ("西直门","2号线","accessible_elevator","B1","换乘通道北侧"),
        ("西直门","2号线","nursing_room","B1","站厅层中部"),
        ("雍和宫","2号线","restroom","B1","站厅层东侧"),
        ("东直门","2号线","restroom","B1","站厅层中部"),
        ("东直门","2号线","accessible_elevator","B1","E口附近"),
        ("东四十条","2号线","restroom","B1","站厅层中部"),
        ("前门","2号线","restroom","B1","站厅层中部"),
        ("崇文门","2号线","restroom","B1","站厅层西侧"),
        ("宣武门","2号线","restroom","B1","站厅层西侧"),
        ("宣武门","2号线","accessible_elevator","B1","换乘通道南侧"),
        ("团结湖","3号线","restroom","B1","站厅层中部"),
        ("朝阳公园","3号线","restroom","B1","站厅层东侧"),
        ("北京朝阳站","3号线","restroom","B1","换乘大厅"),
        ("北京朝阳站","3号线","accessible_elevator","B1","换乘大厅"),
        ("北京朝阳站","3号线","nursing_room","B1","站厅层中部"),
        ("东坝北","3号线","restroom","B1","站厅层中部"),
    ])

    print("Seed data inserted successfully.")


seed_data()
conn.commit()
conn.close()
print(f"SQLite database initialized at: {DB_PATH}")
