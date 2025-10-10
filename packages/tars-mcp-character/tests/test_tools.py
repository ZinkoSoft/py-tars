"""Unit tests for TARS character management tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from tars_mcp_character.server import (
    adjust_personality_trait,
    get_current_traits,
    reset_all_traits,
)


class TestAdjustPersonalityTrait:
    """Tests for adjust_personality_trait tool."""

    def test_adjust_trait_valid_value(self, mock_mqtt_client, mock_env_vars):
        """Test adjusting a trait with a valid value."""            
        result = adjust_personality_trait(trait_name="humor", new_value=50)
            
        assert result["success"] is True
        assert result["trait"] == "humor"
        assert result["new_value"] == 50
        assert "humor" in result["message"].lower()
        
        # Verify mqtt_publish directive is returned (not actual MQTT call)
        assert "mqtt_publish" in result
        assert result["mqtt_publish"]["topic"] == "character/update"

    
    def test_adjust_trait_min_value(self, mock_mqtt_client, mock_env_vars):
        """Test adjusting a trait to minimum value (0)."""           
        result = adjust_personality_trait(trait_name="sarcasm", new_value=0)
        
        assert result["success"] is True
        assert result["trait"] == "sarcasm"
        assert result["new_value"] == 0

    
    def test_adjust_trait_max_value(self, mock_mqtt_client, mock_env_vars):
        """Test adjusting a trait to maximum value (100)."""            
        result = adjust_personality_trait(trait_name="curiosity", new_value=100)
        
        assert result["success"] is True
        assert result["trait"] == "curiosity"
        assert result["new_value"] == 100

    
    def test_adjust_trait_value_too_low(self, mock_mqtt_client, mock_env_vars):
        """Test adjusting a trait with value below minimum."""            
        result = adjust_personality_trait(trait_name="humor", new_value=-10)
        
        assert result["success"] is False
        assert "must be between 0-100" in result["error"]
        

    
    def test_adjust_trait_value_too_high(self, mock_mqtt_client, mock_env_vars):
        """Test adjusting a trait with value above maximum."""            
        result = adjust_personality_trait(trait_name="humor", new_value=150)
        
        assert result["success"] is False
        assert "must be between 0-100" in result["error"]
        

    
    def test_adjust_trait_empty_name(self, mock_mqtt_client, mock_env_vars):
        """Test adjusting a trait with empty name."""
        result = adjust_personality_trait(trait_name="", new_value=50)
        
        assert result["success"] is False
        assert "Unknown trait" in result["error"]
        assert "Valid traits:" in result["error"]
        

    
    def test_adjust_trait_whitespace_name(self, mock_mqtt_client, mock_env_vars):
        """Test adjusting a trait with whitespace-only name."""
        result = adjust_personality_trait(trait_name="   ", new_value=50)
        
        assert result["success"] is False
        assert "Unknown trait" in result["error"]
        assert "Valid traits:" in result["error"]

    
    def test_adjust_trait_case_insensitive(self, mock_mqtt_client, mock_env_vars):
        """Test that trait names are handled case-insensitively."""            
        result = adjust_personality_trait(trait_name="HUMOR", new_value=60)
        
        assert result["success"] is True
        assert result["trait"] == "humor"  # Should be normalized to lowercase

    
    def test_adjust_trait_returns_mqtt_directive(self, mock_mqtt_client, mock_env_vars):
        """Test that function returns mqtt_publish directive (not actual MQTT call)."""            
        result = adjust_personality_trait(trait_name="humor", new_value=50)
            
        # These are pure MCP tools - they return directives, not make MQTT calls
        assert result["success"] is True
        assert "mqtt_publish" in result
        assert result["mqtt_publish"]["event_type"] == "character.trait.update"

    
    def test_adjust_trait_payload_structure(self, mock_mqtt_client, mock_env_vars):
        """Test that mqtt_publish directive has correct structure."""            
        result = adjust_personality_trait(trait_name="curiosity", new_value=75)
        
        # Verify mqtt_publish directive structure (not actual MQTT payload)
        assert "mqtt_publish" in result
        mqtt_directive = result["mqtt_publish"]
        
        # Verify directive structure
        assert mqtt_directive["topic"] == "character/update"
        assert mqtt_directive["event_type"] == "character.trait.update"
        assert "data" in mqtt_directive
        
        # Verify data structure
        data = mqtt_directive["data"]
        assert data["trait"] == "curiosity"
        assert data["value"] == 75


class TestGetCurrentTraits:
    """Tests for get_current_traits tool."""

    
    def test_get_traits_request_structure(self, mock_mqtt_client, mock_env_vars):
        """Test that get_current_traits returns correct directive."""           
        result = get_current_traits()
            
        assert result["success"] is True
        assert "mqtt_publish" in result
        assert result["mqtt_publish"]["topic"] == "character/get"

    
    def test_get_traits_payload_structure(self, mock_mqtt_client, mock_env_vars):
        """Test that mqtt_publish directive for get request has correct structure."""            
        result = get_current_traits()
            
        # Verify mqtt_publish directive structure
        assert "mqtt_publish" in result
        mqtt_directive = result["mqtt_publish"]
        
        # Verify directive structure
        assert mqtt_directive["event_type"] == "character.get"
        assert "data" in mqtt_directive
        assert mqtt_directive["data"]["section"] == "traits"

    
    def test_get_traits_success(self, mock_mqtt_client, mock_env_vars):
        """Test that get_current_traits returns success."""
        result = get_current_traits()
        
        assert result["success"] is True
        assert "message" in result


class TestResetAllTraits:
    """Tests for reset_all_traits tool."""

    
    def test_reset_traits_request_structure(self, mock_mqtt_client, mock_env_vars):
        """Test that reset_all_traits returns correct directive."""            
        result = reset_all_traits()
            
        assert result["success"] is True
        assert "reset" in result["message"].lower()
        assert "mqtt_publish" in result

    
    def test_reset_traits_payload_structure(self, mock_mqtt_client, mock_env_vars):
        """Test that mqtt_publish directive for reset has correct structure."""            
        result = reset_all_traits()
            
        # Verify mqtt_publish directive structure
        assert "mqtt_publish" in result
        mqtt_directive = result["mqtt_publish"]
        
        # Verify directive structure
        assert mqtt_directive["topic"] == "character/update"
        assert mqtt_directive["event_type"] == "character.trait.reset"
        assert "data" in mqtt_directive
        
        # Verify data structure
        data = mqtt_directive["data"]
        assert data["reset_all"] is True

    
    def test_reset_traits_success(self, mock_mqtt_client, mock_env_vars):
        """Test that reset_all_traits returns success."""
        result = reset_all_traits()
            
        assert result["success"] is True
        assert "message" in result


class TestValidationEdgeCases:
    """Tests for edge cases and boundary conditions."""

    
    @pytest.mark.parametrize("value", [0, 1, 25, 50, 75, 99, 100])
    def test_all_valid_values(self, mock_mqtt_client, mock_env_vars, value):
        """Test all valid values from 0 to 100."""            
        result = adjust_personality_trait(trait_name="humor", new_value=value)
        
        assert result["success"] is True
        assert result["new_value"] == value

    
    @pytest.mark.parametrize("value", [-1, -100, 101, 150, 1000])
    def test_all_invalid_values(self, mock_mqtt_client, mock_env_vars, value):
        """Test various invalid values outside 0-100 range."""            
        result = adjust_personality_trait(trait_name="humor", new_value=value)
            
        assert result["success"] is False
        assert "must be between 0-100" in result["error"]

    
    @pytest.mark.parametrize("trait_name", [
        "humor",
        "formality",
        "honesty",
        "sarcasm",
        "curiosity",
        "empathy",
        "confidence",
        "adaptability",
    ])
    def test_all_standard_traits(self, mock_mqtt_client, mock_env_vars, trait_name):
        """Test adjusting all standard TARS personality traits."""            
        result = adjust_personality_trait(trait_name=trait_name, new_value=50)
        
        assert result["success"] is True
        assert result["trait"] == trait_name.lower()

    
    def test_unicode_trait_name(self, mock_mqtt_client, mock_env_vars):
        """Test that unicode trait names are handled (rejected as invalid)."""            
        result = adjust_personality_trait(trait_name="émotivité", new_value=50)
            
        assert result["success"] is False
        assert "Unknown trait" in result["error"]

    
    def test_very_long_trait_name(self, mock_mqtt_client, mock_env_vars):
        """Test handling of very long trait names (rejected as invalid)."""
        long_name = "a" * 1000            
        result = adjust_personality_trait(trait_name=long_name, new_value=50)
        
        assert result["success"] is False
        assert "Unknown trait" in result["error"]
