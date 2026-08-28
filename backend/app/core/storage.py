"""对象存储适配器：支持 local / minio 两种模式

- STORAGE_TYPE=minio 且 MinIO 可用：上传到 MinIO 对象存储
- STORAGE_TYPE=local 或 MinIO 连接失败：自动回退本地磁盘

返回结构统一为 {storage_path, url, size, key}
"""
from __future__ import annotations

import io
import re
import uuid
from pathlib import Path
from typing import Dict, Optional

from fastapi import UploadFile

from app.core.config import settings

_local_root = Path(settings.LOCAL_STORAGE_DIR)
if not _local_root.is_absolute():
    _local_root = Path(__file__).resolve().parent.parent.parent / _local_root

_minio_client = None
_minio_ok: Optional[bool] = None


def _get_minio():
    """惰性创建 MinIO 客户端，连接失败后缓存不可用状态。"""
    global _minio_client, _minio_ok
    if _minio_ok is False:
        return None
    try:
        from minio import Minio  # noqa: PLC0415
    except ImportError:
        _minio_ok = False
        return None
    if _minio_client is None:
        try:
            client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
            if not client.bucket_exists(settings.MINIO_BUCKET):
                client.make_bucket(settings.MINIO_BUCKET)
            _minio_client = client
            _minio_ok = True
        except Exception:  # noqa: BLE001
            _minio_ok = False
            return None
    return _minio_client


def storage_mode() -> str:
    """返回实际生效的存储模式: minio / local"""
    mode = settings.STORAGE_TYPE.lower()
    if mode == "local":
        return "local"
    if mode == "minio":
        return "minio" if _get_minio() is not None else "local"
    # auto: 检测 MinIO 可用性
    return "minio" if _get_minio() is not None else "local"


def _safe_name(filename: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.\-\u4e00-\u9fa5]", "_", filename)


def _minio_url(key: str) -> str:
    scheme = "https" if settings.MINIO_SECURE else "http"
    return f"{scheme}://{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET}/{key}"


async def save_upload(
    file: UploadFile, sub_dir: str = "datasets", max_size: Optional[int] = None
) -> Dict:
    """保存上传文件到当前存储模式，返回统一结构

    - 分块读取，避免一次全量载入内存（max_size 超限时提前终止）
    - 超限抛出 ValueError
    """
    chunk_size = 8 * 1024 * 1024  # 8MB
    total = 0
    chunks = []
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if max_size is not None and total > max_size:
            raise ValueError(
                f"文件大小超过限制（{max_size // (1024 * 1024)}MB）"
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    return save_data(data, file.filename or "unknown", sub_dir)


def save_data(data: bytes, filename: str, sub_dir: str = "datasets") -> Dict:
    """保存原始字节到当前存储模式，返回统一结构 {storage_path, url, size, key}"""
    size = len(data)
    name = _safe_name(filename)
    key = f"{sub_dir}/{uuid.uuid4().hex}/{name}"

    if storage_mode() == "minio":
        client = _get_minio()
        assert client is not None
        client.put_object(
            settings.MINIO_BUCKET,
            key,
            io.BytesIO(data),
            size,
            content_type="application/octet-stream",
        )
        return {
            "storage_path": f"minio://{settings.MINIO_BUCKET}/{key}",
            "url": _minio_url(key),
            "size": size,
            "key": key,
        }

    target = _local_root / "uploads" / key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {
        "storage_path": str(target),
        "url": f"/static/uploads/{key}",
        "size": size,
        "key": key,
    }


def read_object(storage_path: str) -> Optional[bytes]:
    """按 storage_path 读取对象内容（minio:// 或本地绝对路径）"""
    try:
        if storage_path.startswith("minio://"):
            client = _get_minio()
            if client is None:
                return None
            bucket_key = storage_path[len("minio://"):]
            bucket, _, key = bucket_key.partition("/")
            resp = client.get_object(bucket, key)
            try:
                return resp.read()
            finally:
                resp.close()
                resp.release_conn()
        path = Path(storage_path)
        if path.exists() and path.is_file():
            return path.read_bytes()
    except Exception:  # noqa: BLE001
        return None
    return None


def iter_object_chunks(storage_path: str, chunk_size: int = 1024 * 1024):
    """按块迭代对象内容（minio:// 或本地绝对路径），用于流式统计行数等场景"""
    try:
        if storage_path.startswith("minio://"):
            client = _get_minio()
            if client is None:
                return
            bucket_key = storage_path[len("minio://"):]
            bucket, _, key = bucket_key.partition("/")
            resp = client.get_object(bucket, key)
            try:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                resp.close()
                resp.release_conn()
            return
        path = Path(storage_path)
        if path.exists() and path.is_file():
            with path.open("rb") as fh:
                while True:
                    chunk = fh.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
    except Exception:  # noqa: BLE001
        return


def delete_object(storage_path: str) -> bool:
    """按 storage_path 删除对象（minio:// 或本地绝对路径）"""
    try:
        if storage_path.startswith("minio://"):
            client = _get_minio()
            if client is None:
                return False
            bucket_key = storage_path[len("minio://"):]
            bucket, _, key = bucket_key.partition("/")
            client.remove_object(bucket, key)
            return True
        # 本地路径
        path = Path(storage_path)
        if path.exists() and path.is_file():
            path.unlink()
            return True
    except Exception:  # noqa: BLE001
        return False
    return False


def version_key(dataset_id: str, version_id: str) -> str:
    """版本目录对象 key（不含 bucket）：datasets/{dataset_id}/versions/{version_id}"""
    return f"datasets/{dataset_id}/versions/{version_id}"


def version_dir(dataset_id: str, version_id: str) -> str:
    """版本目录 storage_path（本地绝对路径 / minio 前缀），本地模式下自动创建目录"""
    key = version_key(dataset_id, version_id)
    if storage_mode() == "minio":
        return f"minio://{settings.MINIO_BUCKET}/{key}"
    target = _local_root / "uploads" / key
    target.mkdir(parents=True, exist_ok=True)
    return str(target)


def _split_minio(storage_path: str) -> tuple[str, str]:
    bucket_key = storage_path[len("minio://"):]
    bucket, _, key = bucket_key.partition("/")
    return bucket, key


def _copy_or_move(
    src_storage_path: str, dst_sub_dir: str, keep_src: bool
) -> str:
    """复制（keep_src=True）或移动（keep_src=False）对象到新子目录，返回新的 storage_path"""
    if src_storage_path.startswith("minio://"):
        client = _get_minio()
        if client is None:
            return src_storage_path
        bucket, key = _split_minio(src_storage_path)
        name = key.rsplit("/", 1)[-1]
        new_key = f"{dst_sub_dir}/{name}"
        try:
            from minio import CopySource  # noqa: PLC0415
            client.copy_object(bucket, new_key, copy_source=CopySource(bucket, key))
            if not keep_src:
                client.remove_object(bucket, key)
            return f"minio://{bucket}/{new_key}"
        except Exception:  # noqa: BLE001
            return src_storage_path
    path = Path(src_storage_path)
    if path.exists() and path.is_file():
        dst = _local_root / "uploads" / dst_sub_dir / path.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        import shutil  # noqa: PLC0415
        try:
            if keep_src:
                shutil.copy2(str(path), str(dst))
            else:
                shutil.move(str(path), str(dst))
            return str(dst)
        except Exception:  # noqa: BLE001
            return src_storage_path
    return src_storage_path


def move_object(src_storage_path: str, dst_sub_dir: str) -> str:
    """将对象移动到新子目录（保留文件名），返回新的 storage_path"""
    return _copy_or_move(src_storage_path, dst_sub_dir, keep_src=False)


def copy_object(src_storage_path: str, dst_sub_dir: str) -> str:
    """复制对象到新子目录（保留文件名，源保留），返回新的 storage_path"""
    return _copy_or_move(src_storage_path, dst_sub_dir, keep_src=True)


def delete_prefix(prefix: str) -> bool:
    """删除前缀目录下的所有对象（minio 遍历前缀 / 本地 rmtree）"""
    try:
        if storage_mode() == "minio":
            client = _get_minio()
            if client is None:
                return False
            objs = list(
                client.list_objects(settings.MINIO_BUCKET, prefix=prefix, recursive=True)
            )
            for obj in objs:
                client.remove_object(settings.MINIO_BUCKET, obj.object_name)
            return True
        target = _local_root / "uploads" / prefix
        if target.exists():
            import shutil  # noqa: PLC0415
            shutil.rmtree(target)
        return True
    except Exception:  # noqa: BLE001
        return False
