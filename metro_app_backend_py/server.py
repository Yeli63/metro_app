"""地铁智行后端 — FastAPI 入口。"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

load_dotenv()

from config.db import connect_mongo, close_mongo
from middleware.rate_limiter import limiter
from routes.plan import router as plan_router
from routes.auth import router as auth_router
from routes.favorites import router as fav_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_mongo()
    yield
    await close_mongo()


app = FastAPI(
    title="地铁智行 API",
    description="RAPTOR 路径规划 + 票价计算 + 开门提醒 + 用户认证",
    version="1.0.0",
    lifespan=lifespan,
)

# slowapi
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(plan_router)
app.include_router(auth_router)
app.include_router(fav_router)


@app.get("/health")
def health():
    return {"status": "ok"}


# 前端静态文件（API 路由优先，静态文件兜底）
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "metro_app_frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.environ.get("PORT", 3000)), reload=False)
