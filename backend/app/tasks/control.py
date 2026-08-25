"""任务控制信号：暂停/取消指令的存取

优先使用 Redis（与 Celery worker 跨进程共享）；
Redis 不可用时回退到进程内字典（仅本地单进程场景可用）。
"""
from typing import Optional

from app.core.config import settings

try:
    import redis as _redis_module
except Exception:  # pragma: no cover
    _redis_module = None

_local_control: dict = {}
_redis_ok: Optional[bool] = None


def _get_client():
    """惰性创建 Redis 客户端，连接失败后缓存不可用状态。"""
    global _redis_ok
    if _redis_module is None or _redis_ok is False:
        return None
    if _redis_ok is None:
        try:
            client = _redis_module.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
            client.ping()
            _redis_ok = True
        except Exception:
            _redis_ok = False
            return None
    try:
        return _redis_module.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
    except Exception:
        return None


def _key(task_id: str) -> str:
    return f"train:control:{task_id}"


def set_control(task_id: str, action: str) -> None:
    """下发控制指令：pause / resume / cancel"""
    client = _get_client()
    if client is not None:
        try:
            client.set(_key(task_id), action, ex=86400)
            return
        except Exception:
            pass
    _local_control[task_id] = action


def get_control(task_id: str) -> Optional[str]:
    """读取当前控制指令"""
    client = _get_client()
    if client is not None:
        try:
            value = client.get(_key(task_id))
            if value:
                return value.decode("utf-8")
        except Exception:
            pass
    return _local_control.get(task_id)


def clear_control(task_id: str) -> None:
    """清除控制指令"""
    client = _get_client()
    if client is not None:
        try:
            client.delete(_key(task_id))
        except Exception:
            pass
    _local_control.pop(task_id, None)
