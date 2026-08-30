"""模型部署 API"""
import json
import urllib.request
import urllib.error

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.response import success_response
from app.services.deploy_service import DeployService
from app.services.notification_service import NotificationService
from app.api.v1.task_dispatch import dispatch_task
from app.schemas.deployment import DeploymentCreate, DeploymentUpdate, DeploymentTest

router = APIRouter()


@router.get("")
async def list_deployments(
    page_index: int = Query(1, ge=1, alias="pageIndex"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    keyword: str = Query(None),
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = DeployService(db)
    result = await svc.list_deployments(
        page_index=page_index, page_size=page_size,
        keyword=keyword, status=status,
    )
    return success_response(result)


@router.get("/stats")
async def get_deploy_stats(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = DeployService(db)
    result = await svc.get_deploy_stats()
    return success_response(result)


@router.get("/{deploy_id}")
async def get_deployment(
    deploy_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = DeployService(db)
    result = await svc.get_deployment(deploy_id)
    if not result:
        raise HTTPException(status_code=404, detail="部署不存在")
    return success_response(result)


@router.post("")
async def create_deployment(
    data: DeploymentCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = DeployService(db)
    payload = data.model_dump()
    result = await svc.create_deployment(payload, created_by=user["username"])

    # 创建通知
    notify_svc = NotificationService(db)
    await notify_svc.create_notification(
        title="模型部署创建",
        content=f"模型部署「{payload.get('name', '')}」已创建，正在部署中...",
        level="info",
        module="deployment",
        ref_id=result["id"],
    )

    return success_response(result)


@router.put("/{deploy_id}")
async def update_deployment(
    deploy_id: str,
    data: DeploymentUpdate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = DeployService(db)
    result = await svc.update_deployment(deploy_id, data.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="部署不存在")
    return success_response(result)


@router.delete("/{deploy_id}")
async def delete_deployment(
    deploy_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = DeployService(db)
    ok = await svc.delete_deployment(deploy_id)
    if not ok:
        raise HTTPException(status_code=404, detail="部署不存在")
    return success_response({"message": "删除成功"})


@router.post("/{deploy_id}/start")
async def start_deployment(
    deploy_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """启动推理服务：派发到 Celery（或本地后台）执行"""
    svc = DeployService(db)
    deploy = await svc.get_deployment(deploy_id)
    if not deploy:
        raise HTTPException(status_code=404, detail="部署不存在")
    if deploy["status"] == "running":
        raise HTTPException(status_code=400, detail="部署已在运行中")

    result = await svc.update_deploy_status(deploy_id, "creating", progress=10)
    dispatch = dispatch_task("inference", deploy_id)

    # 创建通知
    notify_svc = NotificationService(db)
    await notify_svc.create_notification(
        title="模型部署上线",
        content=f"模型部署「{deploy.get('name', deploy_id)}」正在启动推理服务（调度方式: {dispatch}）",
        level="info",
        module="deployment",
        ref_id=deploy_id,
    )

    return success_response({**result, "dispatch": dispatch})


@router.post("/{deploy_id}/stop")
async def stop_deployment(
    deploy_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = DeployService(db)
    result = await svc.update_deploy_status(deploy_id, "stopped")
    if not result:
        raise HTTPException(status_code=404, detail="部署不存在")
    # 关闭 mock 推理服务并回填实例状态
    from app.tasks.executor import stop_inference_service
    await stop_inference_service(deploy_id)
    return success_response(result)


@router.get("/{deploy_id}/logs")
async def get_deploy_logs(
    deploy_id: str,
    tail: int = Query(200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """读取部署日志（方案7）"""
    svc = DeployService(db)
    deploy = await svc.get_deployment(deploy_id)
    if not deploy:
        raise HTTPException(status_code=404, detail="部署不存在")
    from app.tasks.executor import deploy_log_path
    path = deploy_log_path(deploy_id)
    lines: list[str] = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            lines = []
    return success_response(lines[-tail:])


@router.post("/{deploy_id}/test")
async def test_deployment(
    deploy_id: str,
    prompt: DeploymentTest,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """调用部署的真实推理端点进行测试（OpenAI 兼容接口）"""
    svc = DeployService(db)
    deploy = await svc.get_deployment(deploy_id)
    if not deploy:
        raise HTTPException(status_code=404, detail="部署不存在")
    if deploy.get("status") != "running":
        raise HTTPException(status_code=400, detail="部署未在运行中")
    endpoint = deploy.get("endpoint")
    if not endpoint:
        raise HTTPException(status_code=400, detail="部署尚未分配服务端点")

    url = endpoint.rstrip("/") + "/chat/completions"
    text = prompt.prompt.strip()

    payload = json.dumps({
        "model": deploy.get("modelName") or "model",
        "messages": [{"role": "user", "content": text}],
        "max_tokens": 256,
        "temperature": 0.7,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"推理服务返回错误: {exc.code} {exc.reason}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"推理服务连接失败: {exc}") from exc

    choices = body.get("choices") or []
    reply = choices[0].get("message", {}).get("content", "") if choices else ""
    return success_response({
        "response": reply or (body.get("text") or "（无输出）"),
        "endpoint": endpoint,
        "usage": body.get("usage"),
    })


# ---- 部署实例(POD) ----

@router.get("/{deploy_id}/instances")
async def list_instances(
    deploy_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = DeployService(db)
    result = await svc.list_instances(deploy_id)
    return success_response(result)


@router.get("/{deploy_id}/instances/{instance_id}")
async def get_instance(
    deploy_id: str,
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = DeployService(db)
    result = await svc.get_instance(instance_id)
    if not result:
        raise HTTPException(status_code=404, detail="实例不存在")
    return success_response(result)
