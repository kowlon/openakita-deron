"""
Token 使用统计 API 端点。

GET  /api/stats/tokens/summary   — 按维度汇总统计
GET  /api/stats/tokens/timeline  — 图表用时间序列
GET  /api/stats/tokens/sessions  — 按会话拆分
GET  /api/stats/tokens/total     — 总计
GET  /api/stats/tokens/context   — 当前上下文大小与上限
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Query, Request

from openakita.storage.database import Database
from openakita.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stats/tokens", tags=["token_stats"])

_db_instance: Database | None = None


async def _get_db() -> Database | None:
    """延迟初始化用于统计查询的共享 Database 实例。"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
        await _db_instance.connect()
    return _db_instance


def _parse_range(
    start: str | None,
    end: str | None,
    period: str | None,
) -> tuple[datetime, datetime]:
    """根据显式起止时间或预设周期解析时间范围。"""
    now = datetime.now()
    if start and end:
        return datetime.fromisoformat(start), datetime.fromisoformat(end)

    delta_map = {
        "1d": timedelta(days=1),
        "3d": timedelta(days=3),
        "1w": timedelta(weeks=1),
        "1m": timedelta(days=30),
        "6m": timedelta(days=180),
        "1y": timedelta(days=365),
    }
    delta = delta_map.get(period or "1d", timedelta(days=1))
    return now - delta, now


@router.get("/summary")
async def summary(
    request: Request,
    group_by: str = Query("endpoint_name"),
    period: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    endpoint_name: str | None = Query(None),
    operation_type: str | None = Query(None),
):
    db = await _get_db()
    if db is None:
        return {"error": "database not available"}
    start_dt, end_dt = _parse_range(start, end, period)
    rows = await db.get_token_usage_summary(
        start_time=start_dt,
        end_time=end_dt,
        group_by=group_by,
        endpoint_name=endpoint_name,
        operation_type=operation_type,
    )
    return {"start": start_dt.isoformat(), "end": end_dt.isoformat(), "group_by": group_by, "data": rows}


@router.get("/timeline")
async def timeline(
    request: Request,
    interval: str = Query("hour"),
    period: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    endpoint_name: str | None = Query(None),
):
    db = await _get_db()
    if db is None:
        return {"error": "database not available"}
    start_dt, end_dt = _parse_range(start, end, period)
    rows = await db.get_token_usage_timeline(
        start_time=start_dt,
        end_time=end_dt,
        interval=interval,
        endpoint_name=endpoint_name,
    )
    return {"start": start_dt.isoformat(), "end": end_dt.isoformat(), "interval": interval, "data": rows}


@router.get("/sessions")
async def sessions(
    request: Request,
    period: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
):
    db = await _get_db()
    if db is None:
        return {"error": "database not available"}
    start_dt, end_dt = _parse_range(start, end, period)
    rows = await db.get_token_usage_sessions(
        start_time=start_dt, end_time=end_dt, limit=limit, offset=offset
    )
    return {"start": start_dt.isoformat(), "end": end_dt.isoformat(), "data": rows}


@router.get("/total")
async def total(
    request: Request,
    period: str | None = Query(None),
    start: str | None = Query(None),
    end: str | None = Query(None),
):
    db = await _get_db()
    if db is None:
        return {"error": "database not available"}
    start_dt, end_dt = _parse_range(start, end, period)
    row = await db.get_token_usage_total(start_time=start_dt, end_time=end_dt)
    return {"start": start_dt.isoformat(), "end": end_dt.isoformat(), "data": row}


@router.get("/context")
async def context(request: Request):
    """返回当前会话的上下文 token 使用量与上限。"""
    agent = getattr(request.app.state, "agent", None)
    actual = getattr(agent, "_local_agent", agent) if agent else None
    if actual is None:
        return {"error": "agent not available"}

    try:
        re = getattr(actual, "reasoning_engine", None)
        ctx_mgr = getattr(actual, "context_manager", None) or getattr(re, "_context_manager", None)
        if ctx_mgr and hasattr(ctx_mgr, "get_max_context_tokens"):
            max_ctx = ctx_mgr.get_max_context_tokens()
            messages = getattr(re, "_last_working_messages", None) or getattr(
                getattr(actual, "_context", None), "messages", []
            )
            cur_ctx = ctx_mgr.estimate_messages_tokens(messages) if messages else 0
            return {
                "context_tokens": cur_ctx,
                "context_limit": max_ctx,
                "percent": round(cur_ctx / max_ctx * 100, 1) if max_ctx else 0,
            }
    except Exception as e:
        logger.warning(f"[TokenStats] Failed to get context size: {e}")

    return {"context_tokens": 0, "context_limit": 0, "percent": 0}
