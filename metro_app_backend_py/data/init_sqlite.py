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
""")

# 插入种子数据
def seed_data():
    # 1号线站点
    line1_stations = [
        ("line1_001", "西朗", "1号线", 23.080, 113.230, "island"),
        ("line1_002", "坑口", "1号线", 23.085, 113.240, "island"),
        ("line1_003", "花地湾", "1号线", 23.090, 113.250, "island"),
        ("line1_004", "芳村", "1号线", 23.100, 113.255, "island"),
        ("line1_005", "黄沙", "1号线", 23.110, 113.260, "island"),
    ]

    conn.executemany(
        "INSERT OR IGNORE INTO stations (id, name, line, lat, lng, platform_type) VALUES (?, ?, ?, ?, ?, ?)",
        line1_stations,
    )

    # 1号线边（上下行）
    for i in range(len(line1_stations) - 1):
        conn.execute(
            "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
            (line1_stations[i][0], line1_stations[i + 1][0], "1号线", "up", 3, 1.2),
        )
        conn.execute(
            "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
            (line1_stations[i + 1][0], line1_stations[i][0], "1号线", "down", 3, 1.2),
        )

    # 2号线站点
    line2_stations = [
        ("line2_001", "公园前", "2号线", 23.125, 113.270, "island"),
        ("line2_002", "纪念堂", "2号线", 23.130, 113.275, "island"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO stations (id, name, line, lat, lng, platform_type) VALUES (?, ?, ?, ?, ?, ?)",
        line2_stations,
    )

    # 2号线边
    conn.execute(
        "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
        ("line2_001", "line2_002", "2号线", "up", 2, 0.9),
    )
    conn.execute(
        "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
        ("line2_002", "line2_001", "2号线", "down", 2, 0.9),
    )

    # 1号线公园前站（用于换乘演示）
    conn.execute(
        "INSERT OR IGNORE INTO stations (id, name, line, lat, lng, platform_type) VALUES (?, ?, ?, ?, ?, ?)",
        ("line1_010", "公园前", "1号线", 23.125, 113.270, "island"),
    )
    # 连接黄沙→公园前（1号线延伸段）
    conn.execute(
        "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
        ("line1_005", "line1_010", "1号线", "up", 2, 0.8),
    )
    conn.execute(
        "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
        ("line1_010", "line1_005", "1号线", "down", 2, 0.8),
    )

    # 换乘关系：公园前（1↔2）
    conn.execute(
        "INSERT OR IGNORE INTO transfers (station_id, from_line, to_line, walk_time, is_cross_platform) VALUES (?, ?, ?, ?, ?)",
        ("line1_010", "1号线", "2号线", 5, 0),
    )
    conn.execute(
        "INSERT OR IGNORE INTO transfers (station_id, from_line, to_line, walk_time, is_cross_platform) VALUES (?, ?, ?, ?, ?)",
        ("line2_001", "2号线", "1号线", 5, 0),
    )

    # ── 1号线延伸：公园前 → 体育西路 ──
    conn.execute(
        "INSERT OR IGNORE INTO stations (id, name, line, lat, lng, platform_type) VALUES (?, ?, ?, ?, ?, ?)",
        ("line1_011", "体育西路", "1号线", 23.132, 113.320, "island"),
    )
    # 公园前 → 体育西路
    conn.execute(
        "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
        ("line1_010", "line1_011", "1号线", "up", 3, 1.5),
    )
    conn.execute(
        "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
        ("line1_011", "line1_010", "1号线", "down", 3, 1.5),
    )

    # ── 3号线：机场北 → 体育西路 ──
    line3_stations = [
        ("line3_001", "机场北", "3号线", 23.392, 113.300, "side"),
        ("line3_002", "嘉禾望岗", "3号线", 23.238, 113.280, "island"),
        ("line3_003", "燕塘", "3号线", 23.160, 113.330, "side"),
        ("line3_004", "广州东站", "3号线", 23.150, 113.325, "island"),
        ("line3_005", "体育西路", "3号线", 23.132, 113.320, "island"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO stations (id, name, line, lat, lng, platform_type) VALUES (?, ?, ?, ?, ?, ?)",
        line3_stations,
    )
    # 3号线边（上下行）
    for i in range(len(line3_stations) - 1):
        conn.execute(
            "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
            (line3_stations[i][0], line3_stations[i + 1][0], "3号线", "up", 3, 2.0 + i * 1.5),
        )
        conn.execute(
            "INSERT OR IGNORE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?, ?, ?, ?, ?, ?)",
            (line3_stations[i + 1][0], line3_stations[i][0], "3号线", "down", 3, 2.0 + i * 1.5),
        )

    # 换乘关系：体育西路（1↔3）
    conn.execute(
        "INSERT OR IGNORE INTO transfers (station_id, from_line, to_line, walk_time, is_cross_platform) VALUES (?, ?, ?, ?, ?)",
        ("line1_011", "1号线", "3号线", 6, 0),
    )
    conn.execute(
        "INSERT OR IGNORE INTO transfers (station_id, from_line, to_line, walk_time, is_cross_platform) VALUES (?, ?, ?, ?, ?)",
        ("line3_005", "3号线", "1号线", 6, 0),
    )

    # 默认阶梯票价（广州地铁）
    fare_rules = [
        (0, 4, 2),
        (4, 8, 3),
        (8, 12, 4),
        (12, 18, 5),
        (18, 24, 6),
        (24, 32, 7),
        (32, 40, 8),
        (40, 999, 9),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO fare_rules (start_km, end_km, price) VALUES (?, ?, ?)",
        fare_rules,
    )

    print("Seed data inserted successfully.")


seed_data()
conn.commit()
conn.close()
print(f"SQLite database initialized at: {DB_PATH}")
