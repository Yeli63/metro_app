"""安全测试。"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "metro_app_backend_py"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "metro_app_backend_py"))

from server import app

client = TestClient(app)


def test_sql_injection_plan():
    """SQL 注入尝试 — 参数化查询应防护"""
    resp = client.get("/api/plan", params={"from": "西朗'; DROP TABLE stations; --", "to": "芳村"})
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data or "routes" in data


def test_sql_injection_door():
    """SQL 注入尝试 — 开门查询"""
    resp = client.get("/api/door", params={"line": "' OR 1=1 --", "station": "公园前", "direction": "up"})
    assert resp.status_code == 200
    assert "error" in resp.json()


def test_xss_attempt():
    """XSS 尝试 — 输入应被当作普通字符串处理"""
    resp = client.get("/api/plan", params={"from": "<script>alert('xss')</script>", "to": "芳村"})
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data or "routes" in data


def test_no_token_access():
    """未登录访问 /auth/me 应返回 401"""
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_invalid_token():
    """无效 token 应返回 401"""
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid_token_here"})
    assert resp.status_code == 401


def test_empty_params():
    """空参数测试"""
    resp = client.get("/api/plan", params={"from": "", "to": ""})
    assert resp.status_code in (200, 422)


def test_very_long_input():
    """超长输入 — 不崩溃"""
    long_str = "A" * 1000
    resp = client.get("/api/plan", params={"from": long_str, "to": "芳村"})
    assert resp.status_code in (200, 422)


def test_rate_limit_on_plan():
    """频率限制 — 多次请求规划接口，最终触发 429（放在最后运行避免影响其他测试）"""
    limit_hit = False
    for _ in range(35):
        resp = client.get("/api/plan", params={"from": "西朗", "to": "芳村"})
        if resp.status_code == 429:
            limit_hit = True
            break
    assert limit_hit, "频率限制未生效 — 30次/分钟应触发429"
