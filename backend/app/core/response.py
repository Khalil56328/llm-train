"""统一响应模型"""
from typing import Any, Optional, TypeVar, Generic
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: Optional[T] = None


class PaginatedData(BaseModel, Generic[T]):
    list: list[T]
    total: int
    pageIndex: int
    pageSize: int


def success_response(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def error_response(code: int = 1, message: str = "error") -> dict:
    return {"code": code, "message": message, "data": None}


def paginated_response(list_data: list, total: int, page: int, size: int) -> dict:
    return success_response({
        "list": list_data,
        "total": total,
        "pageIndex": page,
        "pageSize": size,
    })
