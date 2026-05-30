"""地铁智行后端 — FastAPI 入口。"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from config.db import connect_mongo, close_mongo
from routes.plan import router as plan_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    await connect_mongo()
    yield
    # 关闭
    await close_mongo()


app = FastAPI(
    title="地铁智行 API",
    description="RAPTOR 路径规划 + 票价计算服务",
    version="1.0.0",
    lifespan=lifespan,
)

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


@app.get("/health")
def health():
    return {"status": "ok"}
