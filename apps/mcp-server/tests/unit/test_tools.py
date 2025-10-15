"""Unit tests for MCP tool functions."""

from __future__ import annotations

import pytest

from tars_mcp_server.server import adjust_personality_trait, get_current_traits, reset_all_traits


@pytest.mark.asyncio
class TestAdjustPersonalityTrait:
    """Tests for adjust_personality_trait tool."""

    async def test_valid_trait_adjustment(self, mock_mqtt_context):
        """Test adjusting a valid trait with valid value."""
        result = await adjust_personality_trait(trait_name="humor", new_value=75)

        assert result["success"] is True
        assert result["trait"] == "humor"
        assert result["new_value"] == 75
        assert "adjusted to 75%" in result["message"]

        # Verify MQTT publish was called
        mock_mqtt_context.publish.assert_called_once()
        call_args = mock_mqtt_context.publish.call_args
        assert call_args[0][0] == "character/update"
        assert call_args[1]["qos"] == 1

    async def test_invalid_trait_value_too_low(self, mock_mqtt_context):
        """Test rejection of value below 0."""
        result = await adjust_personality_trait(trait_name="humor", new_value=-10)

        assert result["success"] is False
        assert "must be between 0-100" in result["error"]

        # Should not publish to MQTT
        mock_mqtt_context.publish.assert_not_called()

    async def test_invalid_trait_value_too_high(self, mock_mqtt_context):
        """Test rejection of value above 100."""
        result = await adjust_personality_trait(trait_name="humor", new_value=150)

        assert result["success"] is False
        assert "must be between 0-100" in result["error"]

        # Should not publish to MQTT
        mock_mqtt_context.publish.assert_not_called()

    async def test_unknown_trait_name(self, mock_mqtt_context):
        """Test rejection of unknown trait name."""
        result = await adjust_personality_trait(trait_name="invalid_trait", new_value=50)

        assert result["success"] is False
        assert "Unknown trait" in result["error"]
        assert "invalid_trait" in result["error"]

        # Should not publish to MQTT
        mock_mqtt_context.publish.assert_not_called()

    async def test_case_insensitive_trait_names(self, mock_mqtt_context):
        """Test that trait names are case-insensitive."""
        result = await adjust_personality_trait(trait_name="HUMOR", new_value=50)

        assert result["success"] is True
        assert result["trait"] == "humor"  # Normalized to lowercase

    async def test_boundary_values(self, mock_mqtt_context):
        """Test boundary values 0 and 100."""
        result_min = await adjust_personality_trait(trait_name="humor", new_value=0)
        assert result_min["success"] is True
        assert result_min["new_value"] == 0

        result_max = await adjust_personality_trait(trait_name="humor", new_value=100)
        assert result_max["success"] is True
        assert result_max["new_value"] == 100

    async def test_mqtt_publish_failure(self, mock_mqtt_context):
        """Test handling of MQTT publish failure."""
        mock_mqtt_context.publish.side_effect = Exception("Connection failed")

        result = await adjust_personality_trait(trait_name="humor", new_value=50)

        assert result["success"] is False
        assert "Failed to communicate" in result["error"]


@pytest.mark.asyncio
class TestGetCurrentTraits:
    """Tests for get_current_traits tool."""

    async def test_get_traits_success(self, mock_mqtt_context):
        """Test successful trait query."""
        result = await get_current_traits()

        assert result["success"] is True
        assert "Trait query sent" in result["message"]

        # Verify MQTT publish was called
        mock_mqtt_context.publish.assert_called_once()
        call_args = mock_mqtt_context.publish.call_args
        assert call_args[0][0] == "character/get"

    async def test_mqtt_failure(self, mock_mqtt_context):
        """Test handling of MQTT failure."""
        mock_mqtt_context.publish.side_effect = Exception("Connection failed")

        result = await get_current_traits()

        assert result["success"] is False
        assert "Failed to query traits" in result["error"]


@pytest.mark.asyncio
class TestResetAllTraits:
    """Tests for reset_all_traits tool."""

    async def test_reset_success(self, mock_mqtt_context):
        """Test successful trait reset."""
        result = await reset_all_traits()

        assert result["success"] is True
        assert "reset to default" in result["message"].lower()

        # Verify MQTT publish was called
        mock_mqtt_context.publish.assert_called_once()
        call_args = mock_mqtt_context.publish.call_args
        assert call_args[0][0] == "character/update"
        assert call_args[1]["qos"] == 1

    async def test_mqtt_failure(self, mock_mqtt_context):
        """Test handling of MQTT failure."""
        mock_mqtt_context.publish.side_effect = Exception("Connection failed")

        result = await reset_all_traits()

        assert result["success"] is False
        assert "Failed to reset traits" in result["error"]
