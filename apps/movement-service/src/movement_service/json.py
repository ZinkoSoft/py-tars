from __future__ import annotations

from typing import Any

import orjson


def dumps(obj: Any) -> bytes:
    return orjson.dumps(
        obj,
        option=orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_SORT_KEYS,
    )


def loads(data: bytes) -> Any:
    return orjson.loads(data)
