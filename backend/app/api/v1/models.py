"""模型中心 API"""
import io
import uuid
import zipfile
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.response import success_response
from app.core.storage import read_object, save_upload, delete_object
from app.services.model_service import ModelService
from app.schemas.model import (
    ModelCreate, ModelUpdate, ModelCompareReq,
    ModelVersionCreate, ModelVersionUpdate, ModelFileCreate,
)

router = APIRouter()


def _file_type(file_name: str) -> str:
    """根据扩展名推导文件类型"""
    ext = Path(file_name).suffix.lower().lstrip(".")
    known = {"safetensors": "safetensors", "bin": "bin", "json": "json", "txt": "txt", "gguf": "gguf", "onnx": "onnx"}
    return known.get(ext, "other")


def _cleanup_storage(files) -> None:
    """删除文件的存储对象，清理失败不影响主流程"""
    for f in files:
        path = f.get("filePath")
        if path:
            try:
                delete_object(path)
            except Exception:  # noqa: BLE001
                pass


# ========== 广场（静态路由放在动态路由前） ==========
@router.get("/plaza/search")
async def plaza_models(
    page_index: int = Query(1, ge=1, alias="pageIndex"),
    page_size: int = Query(12, ge=1, le=9999, alias="pageSize"),
    keyword: str = Query(None),
    type: str = Query(None),
    spec: str = Query(None),
    vendor: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    result = await svc.list_plaza_models(
        page_index=page_index, page_size=page_size,
        keyword=keyword, type=type, spec=spec, vendor=vendor,
    )
    return success_response(result)


# ========== 统计 ==========
@router.get("/stats/summary")
async def model_stats(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    result = await svc.get_model_stats(owner_id=user["id"])
    return success_response(result)


# ========== 模型对比 ==========
@router.post("/compare")
async def compare_models(
    data: ModelCompareReq,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    result = await svc.compare_models(data.modelIds)
    return success_response(result)


# ========== 版本（静态路由放在动态路由前） ==========
@router.get("/versions/{version_id}")
async def get_version(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    result = await svc.get_version(version_id)
    if not result:
        raise HTTPException(status_code=404, detail="版本不存在")
    return success_response(result)


@router.delete("/versions/{version_id}")
async def delete_version(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    _cleanup_storage(await svc.list_files(version_id))
    ok = await svc.delete_version(version_id)
    if not ok:
        raise HTTPException(status_code=404, detail="版本不存在")
    return success_response({"message": "删除成功"})


# ========== 模型文件（静态路由放在动态路由前） ==========
@router.get("/versions/{version_id}/files")
async def list_files(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    result = await svc.list_files(version_id)
    return success_response(result)


@router.post("/versions/{version_id}/files")
async def create_file(
    version_id: str,
    data: ModelFileCreate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    result = await svc.create_file(version_id, data.model_dump())
    return success_response(result)


@router.post("/versions/{version_id}/files/upload")
async def upload_file(
    version_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """上传单个模型文件（真实落盘到对象存储/本地）"""
    svc = ModelService(db)
    ver = await svc.get_version(version_id)
    if not ver:
        raise HTTPException(status_code=404, detail="版本不存在")
    file_name = file.filename or "unknown"
    try:
        saved = await save_upload(
            file,
            sub_dir=f"models/{ver['modelId']}/{version_id}",
            max_size=settings.MODEL_UPLOAD_MAX_SIZE_MB * 1024 * 1024,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    result = await svc.create_file(version_id, {
        "fileName": file_name,
        "filePath": saved["storage_path"],
        "fileSize": saved["size"],
        "fileType": _file_type(file_name),
        "status": "ready",
    })
    return success_response({**result, "url": saved["url"]})


@router.post("/versions/{version_id}/files/upload-batch")
async def upload_files_batch(
    version_id: str,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """批量上传模型文件（真实落盘，逐个结果上报）"""
    svc = ModelService(db)
    ver = await svc.get_version(version_id)
    if not ver:
        raise HTTPException(status_code=404, detail="版本不存在")
    if not files:
        raise HTTPException(status_code=400, detail="未选择任何文件")
    if len(files) > settings.MODEL_UPLOAD_MAX_FILES_PER_BATCH:
        raise HTTPException(status_code=400, detail=f"单次最多上传 {settings.MODEL_UPLOAD_MAX_FILES_PER_BATCH} 个文件")

    sub_dir = f"models/{ver['modelId']}/{version_id}"
    max_size = settings.MODEL_UPLOAD_MAX_SIZE_MB * 1024 * 1024
    results = []
    seen_names = set()
    for file in files:
        file_name = file.filename or "unknown"
        if file_name in seen_names:
            results.append({"fileName": file_name, "status": "failed", "errorMessage": "同批次内文件名重复"})
            continue
        seen_names.add(file_name)
        try:
            saved = await save_upload(file, sub_dir=sub_dir, max_size=max_size)
            created = await svc.create_file(version_id, {
                "fileName": file_name,
                "filePath": saved["storage_path"],
                "fileSize": saved["size"],
                "fileType": _file_type(file_name),
                "status": "ready",
            })
            results.append({"id": created.get("id"), "fileName": file_name, "status": "success", "size": saved["size"]})
        except ValueError as e:
            results.append({"fileName": file_name, "status": "failed", "errorMessage": str(e)})
        except Exception:  # noqa: BLE001
            results.append({"fileName": file_name, "status": "failed", "errorMessage": "文件处理失败"})

    return success_response({"batchId": uuid.uuid4().hex, "source": "local_upload", "files": results})


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    f = await svc.get_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="文件不存在")
    _cleanup_storage([f])
    ok = await svc.delete_file(file_id)
    if not ok:
        raise HTTPException(status_code=404, detail="文件不存在")
    return success_response({"message": "删除成功"})


@router.get("/versions/{version_id}/files/{file_id}/download")
async def download_file(
    version_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """下载模型版本下的单个文件"""
    svc = ModelService(db)
    files = await svc.list_files(version_id)
    f = next((x for x in files if x["id"] == file_id), None)
    if not f:
        raise HTTPException(status_code=404, detail="文件不存在")
    storage_path = f.get("filePath")
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


@router.get("/versions/{version_id}/download")
async def download_version_files(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """下载版本的全部文件：单文件直接返回，多文件打包 zip"""
    svc = ModelService(db)
    ver = await svc.get_version(version_id)
    if not ver:
        raise HTTPException(status_code=404, detail="版本不存在")
    files = await svc.list_files(version_id)
    if not files:
        raise HTTPException(status_code=404, detail="该版本暂无文件可下载")

    # 单个文件直接返回
    if len(files) == 1:
        f = files[0]
        data = read_object(f.get("filePath") or "")
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
            data = read_object(f.get("filePath") or "")
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

    filename = quote(f"{ver['version']}_files.zip")
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


# ========== 模型主表（动态路由放在后面） ==========
@router.get("")
async def list_models(
    page_index: int = Query(1, ge=1, alias="pageIndex"),
    page_size: int = Query(12, ge=1, le=9999, alias="pageSize"),
    keyword: str = Query(None),
    type: str = Query(None),
    spec: str = Query(None),
    vendor: str = Query(None),
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    result = await svc.list_models(
        page_index=page_index, page_size=page_size,
        keyword=keyword, type=type, spec=spec, vendor=vendor, status=status,
        owner_id=user["id"],
    )
    return success_response(result)


@router.get("/{model_id}")
async def get_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    result = await svc.get_model(model_id)
    if not result:
        raise HTTPException(status_code=404, detail="模型不存在")
    return success_response(result)


@router.post("")
async def create_model(
    data: ModelCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    result = await svc.create_model(data.model_dump(), owner_id=user["id"])
    return success_response(result)


@router.put("/{model_id}")
async def update_model(
    model_id: str,
    data: ModelUpdate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    result = await svc.update_model(model_id, data.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="模型不存在")
    return success_response(result)


@router.delete("/{model_id}")
async def delete_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    for v in await svc.list_versions(model_id):
        _cleanup_storage(await svc.list_files(v["id"]))
    ok = await svc.delete_model(model_id)
    if not ok:
        raise HTTPException(status_code=404, detail="模型不存在")
    return success_response({"message": "删除成功"})


@router.post("/{model_id}/import")
async def import_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    result = await svc.import_model(model_id, owner_id=user["id"])
    if not result:
        raise HTTPException(status_code=404, detail="模型不存在")
    return success_response(result)


# ========== 版本（动态路由） ==========
@router.get("/{model_id}/versions")
async def list_versions(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    result = await svc.list_versions(model_id)
    return success_response(result)


@router.post("/{model_id}/versions")
async def create_version(
    model_id: str,
    data: ModelVersionCreate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    result = await svc.create_version(model_id, data.model_dump())
    if not result:
        raise HTTPException(status_code=404, detail="模型不存在")
    return success_response(result)


@router.put("/{model_id}/versions/{version_id}")
async def update_version(
    model_id: str,
    version_id: str,
    data: ModelVersionUpdate,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    result = await svc.update_version(version_id, data.model_dump(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="版本不存在")
    return success_response(result)


@router.put("/{model_id}/versions/{version_id}/default")
async def set_default_version(
    model_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    svc = ModelService(db)
    ok = await svc.set_default_version(model_id, version_id)
    return success_response({"message": "设置成功"})
