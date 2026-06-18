"""批量构建完整北京地铁网络。

使用近似坐标（基于关键站推算），纯本地计算，秒级完成。
"""

import sqlite3
import math
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

DB_PATH = os.environ.get("SQLITE_PATH", "./data/metro_network.sqlite")
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

SPEED_KPH = 35


def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


# 关键站精确坐标（手动录入锚点）
ANCHORS = {
    "苹果园": (39.926, 116.178), "环球度假区": (39.880, 116.725),
    "西直门": (39.940, 116.355), "车公庄": (39.932, 116.355),
    "建国门": (39.909, 116.436), "复兴门": (39.908, 116.357),
    "国贸": (39.909, 116.461), "东单": (39.915, 116.422),
    "西单": (39.913, 116.374), "东直门": (39.941, 116.435),
    "海淀黄庄": (39.976, 116.319), "天安门东": (39.914, 116.401),
    "北京南站": (39.865, 116.379), "宋家庄": (39.846, 116.428),
    "天通苑北": (40.073, 116.413), "巴沟": (39.974, 116.294),
    "公主坟": (39.908, 116.310), "三元桥": (39.962, 116.457),
    "知春路": (39.977, 116.343), "草桥": (39.845, 116.371),
    "十里河": (39.867, 116.463), "新宫": (39.813, 116.372),
    "郭公庄": (39.815, 116.300), "朱辛庄": (40.098, 116.329),
    "霍营": (40.067, 116.365), "望京": (39.997, 116.479),
    "北京西站": (39.895, 116.322), "国家图书馆": (39.960, 116.327),
    "花庄": (39.886, 116.710), "土桥": (39.897, 116.694),
    "俸伯": (40.133, 116.699), "阎村东": (39.736, 116.112),
    "大兴机场": (39.520, 116.413), "香山": (39.997, 116.196),
    "昌平西山口": (40.254, 116.218), "亦庄火车站": (39.790, 116.593),
    # 补充锚点（提高坐标精度）
    "丰台东大街": (39.858, 116.297), "惠新西街北口": (39.988, 116.417),
    "惠新西街南口": (39.978, 116.417), "和平西桥": (39.969, 116.418),
    "大屯路东": (40.004, 116.417), "天坛东门": (39.884, 116.421),
    "磁器口": (39.895, 116.410), "灯市口": (39.918, 116.415),
    "张自忠路": (39.934, 116.416), "和平里北街": (39.959, 116.418),
    "泥洼": (39.855, 116.305), "莲花桥": (39.898, 116.313),
    "火器营": (39.965, 116.286), "长春桥": (39.959, 116.296),
    "车道沟": (39.950, 116.303), "慈寿寺": (39.934, 116.307),
    "西钓鱼台": (39.922, 116.308), "健德门": (39.977, 116.383),
    "北土城": (39.978, 116.397), "安贞门": (39.978, 116.406),
    "牡丹园": (39.975, 116.372), "西土城": (39.977, 116.357),
}


def estimate_coords(name, line_name, idx, total):
    """估算站坐标：用锚点插值或根据线路位置推算。"""
    if name in ANCHORS:
        return ANCHORS[name]

    # 同一线路上找到最近的锚点
    best = None
    for aname, coords in ANCHORS.items():
        if best is None:
            best = coords
    # 没有精确锚点=用线路前缀估算
    lng = 116.300 + (hash(line_name + name) % 200) * 0.003
    lat = 39.850 + (hash(name + line_name) % 150) * 0.002
    return (lat, lng)


def interpolate_coords(line_name, station_names):
    """为一条线路上的所有站点分配坐标（沿路径均匀分布+关键站锚定）。"""
    coords = []
    # 先收集锚点位置
    anchor_indices = {}
    for i, name in enumerate(station_names):
        if name in ANCHORS:
            anchor_indices[i] = ANCHORS[name]

    if not anchor_indices:
        # 全无锚点：粗略估算
        base_lng = 116.300 + hash(line_name) % 100 * 0.004
        base_lat = 39.900 + (hash(line_name) % 50) * 0.001
        return [(base_lat + i * 0.001, base_lng + i * 0.008) for i in range(len(station_names))]

    # 有锚点：锚点之间线性插值
    result = [None] * len(station_names)
    for idx, coords in anchor_indices.items():
        result[idx] = coords

    sorted_anchors = sorted(anchor_indices.keys())

    # 插值锚点之间
    for ai in range(len(sorted_anchors) - 1):
        a1 = sorted_anchors[ai]
        a2 = sorted_anchors[ai + 1]
        lat1, lng1 = result[a1]
        lat2, lng2 = result[a2]
        for j in range(a1 + 1, a2):
            frac = (j - a1) / (a2 - a1)
            result[j] = (lat1 + (lat2 - lat1) * frac, lng1 + (lng2 - lng1) * frac)

    # 首尾延伸
    first = sorted_anchors[0]
    last = sorted_anchors[-1]
    for j in range(0, first):
        result[j] = (result[first][0] + (j - first) * 0.002, result[first][1] + (j - first) * 0.005)
    for j in range(last + 1, len(station_names)):
        result[j] = (result[last][0] + (j - last) * 0.002, result[last][1] + (j - last) * 0.005)

    return result


# ═══════════════════════════════════════════════════
# 北京地铁全部运营线路
# ═══════════════════════════════════════════════════

ALL_LINES = {

"1号线": [
    "苹果园","古城","八角游乐园","八宝山","玉泉路","五棵松","万寿路","公主坟",
    "军事博物馆","木樨地","南礼士路","复兴门","西单","天安门西","天安门东",
    "王府井","东单","建国门","永安里","国贸","大望路","四惠","四惠东",
    "高碑店","传媒大学","双桥","管庄","八里桥","通州北苑","果园","九棵树",
    "梨园","临河里","土桥","花庄","环球度假区",
],

"2号线": [
    "西直门","积水潭","鼓楼大街","安定门","雍和宫","东直门","东四十条",
    "朝阳门","建国门","北京站","崇文门","前门","和平门","宣武门","长椿街",
    "复兴门","阜成门","车公庄",
],

"3号线": [
    "东四十条","工人体育场","团结湖","朝阳公园","石佛营","北京朝阳站",
    "姚家园","东坝南","东坝","东坝北",
],

"4号线": [
    "安河桥北","北宫门","西苑","圆明园","北京大学东门","中关村","海淀黄庄",
    "人民大学","魏公村","国家图书馆","动物园","西直门","新街口","平安里",
    "西四","灵境胡同","西单","宣武门","菜市口","陶然亭","北京南站",
    "马家堡","角门西","公益西桥","新宫","西红门","高米店北","高米店南",
    "枣园","清源路","黄村西大街","黄村火车站","义和庄","生物医药基地","天宫院",
],

"5号线": [
    "天通苑北","天通苑","天通苑南","立水桥","立水桥南","北苑路北",
    "大屯路东","惠新西街北口","惠新西街南口","和平西桥","和平里北街",
    "雍和宫","北新桥","张自忠路","东四","灯市口","东单","崇文门",
    "磁器口","天坛东门","蒲黄榆","刘家窑","宋家庄",
],

"6号线": [
    "金安桥","苹果园","杨庄","西黄村","廖公庄","田村","海淀五路居",
    "慈寿寺","花园桥","白石桥南","车公庄西","车公庄","平安里","北海北",
    "南锣鼓巷","东四","朝阳门","东大桥","呼家楼","金台路","十里堡",
    "青年路","褡裢坡","黄渠","常营","草房","物资学院路","通州北关",
    "北运河西","北运河东","郝家府","东夏园","潞城",
],

"7号线": [
    "北京西站","湾子","达官营","广安门内","菜市口","虎坊桥","珠市口",
    "桥湾","磁器口","广渠门内","广渠门外","双井","九龙山","大郊亭",
    "百子湾","化工","南楼梓庄","欢乐谷景区","垡头","双合","焦化厂",
    "黄厂","郎辛庄","黑庄户","万盛西","万盛东","群芳","高楼金","花庄","环球度假区",
],

"8号线": [
    "朱辛庄","育知路","平西府","回龙观东大街","霍营","育新","西小口",
    "永泰庄","林萃桥","森林公园南门","奥林匹克公园","奥体中心","安华桥",
    "安德里北街","鼓楼大街","什刹海","南锣鼓巷","中国美术馆","金鱼胡同",
    "王府井","前门","珠市口","天桥","永定门外","木樨园","海户屯",
    "大红门南","和义","东高地","火箭万源","五福堂","德茂","瀛海",
],

"9号线": [
    "国家图书馆","白石桥南","白堆子","军事博物馆","北京西站","六里桥东",
    "六里桥","七里庄","丰台东大街","丰台南路","科怡路","丰台科技园","郭公庄",
],

"10号线": [
    "巴沟","火器营","长春桥","车道沟","慈寿寺","西钓鱼台","公主坟",
    "莲花桥","六里桥","西局","泥洼","丰台站","首经贸","纪家庙","草桥",
    "角门西","角门东","大红门","石榴庄","宋家庄","成寿寺","分钟寺",
    "十里河","潘家园","劲松","双井","国贸","金台夕照","呼家楼","团结湖",
    "农业展览馆","亮马桥","三元桥","太阳宫","芍药居","惠新西街南口",
    "安贞门","北土城","健德门","牡丹园","西土城","知春路","知春里",
    "海淀黄庄","苏州街",
],

"13号线": [
    "西直门","大钟寺","知春路","五道口","上地","清河站","西二旗",
    "龙泽","回龙观","霍营","立水桥","北苑","望京西","芍药居","光熙门",
    "柳芳","东直门",
],

"14号线": [
    "张郭庄","园博园","大瓦窑","郭庄子","大井","七里庄","西局",
    "东管头","丽泽商务区","菜户营","西铁营","景风门","北京南站","陶然桥",
    "永定门外","景泰","蒲黄榆","方庄","十里河","北工大西门","平乐园",
    "九龙山","大望路","红庙","金台路","朝阳公园","枣营","东风北桥",
    "将台","望京南","阜通","望京","东湖渠","来广营","善各庄",
],

"15号线": [
    "清华东路西口","六道口","北沙滩","奥林匹克公园","安立路","大屯路东",
    "关庄","望京西","望京","望京东","崔各庄","马泉营","孙河","国展",
    "花梨坎","后沙峪","南法信","石门","顺义","俸伯",
],

"16号线": [
    "北安河","温阳路","稻香湖路","屯佃","永丰","永丰南","西北旺",
    "马连洼","农大南路","西苑","万泉河桥","苏州街","苏州桥","万寿寺",
    "国家图书馆","甘家口","玉渊潭东门","木樨地","达官营","红莲南路",
    "丽泽商务区","东管头南","丰台站","丰台南路","富丰桥","看丹","榆树庄",
],

"19号线": [
    "牡丹园","北太平庄","积水潭","平安里","太平桥","牛街","景风门",
    "草桥","新发地","新宫",
],

"昌平线": [
    "昌平西山口","十三陵景区","昌平","昌平东关","北邵洼","南邵",
    "沙河高教园","沙河","巩华城","朱辛庄","生命科学园","西二旗",
    "清河站","朱房北","小营桥","学知园","六道口","学院桥","西土城","蓟门桥",
],

"房山线": [
    "东管头南","首经贸","花乡东桥","白盆窑","郭公庄","大葆台","稻田",
    "长阳","篱笆房","广阳城","良乡大学城北","良乡大学城","良乡大学城西",
    "良乡南关","苏庄","阎村东",
],

"亦庄线": [
    "宋家庄","肖村","小红门","旧宫","亦庄桥","亦庄文化园","万源街",
    "荣京东街","荣昌东街","同济南路","经海路","次渠南","次渠","亦庄火车站",
],

"S1线": [
    "苹果园","金安桥","四道桥","桥户营","上岸","栗园庄","小园","石厂",
],

"首都机场线": [
    "北新桥","东直门","三元桥","3号航站楼","2号航站楼",
],

"大兴机场线": [
    "草桥","大兴新城","大兴机场",
],

"燕房线": [
    "阎村东","紫草坞","阎村","星城","大石河东","马各庄","饶乐府","房山城关","燕山",
],

"西郊线": [
    "巴沟","颐和园西门","茶棚","万安","国家植物园","香山",
],

}

# ═══════════════════════════════════════════════════
# 换乘关系定义（只需站名，自动匹配线路）
# ═══════════════════════════════════════════════════

TRANSFER_STATIONS = {
    "复兴门": ["1号线","2号线"],
    "建国门": ["1号线","2号线"],
    "东单": ["1号线","5号线"],
    "国贸": ["1号线","10号线"],
    "大望路": ["1号线","14号线"],
    "公主坟": ["1号线","10号线"],
    "军事博物馆": ["1号线","9号线"],
    "四惠": ["1号线","八通线"],
    "四惠东": ["1号线","八通线"],
    "王府井": ["1号线","8号线"],
    "西单": ["1号线","4号线"],
    "苹果园": ["1号线","6号线","S1线"],
    "环球度假区": ["1号线","7号线"],
    "花庄": ["1号线","7号线"],
    "东四十条": ["2号线","3号线"],
    "雍和宫": ["2号线","5号线"],
    "崇文门": ["2号线","5号线"],
    "东直门": ["2号线","13号线","首都机场线"],
    "鼓楼大街": ["2号线","8号线"],
    "前门": ["2号线","8号线"],
    "朝阳门": ["2号线","6号线"],
    "车公庄": ["2号线","6号线"],
    "宣武门": ["2号线","4号线"],
    "积水潭": ["2号线","19号线"],
    "西直门": ["2号线","4号线","13号线"],
    "国家图书馆": ["4号线","9号线","16号线"],
    "海淀黄庄": ["4号线","10号线"],
    "角门西": ["4号线","10号线"],
    "北京南站": ["4号线","14号线"],
    "平安里": ["4号线","6号线","19号线"],
    "菜市口": ["4号线","7号线"],
    "西苑": ["4号线","16号线"],
    "新宫": ["4号线","19号线"],
    "惠新西街南口": ["5号线","10号线"],
    "大屯路东": ["5号线","15号线"],
    "立水桥": ["5号线","13号线"],
    "宋家庄": ["5号线","10号线","亦庄线"],
    "东四": ["5号线","6号线"],
    "磁器口": ["5号线","7号线"],
    "北新桥": ["5号线","首都机场线"],
    "慈寿寺": ["6号线","10号线"],
    "呼家楼": ["6号线","10号线"],
    "南锣鼓巷": ["6号线","8号线"],
    "白石桥南": ["6号线","9号线"],
    "金安桥": ["6号线","S1线"],
    "金台路": ["6号线","14号线"],
    "珠市口": ["7号线","8号线"],
    "双井": ["7号线","10号线"],
    "九龙山": ["7号线","14号线"],
    "北京西站": ["7号线","9号线"],
    "奥林匹克公园": ["8号线","15号线"],
    "永定门外": ["8号线","14号线"],
    "朱辛庄": ["8号线","昌平线"],
    "霍营": ["8号线","13号线"],
    "六里桥": ["9号线","10号线"],
    "郭公庄": ["9号线","房山线"],
    "七里庄": ["9号线","14号线"],
    "知春路": ["10号线","13号线"],
    "芍药居": ["10号线","13号线"],
    "三元桥": ["10号线","首都机场线"],
    "西土城": ["10号线","昌平线"],
    "六道口": ["15号线","昌平线"],
    "望京西": ["13号线","15号线"],
    "望京": ["14号线","15号线"],
    "西局": ["10号线","14号线"],
    "十里河": ["10号线","14号线","17号线"],
    "草桥": ["10号线","19号线","大兴机场线"],
    "牡丹园": ["10号线","19号线"],
    "景风门": ["14号线","19号线"],
    "丰台站": ["10号线","16号线"],
    "丰台南路": ["9号线","16号线"],
    "苏州街": ["10号线","16号线"],
    "达官营": ["7号线","16号线"],
    "西二旗": ["13号线","昌平线"],
    "首经贸": ["10号线","房山线"],
    "东管头南": ["14号线","房山线"],
    "阎村东": ["房山线","燕房线"],
    "巴沟": ["10号线","西郊线"],
}


def build():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # 复用 init_sqlite.py 的建表
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS stations (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, line TEXT NOT NULL,
            lat REAL, lng REAL, platform_type TEXT DEFAULT 'island'
        );
        CREATE TABLE IF NOT EXISTS edges (
            from_station TEXT NOT NULL, to_station TEXT NOT NULL,
            line TEXT NOT NULL, direction TEXT NOT NULL CHECK(direction IN ('up','down')),
            travel_time INT NOT NULL, distance_km REAL,
            PRIMARY KEY (from_station, to_station, line)
        );
        CREATE TABLE IF NOT EXISTS transfers (
            station_id TEXT NOT NULL, from_line TEXT NOT NULL,
            to_line TEXT NOT NULL, walk_time INT DEFAULT 5, is_cross_platform INT DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS fare_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT, city TEXT DEFAULT 'default',
            fare_type TEXT CHECK(fare_type IN ('distance','section')),
            start_km REAL, end_km REAL, price REAL
        );
        CREATE TABLE IF NOT EXISTS facilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT, station_name TEXT NOT NULL,
            line TEXT NOT NULL,
            facility_type TEXT NOT NULL CHECK(facility_type IN ('restroom','accessible_restroom','nursing_room','accessible_elevator','elevator','escalator','ticket_machine','service_center')),
            floor TEXT DEFAULT '', location_desc TEXT DEFAULT '', source TEXT DEFAULT 'manual'
        );
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_phone TEXT NOT NULL,
            fav_type TEXT NOT NULL CHECK(fav_type IN ('route','station')),
            from_name TEXT DEFAULT '',
            to_name TEXT DEFAULT '',
            station_name TEXT DEFAULT '',
            lines TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    sid_map = {}  # (name, line) → station_id
    total_stations = 0

    for line_name, station_names in ALL_LINES.items():
        print(f"  处理 {line_name} ({len(station_names)}站)...", end=" ", flush=True)
        ids = []

        # 用锚点插值估算整条线的坐标
        est_coords = interpolate_coords(line_name, station_names)

        for i, name in enumerate(station_names):
            sid = f"{line_name}_{i+1:03d}"
            ids.append(sid)
            sid_map[(name, line_name)] = sid
            lat, lng = est_coords[i]
            conn.execute(
                "INSERT OR REPLACE INTO stations (id, name, line, lat, lng, platform_type) VALUES (?,?,?,?,?,?)",
                (sid, name, line_name, lat, lng, "island"),
            )
            total_stations += 1

        # 生成边
        for i in range(len(ids) - 1):
            s1 = conn.execute("SELECT lat,lng FROM stations WHERE id=?", (ids[i],)).fetchone()
            s2 = conn.execute("SELECT lat,lng FROM stations WHERE id=?", (ids[i+1],)).fetchone()
            if s1 and s2:
                dist = round(haversine_km(s1[0], s1[1], s2[0], s2[1]), 2)
                t = max(1, round(dist / SPEED_KPH * 60))
                conn.execute(
                    "INSERT OR REPLACE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?,?,?,?,?,?)",
                    (ids[i], ids[i+1], line_name, "up", t, dist),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?,?,?,?,?,?)",
                    (ids[i+1], ids[i], line_name, "down", t, dist),
                )
        # 环线闭合（2号线、10号线）
        if line_name in ("2号线", "10号线") and len(ids) > 1:
            s1 = conn.execute("SELECT lat,lng FROM stations WHERE id=?", (ids[-1],)).fetchone()
            s2 = conn.execute("SELECT lat,lng FROM stations WHERE id=?", (ids[0],)).fetchone()
            if s1 and s2:
                dist = round(haversine_km(s1[0], s1[1], s2[0], s2[1]), 2)
                t = max(1, round(dist / SPEED_KPH * 60))
                conn.execute(
                    "INSERT OR REPLACE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?,?,?,?,?,?)",
                    (ids[-1], ids[0], line_name, "up", t, dist),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO edges (from_station, to_station, line, direction, travel_time, distance_km) VALUES (?,?,?,?,?,?)",
                    (ids[0], ids[-1], line_name, "down", t, dist),
                )

        print(f"OK")

    # 生成换乘关系
    print("  生成换乘关系...")
    transfer_count = 0
    for name, lines in TRANSFER_STATIONS.items():
        for i in range(len(lines)):
            for j in range(len(lines)):
                if i == j:
                    continue
                a = sid_map.get((name, lines[i]))
                b = sid_map.get((name, lines[j]))
                if a and b:
                    conn.execute(
                        "INSERT OR IGNORE INTO transfers (station_id, from_line, to_line, walk_time, is_cross_platform) VALUES (?,?,?,?,?)",
                        (a, lines[i], lines[j], 5, 0),
                    )
                    transfer_count += 1

    # 票价规则
    conn.executemany(
        "INSERT OR IGNORE INTO fare_rules (start_km, end_km, price) VALUES (?,?,?)",
        [(0,6,3),(6,12,4),(12,22,5),(22,32,6),(32,52,7),(52,72,8),(72,92,9),(92,999,10)],
    )

    # ═══ 站内设施种子数据（换乘大站+热门站） ═══
    print("  填充设施数据...")
    conn.executemany(
        "INSERT OR IGNORE INTO facilities (station_name, line, facility_type, floor, location_desc) VALUES (?,?,?,?,?)",
        [
            ("复兴门","1号线","restroom","B1","站厅层中部"),
            ("复兴门","1号线","accessible_elevator","B1","换乘通道南侧"),
            ("复兴门","1号线","nursing_room","B1","无障碍卫生间旁"),
            ("建国门","1号线","restroom","B1","站厅层西侧"),
            ("建国门","1号线","accessible_elevator","B1","换乘通道东侧"),
            ("建国门","1号线","nursing_room","B1","站厅层中部"),
            ("国贸","1号线","restroom","B1","C口附近"),
            ("国贸","1号线","accessible_elevator","B1","C口附近"),
            ("国贸","1号线","nursing_room","B1","站厅层中部"),
            ("西单","1号线","restroom","B1","站厅层东侧"),
            ("西单","1号线","accessible_elevator","B1","F口附近"),
            ("西单","1号线","nursing_room","B1","站厅层中部"),
            ("王府井","1号线","restroom","B1","站厅层中部"),
            ("天安门东","1号线","restroom","B1","站厅层中部"),
            ("天安门东","1号线","accessible_elevator","B1","B口附近"),
            ("四惠","1号线","restroom","B1","站厅层西侧"),
            ("四惠","1号线","accessible_elevator","B1","A口附近"),
            ("公主坟","1号线","restroom","B1","站厅层西侧"),
            ("军事博物馆","1号线","restroom","B1","站厅层中部"),
            ("环球度假区","1号线","restroom","B1","站厅层中部"),
            ("环球度假区","1号线","accessible_elevator","B1","换乘大厅"),
            ("环球度假区","1号线","nursing_room","B1","站厅层中部"),
            ("西直门","2号线","restroom","B1","站厅层中部"),
            ("西直门","2号线","accessible_elevator","B1","换乘通道北侧"),
            ("西直门","2号线","nursing_room","B1","站厅层中部"),
            ("东直门","2号线","restroom","B1","站厅层中部"),
            ("东直门","2号线","accessible_elevator","B1","E口附近"),
            ("雍和宫","2号线","restroom","B1","站厅层东侧"),
            ("前门","2号线","restroom","B1","站厅层中部"),
            ("北京站","2号线","restroom","B1","站厅层中部"),
            ("北京站","2号线","accessible_elevator","B1","出站大厅"),
            ("北京朝阳站","3号线","restroom","B1","换乘大厅"),
            ("北京朝阳站","3号线","accessible_elevator","B1","换乘大厅"),
            ("北京朝阳站","3号线","nursing_room","B1","站厅层中部"),
            ("宋家庄","5号线","restroom","B1","站厅层中部"),
            ("东单","5号线","restroom","B1","站厅层中部"),
            ("雍和宫","5号线","restroom","B1","站厅层中部"),
            ("惠新西街南口","5号线","restroom","B1","站厅层中部"),
            ("海淀黄庄","10号线","restroom","B1","站厅层中部"),
            ("知春路","10号线","restroom","B1","站厅层中部"),
            ("六里桥","10号线","restroom","B1","站厅层中部"),
            ("北京西站","7号线","restroom","B1","站厅层中部"),
            ("北京西站","7号线","accessible_elevator","B1","换乘大厅"),
            ("北京南站","4号线","restroom","B1","站厅层中部"),
            ("北京南站","4号线","accessible_elevator","B1","换乘大厅北侧"),
            ("北京南站","4号线","nursing_room","B1","站厅层中部"),
            ("丰台东大街","9号线","restroom","B1","站厅层中部"),
            ("惠新西街北口","5号线","restroom","B1","站厅层中部"),
            ("苹果园","1号线","restroom","B1","站厅层中部"),
            ("苹果园","1号线","accessible_elevator","B1","A口附近"),
            ("永泰庄","8号线","restroom","B1","站厅层中部"),
            ("磁器口","5号线","restroom","B1","站厅层中部"),
            ("奥林匹克公园","8号线","restroom","B1","站厅层中部"),
            ("奥林匹克公园","8号线","accessible_elevator","B1","D口附近"),
            ("鼓楼大街","2号线","restroom","B1","站厅层中部"),
            ("什刹海","8号线","restroom","B1","站厅层中部"),
        ],
    )

    conn.commit()
    conn.close()

    # 统计
    conn2 = sqlite3.connect(DB_PATH)
    conn2.row_factory = sqlite3.Row
    st_cnt = conn2.execute("SELECT COUNT(*) as c FROM stations").fetchone()["c"]
    ed_cnt = conn2.execute("SELECT COUNT(*) as c FROM edges").fetchone()["c"]
    tr_cnt = conn2.execute("SELECT COUNT(*) as c FROM transfers").fetchone()["c"]
    lines = conn2.execute("SELECT DISTINCT line FROM stations ORDER BY line").fetchall()
    conn2.close()

    print(f"\n  === 构建完成 ===")
    print(f"  线路: {len(lines)} 条")
    for l in lines:
        cnt = conn2.execute("SELECT COUNT(*) as c FROM stations WHERE line=?", (l["line"],)).fetchone()["c"]
    print(f"  站点: {st_cnt} 个")
    print(f"  边: {ed_cnt} 条")
    print(f"  换乘关系: {transfer_count} 条")
    print(f"  DB路径: {DB_PATH}")


if __name__ == "__main__":
    build()
