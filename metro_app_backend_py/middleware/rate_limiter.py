"""频率限制中间件 — 基于 slowapi，使用内存存储。"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# 各接口限制
LOGIN_LIMIT = "5/minute"
PLAN_LIMIT = "30/minute"
