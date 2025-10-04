"""Integration tests for TARS character MCP server.

These tests verify the full MCP protocol flow with a client.
"""

import pytest
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.integration
class TestMCPProtocolIntegration:
    """Integration tests for MCP protocol communication."""

    @pytest.mark.asyncio
    async def test_server_initialization(self):
        """Test that server can be initialized via stdio."""
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "tars_mcp_character"],
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize session
                init_result = await session.initialize()
                
                assert init_result is not None
                assert hasattr(init_result, "serverInfo")

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test listing all available tools."""
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "tars_mcp_character"],
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # List tools
                tools_result = await session.list_tools()
                tool_names = [t.name for t in tools_result.tools]
                
                # Verify all expected tools are present
                assert "adjust_personality_trait" in tool_names
                assert "get_current_traits" in tool_names
                assert "reset_all_traits" in tool_names
                assert len(tool_names) == 3

    @pytest.mark.asyncio
    async def test_tool_metadata(self):
        """Test that tool metadata is complete and correct."""
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "tars_mcp_character"],
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                tools_result = await session.list_tools()
                tools_by_name = {t.name: t for t in tools_result.tools}
                
                # Check adjust_personality_trait
                adjust_tool = tools_by_name["adjust_personality_trait"]
                assert adjust_tool.description is not None
                assert "trait" in adjust_tool.description.lower()
                assert adjust_tool.inputSchema is not None
                
                # Check get_current_traits
                get_tool = tools_by_name["get_current_traits"]
                assert get_tool.description is not None
                assert "retrieve" in get_tool.description.lower() or "get" in get_tool.description.lower()
                
                # Check reset_all_traits
                reset_tool = tools_by_name["reset_all_traits"]
                assert reset_tool.description is not None
                assert "reset" in reset_tool.description.lower()

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.config.getoption("--run-mqtt", default=False),
        reason="Requires running MQTT broker"
    )
    async def test_call_adjust_personality_trait(self):
        """Test calling adjust_personality_trait tool (requires MQTT broker)."""
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "tars_mcp_character"],
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Call the tool
                result = await session.call_tool(
                    "adjust_personality_trait",
                    arguments={"trait_name": "humor", "new_value": 50}
                )
                
                # Verify result structure
                assert result.content is not None
                assert len(result.content) > 0
                
                # Parse result
                result_text = result.content[0].text
                assert "humor" in result_text.lower()
                assert "50" in result_text

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.config.getoption("--run-mqtt", default=False),
        reason="Requires running MQTT broker"
    )
    async def test_call_get_current_traits(self):
        """Test calling get_current_traits tool (requires MQTT broker)."""
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "tars_mcp_character"],
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Call the tool
                result = await session.call_tool("get_current_traits", arguments={})
                
                # Verify result structure
                assert result.content is not None
                assert len(result.content) > 0

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.config.getoption("--run-mqtt", default=False),
        reason="Requires running MQTT broker"
    )
    async def test_call_reset_all_traits(self):
        """Test calling reset_all_traits tool (requires MQTT broker)."""
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "tars_mcp_character"],
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Call the tool
                result = await session.call_tool("reset_all_traits", arguments={})
                
                # Verify result structure
                assert result.content is not None
                assert len(result.content) > 0
                result_text = result.content[0].text
                assert "reset" in result_text.lower()

    @pytest.mark.asyncio
    async def test_invalid_tool_call(self):
        """Test calling a non-existent tool."""
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "tars_mcp_character"],
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Try to call invalid tool
                with pytest.raises(Exception):
                    await session.call_tool("nonexistent_tool", arguments={})

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self):
        """Test multiple sequential tool calls in same session."""
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "tars_mcp_character"],
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Call list_tools multiple times
                result1 = await session.list_tools()
                result2 = await session.list_tools()
                result3 = await session.list_tools()
                
                # All should succeed and return same tools
                assert len(result1.tools) == len(result2.tools) == len(result3.tools)


def pytest_addoption(parser):
    """Add custom pytest command-line options."""
    parser.addoption(
        "--run-mqtt",
        action="store_true",
        default=False,
        help="Run tests that require MQTT broker"
    )


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires full environment)"
    )
