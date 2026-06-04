"""认证 API 测试（需要 MongoDB 运行）。"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "metro_app_backend_py"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "metro_app_backend_py"))

from server import app

client = TestClient(app)
TEST_PHONE = "13800138000"
TEST_PASSWORD = "test123456"


@pytest.mark.skip(reason="需要 MongoDB 运行，本地环境可能未安装")
def test_register():
    resp = client.post("/api/auth/register", json={
        "phone": TEST_PHONE,
        "password": TEST_PASSWORD,
    })
    assert resp.status_code in (201, 409)  # 201 成功 或 409 已存在


@pytest.mark.skip(reason="需要 MongoDB 运行")
def test_login():
    resp = client.post("/api/auth/login", json={
        "phone": TEST_PHONE,
        "password": TEST_PASSWORD,
    })
    if resp.status_code == 200:
        data = resp.json()
        assert "token" in data


@pytest.mark.skip(reason="需要 MongoDB 运行")
def test_login_wrong_password():
    resp = client.post("/api/auth/login", json={
        "phone": TEST_PHONE,
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.skip(reason="需要 MongoDB 运行")
def test_me_unauthorized():
    resp = client.get("/api/auth/me")
    assert resp.status_code == 403  # 无 Bearer token


def test_register_invalid_phone():
    """手机号格式错误"""
    resp = client.post("/api/auth/register", json={
        "phone": "12345",
        "password": "123456",
    })
    assert resp.status_code == 422


def test_register_short_password():
    """密码太短"""
    resp = client.post("/api/auth/register", json={
        "phone": "13800138001",
        "password": "12",
    })
    assert resp.status_code == 422
