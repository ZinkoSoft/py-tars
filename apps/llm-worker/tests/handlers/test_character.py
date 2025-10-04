"""Tests for CharacterManager."""
from __future__ import annotations

import pytest

from llm_worker.handlers.character import CharacterManager


@pytest.fixture
def character_mgr():
    """Create a CharacterManager instance."""
    return CharacterManager()


def test_initial_state(character_mgr):
    """Test initial state is empty."""
    assert character_mgr.character == {}
    assert character_mgr.get_name() is None


def test_get_name(character_mgr):
    """Test getting character name."""
    character_mgr.character = {"name": "TARS"}
    assert character_mgr.get_name() == "TARS"


def test_update_from_current_full_snapshot(character_mgr):
    """Test updating from full character snapshot."""
    data = {
        "name": "TARS",
        "description": "Tactical Assistant Robot System",
        "systemprompt": "You are TARS, a helpful robot.",
        "traits": {"humor": "90%", "honesty": "100%"},
        "voice": {"model": "en_US-male-medium"},
    }
    character_mgr.update_from_current(data)
    
    assert character_mgr.character == data
    assert character_mgr.get_name() == "TARS"


def test_update_section(character_mgr):
    """Test updating a single section."""
    character_mgr.character = {"name": "TARS"}
    character_mgr.update_section("traits", {"humor": "95%"})
    
    assert character_mgr.character["traits"] == {"humor": "95%"}
    assert character_mgr.character["name"] == "TARS"


def test_merge_update(character_mgr):
    """Test merging partial update."""
    character_mgr.character = {"name": "TARS", "description": "Robot"}
    character_mgr.merge_update({"traits": {"humor": "90%"}})
    
    assert character_mgr.character["name"] == "TARS"
    assert character_mgr.character["traits"] == {"humor": "90%"}
    assert character_mgr.character["description"] == "Robot"


def test_update_deprecated_full_snapshot(character_mgr):
    """Test deprecated update() with full snapshot (has 'name')."""
    data = {"name": "CASE", "description": "Another robot"}
    character_mgr.update(data)
    
    assert character_mgr.character == data


def test_update_deprecated_section(character_mgr):
    """Test deprecated update() with section update."""
    character_mgr.character = {"name": "TARS"}
    character_mgr.update({"section": "voice", "value": {"model": "en_US"}})
    
    assert character_mgr.character["voice"] == {"model": "en_US"}


def test_update_deprecated_partial(character_mgr):
    """Test deprecated update() with partial merge."""
    character_mgr.character = {"name": "TARS"}
    character_mgr.update({"description": "Updated robot"})
    
    assert character_mgr.character["name"] == "TARS"
    assert character_mgr.character["description"] == "Updated robot"


def test_build_system_prompt_no_character(character_mgr):
    """Test system prompt with no character loaded."""
    result = character_mgr.build_system_prompt()
    assert result is None
    
    result = character_mgr.build_system_prompt("Base system prompt")
    assert result == "Base system prompt"


def test_build_system_prompt_with_systemprompt(character_mgr):
    """Test system prompt when character has systemprompt."""
    character_mgr.character = {
        "name": "TARS",
        "systemprompt": "You are TARS, a helpful robot.",
        "traits": {"humor": "90%", "honesty": "100%"},
    }
    
    result = character_mgr.build_system_prompt()
    assert "You are TARS, a helpful robot." in result
    assert "You are TARS. Traits:" in result
    assert "humor: 90%" in result
    assert "honesty: 100%" in result


def test_build_system_prompt_with_systemprompt_and_description(character_mgr):
    """Test system prompt with systemprompt, traits, and description."""
    character_mgr.character = {
        "name": "TARS",
        "systemprompt": "Custom system prompt.",
        "traits": {"humor": "90%"},
        "description": "A tactical robot.",
    }
    
    result = character_mgr.build_system_prompt()
    assert "Custom system prompt." in result
    assert "You are TARS. Traits:" in result
    assert "A tactical robot." in result


def test_build_system_prompt_traits_only(character_mgr):
    """Test system prompt with traits but no systemprompt."""
    character_mgr.character = {
        "name": "TARS",
        "traits": {"humor": "90%", "honesty": "100%"},
    }
    
    result = character_mgr.build_system_prompt()
    assert result is not None
    assert "You are TARS. Traits:" in result
    assert "humor: 90%" in result
    assert "honesty: 100%" in result


def test_build_system_prompt_traits_and_description(character_mgr):
    """Test system prompt with traits and description."""
    character_mgr.character = {
        "name": "TARS",
        "traits": {"humor": "90%"},
        "description": "Tactical Assistant Robot System",
    }
    
    result = character_mgr.build_system_prompt()
    assert "You are TARS. Traits:" in result
    assert "humor: 90%" in result
    assert "Tactical Assistant Robot System" in result


def test_build_system_prompt_minimal(character_mgr):
    """Test system prompt with only name."""
    character_mgr.character = {"name": "TARS"}
    
    result = character_mgr.build_system_prompt()
    assert result is not None
    assert "You are TARS." in result


def test_build_system_prompt_with_base_system(character_mgr):
    """Test combining character prompt with base system prompt."""
    character_mgr.character = {
        "name": "TARS",
        "systemprompt": "You are TARS.",
        "traits": {"humor": "90%"},
    }
    
    result = character_mgr.build_system_prompt("Additional instructions.")
    assert "You are TARS." in result
    assert "Additional instructions." in result


def test_build_system_prompt_description_in_meta(character_mgr):
    """Test description fallback to meta.description."""
    character_mgr.character = {
        "name": "TARS",
        "meta": {"description": "Robot from meta"},
    }
    
    result = character_mgr.build_system_prompt()
    assert "You are TARS." in result
    assert "Robot from meta" in result


def test_build_system_prompt_default_name(character_mgr):
    """Test default name when name is missing."""
    character_mgr.character = {"traits": {"humor": "90%"}}
    
    result = character_mgr.build_system_prompt()
    assert "You are Assistant. Traits:" in result
