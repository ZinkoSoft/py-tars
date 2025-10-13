"""Tests for movement tool functions."""
import pytest

from tars_mcp_movement import server


class TestMovementTools:
    """Test movement control tools."""
    
    def test_move_forward_valid(self, mock_env):
        """Test move_forward with valid speed."""
        result = server.move_forward(speed=0.8)
        
        assert result["success"] is True
        assert "mqtt_publish" in result
        
        mqtt_data = result["mqtt_publish"]
        assert mqtt_data["topic"] == "movement/test"
        assert mqtt_data["event_type"] == "movement.command"
        assert mqtt_data["data"]["command"] == "step_forward"
        assert mqtt_data["data"]["speed"] == 0.8
        assert "request_id" in mqtt_data["data"]
    
    def test_move_backward_valid(self, mock_env):
        """Test move_backward with valid speed."""
        result = server.move_backward(speed=0.7)
        
        assert result["success"] is True
        assert result["mqtt_publish"]["data"]["command"] == "step_backward"
        assert result["mqtt_publish"]["data"]["speed"] == 0.7
    
    def test_turn_left_valid(self, mock_env):
        """Test turn_left with valid speed."""
        result = server.turn_left(speed=0.9)
        
        assert result["success"] is True
        assert result["mqtt_publish"]["data"]["command"] == "turn_left"
        assert result["mqtt_publish"]["data"]["speed"] == 0.9
    
    def test_turn_right_valid(self, mock_env):
        """Test turn_right with valid speed."""
        result = server.turn_right(speed=0.6)
        
        assert result["success"] is True
        assert result["mqtt_publish"]["data"]["command"] == "turn_right"
        assert result["mqtt_publish"]["data"]["speed"] == 0.6
    
    def test_stop_movement(self, mock_env):
        """Test emergency stop."""
        result = server.stop_movement()
        
        assert result["success"] is True
        assert result["mqtt_publish"]["topic"] == "movement/stop"
        assert result["mqtt_publish"]["event_type"] == "movement.stop"
        assert result["mqtt_publish"]["data"] == {}
    
    def test_invalid_speed_low(self, mock_env):
        """Test movement with speed too low."""
        result = server.move_forward(speed=0.05)
        
        assert result["success"] is False
        assert "error" in result
        assert "0.1-1.0" in result["error"]
    
    def test_invalid_speed_high(self, mock_env):
        """Test movement with speed too high."""
        result = server.turn_left(speed=1.5)
        
        assert result["success"] is False
        assert "error" in result
        assert "0.1-1.0" in result["error"]


class TestActionTools:
    """Test expressive action tools."""
    
    def test_wave_valid(self, mock_env):
        """Test wave gesture."""
        result = server.wave(speed=0.7)
        
        assert result["success"] is True
        assert result["mqtt_publish"]["data"]["command"] == "wave"
        assert result["mqtt_publish"]["data"]["speed"] == 0.7
    
    def test_laugh_valid(self, mock_env):
        """Test laugh animation."""
        result = server.laugh(speed=0.9)
        
        assert result["success"] is True
        assert result["mqtt_publish"]["data"]["command"] == "laugh"
        assert result["mqtt_publish"]["data"]["speed"] == 0.9
    
    def test_bow_valid(self, mock_env):
        """Test bow gesture."""
        result = server.bow(speed=0.5)
        
        assert result["success"] is True
        assert result["mqtt_publish"]["data"]["command"] == "bow"
        assert result["mqtt_publish"]["data"]["speed"] == 0.5
    
    def test_point_valid(self, mock_env):
        """Test point gesture (maps to 'now' in ESP32)."""
        result = server.point(speed=0.7)
        
        assert result["success"] is True
        assert result["mqtt_publish"]["data"]["command"] == "now"
        assert result["mqtt_publish"]["data"]["speed"] == 0.7
    
    def test_pose_valid(self, mock_env):
        """Test pose action."""
        result = server.pose(speed=0.6)
        
        assert result["success"] is True
        assert result["mqtt_publish"]["data"]["command"] == "pose"
        assert result["mqtt_publish"]["data"]["speed"] == 0.6
    
    def test_celebrate_valid(self, mock_env):
        """Test celebrate action (maps to 'balance' in ESP32)."""
        result = server.celebrate(speed=0.8)
        
        assert result["success"] is True
        assert result["mqtt_publish"]["data"]["command"] == "balance"
        assert result["mqtt_publish"]["data"]["speed"] == 0.8
    
    def test_swing_legs_valid(self, mock_env):
        """Test swing_legs action."""
        result = server.swing_legs(speed=0.6)
        
        assert result["success"] is True
        assert result["mqtt_publish"]["data"]["command"] == "swing_legs"
        assert result["mqtt_publish"]["data"]["speed"] == 0.6
    
    def test_reset_position_valid(self, mock_env):
        """Test reset to neutral position."""
        result = server.reset_position(speed=0.8)
        
        assert result["success"] is True
        assert result["mqtt_publish"]["data"]["command"] == "reset"
        assert result["mqtt_publish"]["data"]["speed"] == 0.8
    
    def test_action_invalid_speed(self, mock_env):
        """Test action with invalid speed."""
        result = server.wave(speed=2.0)
        
        assert result["success"] is False
        assert "error" in result


class TestReturnStructure:
    """Test return value structure and contracts."""
    
    def test_mqtt_publish_structure(self, mock_env):
        """Test mqtt_publish field has required structure."""
        result = server.wave(speed=0.7)
        
        mqtt_pub = result["mqtt_publish"]
        
        # Required fields
        assert "topic" in mqtt_pub
        assert "event_type" in mqtt_pub
        assert "data" in mqtt_pub
        assert "source" in mqtt_pub
        
        # Source should be mcp-movement
        assert mqtt_pub["source"] == "mcp-movement"
        
        # Data should have command and speed
        assert "command" in mqtt_pub["data"]
        assert "speed" in mqtt_pub["data"]
        assert "request_id" in mqtt_pub["data"]
    
    def test_request_id_uniqueness(self, mock_env):
        """Test that request_ids are unique."""
        result1 = server.wave(speed=0.7)
        result2 = server.wave(speed=0.7)
        
        req_id1 = result1["mqtt_publish"]["data"]["request_id"]
        req_id2 = result2["mqtt_publish"]["data"]["request_id"]
        
        assert req_id1 != req_id2
    
    def test_error_no_mqtt_publish(self, mock_env):
        """Test that errors don't include mqtt_publish field."""
        result = server.move_forward(speed=5.0)
        
        assert result["success"] is False
        assert "mqtt_publish" not in result
        assert "error" in result
