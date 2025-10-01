from __future__ import annotations

from pathlib import Path

import pytest
from mcp import types

from mcp_bridge.servers.filesystem import FilesystemContext, build_server


@pytest.mark.asyncio
async def test_build_server_lists_tools(tmp_path: Path) -> None:
    ctx = FilesystemContext.from_root(str(tmp_path))
    server = build_server(ctx)
    list_handler = server.request_handlers[types.ListToolsRequest]
    result = await list_handler(types.ListToolsRequest())
    tools = result.root.tools  # type: ignore[attr-defined]
    names = {tool.name for tool in tools}
    assert {"read_file", "write_file", "list_dir"}.issubset(names)


def test_resolve_rejects_escape(tmp_path: Path) -> None:
    ctx = FilesystemContext.from_root(str(tmp_path))
    with pytest.raises(ValueError):
        ctx.resolve("../outside.txt")


def test_read_write_roundtrip(tmp_path: Path) -> None:
    ctx = FilesystemContext.from_root(str(tmp_path))
    ctx.write_file("folder/example.txt", "hello")
    assert ctx.read_file("folder/example.txt") == "hello"


def test_list_dir_returns_entries(tmp_path: Path) -> None:
    ctx = FilesystemContext.from_root(str(tmp_path))
    ctx.write_file("names.txt", "hi")
    entries = ctx.list_dir(".", recursive=False, include_hidden=False)
    assert any(entry["path"] == "names.txt" for entry in entries)
