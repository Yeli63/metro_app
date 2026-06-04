"""路径规划 API 测试。"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "metro_app_backend_py"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "metro_app_backend_py"))

from server import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_direct_route():
    """直达：西朗 → 芳村（同线路，1号线）"""
    resp = client.get("/api/plan", params={"from": "西朗", "to": "芳村"})
    assert resp.status_code == 200
    data = resp.json()
    assert "routes" in data
    assert len(data["routes"]) > 0
    r = data["routes"][0]
    assert r["transfers"] == 0
    assert r["totalTime"] == 9
    assert "1号线" in r["lines"]


def test_one_transfer():
    """一次换乘：西朗 → 纪念堂（1号线 → 2号线，公园前换乘）"""
    resp = client.get("/api/plan", params={"from": "西朗", "to": "纪念堂"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["routes"]) > 0
    r = data["routes"][0]
    assert r["transfers"] == 1
    assert "公园前" in str(r["details"]["transfers"])


def test_two_transfers():
    """两次换乘：纪念堂 → 机场北（2号线 → 1号线 → 3号线）"""
    resp = client.get("/api/plan", params={"from": "纪念堂", "to": "机场北"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["routes"]) > 0
    r = data["routes"][0]
    assert r["transfers"] >= 2


def test_strategy_time():
    """时间优先策略"""
    resp = client.get("/api/plan", params={"from": "西朗", "to": "纪念堂", "strategy": "time"})
    assert resp.status_code == 200
    routes = resp.json()["routes"]
    # 应按时间升序
    times = [r["totalTime"] for r in routes]
    assert times == sorted(times)


def test_strategy_transfers():
    """换乘最少策略"""
    resp = client.get("/api/plan", params={"from": "西朗", "to": "纪念堂", "strategy": "transfers"})
    assert resp.status_code == 200
    routes = resp.json()["routes"]
    transfers = [r["transfers"] for r in routes]
    assert transfers == sorted(transfers)


def test_strategy_price():
    """票价最低策略"""
    resp = client.get("/api/plan", params={"from": "西朗", "to": "机场北", "strategy": "price"})
    assert resp.status_code == 200
    routes = resp.json()["routes"]
    prices = [r["price"] for r in routes]
    assert prices == sorted(prices)


def test_nonexistent_station():
    """不存在的站点"""
    resp = client.get("/api/plan", params={"from": "不存在的站", "to": "芳村"})
    assert resp.status_code == 200
    assert "error" in resp.json()


def test_missing_params():
    """缺少参数"""
    resp = client.get("/api/plan")
    assert resp.status_code == 422  # FastAPI 参数校验


def test_door_island_left():
    """岛式站台上行 → 开左侧门"""
    resp = client.get("/api/door", params={"line": "1号线", "station": "公园前", "direction": "up"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["doorSide"] == "left"
    assert data["platformType"] == "island"


def test_door_side_right():
    """侧式站台上行 → 开右侧门"""
    resp = client.get("/api/door", params={"line": "3号线", "station": "机场北", "direction": "up"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["doorSide"] == "right"
    assert data["platformType"] == "side"


def test_door_invalid():
    """不存在的站点"""
    resp = client.get("/api/door", params={"line": "99号线", "station": "不存在", "direction": "up"})
    assert resp.status_code == 200
    assert "error" in resp.json()
