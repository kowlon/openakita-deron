"""
Task management API routes.

Provides RESTful endpoints for task orchestration:
- List/create tasks
- Get/update/delete tasks
- Resume/pause/cancel tasks
- Get/update steps
- List best practice templates
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from openakita.orchestration import (
    BestPracticeConfig,
    OrchestrationTask,
    StepStatus,
    TaskStatus,
    TaskStep,
)
from openakita.orchestration.task_orchestrator import TaskNotFoundError, TemplateNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Request/Response Models ====================


class CreateTaskRequest(BaseModel):
    """创建任务请求"""

    session_id: str = Field(..., description="会话 ID")
    template_id: str | None = Field(None, description="最佳实践模板 ID")
    name: str | None = Field(None, description="任务名称")
    description: str | None = Field(None, description="任务描述")
    input_payload: dict[str, Any] | None = Field(None, description="初始输入数据")


class TaskResponse(BaseModel):
    """任务响应"""

    id: str
    session_id: str
    template_id: str | None
    name: str
    description: str
    status: str
    current_step_index: int
    total_steps: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class TaskDetailResponse(BaseModel):
    """任务详情响应"""

    id: str
    session_id: str
    template_id: str | None
    name: str
    description: str
    status: str
    current_step_index: int
    steps: list[dict[str, Any]]
    context_variables: dict[str, Any]
    created_at: str
    updated_at: str


class StepResponse(BaseModel):
    """步骤响应"""

    id: str
    task_id: str
    index: int
    name: str
    description: str
    status: str
    input_args: dict[str, Any]
    output_result: dict[str, Any]


class UpdateStepRequest(BaseModel):
    """更新步骤请求"""

    output_result: dict[str, Any] | None = Field(None, description="步骤输出结果")
    user_feedback: str | None = Field(None, description="用户反馈")


class TemplateResponse(BaseModel):
    """模板响应"""

    id: str
    name: str
    description: str
    steps: list[dict[str, Any]]


class ErrorResponse(BaseModel):
    """错误响应"""

    error: str
    detail: str | None = None


# ==================== Helper Functions ====================


def _get_orchestrator(request: Request):
    """获取 TaskOrchestrator 实例"""
    orchestrator = getattr(request.app.state, "task_orchestrator", None)
    if orchestrator is None:
        raise HTTPException(
            status_code=503,
            detail="Task orchestrator not initialized",
        )
    return orchestrator


def _task_to_response(task: OrchestrationTask) -> TaskResponse:
    """将任务转换为响应"""
    return TaskResponse(
        id=task.id,
        session_id=task.session_id,
        template_id=task.template_id,
        name=task.name,
        description=task.description,
        status=task.status,
        current_step_index=task.current_step_index,
        total_steps=len(task.steps),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _task_to_detail_response(task: OrchestrationTask) -> TaskDetailResponse:
    """将任务转换为详情响应"""
    return TaskDetailResponse(
        id=task.id,
        session_id=task.session_id,
        template_id=task.template_id,
        name=task.name,
        description=task.description,
        status=task.status,
        current_step_index=task.current_step_index,
        steps=[s.to_dict() for s in task.steps],
        context_variables=task.context_variables,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _template_to_response(template: BestPracticeConfig) -> TemplateResponse:
    """将模板转换为响应"""
    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        steps=[s.to_dict() for s in template.steps],
    )


# ==================== Task Endpoints ====================


@router.get("/api/tasks", response_model=list[TaskResponse])
async def list_tasks(
    request: Request,
    session_id: str | None = None,
    status: str | None = None,
):
    """
    列出任务

    Args:
        session_id: 过滤会话 ID
        status: 过滤状态
    """
    orchestrator = _get_orchestrator(request)

    # 如果指定了 session_id，从该会话获取任务
    if session_id:
        session_tasks = await orchestrator.get_session_tasks(session_id)
        tasks = session_tasks.get_all_tasks()
    else:
        # 获取所有任务（需要遍历所有会话）
        tasks = []
        for session_id_key, session_tasks in orchestrator._session_tasks.items():
            tasks.extend(session_tasks.get_all_tasks())

    # 过滤状态
    if status:
        tasks = [t for t in tasks if t.status == status]

    return [_task_to_response(t) for t in tasks]


@router.post("/api/tasks", response_model=TaskDetailResponse, status_code=201)
async def create_task(request: Request, body: CreateTaskRequest):
    """
    创建任务

    Args:
        body: 创建请求
    """
    orchestrator = _get_orchestrator(request)

    try:
        task = await orchestrator.create_task(
            session_id=body.session_id,
            template_id=body.template_id,
            name=body.name,
            description=body.description,
            input_payload=body.input_payload or {},
        )
        return _task_to_detail_response(task)

    except TemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ==================== Stats Endpoint (before {task_id} routes) ====================


@router.get("/api/tasks/stats")
async def get_task_stats(request: Request):
    """
    获取任务统计信息
    """
    orchestrator = _get_orchestrator(request)
    return orchestrator.get_stats()


# ==================== Task Detail Endpoints ====================


@router.get("/api/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(request: Request, task_id: str):
    """
    获取任务详情

    Args:
        task_id: 任务 ID
    """
    orchestrator = _get_orchestrator(request)

    task = await orchestrator._storage.load_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return _task_to_detail_response(task)


@router.delete("/api/tasks/{task_id}")
async def delete_task(request: Request, task_id: str):
    """
    删除/取消任务

    Args:
        task_id: 任务 ID
    """
    orchestrator = _get_orchestrator(request)

    try:
        await orchestrator.cancel_task(task_id)
        return {"status": "cancelled", "task_id": task_id}

    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/tasks/{task_id}/resume", response_model=TaskDetailResponse)
async def resume_task(request: Request, task_id: str):
    """
    恢复暂停的任务

    Args:
        task_id: 任务 ID
    """
    orchestrator = _get_orchestrator(request)

    try:
        task = await orchestrator.resume_task(task_id)
        return _task_to_detail_response(task)

    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/api/tasks/{task_id}/pause")
async def pause_task(request: Request, task_id: str, reason: str = "user_requested"):
    """
    暂停任务

    Args:
        task_id: 任务 ID
        reason: 暂停原因
    """
    orchestrator = _get_orchestrator(request)

    try:
        await orchestrator.pause_task(task_id, reason)
        return {"status": "paused", "task_id": task_id}

    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ==================== Step Endpoints ====================


@router.get("/api/tasks/{task_id}/steps/{step_id}", response_model=StepResponse)
async def get_step(request: Request, task_id: str, step_id: str):
    """
    获取步骤详情

    Args:
        task_id: 任务 ID
        step_id: 步骤 ID
    """
    orchestrator = _get_orchestrator(request)

    task = await orchestrator._storage.load_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    for step in task.steps:
        if step.id == step_id:
            return StepResponse(
                id=step.id,
                task_id=step.task_id,
                index=step.index,
                name=step.name,
                description=step.description,
                status=step.status,
                input_args=step.input_args,
                output_result=step.output_result,
            )

    raise HTTPException(status_code=404, detail=f"Step not found: {step_id}")


@router.patch("/api/tasks/{task_id}/steps/{step_id}", response_model=StepResponse)
async def update_step(
    request: Request,
    task_id: str,
    step_id: str,
    body: UpdateStepRequest,
):
    """
    更新步骤

    允许用户编辑步骤输出或提供反馈。

    Args:
        task_id: 任务 ID
        step_id: 步骤 ID
        body: 更新请求
    """
    orchestrator = _get_orchestrator(request)

    task = await orchestrator._storage.load_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    for step in task.steps:
        if step.id == step_id:
            if body.output_result is not None:
                step.output_result = body.output_result
            if body.user_feedback is not None:
                step.user_feedback = body.user_feedback

            await orchestrator._storage.save_step(step)

            return StepResponse(
                id=step.id,
                task_id=step.task_id,
                index=step.index,
                name=step.name,
                description=step.description,
                status=step.status,
                input_args=step.input_args,
                output_result=step.output_result,
            )

    raise HTTPException(status_code=404, detail=f"Step not found: {step_id}")


# ==================== Template Endpoints ====================


@router.get("/api/best-practices", response_model=list[TemplateResponse])
async def list_templates(request: Request):
    """
    列出可用的最佳实践模板
    """
    orchestrator = _get_orchestrator(request)
    templates = orchestrator.list_templates()
    return [_template_to_response(t) for t in templates]


@router.get(
    "/api/best-practices/{template_id}",
    response_model=TemplateResponse,
)
async def get_template(request: Request, template_id: str):
    """
    获取模板详情

    Args:
        template_id: 模板 ID
    """
    orchestrator = _get_orchestrator(request)

    template = orchestrator.get_template(template_id)
    if not template:
        raise HTTPException(
            status_code=404,
            detail=f"Template not found: {template_id}",
        )

    return _template_to_response(template)