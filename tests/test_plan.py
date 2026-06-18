"""路径规划 API 测试 — 基于北京地铁实际路网数据。"""

import os
import sys

# 强制使用本地 RAPTOR 引擎，保证测试结果可复现
os.environ["AMAP_KEY"] = ""

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "metro_app_backend_py"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "metro_app_backend_py"))

from server import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health():
    """健康检查"""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_direct_route():
    """直达：苹果园 → 国贸（同属 1 号线，0 换乘）"""
    resp = client.get("/api/plan", params={"from": "苹果园", "to": "国贸"})
    assert resp.status_code == 200
    data = resp.json()
    assert "routes" in data
    assert len(data["routes"]) > 0
    r = data["routes"][0]
    assert r["transfers"] == 0
    assert any("1号线" in line for line in r["lines"])


def test_one_transfer():
    """一次换乘：古城 → 阜成门（1 号线 → 2 号线，不同线路无共线）"""
    resp = client.get("/api/plan", params={"from": "古城", "to": "阜成门"})
    assert resp.status_code == 200
    data = resp.json()
    assert "routes" in data
    assert len(data["routes"]) > 0
    r = data["routes"][0]
    assert r["transfers"] >= 1
    assert len(r["lines"]) >= 2


def test_two_transfers():
    """两次换乘：古城 → 东坝北（1 号线 → 2 号线 → 3 号线，无共线）"""
    resp = client.get("/api/plan", params={"from": "古城", "to": "东坝北"})
    assert resp.status_code == 200
    data = resp.json()
    assert "routes" in data
    assert len(data["routes"]) > 0
    r = data["routes"][0]
    assert r["transfers"] >= 2
    assert len(r["lines"]) >= 3


def test_strategy_time():
    """时间优先策略 — 返回有效路线且首条为最优"""
    resp = client.get("/api/plan", params={
        "from": "古城", "to": "阜成门", "strategy": "time"
    })
    assert resp.status_code == 200
    routes = resp.json()["routes"]
    assert len(routes) > 0
    r = routes[0]
    assert r["totalTime"] > 0
    assert r["transfers"] >= 1


def test_strategy_transfers():
    """换乘最少策略 — 返回有效路线且换乘数合理"""
    resp = client.get("/api/plan", params={
        "from": "古城", "to": "阜成门", "strategy": "transfers"
    })
    assert resp.status_code == 200
    routes = resp.json()["routes"]
    assert len(routes) > 0
    r = routes[0]
    assert r["transfers"] >= 1
    assert len(r["lines"]) >= 2


def test_strategy_price():
    """票价最低策略 — 返回有效路线且票价合理"""
    resp = client.get("/api/plan", params={
        "from": "古城", "to": "东坝北", "strategy": "price"
    })
    assert resp.status_code == 200
    routes = resp.json()["routes"]
    assert len(routes) > 0
    r = routes[0]
    assert r["price"] >= 3
    assert r["transfers"] >= 2


def test_nonexistent_station():
    """不存在的站点 — 返回错误信息"""
    resp = client.get("/api/plan", params={"from": "不存在的站", "to": "国贸"})
    assert resp.status_code == 200
    assert "error" in resp.json()


def test_missing_params():
    """缺少必要参数 — FastAPI 返回 422"""
    resp = client.get("/api/plan")
    assert resp.status_code == 422


def test_door_island_left():
    """岛式站台上行 → 开左侧门（1 号线复兴门，platform_type=island）"""
    resp = client.get("/api/door", params={
        "line": "1号线", "station": "复兴门", "direction": "up"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["doorSide"] == "left"
    assert data["platformType"] == "island"


def test_door_side_down_right():
    """岛式站台下行 → 开右侧门（岛式站下行等价于侧式站上行）"""
    resp = client.get("/api/door", params={
        "line": "1号线", "station": "苹果园", "direction": "down"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["doorSide"] == "right"
    assert data["platformType"] == "island"


def test_door_invalid():
    """不存在的线路/站点 — 返回错误"""
    resp = client.get("/api/door", params={
        "line": "99号线", "station": "不存在", "direction": "up"
    })
    assert resp.status_code == 200
    assert "error" in resp.json()
