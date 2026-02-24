"""
桌面聊天的文件服务端点。

允许桌面前端访问工作区文件（图片、文档等），这些文件由 deliver_artifacts、generate_image 等代理工具生成。

安全性：仅提供当前工作区目录下的文件。
"""

import logging
import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])


def _get_workspace_root(request: Request) -> Path:
    """从运行中的代理获取工作区根目录。"""
    agent = getattr(request.app.state, "agent", None)

    if agent is not None:
        # 尝试从 agent 获取 workspace_dir
        ws_dir = getattr(agent, "workspace_dir", None) or getattr(agent, "_workspace_dir", None)
        if ws_dir:
            return Path(ws_dir)

    # 回退：尝试 settings
    try:
        from openakita.core.settings import settings
        if settings.workspace_dir:
            return Path(settings.workspace_dir)
    except Exception:
        pass

    # 最后手段：当前工作目录
    return Path.cwd()


@router.get("")
async def serve_file(request: Request, path: str = ""):
    """
    从工作区目录提供文件。

    查询参数 `path` 可以是相对工作区根目录的路径，也可以是绝对路径。
    示例：/api/files?path=data/temp/image.png
    示例：/api/files?path=D:/coder/myagent/data/temp/image.png
    """
    if not path:
        raise HTTPException(status_code=400, detail="Missing 'path' parameter")

    workspace = _get_workspace_root(request)

    # 处理相对与绝对路径
    requested = Path(path)
    full_path = requested if requested.is_absolute() else workspace / path

    # 解析路径以防止目录遍历
    try:
        full_path = full_path.resolve()
    except (OSError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid path")

    # 安全：确保文件位于工作区或已知安全目录下
    # （例如用户主目录、代理工具使用的临时目录）
    # 使用 Path.is_relative_to() 代替字符串前缀匹配，以避免
    # 误判（例如 /home/user 匹配 /home/user_docs），并避免
    # Windows 上大小写敏感问题。
    workspace_resolved = workspace.resolve()
    safe_roots = [
        workspace_resolved,
        Path.home().resolve(),  # 允许访问用户主目录（下载等）
    ]

    is_safe = any(
        full_path.is_relative_to(root) for root in safe_roots
    )
    if not is_safe:
        raise HTTPException(status_code=403, detail="Access denied: path outside allowed directories")

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    # 确定内容类型
    content_type, _ = mimetypes.guess_type(str(full_path))
    if not content_type:
        content_type = "application/octet-stream"

    return FileResponse(
        path=str(full_path),
        media_type=content_type,
        filename=full_path.name,
    )
