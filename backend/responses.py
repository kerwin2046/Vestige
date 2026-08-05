from __future__ import annotations

from typing import Any


def success(data: Any = None) -> dict[str, Any]:
    return {"code": 0, "message": "success", "data": data}

