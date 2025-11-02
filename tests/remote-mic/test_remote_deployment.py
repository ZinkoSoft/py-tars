"""
Test suite for remote microphone deployment configuration.

Validates that compose.remote-mic.yml is correctly structured and all
required services, volumes, and dependencies are properly configured.
"""

import os
import pytest
import yaml
from pathlib import Path


@pytest.fixture
def compose_file_path():
    """Path to remote microphone compose file."""
    repo_root = Path(__file__).parent.parent.parent
    return repo_root / "ops" / "compose.remote-mic.yml"


@pytest.fixture
def compose_config(compose_file_path):
    """Load and parse compose file."""
    with open(compose_file_path) as f:
        return yaml.safe_load(f)


def test_compose_file_exists(compose_file_path):
    """Verify compose.remote-mic.yml exists."""
    assert compose_file_path.exists(), f"Compose file not found: {compose_file_path}"


def test_compose_file_valid_yaml(compose_file_path):
    """Verify compose file is valid YAML."""
    with open(compose_file_path) as f:
        config = yaml.safe_load(f)
    assert config is not None, "Compose file is empty or invalid YAML"


def test_required_services_defined(compose_config):
    """Verify stt-worker and wake-activation services are defined."""
    services = compose_config.get("services", {})
    assert "stt" in services, "stt service not defined"
    assert "wake-activation" in services, "wake-activation service not defined"


def test_only_required_services(compose_config):
    """Verify only stt and wake-activation services are defined (no router, llm, tts, etc.)."""
    services = compose_config.get("services", {})
    assert len(services) == 2, f"Expected 2 services, found {len(services)}: {list(services.keys())}"
    assert set(services.keys()) == {"stt", "wake-activation"}, \
        f"Unexpected services: {services.keys()}"


def test_stt_service_configuration(compose_config):
    """Verify stt service has correct configuration."""
    stt = compose_config["services"]["stt"]
    
    # Build configuration
    assert "build" in stt, "stt service missing build config"
    assert stt["build"]["dockerfile"] == "docker/specialized/stt-worker.Dockerfile", \
        "stt service using wrong Dockerfile"
    
    # Environment variables
    env = stt.get("environment", {})
    assert "MQTT_HOST" in env, "stt missing MQTT_HOST"
    assert "MQTT_PORT" in env, "stt missing MQTT_PORT"
    assert "WHISPER_MODEL" in env, "stt missing WHISPER_MODEL"
    assert "AUDIO_FANOUT_PATH" in env, "stt missing AUDIO_FANOUT_PATH"
    
    # Healthcheck
    assert "healthcheck" in stt, "stt service missing healthcheck"
    assert "test" in stt["healthcheck"], "stt healthcheck missing test command"
    healthcheck_test = " ".join(stt["healthcheck"]["test"])
    assert "audio-fanout.sock" in healthcheck_test, \
        "stt healthcheck doesn't validate audio fanout socket"
    
    # Devices
    assert "devices" in stt, "stt service missing devices mapping"
    assert "/dev/snd:/dev/snd" in stt["devices"], \
        "stt service missing /dev/snd device mapping"
    
    # Volumes
    assert "volumes" in stt, "stt service missing volumes"
    volumes = stt["volumes"]
    assert any("wake-cache:/tmp/tars" in str(v) for v in volumes), \
        "stt service missing wake-cache volume mount"


def test_wake_activation_service_configuration(compose_config):
    """Verify wake-activation service has correct configuration."""
    wake = compose_config["services"]["wake-activation"]
    
    # Build configuration
    assert "build" in wake, "wake-activation service missing build config"
    assert wake["build"]["dockerfile"] == "docker/specialized/wake-activation.Dockerfile", \
        "wake-activation service using wrong Dockerfile"
    
    # Environment variables
    env = wake.get("environment", {})
    assert "MQTT_HOST" in env, "wake-activation missing MQTT_HOST"
    assert "MQTT_PORT" in env, "wake-activation missing MQTT_PORT"
    assert "WAKE_AUDIO_FANOUT" in env, "wake-activation missing WAKE_AUDIO_FANOUT"
    assert "WAKE_MODEL_PATH" in env, "wake-activation missing WAKE_MODEL_PATH"
    
    # Dependencies
    assert "depends_on" in wake, "wake-activation missing depends_on"
    assert "stt" in wake["depends_on"], "wake-activation doesn't depend on stt"
    
    # Verify stt dependency has health condition
    stt_dep = wake["depends_on"]["stt"]
    if isinstance(stt_dep, dict):
        assert stt_dep.get("condition") == "service_healthy", \
            "wake-activation should wait for stt to be healthy"
    
    # Volumes
    assert "volumes" in wake, "wake-activation service missing volumes"
    volumes = wake["volumes"]
    assert any("wake-cache:/tmp/tars" in str(v) for v in volumes), \
        "wake-activation service missing wake-cache volume mount"
    assert any("openwakeword" in str(v) for v in volumes), \
        "wake-activation service missing model volume mount"


def test_shared_volume_defined(compose_config):
    """Verify wake-cache volume is defined for audio fanout socket sharing."""
    volumes = compose_config.get("volumes", {})
    assert "wake-cache" in volumes, "wake-cache volume not defined"


def test_container_naming(compose_config):
    """Verify containers have appropriate names."""
    stt = compose_config["services"]["stt"]
    wake = compose_config["services"]["wake-activation"]
    
    assert stt.get("container_name") == "tars-stt-remote", \
        f"stt container name incorrect: {stt.get('container_name')}"
    assert wake.get("container_name") == "tars-wake-activation-remote", \
        f"wake-activation container name incorrect: {wake.get('container_name')}"


def test_mqtt_host_uses_env_var(compose_config):
    """Verify MQTT_HOST uses ${MQTT_HOST} from .env (not hardcoded)."""
    stt_env = compose_config["services"]["stt"]["environment"]
    wake_env = compose_config["services"]["wake-activation"]["environment"]
    
    # Check that MQTT_HOST references env var
    assert "${MQTT_HOST}" in str(stt_env["MQTT_HOST"]), \
        "stt MQTT_HOST should use ${MQTT_HOST} env var"
    assert "${MQTT_HOST}" in str(wake_env["MQTT_HOST"]), \
        "wake-activation MQTT_HOST should use ${MQTT_HOST} env var"


def test_restart_policy(compose_config):
    """Verify services have restart policy."""
    stt = compose_config["services"]["stt"]
    wake = compose_config["services"]["wake-activation"]
    
    assert stt.get("restart") == "unless-stopped", \
        "stt service should have 'unless-stopped' restart policy"
    assert wake.get("restart") == "unless-stopped", \
        "wake-activation service should have 'unless-stopped' restart policy"


def test_env_file_reference(compose_file_path):
    """Verify .env.remote-mic.example exists."""
    env_file = compose_file_path.parent / ".env.remote-mic.example"
    assert env_file.exists(), f"Example env file not found: {env_file}"


def test_env_example_has_required_vars():
    """Verify .env.remote-mic.example contains required variables."""
    repo_root = Path(__file__).parent.parent.parent
    env_file = repo_root / "ops" / ".env.remote-mic.example"
    
    with open(env_file) as f:
        env_content = f.read()
    
    required_vars = [
        "MQTT_HOST",
        "MQTT_PORT",
        "AUDIO_DEVICE_NAME",
        "WHISPER_MODEL",
        "WAKE_AUDIO_FANOUT",
        "WAKE_MODEL_PATH",
        "WAKE_DETECTION_THRESHOLD",
        "LOG_LEVEL",
    ]
    
    for var in required_vars:
        assert var in env_content, f"Required variable {var} not in .env.remote-mic.example"


def test_documentation_exists():
    """Verify REMOTE_MICROPHONE_SETUP.md documentation exists."""
    repo_root = Path(__file__).parent.parent.parent
    doc_file = repo_root / "docs" / "REMOTE_MICROPHONE_SETUP.md"
    assert doc_file.exists(), f"Documentation file not found: {doc_file}"


def test_documentation_sections():
    """Verify documentation has essential sections."""
    repo_root = Path(__file__).parent.parent.parent
    doc_file = repo_root / "docs" / "REMOTE_MICROPHONE_SETUP.md"
    
    with open(doc_file) as f:
        doc_content = f.read()
    
    required_sections = [
        "## Prerequisites",
        "## Quick Setup",
        "## Network Configuration",
        "## Troubleshooting",
        "## Verification",
    ]
    
    for section in required_sections:
        assert section in doc_content, f"Documentation missing section: {section}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
