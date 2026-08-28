"""模型在线推理端点（OpenAI 兼容，支持流式）

将推理请求转发到部署的 endpoint（vLLM / swift / mock 服务），
支持非流式（/chat/completions）与流式（stream=true, SSE）两种模式。
"""
import json
from typing import Any, Dict

from fastapi import APIRouter, Depends, Body, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.response import success_response
from app.services.deploy_service import DeployService

router = APIRouter()

try:
    import httpx
    _HAVE_HTTPX = True
except ImportError:  # pragma: no cover
    _HAVE_HTTPX = False


async def _resolve_deploy(db: AsyncSession, deploy_id: str) -> Dict:
    """校验部署存在且运行中，返回部署信息"""
    svc = DeployService(db)
    deploy = await svc.get_deployment(deploy_id)
    if not deploy:
        raise HTTPException(status_code=404, detail="部署不存在")
    if deploy.get("status") != "running":
        raise HTTPException(status_code=400, detail="部署未在运行中")
    endpoint = deploy.get("endpoint")
    if not endpoint:
        raise HTTPException(status_code=400, detail="部署尚未分配服务端点")
    return deploy


def _base_url(endpoint: str) -> str:
    return endpoint.rstrip("/")


@router.post("/inference/chat/completions")
async def chat_completions(
    # 前端与其余 API 一致使用 camelCase（如 modelId/accessPort），此处加别名兼容
    deploy_id: str = Body(..., embed=True, alias="deployId"),
    payload: Dict[str, Any] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """调用部署的 OpenAI 兼容接口，支持流式（SSE）与非流式"""
    deploy = await _resolve_deploy(db, deploy_id)
    base = _base_url(deploy.get("endpoint", ""))
    if "model" not in payload:
        payload["model"] = deploy.get("modelName") or "model"
    stream = bool(payload.get("stream"))

    if not _HAVE_HTTPX:
        # 降级：非流式转发
        return await _forward_sync(base, deploy_id, payload)

    if stream:
        async def _proxy_stream():
            # 注意：client 的生命周期必须由生成器自己管理。
            # StreamingResponse 在 handler 返回后才被 FastAPI 迭代，
            # 若 client 在 handler 作用域内创建，返回时即被 aclose()，
            # 生成器一启动就会抛 "client has been closed" 导致流中断（前端 network error）。
            async with httpx.AsyncClient(timeout=None) as client:
                # client.stream() 是 httpx 标准流式上下文管理器；
                # 注意 client.send() 是普通协程方法（需 await，返回 Response），
                # 不支持 async with，误用会在首次迭代时抛 TypeError 导致空流。
                async with client.stream(
                    "POST", base + "/chat/completions", json=payload
                ) as resp:
                    if resp.status_code >= 400:
                        text = (await resp.aread()).decode("utf-8", "replace")
                        yield f"data: {json.dumps({'error': {'message': f'HTTP {resp.status_code}: {text}'}}, ensure_ascii=False)}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                    async for chunk in resp.aiter_bytes():
                        yield chunk
        return StreamingResponse(_proxy_stream(), media_type="text/event-stream")

    async with httpx.AsyncClient(timeout=None) as client:
        resp = await client.post(base + "/chat/completions", json=payload)
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"推理服务返回错误: HTTP {resp.status_code}")
        return success_response(resp.json())


async def _forward_sync(base: str, deploy_id: str, payload: Dict[str, Any]) -> Dict:
    """无 httpx 时的 urllib 降级实现（非流式）"""
    import urllib.request
    import urllib.error
    url = base + "/chat/completions"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"推理服务返回错误: {exc.code}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"推理服务连接失败: {exc}") from exc
    return body
