# 地铁智行

多策略地铁换乘规划、开门提醒与票价计算 — 软件安全工程课程项目。

## 功能

- **多线路换乘规划** — RAPTOR 引擎，支持时间最短 / 换乘最少 / 票价最低三种策略
- **开门方向提醒** — 根据站台类型和行驶方向动态判断开门侧
- **票价计算** — 基于 Haversine 距离的阶梯票价
- **用户认证** — JWT 登录/注册（需要 MongoDB）
- **频率限制** — slowapi 接口级速率控制
- **Web 前端** — 响应式单页应用

## 技术栈

| 层面 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python 3.12+) |
| 数据库 | SQLite (路网) + MongoDB (用户) |
| 前端 | HTML + CSS + JavaScript |
| 安全 | JWT + bcrypt + slowapi + Pydantic |

## 快速开始

```bash
cd metro_app_backend_py

# 1. 安装依赖
pip install -r requirements.txt

# 2. 初始化路网数据库
python data/init_sqlite.py

# 3. 启动服务
python server.py
```

访问 `http://localhost:3000` — 前端页面  
访问 `http://localhost:3000/docs` — Swagger API 文档

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/plan?from=xx&to=xx&strategy=time` | 路径规划 |
| GET | `/api/door?line=xx&station=xx&direction=up` | 开门方向查询 |
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录 |
| GET | `/api/auth/me` | 当前用户信息（需 JWT） |
| GET | `/health` | 健康检查 |

## 运行测试

```bash
pytest tests/ -v
```

## 项目结构

```
metro_app/
├── metro_app_backend_py/     # Python 后端
│   ├── server.py             # FastAPI 入口
│   ├── config/db.py          # MongoDB + SQLite 连接
│   ├── routes/
│   │   ├── plan.py           # 路径规划 + 开门提醒 API
│   │   └── auth.py           # 认证 API
│   ├── services/
│   │   ├── raptor_engine.py  # RAPTOR 路径规划引擎
│   │   ├── fare_calculator.py # 票价计算
│   │   └── door_reminder.py  # 开门方向判断
│   ├── middleware/
│   │   ├── auth.py           # JWT 验证
│   │   └── rate_limiter.py   # 频率限制
│   ├── models/user.py        # 用户模型
│   └── data/init_sqlite.py   # 路网初始化
├── metro_app_frontend/       # Web 前端
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── tests/                    # 测试
│   ├── test_plan.py
│   ├── test_auth.py
│   └── test_security.py
└── security_checklist.md     # 安全威胁应对清单
```
