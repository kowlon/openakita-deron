"""
场景管理 API 路由

提供场景的查询和启动等 REST API。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


# ==================== 请求/响应模型 ====================


class ScenarioStepModel(BaseModel):
    """场景步骤模型"""

    step_id: str
    name: str
    description: str = ""
    requires_confirmation: bool = True
    dependencies: list[str] = Field(default_factory=list)


class ScenarioResponse(BaseModel):
    """场景响应"""

    scenario_id: str
    name: str
    description: str = ""
    category: str = "general"
    version: str = "1.0"
    steps: list[ScenarioStepModel]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScenarioListResponse(BaseModel):
    """场景列表响应"""

    scenarios: list[ScenarioResponse]
    total: int


class CategoryListResponse(BaseModel):
    """分类列表响应"""

    categories: list[str]


class StartScenarioRequest(BaseModel):
    """启动场景请求"""

    session_id: Optional[str] = Field(None, description="会话 ID")
    context: dict[str, Any] = Field(default_factory=dict, description="初始上下文")


class StartScenarioResponse(BaseModel):
    """启动场景响应"""

    task_id: str
    scenario_id: str
    status: str


# ==================== API 端点 ====================


@router.get("", response_model=ScenarioListResponse)
async def list_scenarios(
    category: Optional[str] = None,
    http_request: Request = None,
) -> ScenarioListResponse:
    """
    列出所有场景

    可选过滤:
    - category: 按分类过滤
    """
    registry = _get_scenario_registry(http_request)
    if not registry:
        raise HTTPException(status_code=503, detail="ScenarioRegistry not available")

    if category:
        scenarios = registry.list_by_category(category)
    else:
        scenarios = registry.list_all()

    return ScenarioListResponse(
        scenarios=[_scenario_to_response(s) for s in scenarios],
        total=len(scenarios),
    )


@router.get("/categories", response_model=CategoryListResponse)
async def list_categories(http_request: Request) -> CategoryListResponse:
    """列出所有分类"""
    registry = _get_scenario_registry(http_request)
    if not registry:
        raise HTTPException(status_code=503, detail="ScenarioRegistry not available")

    return CategoryListResponse(categories=registry.list_categories())


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(scenario_id: str, http_request: Request) -> ScenarioResponse:
    """获取场景详情"""
    registry = _get_scenario_registry(http_request)
    if not registry:
        raise HTTPException(status_code=503, detail="ScenarioRegistry not available")

    scenario = registry.get(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    return _scenario_to_response(scenario)


@router.post("/{scenario_id}/start", response_model=StartScenarioResponse)
async def start_scenario(
    scenario_id: str,
    request: StartScenarioRequest,
    http_request: Request,
) -> StartScenarioResponse:
    """启动场景任务"""
    orchestrator = _get_orchestrator(http_request)
    if not orchestrator:
        raise HTTPException(status_code=503, detail="TaskOrchestrator not available")

    # 创建任务
    task_session = await orchestrator.create_task_manual(
        scenario_id=scenario_id,
        session_id=request.session_id,
        context=request.context,
    )

    if not task_session:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # 启动任务
    await orchestrator.start_task(task_session.state.task_id)

    return StartScenarioResponse(
        task_id=task_session.state.task_id,
        scenario_id=scenario_id,
        status=task_session.state.status.value,
    )


# ==================== 辅助函数 ====================


def _get_scenario_registry(request: Request):
    """获取 ScenarioRegistry 实例"""
    # 首先尝试从 orchestrator 获取
    orchestrator = getattr(request.app.state, "task_orchestrator", None)
    if orchestrator:
        return orchestrator.scenario_registry

    # 直接从 app.state 获取
    return getattr(request.app.state, "scenario_registry", None)


def _get_orchestrator(request: Request):
    """获取 TaskOrchestrator 实例"""
    return getattr(request.app.state, "task_orchestrator", None)


def _scenario_to_response(scenario) -> ScenarioResponse:
    """将 ScenarioDefinition 转换为响应模型"""
    steps = []
    for step in scenario.steps:
        steps.append(ScenarioStepModel(
            step_id=step.step_id,
            name=step.name,
            description=step.description,
            requires_confirmation=step.requires_confirmation,
            dependencies=step.dependencies,
        ))

    return ScenarioResponse(
        scenario_id=scenario.scenario_id,
        name=scenario.name,
        description=scenario.description,
        category=scenario.category,
        version=scenario.version,
        steps=steps,
        metadata=scenario.metadata,
    )