from fastapi import Header
from typing import Optional
from pydantic import BaseModel


class ApiResponse(BaseModel):
    code: int
    message: str
    data: Optional[dict] = None


def success(data=None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def error(message: str, code: int = 1) -> dict:
    return {"code": code, "message": message}


def get_current_user_id(x_user_id: Optional[str] = Header(None)) -> str:
    return x_user_id or "u1"
