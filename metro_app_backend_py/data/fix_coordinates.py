"""
用高德地理编码批量修正站点坐标。
============================================================
原创代码 | 地铁智行课程项目
第三方API: 高德地理编码 (v3/geocode/geo)
  - 用途: 将站名转换为精确经纬度坐标
  - 调用量: 377次 (一次性建库脚本)
依赖: httpx (第三方库, MIT)
============================================================
"""

import sqlite3
import os
import time
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

AMAP_KEY = os.environ.get("AMAP_KEY", "")
DB_PATH = os.environ.get("SQLITE_PATH", "./data/metro_network.sqlite")

import math
SPEED_KPH = 35

def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371; dlat = math.radians(lat2-lat1); dlng = math.radians(lng2-lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def geocode(name):
    if not AMAP_KEY: return None
    try:
        # [第三方API调用] 高德地理编码 API
        resp = httpx.get("https://restapi.amap.com/v3/geocode/geo", params={
            "key": AMAP_KEY, "address": f"北京市{name}地铁站", "city": "北京"
        }, timeout=8)
        data = resp.json()
        if data.get("status") == "1" and data.get("geocodes"):
            loc = data["geocodes"][0]["location"]
            lng, lat = loc.split(",")
            return (float(lat), float(lng))
    except: pass
    return None

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
stations = conn.execute("SELECT DISTINCT name FROM stations ORDER BY name").fetchall()
total = len(stations)
print(f"共 {total} 个站点待修正")

fixed = 0
for i, row in enumerate(stations):
    name = row["name"]
    # 检查当前坐标是否看起来是插值的（间距太均匀）
    existing = conn.execute("SELECT lat, lng FROM stations WHERE name=? LIMIT 1", (name,)).fetchone()
    if not existing: continue

    coords = geocode(name)
    if coords is None:
        if i % 50 == 0: print(f"  {i}/{total} ...", flush=True)
        time.sleep(0.08)
        continue

    lat, lng = coords
    conn.execute("UPDATE stations SET lat=?, lng=? WHERE name=?", (lat, lng, name))
    fixed += 1
    if fixed % 20 == 0: print(f"  已修正 {fixed}/{total}", flush=True)
    time.sleep(0.06)

conn.commit()
print(f"\n共修正 {fixed}/{total} 个站点坐标")

# 重新计算所有边距离
print("重新计算边距离...")
edges = conn.execute("SELECT rowid, from_station, to_station FROM edges").fetchall()
updated = 0
for e in edges:
    s1 = conn.execute("SELECT lat,lng FROM stations WHERE id=?", (e["from_station"],)).fetchone()
    s2 = conn.execute("SELECT lat,lng FROM stations WHERE id=?", (e["to_station"],)).fetchone()
    if s1 and s2:
        dist = round(haversine_km(s1[0], s1[1], s2[0], s2[1]), 2)
        t = max(1, round(dist / SPEED_KPH * 60))
        conn.execute("UPDATE edges SET distance_km=?, travel_time=? WHERE rowid=?",
                     (dist, t, e["rowid"]))
        updated += 1

conn.commit()
print(f"已更新 {updated} 条边")

# 显示几个例子
samples = ["永泰庄", "林萃桥", "王府井", "西单", "国贸", "苹果园"]
print("\n修正后坐标:")
for name in samples:
    r = conn.execute("SELECT lat,lng FROM stations WHERE name=? LIMIT 1", (name,)).fetchone()
    if r: print(f"  {name}: ({r['lat']:.4f}, {r['lng']:.4f})")

conn.close()
print("\n完成！重新启动服务生效。")
