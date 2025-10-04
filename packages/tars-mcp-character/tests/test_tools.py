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

    @pytest.mark.asyncio
    async def test_adjust_trait_valid_value(self, mock_mqtt_client, mock_env_vars):
        """Test adjusting a trait with a valid value."""            
        result = await adjust_personality_trait(trait_name="humor", new_value=50)
            
        assert result["success"] is True
        assert result["trait"] == "humor"
        assert result["new_value"] == 50
        assert "humor" in result["message"].lower()
        
        # Verify MQTT publish was called
        mock_mqtt_client.publish.assert_called_once()
        call_args = mock_mqtt_client.publish.call_args
        assert call_args[0][0] == "character/update"  # topic

    @pytest.mark.asyncio
    async def test_adjust_trait_min_value(self, mock_mqtt_client, mock_env_vars):
        """Test adjusting a trait to minimum value (0)."""           
        result = await adjust_personality_trait(trait_name="sarcasm", new_value=0)
        
        assert result["success"] is True
        assert result["trait"] == "sarcasm"
        assert result["new_value"] == 0

    @pytest.mark.asyncio
    async def test_adjust_trait_max_value(self, mock_mqtt_client, mock_env_vars):
        """Test adjusting a trait to maximum value (100)."""            
        result = await adjust_personality_trait(trait_name="curiosity", new_value=100)
        
        assert result["success"] is True
        assert result["trait"] == "curiosity"
        assert result["new_value"] == 100

    @pytest.mark.asyncio
    async def test_adjust_trait_value_too_low(self, mock_mqtt_client, mock_env_vars):
        """Test adjusting a trait with value below minimum."""            
        result = await adjust_personality_trait(trait_name="humor", new_value=-10)
        
        assert result["success"] is False
        assert "must be between 0-100" in result["error"]
        
        # Verify MQTT publish was NOT called
        mock_mqtt_client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_adjust_trait_value_too_high(self, mock_mqtt_client, mock_env_vars):
        """Test adjusting a trait with value above maximum."""            
        result = await adjust_personality_trait(trait_name="humor", new_value=150)
        
        assert result["success"] is False
        assert "must be between 0-100" in result["error"]
        
        # Verify MQTT publish was NOT called
        mock_mqtt_client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_adjust_trait_empty_name(self, mock_mqtt_client, mock_env_vars):
        """Test adjusting a trait with empty name."""
        result = await adjust_personality_trait(trait_name="", new_value=50)
        
        assert result["success"] is False
        assert "Unknown trait" in result["error"]
        assert "Valid traits:" in result["error"]
        
        # Verify MQTT publish was NOT called
        mock_mqtt_client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_adjust_trait_whitespace_name(self, mock_mqtt_client, mock_env_vars):
        """Test adjusting a trait with whitespace-only name."""
        result = await adjust_personality_trait(trait_name="   ", new_value=50)
        
        assert result["success"] is False
        assert "Unknown trait" in result["error"]
        assert "Valid traits:" in result["error"]

    @pytest.mark.asyncio
    async def test_adjust_trait_case_insensitive(self, mock_mqtt_client, mock_env_vars):
        """Test that trait names are handled case-insensitively."""            
        result = await adjust_personality_trait(trait_name="HUMOR", new_value=60)
        
        assert result["success"] is True
        assert result["trait"] == "humor"  # Should be normalized to lowercase

    @pytest.mark.asyncio
    async def test_adjust_trait_mqtt_publish_error(self, mock_mqtt_client, mock_env_vars):
        """Test handling of MQTT publish errors."""
        mock_mqtt_client.publish.side_effect = Exception("MQTT connection error")            
        result = await adjust_personality_trait(trait_name="humor", new_value=50)
            
        assert result["success"] is False
        assert "error" in result
        assert "MQTT" in result["error"] or "connection" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_adjust_trait_payload_structure(self, mock_mqtt_client, mock_env_vars):
        """Test that MQTT payload has correct Pydantic structure."""            
        await adjust_personality_trait(trait_name="curiosity", new_value=75)
        
        # Get the payload that was published
        call_args = mock_mqtt_client.publish.call_args
        payload_bytes = call_args[0][1]
    
        # Parse payload and verify structure
        import orjson
        from tars.contracts.envelope import Envelope
        
        envelope_data = orjson.loads(payload_bytes)
        
        # Verify envelope structure
        assert "type" in envelope_data
        assert envelope_data["type"] == "character.update"
        assert "data" in envelope_data
        
        # Verify data structure
        data = envelope_data["data"]
        assert data["section"] == "traits"
        assert data["trait"] == "curiosity"
        assert data["value"] == 75


class TestGetCurrentTraits:
    """Tests for get_current_traits tool."""

    @pytest.mark.asyncio
    async def test_get_traits_request_structure(self, mock_mqtt_client, mock_env_vars):
        """Test that get_current_traits publishes correct request."""           
        result = await get_current_traits()
            
        assert result["success"] is True
        assert "Trait query sent" in result["message"]
        
        # Verify MQTT publish was called
        mock_mqtt_client.publish.assert_called_once()
        call_args = mock_mqtt_client.publish.call_args
        assert call_args[0][0] == "character/get"  # topic

    @pytest.mark.asyncio
    async def test_get_traits_payload_structure(self, mock_mqtt_client, mock_env_vars):
        """Test that MQTT payload for get request has correct structure."""            
        await get_current_traits()
            
        # Get the payload that was published
        call_args = mock_mqtt_client.publish.call_args
        payload_bytes = call_args[0][1]
        
        import orjson
        envelope_data = orjson.loads(payload_bytes)
        
        # Verify envelope structure
        assert "type" in envelope_data
        assert envelope_data["type"] == "character.get"
        assert "data" in envelope_data

    @pytest.mark.asyncio
    async def test_get_traits_mqtt_error(self, mock_mqtt_client, mock_env_vars):
        """Test handling of MQTT publish errors during get request."""
        mock_mqtt_client.publish.side_effect = Exception("Connection lost")            
        result = await get_current_traits()
        
        assert result["success"] is False
        assert "error" in result


class TestResetAllTraits:
    """Tests for reset_all_traits tool."""

    @pytest.mark.asyncio
    async def test_reset_traits_request_structure(self, mock_mqtt_client, mock_env_vars):
        """Test that reset_all_traits publishes correct request."""            
        result = await reset_all_traits()
            
        assert result["success"] is True
        assert "reset" in result["message"].lower()
        
        # Verify MQTT publish was called
        mock_mqtt_client.publish.assert_called_once()
        call_args = mock_mqtt_client.publish.call_args
        assert call_args[0][0] == "character/update"  # topic

    @pytest.mark.asyncio
    async def test_reset_traits_payload_structure(self, mock_mqtt_client, mock_env_vars):
        """Test that MQTT payload for reset has correct structure."""            
        await reset_all_traits()
            
        # Get the payload that was published
        call_args = mock_mqtt_client.publish.call_args
        payload_bytes = call_args[0][1]
        
        import orjson
        from tars.contracts.envelope import Envelope
        
        envelope_data = orjson.loads(payload_bytes)
        
        # Verify envelope structure
        assert "type" in envelope_data
        assert envelope_data["type"] == "character.update"
        assert "data" in envelope_data
        
        # Verify data structure
        data = envelope_data["data"]
        assert data["action"] == "reset_traits"

    @pytest.mark.asyncio
    async def test_reset_traits_mqtt_error(self, mock_mqtt_client, mock_env_vars):
        """Test handling of MQTT publish errors during reset."""
        mock_mqtt_client.publish.side_effect = Exception("Network error")            
        result = await reset_all_traits()
            
        assert result["success"] is False
        assert "error" in result


class TestValidationEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("value", [0, 1, 25, 50, 75, 99, 100])
    async def test_all_valid_values(self, mock_mqtt_client, mock_env_vars, value):
        """Test all valid values from 0 to 100."""            
        result = await adjust_personality_trait(trait_name="humor", new_value=value)
        
        assert result["success"] is True
        assert result["new_value"] == value

    @pytest.mark.asyncio
    @pytest.mark.parametrize("value", [-1, -100, 101, 150, 1000])
    async def test_all_invalid_values(self, mock_mqtt_client, mock_env_vars, value):
        """Test various invalid values outside 0-100 range."""            
        result = await adjust_personality_trait(trait_name="humor", new_value=value)
            
        assert result["success"] is False
        assert "must be between 0-100" in result["error"]

    @pytest.mark.asyncio
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
    async def test_all_standard_traits(self, mock_mqtt_client, mock_env_vars, trait_name):
        """Test adjusting all standard TARS personality traits."""            
        result = await adjust_personality_trait(trait_name=trait_name, new_value=50)
        
        assert result["success"] is True
        assert result["trait"] == trait_name.lower()

    @pytest.mark.asyncio
    async def test_unicode_trait_name(self, mock_mqtt_client, mock_env_vars):
        """Test that unicode trait names are handled (rejected as invalid)."""            
        result = await adjust_personality_trait(trait_name="émotivité", new_value=50)
            
        assert result["success"] is False
        assert "Unknown trait" in result["error"]

    @pytest.mark.asyncio
    async def test_very_long_trait_name(self, mock_mqtt_client, mock_env_vars):
        """Test handling of very long trait names (rejected as invalid)."""
        long_name = "a" * 1000            
        result = await adjust_personality_trait(trait_name=long_name, new_value=50)
        
        assert result["success"] is False
        assert "Unknown trait" in result["error"]
