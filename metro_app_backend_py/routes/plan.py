"""路径规划 API 路由。

GET /api/plan?from=xx&to=xx&strategy=time
"""

from fastapi import APIRouter, Query
from services.raptor_engine import raptor_engine

router = APIRouter()


@router.get("/api/plan")
def plan_route(
    from_: str = Query(..., alias="from", description="起点站名称"),
    to: str = Query(..., description="终点站名称"),
    strategy: str = Query("time", description="排序策略: time | transfers | price"),
):
    result = raptor_engine.find_path(from_, to, strategy)
    if "error" in result:
        return {"error": result["error"]}
    return result
