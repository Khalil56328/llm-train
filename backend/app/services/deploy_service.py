"""模型部署服务"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import Deployment, DeployInstance


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now()


class DeployService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_deployments(
        self,
        *,
        page_index: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict:
        q = select(Deployment)
        count_q = select(func.count(Deployment.id))

        if keyword:
            f = Deployment.name.contains(keyword)
            q, count_q = q.where(f), count_q.where(f)
        if status:
            q, count_q = q.where(Deployment.status == status), count_q.where(Deployment.status == status)

        total = (await self.db.execute(count_q)).scalar() or 0
        rows = (await self.db.execute(
            q.order_by(Deployment.created_at.desc())
             .offset((page_index - 1) * page_size).limit(page_size)
        )).scalars().all()

        return {
            "list": [_deploy_to_dict(d) for d in rows],
            "total": total,
            "pageIndex": page_index,
            "pageSize": page_size,
        }

    async def get_deployment(self, deploy_id: str) -> Optional[Dict]:
        result = await self.db.execute(select(Deployment).where(Deployment.id == deploy_id))
        d = result.scalar_one_or_none()
        return _deploy_to_dict(d) if d else None

    async def create_deployment(self, data: Dict, *, created_by: str) -> Dict:
        d = Deployment(
            id=_uuid(),
            name=data.get("name"),
            description=data.get("description"),
            model_id=data.get("modelId", ""),
            model_name=data.get("modelName"),
            model_version=data.get("modelVersion"),
            inference_framework=data.get("inferenceFramework", "vLLM"),
            operator_id=data.get("operatorId"),
            operator_version=data.get("operatorVersion"),
            params=data.get("params", {}),
            env_vars=data.get("envVars", {}),
            resource_config=data.get("resourceConfig", {}),
            instances=data.get("instances", 1),
            container_port=data.get("containerPort", 8000),
            access_port=data.get("accessPort"),
            endpoint=data.get("endpoint"),
            status="creating",
            progress=0,
            created_by=created_by,
        )
        self.db.add(d)
        await self.db.flush()
        await self.db.refresh(d)
        # 创建模拟POD实例
        for i in range(d.instances or 1):
            inst = DeployInstance(
                id=_uuid(),
                deploy_id=d.id,
                pod_name=f"{d.name}-pod-{i+1}",
                status="pending",
                host_ip="",
                pod_ip="",
            )
            self.db.add(inst)
        await self.db.flush()
        return _deploy_to_dict(d)

    async def update_deployment(self, deploy_id: str, data: Dict) -> Optional[Dict]:
        result = await self.db.execute(select(Deployment).where(Deployment.id == deploy_id))
        d = result.scalar_one_or_none()
        if not d:
            return None
        field_map = {
            "modelId": "model_id", "modelName": "model_name",
            "modelVersion": "model_version", "inferenceFramework": "inference_framework",
            "operatorId": "operator_id", "operatorVersion": "operator_version",
            "envVars": "env_vars", "resourceConfig": "resource_config",
            "errorMessage": "error_message", "createdBy": "created_by",
            "instances": "instances", "containerPort": "container_port",
            "accessPort": "access_port",
        }
        for k, v in data.items():
            if v is not None:
                setattr(d, field_map.get(k, k), v)
        d.updated_at = _now()
        await self.db.flush()
        await self.db.refresh(d)
        return _deploy_to_dict(d)

    async def update_deploy_status(
        self, deploy_id: str, status: str, *,
        progress: Optional[int] = None,
        error_message: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> Optional[Dict]:
        result = await self.db.execute(select(Deployment).where(Deployment.id == deploy_id))
        d = result.scalar_one_or_none()
        if not d:
            return None
        d.status = status
        if progress is not None:
            d.progress = progress
        if error_message is not None:
            d.error_message = error_message
        if endpoint is not None:
            d.endpoint = endpoint
        if status == "running":
            d.progress = 100
        d.updated_at = _now()
        await self.db.flush()
        await self.db.refresh(d)
        return _deploy_to_dict(d)

    async def delete_deployment(self, deploy_id: str) -> bool:
        # 先删除关联实例
        await self.db.execute(delete(DeployInstance).where(DeployInstance.deploy_id == deploy_id))
        result = await self.db.execute(select(Deployment).where(Deployment.id == deploy_id))
        d = result.scalar_one_or_none()
        if not d:
            return False
        await self.db.delete(d)
        await self.db.flush()
        return True

    async def get_deploy_stats(self) -> Dict:
        result = await self.db.execute(
            select(Deployment.status, func.count(Deployment.id)).group_by(Deployment.status)
        )
        rows = result.all()
        stats = {row[0]: row[1] for row in rows}
        return {
            "creating": stats.get("creating", 0),
            "running": stats.get("running", 0),
            "stopped": stats.get("stopped", 0),
            "failed": stats.get("failed", 0),
            "deleting": stats.get("deleting", 0),
            "total": sum(stats.values()),
        }

    # ---- 部署实例(POD) ----
    async def list_instances(self, deploy_id: str) -> List[Dict]:
        result = await self.db.execute(
            select(DeployInstance).where(DeployInstance.deploy_id == deploy_id)
            .order_by(DeployInstance.created_at)
        )
        rows = result.scalars().all()
        return [_instance_to_dict(i) for i in rows]

    async def get_instance(self, instance_id: str) -> Optional[Dict]:
        result = await self.db.execute(select(DeployInstance).where(DeployInstance.id == instance_id))
        i = result.scalar_one_or_none()
        return _instance_to_dict(i) if i else None

    async def update_instance_status(self, instance_id: str, data: Dict) -> Optional[Dict]:
        result = await self.db.execute(select(DeployInstance).where(DeployInstance.id == instance_id))
        i = result.scalar_one_or_none()
        if not i:
            return None
        if "status" in data:
            i.status = data["status"]
        if "hostIp" in data:
            i.host_ip = data["hostIp"]
        if "podIp" in data:
            i.pod_ip = data["podIp"]
        i.updated_at = _now()
        await self.db.flush()
        await self.db.refresh(i)
        return _instance_to_dict(i)


def _deploy_to_dict(d: Deployment) -> Dict:
    return {
        "id": d.id,
        "name": d.name,
        "description": d.description,
        "modelId": d.model_id,
        "modelName": d.model_name,
        "modelVersion": d.model_version,
        "inferenceFramework": d.inference_framework,
        "operatorId": d.operator_id,
        "operatorVersion": d.operator_version,
        "params": d.params,
        "envVars": d.env_vars,
        "resourceConfig": d.resource_config,
        "instances": d.instances or 1,
        "containerPort": d.container_port or 8000,
        "accessPort": d.access_port,
        "endpoint": d.endpoint,
        "status": d.status,
        "progress": d.progress or 0,
        "errorMessage": d.error_message,
        "createdBy": d.created_by,
        "createdAt": d.created_at.isoformat() if d.created_at else None,
        "updatedAt": d.updated_at.isoformat() if d.updated_at else None,
    }


def _instance_to_dict(i: DeployInstance) -> Dict:
    return {
        "id": i.id,
        "deployId": i.deploy_id,
        "podName": i.pod_name,
        "status": i.status,
        "hostIp": i.host_ip,
        "podIp": i.pod_ip,
        "createdAt": i.created_at.isoformat() if i.created_at else None,
        "updatedAt": i.updated_at.isoformat() if i.updated_at else None,
    }
