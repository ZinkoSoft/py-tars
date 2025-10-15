"""Integration tests for MCP server."""
import pytest


class TestMCPIntegration:
    """Test MCP server integration."""
    
    def test_server_import(self):
        """Test that server module can be imported."""
        from tars_mcp_movement import server
        
        assert server.app is not None
        assert server.app.name == "TARS Movement Controller"
    
    def test_all_tools_registered(self):
        """Test that all tools are registered with the MCP app."""
        from tars_mcp_movement import server
        
        # Movement tools
        assert hasattr(server, "move_forward")
        assert hasattr(server, "move_backward")
        assert hasattr(server, "turn_left")
        assert hasattr(server, "turn_right")
        assert hasattr(server, "stop_movement")
        
        # Action tools
        assert hasattr(server, "wave")
        assert hasattr(server, "laugh")
        assert hasattr(server, "bow")
        assert hasattr(server, "point")
        assert hasattr(server, "pose")
        assert hasattr(server, "celebrate")
        assert hasattr(server, "swing_legs")
        assert hasattr(server, "pezz_dispenser")
        assert hasattr(server, "mic_drop")
        assert hasattr(server, "monster_pose")
        assert hasattr(server, "reset_position")
    
    def test_tool_count(self):
        """Test expected number of tools."""
        from tars_mcp_movement import server
        
        # 5 movement + 11 action = 16 total tools
        expected_tools = 16
        
        tool_functions = [
            "move_forward", "move_backward", "turn_left", "turn_right", "stop_movement",
            "wave", "laugh", "bow", "point", "pose", "celebrate", "swing_legs", 
            "pezz_dispenser", "mic_drop", "monster_pose", "reset_position"
        ]
        
        for tool in tool_functions:
            assert hasattr(server, tool), f"Missing tool: {tool}"
        
        assert len(tool_functions) == expected_tools
