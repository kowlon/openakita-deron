"""
任务管理 API 路由

提供任务的创建、查询、取消等 REST API。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ==================== 请求/响应模型 ====================


class CreateTaskRequest(BaseModel):
    """创建任务请求"""

    scenario_id: Optional[str] = Field(None, description="场景 ID（手动创建时使用）")
    message: Optional[str] = Field(None, description="用户消息（从对话创建时使用）")
    session_id: Optional[str] = Field(None, description="会话 ID")
    context: dict[str, Any] = Field(default_factory=dict, description="初始上下文")


class ConfirmStepRequest(BaseModel):
    """确认步骤请求"""

    step_id: str = Field(..., description="步骤 ID")
    edited_output: Optional[dict[str, Any]] = Field(None, description="编辑后的输出")


class SwitchStepRequest(BaseModel):
    """切换步骤请求"""

    step_id: str = Field(..., description="目标步骤 ID")


class TaskResponse(BaseModel):
    """任务响应"""

    task_id: str
    scenario_id: str
    session_id: Optional[str] = None
    status: str
    current_step_id: Optional[str] = None
    total_steps: int = 0
    completed_steps: int = 0
    progress_percent: float = 0.0
    created_at: str
    context: dict[str, Any] = Field(default_factory=dict)


class TaskListResponse(BaseModel):
    """任务列表响应"""

    tasks: list[TaskResponse]
    total: int


class TaskDetailResponse(BaseModel):
    """任务详情响应"""

    task: TaskResponse
    scenario_name: str
    scenario_description: str
    step_sessions: list[dict[str, Any]]


# ==================== API 端点 ====================


@router.post("", response_model=TaskResponse)
async def create_task(request: CreateTaskRequest, http_request: Request) -> TaskResponse:
    """
    创建任务

    可以通过两种方式创建:
    1. 指定 scenario_id 手动创建
    2. 提供 message 从对话匹配创建
    """
    orchestrator = _get_orchestrator(http_request)
    if not orchestrator:
        raise HTTPException(status_code=503, detail="TaskOrchestrator not available")

    task_session = None

    if request.scenario_id:
        # 手动创建
        task_session = await orchestrator.create_task_manual(
            scenario_id=request.scenario_id,
            session_id=request.session_id,
            context=request.context,
        )
    elif request.message:
        # 从对话创建
        task_session = await orchestrator.create_task_from_dialog(
            message=request.message,
            session_id=request.session_id,
            context=request.context,
        )
    else:
        raise HTTPException(status_code=400, detail="Either scenario_id or message is required")

    if not task_session:
        raise HTTPException(status_code=404, detail="Scenario not found or no match")

    # 启动任务
    await orchestrator.start_task(task_session.state.task_id)

    return _task_to_response(task_session)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status: Optional[str] = None,
    session_id: Optional[str] = None,
    http_request: Request = None,
) -> TaskListResponse:
    """
    列出任务

    可选过滤:
    - status: 按状态过滤
    - session_id: 按会话 ID 过滤
    """
    orchestrator = _get_orchestrator(http_request)
    if not orchestrator:
        raise HTTPException(status_code=503, detail="TaskOrchestrator not available")

    tasks = orchestrator.list_active_tasks()

    # 过滤
    if status:
        from openakita.orchestration.models import TaskStatus
        try:
            task_status = TaskStatus(status)
            tasks = [t for t in tasks if t.state.status == task_status]
        except ValueError:
            pass

    if session_id:
        tasks = [t for t in tasks if t.state.session_id == session_id]

    return TaskListResponse(
        tasks=[_task_to_response(t) for t in tasks],
        total=len(tasks),
    )


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: str, http_request: Request) -> TaskDetailResponse:
    """获取任务详情"""
    orchestrator = _get_orchestrator(http_request)
    if not orchestrator:
        raise HTTPException(status_code=503, detail="TaskOrchestrator not available")

    task_session = orchestrator.get_task(task_id)
    if not task_session:
        raise HTTPException(status_code=404, detail="Task not found")

    scenario = task_session.scenario

    return TaskDetailResponse(
        task=_task_to_response(task_session),
        scenario_name=scenario.name,
        scenario_description=scenario.description,
        step_sessions=[
            {
                "step_id": ss.step_id,
                "status": ss.status.value,
                "started_at": ss.started_at,
                "completed_at": ss.completed_at,
            }
            for ss in task_session.step_sessions.values()
        ],
    )


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str, http_request: Request) -> dict[str, Any]:
    """取消任务"""
    orchestrator = _get_orchestrator(http_request)
    if not orchestrator:
        raise HTTPException(status_code=503, detail="TaskOrchestrator not available")

    success = await orchestrator.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")

    return {"success": True, "task_id": task_id, "status": "cancelled"}


@router.post("/{task_id}/confirm")
async def confirm_step(
    task_id: str,
    request: ConfirmStepRequest,
    http_request: Request,
) -> dict[str, Any]:
    """确认步骤"""
    orchestrator = _get_orchestrator(http_request)
    if not orchestrator:
        raise HTTPException(status_code=503, detail="TaskOrchestrator not available")

    success = await orchestrator.confirm_step(
        task_id=task_id,
        step_id=request.step_id,
        edited_output=request.edited_output,
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to confirm step")

    return {"success": True, "task_id": task_id, "step_id": request.step_id}


@router.post("/{task_id}/switch")
async def switch_step(
    task_id: str,
    request: SwitchStepRequest,
    http_request: Request,
) -> dict[str, Any]:
    """切换步骤"""
    orchestrator = _get_orchestrator(http_request)
    if not orchestrator:
        raise HTTPException(status_code=503, detail="TaskOrchestrator not available")

    success = await orchestrator.switch_step(
        task_id=task_id,
        step_id=request.step_id,
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to switch step")

    return {"success": True, "task_id": task_id, "current_step_id": request.step_id}


@router.get("/{task_id}/context")
async def get_task_context(task_id: str, http_request: Request) -> dict[str, Any]:
    """获取任务上下文"""
    orchestrator = _get_orchestrator(http_request)
    if not orchestrator:
        raise HTTPException(status_code=503, detail="TaskOrchestrator not available")

    task_session = orchestrator.get_task(task_id)
    if not task_session:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "context": task_session.context,
    }


# ==================== 辅助函数 ====================


def _get_orchestrator(request: Request):
    """获取 TaskOrchestrator 实例"""
    # 从 app.state 获取
    orchestrator = getattr(request.app.state, "task_orchestrator", None)
    return orchestrator


def _task_to_response(task_session) -> TaskResponse:
    """将 TaskSession 转换为响应模型"""
    state = task_session.state
    progress = state.get_progress()

    return TaskResponse(
        task_id=state.task_id,
        scenario_id=state.scenario_id,
        session_id=state.session_id,
        status=state.status.value,
        current_step_id=state.current_step_id,
        total_steps=state.total_steps,
        completed_steps=state.completed_steps,
        progress_percent=state.get_progress_percent(),
        created_at=state.created_at,
        context=state.context,
    )