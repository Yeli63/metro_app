"""路径规划与开门提醒 API 路由。"""

from fastapi import APIRouter, Query, Request
from services.raptor_engine import raptor_engine
from services.door_reminder import door_reminder
from middleware.rate_limiter import limiter, PLAN_LIMIT

router = APIRouter()


@router.get("/api/plan")
@limiter.limit(PLAN_LIMIT)
def plan_route(
    request: Request,
    from_: str = Query(..., alias="from", description="起点站名称"),
    to: str = Query(..., description="终点站名称"),
    strategy: str = Query("time", description="排序策略: time | transfers | price"),
):
    result = raptor_engine.find_path(from_, to, strategy)
    if "error" in result:
        return {"error": result["error"]}
    return result


@router.get("/api/door")
def door_side(
    line: str = Query(..., description="线路名称"),
    station: str = Query(..., description="站名"),
    direction: str = Query(..., description="行驶方向: up | down"),
):
    result = door_reminder.get_door_side(line, station, direction)
    if result is None:
        return {"error": "站点不存在"}
    return result
