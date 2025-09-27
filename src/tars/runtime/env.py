from __future__ import annotations

import os
from typing import Iterable, Mapping, MutableMapping, Optional, TypeVar

EnvMapping = Mapping[str, str]
MutableEnvMapping = MutableMapping[str, str]

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _resolve_env(env: EnvMapping | MutableEnvMapping | None = None) -> EnvMapping:
    return env if env is not None else os.environ  # type: ignore[return-value]


def _first_value(name: str, *, env: EnvMapping | None, aliases: Iterable[str] | None) -> Optional[str]:
    mapping = _resolve_env(env)
    keys = (name, *aliases) if aliases else (name,)
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def get_str(
    name: str,
    default: str,
    *,
    env: EnvMapping | None = None,
    aliases: Iterable[str] | None = None,
) -> str:
    value = _first_value(name, env=env, aliases=aliases)
    if value is None:
        return default
    return value


def get_bool(
    name: str,
    default: bool,
    *,
    env: EnvMapping | None = None,
    aliases: Iterable[str] | None = None,
) -> bool:
    value = _first_value(name, env=env, aliases=aliases)
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    return default


def _convert_number(
    value: str,
    converter,
    default,
):
    try:
        return converter(value)
    except (TypeError, ValueError):
        return default


def get_int(
    name: str,
    default: int,
    *,
    env: EnvMapping | None = None,
    aliases: Iterable[str] | None = None,
) -> int:
    value = _first_value(name, env=env, aliases=aliases)
    if value is None:
        return default
    return _convert_number(value, int, default)


def get_float(
    name: str,
    default: float,
    *,
    env: EnvMapping | None = None,
    aliases: Iterable[str] | None = None,
) -> float:
    value = _first_value(name, env=env, aliases=aliases)
    if value is None:
        return default
    return _convert_number(value, float, default)


__all__ = [
    "EnvMapping",
    "MutableEnvMapping",
    "get_bool",
    "get_int",
    "get_float",
    "get_str",
]
