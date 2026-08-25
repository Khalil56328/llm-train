"""数据中心 API"""
import io
import json
import uuid
import zipfile
from pathlib import Path
from urllib.parse import quote

from typing import Dict

from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.response import success_response
from app.core.storage import read_object, save_upload
from app.services.dataset_service import DatasetService
from app.schemas.dataset import DatasetCreate, DatasetUpdate, DatasetVersionCreate, DatasetFileCreate

router = APIRouter()

# 内置示例模板：与 MS-Swift 数据集格式对齐
# SFT: instruction/output；CPT(续写): text
BUILTIN_TEMPLATES = {
    "sft": {
        "file_name": "example_sft.jsonl",
        "description": "SFT 指令微调格式示例（instruction/output）",
        "content": [
            {"instruction": "请以“咏梅”为题创作一首五言绝句。", "output": "墙角数枝梅，凌寒独自开。遥知不是雪，为有暗香来。"},
            {"instruction": "请解释这首诗的含义：床前明月光，疑是地上霜。", "output": "诗人深夜不眠，看到床前洒落的月光，误以为地上铺满了秋霜，借景抒发了游子的思乡之情。"},
            {"instruction": "请写一首描写春天景色的诗。", "output": "迟日江山丽，春风花草香。泥融飞燕子，沙暖睡鸳鸯。"},
        ],
    },
    "cpt": {
        "file_name": "example_cpt.jsonl",
        "description": "CPT 续写/预训练格式示例（text）",
        "content": [
            {"text": "床前明月光，疑是地上霜。举头望明月，低头思故乡。"},
            {"text": "春眠不觉晓，处处闻啼鸟。夜来风雨声，花落知多少。"},
            {"text": "白日依山尽，黄河入海流。欲穷千里目，更上一层楼。"},
        ],
    },
}


def _is_admin(user: dict) -> bool:
    return user.get("role") in ("super_admin", "admin")


def _new_batch_id() -> str:
    return uuid.uuid4().hex


async def _get_dataset_or_404(svc: DatasetService, dataset_id: str) -> Dict:
    dataset = await svc.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return dataset


def _ensure_readable(dataset: Dict, user: dict) -> None:
    """读操作权限：管理员 / 数据所有者 / 公开数据集可访问"""
    if _is_admin(user):
        return
    if dataset.get("ownerId") == user["id"]:
        return
    if dataset.get("isPublic"):
        return
    raise HTTPException(status_code=403, detail="无权访问该数据集")


def _ensure_owned(dataset: Dict, user: dict) -> None:
    """写操作权限：仅管理员 / 数据所有者可操作"""
    if _is_admin(user):
        return
    if dataset.get("ownerId") != user["id"]:
        raise HTTPException(status_code=403, detail="无权操作该数据集")


def _invalid_ext(file_name: str) -> bool:
    """校验文件扩展名是否在允许列表中"""
    ext = Path(file_name).suffix.lower()
    allowed = {e.strip().lower() for e in settings.UPLOAD_ALLOWED_EXTS.split(",")}
    return ext not in allowed



@router.get("")
async def list_datasets(
    page_index: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None),
    category: str = Query(None),
    data_type: str = Query(None),
    status: str = Query(None),
    dataset_type: str = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = DatasetService(db)
    result = await svc.list_datasets(
        page_index=page_index, page_size=page_size,
        keyword=keyword, category=category,
        data_type=data_type, status=status,
        dataset_type=dataset_type, owner_id=user["id"],
    )
    return success_response(result)


@router.get("/{dataset_id}")
async def get_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = DatasetService(db)
    result = await _get_dataset_or_404(svc, dataset_id)
    _ensure_readable(result, user)
    return success_response(result)


@router.post("")
async def create_dataset(
    data: DatasetCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = DatasetService(db)
    owner_name = user.get("nickname") or user.get("username")
    result = await svc.create_dataset(data.model_dump(), owner_id=user["id"], owner_name=owner_name)
    return success_response(result)


@router.put("/{dataset_id}")
async def update_dataset(
    dataset_id: str,
    data: DatasetUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = DatasetService(db)
    dataset = await _get_dataset_or_404(svc, dataset_id)
    _ensure_owned(dataset, user)
    result = await svc.update_dataset(dataset_id, data.model_dump(exclude_unset=True))
    return success_response(result)


@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = DatasetService(db)
    dataset = await _get_dataset_or_404(svc, dataset_id)
    _ensure_owned(dataset, user)
    ok = await svc.delete_dataset(dataset_id)
    if not ok:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return success_response({"message": "删除成功"})


# ========== 版本 ==========
@router.get("/{dataset_id}/versions")
async def list_versions(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = DatasetService(db)
    dataset = await _get_dataset_or_404(svc, dataset_id)
    _ensure_readable(dataset, user)
    result = await svc.list_versions(dataset_id)
    return success_response(result)


@router.post("/{dataset_id}/versions")
async def create_version(
    dataset_id: str,
    data: DatasetVersionCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = DatasetService(db)
    dataset = await _get_dataset_or_404(svc, dataset_id)
    _ensure_owned(dataset, user)
    result = await svc.create_version(dataset_id, data.model_dump())
    return success_response(result)


@router.delete("/versions/{version_id}")
async def delete_version(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = DatasetService(db)
    ok = await svc.delete_version(version_id)
    if not ok:
        raise HTTPException(status_code=404, detail="版本不存在")
    return success_response({"message": "删除成功"})


# ========== 文件 ==========
@router.get("/{dataset_id}/files")
async def list_files(
    dataset_id: str,
    page_index: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: str = Query(None),
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = DatasetService(db)
    dataset = await _get_dataset_or_404(svc, dataset_id)
    _ensure_readable(dataset, user)
    result = await svc.list_files(
        dataset_id,
        page_index=page_index,
        page_size=page_size,
        keyword=keyword,
        status=status,
    )
    return success_response(result)


@router.get("/{dataset_id}/files/stats")
async def get_file_stats(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = DatasetService(db)
    dataset = await _get_dataset_or_404(svc, dataset_id)
    _ensure_readable(dataset, user)
    result = await svc.get_file_stats(dataset_id)
    return success_response(result)


@router.get("/{dataset_id}/files/collect-tasks")
async def list_collect_tasks(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """采集任务：按用户上传批次(batch_id)聚合统计"""
    svc = DatasetService(db)
    dataset = await _get_dataset_or_404(svc, dataset_id)
    _ensure_readable(dataset, user)
    result = await svc.list_collect_tasks(dataset_id)
    return success_response(result)


@router.post("/{dataset_id}/files")
async def create_file(
    dataset_id: str,
    data: DatasetFileCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = DatasetService(db)
    dataset = await _get_dataset_or_404(svc, dataset_id)
    _ensure_owned(dataset, user)
    result = await svc.create_file(dataset_id, data.model_dump(exclude_unset=True))
    return success_response(result)


@router.post("/{dataset_id}/files/upload")
async def upload_file(
    dataset_id: str,
    file: UploadFile = File(...),
    source: str = Form("local_upload"),
    batch_id: str = Form(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """上传单个数据集文件

    - source: 数据来源(采集方式)，如 local_upload / platform
    - batch_id: 采集批次 ID（一次上传的多个文件共享，用于采集任务聚合）
    """
    svc = DatasetService(db)
    dataset = await _get_dataset_or_404(svc, dataset_id)
    _ensure_owned(dataset, user)

    file_name = file.filename or "unknown"
    if _invalid_ext(file_name):
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {Path(file_name).suffix}")

    # 通过存储适配器保存（minio / local 自动切换），分块读取 + 大小限制
    max_size = settings.UPLOAD_MAX_SIZE_MB * 1024 * 1024
    try:
        saved = await save_upload(
            file, sub_dir=f"datasets/{dataset_id}", max_size=max_size
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    storage_path = saved["storage_path"]
    sample_count = DatasetService.count_file_rows(storage_path, file_name)
    result = await svc.create_file(
        dataset_id,
        {
            "file_name": file_name,
            "source": source,
            "status": "success",
            "size": saved["size"],
            "storage_path": storage_path,
            "batch_id": batch_id or _new_batch_id(),
            "sample_count": sample_count,
        },
    )
    return success_response({**result, "url": saved["url"]})


@router.post("/{dataset_id}/files/upload-batch")
async def upload_files_batch(
    dataset_id: str,
    files: list[UploadFile] = File(...),
    source: str = Form("local_upload"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """批量上传数据集文件（一次上传生成一个采集批次 batch_id）

    - source: 数据来源(采集方式)
    - 单个文件失败不影响其他文件；批次状态由文件状态聚合得出
    """
    svc = DatasetService(db)
    dataset = await _get_dataset_or_404(svc, dataset_id)
    _ensure_owned(dataset, user)

    if not files:
        raise HTTPException(status_code=400, detail="未选择任何文件")
    if len(files) > settings.UPLOAD_MAX_FILES_PER_BATCH:
        raise HTTPException(
            status_code=400,
            detail=f"单次最多上传 {settings.UPLOAD_MAX_FILES_PER_BATCH} 个文件",
        )

    batch_id = _new_batch_id()
    max_size = settings.UPLOAD_MAX_SIZE_MB * 1024 * 1024
    results = []
    seen_names = set()
    for file in files:
        file_name = file.filename or "unknown"
        if file_name in seen_names:
            results.append({
                "fileName": file_name,
                "status": "failed",
                "errorMessage": "同批次内文件名重复",
            })
            continue
        seen_names.add(file_name)
        if _invalid_ext(file_name):
            results.append({
                "fileName": file_name,
                "status": "failed",
                "errorMessage": f"不支持的文件类型: {Path(file_name).suffix}",
            })
            continue
        try:
            saved = await save_upload(
                file, sub_dir=f"datasets/{dataset_id}", max_size=max_size
            )
            storage_path = saved["storage_path"]
            sample_count = DatasetService.count_file_rows(storage_path, file_name)
            created = await svc.create_file(
                dataset_id,
                {
                    "file_name": file_name,
                    "source": source,
                    "status": "success",
                    "size": saved["size"],
                    "storage_path": storage_path,
                    "batch_id": batch_id,
                    "sample_count": sample_count,
                },
            )
            results.append({
                "id": created.get("id"),
                "fileName": file_name,
                "status": "success",
                "sampleCount": sample_count,
                "size": saved["size"],
            })
        except ValueError as e:
            results.append({
                "fileName": file_name,
                "status": "failed",
                "errorMessage": str(e),
            })
        except Exception:  # noqa: BLE001
            results.append({
                "fileName": file_name,
                "status": "failed",
                "errorMessage": "文件处理失败",
            })

    return success_response({"batchId": batch_id, "source": source, "files": results})


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = DatasetService(db)
    f = await svc.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="文件不存在")
    dataset = await _get_dataset_or_404(svc, f.get("datasetId"))
    _ensure_owned(dataset, user)
    ok = await svc.delete_file(file_id)
    if not ok:
        raise HTTPException(status_code=404, detail="文件不存在")
    return success_response({"message": "删除成功"})


@router.get("/{dataset_id}/files/{file_id}/download")
async def download_file(
    dataset_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """下载数据集的单个文件"""
    svc = DatasetService(db)
    f = await svc.get_file(file_id)
    if not f or f.get("datasetId") != dataset_id:
        raise HTTPException(status_code=404, detail="文件不存在")
    dataset = await _get_dataset_or_404(svc, dataset_id)
    _ensure_readable(dataset, user)
    storage_path = f.get("storagePath")
    if not storage_path:
        raise HTTPException(status_code=404, detail="文件无存储路径")
    data = read_object(storage_path)
    if data is None:
        raise HTTPException(status_code=404, detail="文件内容读取失败")
    filename = quote(f.get("fileName") or "download")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


# ========== 广场 ==========
@router.get("/plaza/search")
async def plaza_datasets(
    page_index: int = Query(1),
    page_size: int = Query(12),
    keyword: str = Query(None),
    dataset_type: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = DatasetService(db)
    result = await svc.list_datasets(
        page_index=page_index, page_size=page_size, keyword=keyword,
        dataset_type=dataset_type, is_public=True,
    )
    return success_response(result)


@router.post("/{dataset_id}/import")
async def import_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = DatasetService(db)
    dataset = await svc.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    # 将公开数据集复制到当前用户名下
    owner_name = user.get("nickname") or user.get("username")
    result = await svc.create_dataset(
        {
            "name": f"{dataset['name']}_copy",
            "category": dataset.get("category"),
            "type": dataset.get("type", "training"),
            "data_type": dataset.get("dataType"),
            "eval_dimensions": dataset.get("evalDimensions"),
            "description": dataset.get("description"),
            "source": "import",
            "storage_path": dataset.get("storagePath"),
            "size": dataset.get("size", 0),
            "sample_count": dataset.get("sampleCount", 0),
            "is_public": False,
        },
        owner_id=user["id"],
        owner_name=owner_name,
    )
    # 同步复制文件记录
    await svc.copy_files(dataset_id, result["id"])
    return success_response(result)


@router.get("/{dataset_id}/download")
async def download_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """下载整个数据集：单文件直接下载，多文件打包 zip"""
    svc = DatasetService(db)
    dataset = await _get_dataset_or_404(svc, dataset_id)
    _ensure_readable(dataset, user)

    files_result = await svc.list_files(dataset_id, page_index=1, page_size=100, status="success")
    files = (files_result or {}).get("list") or []
    if not files:
        raise HTTPException(status_code=404, detail="该数据集暂无文件可下载")

    # 单个文件直接返回
    if len(files) == 1:
        f = files[0]
        data = read_object(f.get("storagePath") or "")
        if data is None:
            raise HTTPException(status_code=404, detail="文件内容读取失败")
        filename = quote(f.get("fileName") or "download")
        return Response(
            content=data,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
        )

    # 多个文件打包 zip
    buf = io.BytesIO()
    seen: set = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            data = read_object(f.get("storagePath") or "")
            if data is None:
                continue
            name = f.get("fileName") or "file"
            if name in seen:
                stem = Path(name).stem
                suffix = Path(name).suffix
                name = f"{stem}_{len(seen) + 1}{suffix}"
            seen.add(name)
            zf.writestr(name, data)
    if not seen:
        raise HTTPException(status_code=404, detail="文件内容读取失败")

    filename = quote(f"{dataset['name']}.zip")
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


# ========== 示例模板 ==========
@router.get("/templates/{name}")
async def download_template(
    name: str,
    _user: dict = Depends(get_current_user),
):
    """下载内置示例数据集模板（与 MS-Swift 数据集格式对齐）"""
    template = BUILTIN_TEMPLATES.get(name)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    lines = [json.dumps(item, ensure_ascii=False) for item in template["content"]]
    data = ("\n".join(lines) + "\n").encode("utf-8")
    filename = quote(template["file_name"])
    # 注意：响应头值会被 Starlette 按 latin-1 编码，中文描述会抛 UnicodeEncodeError，
    # 因此这里不使用非 ASCII 的自定义响应头（模板描述前端无需读取）。
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
        },
    )
