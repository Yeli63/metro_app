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
def seed_data():
    # ═══ 北京地铁 1号线 ═══
    line1_stations = [
        ("line1_001", "苹果园",   "1号线", 39.926, 116.178, "side"),
        ("line1_002", "公主坟",   "1号线", 39.908, 116.310, "island"),
        ("line1_003", "军事博物馆", "1号线", 39.908, 116.327, "island"),
        ("line1_004", "复兴门",   "1号线", 39.908, 116.357, "island"),
        ("line1_005", "西单",     "1号线", 39.913, 116.374, "island"),
        ("line1_006", "天安门东", "1号线", 39.914, 116.401, "island"),
        ("line1_007", "建国门",   "1号线", 39.909, 116.436, "island"),
        ("line1_008", "国贸",     "1号线", 39.909, 116.461, "island"),
        ("line1_009", "四惠",     "1号线", 39.909, 116.496, "side"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO stations (id, name, line, lat, lng, platform_type) VALUES (?, ?, ?, ?, ?, ?)",
        line1_stations,
    )
    for i in range(len(line1_stations) - 1):
        conn.execute(
            "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
            (line1_stations[i][0], line1_stations[i + 1][0], "1号线", "up", 2, 1.3),
        )
        conn.execute(
            "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
            (line1_stations[i + 1][0], line1_stations[i][0], "1号线", "down", 2, 1.3),
        )

    # ═══ 北京地铁 2号线（环线北半圈） ═══
    line2_stations = [
        ("line2_001", "西直门", "2号线", 39.940, 116.355, "island"),
        ("line2_002", "雍和宫", "2号线", 39.948, 116.417, "island"),
        ("line2_003", "东直门", "2号线", 39.941, 116.435, "island"),
        ("line2_004", "建国门", "2号线", 39.909, 116.436, "island"),
        ("line2_005", "前门",   "2号线", 39.900, 116.398, "island"),
        ("line2_006", "宣武门", "2号线", 39.899, 116.376, "island"),
        ("line2_007", "复兴门", "2号线", 39.908, 116.357, "island"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO stations (id, name, line, lat, lng, platform_type) VALUES (?, ?, ?, ?, ?, ?)",
        line2_stations,
    )
    for i in range(len(line2_stations) - 1):
        conn.execute(
            "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
            (line2_stations[i][0], line2_stations[i + 1][0], "2号线", "up", 2, 1.1),
        )
        conn.execute(
            "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
            (line2_stations[i + 1][0], line2_stations[i][0], "2号线", "down", 2, 1.1),
        )

    # ═══ 北京地铁 4号线 ═══
    line4_stations = [
        ("line4_001", "安河桥北",   "4号线", 40.012, 116.272, "island"),
        ("line4_002", "圆明园",     "4号线", 40.000, 116.303, "island"),
        ("line4_003", "海淀黄庄",   "4号线", 39.976, 116.319, "island"),
        ("line4_004", "国家图书馆", "4号线", 39.960, 116.327, "island"),
        ("line4_005", "西直门",     "4号线", 39.940, 116.355, "island"),
        ("line4_006", "西单",       "4号线", 39.913, 116.374, "side"),
        ("line4_007", "宣武门",     "4号线", 39.899, 116.376, "island"),
        ("line4_008", "北京南站",   "4号线", 39.865, 116.379, "side"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO stations (id, name, line, lat, lng, platform_type) VALUES (?, ?, ?, ?, ?, ?)",
        line4_stations,
    )
    for i in range(len(line4_stations) - 1):
        conn.execute(
            "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
            (line4_stations[i][0], line4_stations[i + 1][0], "4号线", "up", 2, 1.6),
        )
        conn.execute(
            "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
            (line4_stations[i + 1][0], line4_stations[i][0], "4号线", "down", 2, 1.6),
        )

    # ═══ 换乘关系 ═══
    transfer_list = [
        # 复兴门 1↔2
        ("line1_004", "1号线", "2号线", 4, 0),
        ("line2_007", "2号线", "1号线", 4, 0),
        # 建国门 1↔2
        ("line1_007", "1号线", "2号线", 5, 0),
        ("line2_004", "2号线", "1号线", 5, 0),
        # 西单 1↔4
        ("line1_005", "1号线", "4号线", 3, 0),
        ("line4_006", "4号线", "1号线", 3, 0),
        # 西直门 2↔4
        ("line2_001", "2号线", "4号线", 5, 0),
        ("line4_005", "4号线", "2号线", 5, 0),
        # 宣武门 2↔4
        ("line2_006", "2号线", "4号线", 4, 0),
        ("line4_007", "4号线", "2号线", 4, 0),
    ]
    for t in transfer_list:
        conn.execute(
            "INSERT OR IGNORE INTO transfers (station_id, from_line, to_line, walk_time, is_cross_platform) VALUES (?, ?, ?, ?, ?)",
            t,
        )

    # ═══ 北京地铁阶梯票价 ═══
    fare_rules = [
        (0, 6, 3),
        (6, 12, 4),
        (12, 22, 5),
        (22, 32, 6),
        (32, 52, 7),
        (52, 72, 8),
        (72, 92, 9),
        (92, 999, 10),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO fare_rules (start_km, end_km, price) VALUES (?, ?, ?)",
        fare_rules,
    )

    # ═══ 站内设施数据 ═══
    # 每个站至少录入卫生间，换乘大站补充更多设施
    facility_data = [
        # 1号线
        ("苹果园", "1号线", "restroom", "B1", "站厅层中部"),
        ("苹果园", "1号线", "accessible_elevator", "B1", "A口附近"),
        ("公主坟", "1号线", "restroom", "B1", "站厅层西侧"),
        ("军事博物馆", "1号线", "restroom", "B1", "站厅层中部"),
        ("军事博物馆", "1号线", "accessible_elevator", "B1", "B口附近"),
        ("复兴门", "1号线", "restroom", "B1", "站厅层中部"),
        ("复兴门", "1号线", "accessible_elevator", "B1", "换乘通道南侧"),
        ("复兴门", "1号线", "nursing_room", "B1", "无障碍卫生间旁"),
        ("西单", "1号线", "restroom", "B1", "站厅层东侧"),
        ("西单", "1号线", "accessible_elevator", "B1", "F口附近"),
        ("西单", "1号线", "nursing_room", "B1", "站厅层中部"),
        ("天安门东", "1号线", "restroom", "B1", "站厅层中部"),
        ("天安门东", "1号线", "accessible_elevator", "B1", "B口附近"),
        ("建国门", "1号线", "restroom", "B1", "站厅层西侧"),
        ("建国门", "1号线", "accessible_elevator", "B1", "换乘通道东侧"),
        ("建国门", "1号线", "nursing_room", "B1", "站厅层中部"),
        ("国贸", "1号线", "restroom", "B1", "站厅层中部"),
        ("国贸", "1号线", "accessible_elevator", "B1", "C口附近"),
        ("国贸", "1号线", "nursing_room", "B1", "站厅层中部"),
        ("四惠", "1号线", "restroom", "B1", "站厅层西侧"),
        ("四惠", "1号线", "accessible_elevator", "B1", "A口附近"),
        # 2号线
        ("西直门", "2号线", "restroom", "B1", "站厅层中部"),
        ("西直门", "2号线", "accessible_elevator", "B1", "换乘通道北侧"),
        ("西直门", "2号线", "nursing_room", "B1", "站厅层中部"),
        ("雍和宫", "2号线", "restroom", "B1", "站厅层东侧"),
        ("东直门", "2号线", "restroom", "B1", "站厅层中部"),
        ("东直门", "2号线", "accessible_elevator", "B1", "E口附近"),
        ("前门", "2号线", "restroom", "B1", "站厅层中部"),
        ("前门", "2号线", "accessible_elevator", "B1", "B口附近"),
        ("宣武门", "2号线", "restroom", "B1", "站厅层西侧"),
        ("宣武门", "2号线", "accessible_elevator", "B1", "换乘通道南侧"),
        # 4号线
        ("安河桥北", "4号线", "restroom", "B1", "站厅层中部"),
        ("圆明园", "4号线", "restroom", "B1", "站厅层东侧"),
        ("海淀黄庄", "4号线", "restroom", "B1", "站厅层中部"),
        ("海淀黄庄", "4号线", "accessible_elevator", "B1", "B口附近"),
        ("国家图书馆", "4号线", "restroom", "B1", "站厅层中部"),
        ("国家图书馆", "4号线", "accessible_elevator", "B1", "D口附近"),
        ("国家图书馆", "4号线", "nursing_room", "B1", "站厅层中部"),
        ("北京南站", "4号线", "restroom", "B1", "站厅层中部"),
        ("北京南站", "4号线", "accessible_elevator", "B1", "换乘大厅北侧"),
        ("北京南站", "4号线", "nursing_room", "B1", "站厅层中部"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO facilities (station_name, line, facility_type, floor, location_desc) VALUES (?, ?, ?, ?, ?)",
        facility_data,
    )

    print("Seed data inserted successfully.")


seed_data()
conn.commit()
conn.close()
print(f"SQLite database initialized at: {DB_PATH}")
