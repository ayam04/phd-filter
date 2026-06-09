from __future__ import annotations

import functools
import hashlib
import inspect
import json
from pathlib import Path

from .config import CACHE_DIR


def _key(args: tuple, kwargs: dict) -> str:
    blob = json.dumps([args, kwargs], sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def _path(namespace: str, key: str) -> Path:
    d = CACHE_DIR / namespace
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


def get(namespace: str, key: str):
    p = _path(namespace, key)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def put(namespace: str, key: str, value) -> None:
    _path(namespace, key).write_text(
        json.dumps(value, ensure_ascii=False), encoding="utf-8"
    )


def cached(namespace: str):
    def deco(fn):
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def awrapper(*args, **kwargs):
                k = _key(args, kwargs)
                p = _path(namespace, k)
                if p.exists():
                    return json.loads(p.read_text(encoding="utf-8"))
                val = await fn(*args, **kwargs)
                p.write_text(json.dumps(val, ensure_ascii=False), encoding="utf-8")
                return val

            return awrapper

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            k = _key(args, kwargs)
            p = _path(namespace, k)
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
            val = fn(*args, **kwargs)
            p.write_text(json.dumps(val, ensure_ascii=False), encoding="utf-8")
            return val

        return wrapper

    return deco
