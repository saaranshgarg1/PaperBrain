from __future__ import annotations

from fastapi import Request

from paperbrain.api.container import Container


def get_container(request: Request) -> Container:
    return request.app.state.container
