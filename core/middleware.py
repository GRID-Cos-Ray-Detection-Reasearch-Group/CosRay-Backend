from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol
from typing import cast
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest
    from django.http import HttpResponse


class _HasRequestId(Protocol):
    request_id: str


class RequestIdMiddleware:
    header_name = "X-Request-Id"
    meta_key = "HTTP_X_REQUEST_ID"

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.META.get(self.meta_key, "")
        request_id = incoming.strip() if isinstance(incoming, str) else ""
        if not request_id:
            request_id = uuid4().hex

        cast("_HasRequestId", request).request_id = request_id
        response = self.get_response(request)
        response[self.header_name] = request_id
        return response
