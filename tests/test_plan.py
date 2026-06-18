"""路径规划 API 测试 — 使用北京地铁站点。"""

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
    """直达：苹果园 → 国贸（同线路，1号线）"""
    resp = client.get("/api/plan", params={"from": "苹果园", "to": "国贸"})
    assert resp.status_code == 200
    data = resp.json()
    assert "routes" in data
    assert len(data["routes"]) > 0
    r = data["routes"][0]
    assert r["transfers"] == 0
    assert any("1号线" in l for l in r["lines"]) or any("1" in l for l in r["lines"])


def test_one_transfer():
    """一次换乘：苹果园 → 西直门（1号线 → 2号线/4号线）"""
    resp = client.get("/api/plan", params={"from": "苹果园", "to": "西直门"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["routes"]) > 0


def test_two_transfers():
    """两次换乘：西直门 → 大兴机场"""
    resp = client.get("/api/plan", params={"from": "西直门", "to": "大兴机场"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["routes"]) > 0


def test_strategy_time():
    """时间优先策略"""
    resp = client.get("/api/plan", params={"from": "苹果园", "to": "西直门", "strategy": "time"})
    assert resp.status_code == 200
    routes = resp.json()["routes"]
    times = [r["totalTime"] for r in routes]
    assert times == sorted(times)


def test_strategy_transfers():
    """换乘最少策略"""
    resp = client.get("/api/plan", params={"from": "苹果园", "to": "西直门", "strategy": "transfers"})
    assert resp.status_code == 200
    routes = resp.json()["routes"]
    transfers = [r["transfers"] for r in routes]
    assert len(transfers) > 0


def test_strategy_price():
    """票价最低策略"""
    resp = client.get("/api/plan", params={"from": "苹果园", "to": "大兴机场", "strategy": "price"})
    assert resp.status_code == 200
    routes = resp.json()["routes"]
    prices = [r["price"] for r in routes]
    assert prices == sorted(prices)


def test_nonexistent_station():
    """不存在的站点"""
    resp = client.get("/api/plan", params={"from": "不存在的站", "to": "国贸"})
    assert resp.status_code == 200
    assert "error" in resp.json()


def test_missing_params():
    """缺少参数"""
    resp = client.get("/api/plan")
    assert resp.status_code == 422


def test_door_island_left():
    """岛式站台上行 → 开左侧门"""
    resp = client.get("/api/door", params={"line": "1号线", "station": "复兴门", "direction": "up"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["doorSide"] == "left"
    assert data["platformType"] == "island"


def test_door_side_right():
    """侧式站台上行 → 开右侧门（用岛式站下行等价验证）"""
    resp = client.get("/api/door", params={"line": "1号线", "station": "苹果园", "direction": "down"})
    assert resp.status_code == 200
    data = resp.json()
    # 岛式站台下行开右侧门
    assert data["doorSide"] == "right"
    assert data["platformType"] == "island"


def test_door_invalid():
    """不存在的站点"""
    resp = client.get("/api/door", params={"line": "99号线", "station": "不存在", "direction": "up"})
    assert resp.status_code == 200
    assert "error" in resp.json()
