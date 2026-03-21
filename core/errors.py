from __future__ import annotations

from .schemas import ErrorResponse


def build_error(*, detail: str, code: str | None = None, request_id: str) -> ErrorResponse:
    return ErrorResponse(detail=detail, code=code, request_id=request_id)
