"""Pydantic models for configuration management."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from tars.config.types import ConfigComplexity, ConfigSource, ConfigType
from tars.config import validators


class ConfigFieldMetadata(BaseModel):
    """Metadata for a single configuration field."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., description="Unique config key (e.g., 'stt.whisper_model')")
    service: str = Field(..., description="Service name (e.g., 'stt-worker')")
    type: ConfigType = Field(..., description="Value type")
    complexity: ConfigComplexity = Field(default=ConfigComplexity.SIMPLE)
    description: str = Field(..., description="User-facing explanation")
    help_text: str = Field(default="", description="Detailed documentation")
    is_secret: bool = Field(default=False, description="Whether value should be masked")
    secret_source: ConfigSource | None = Field(None, description="Secret source (env/database)")
    validation_min: int | float | None = Field(None, description="Min value for numeric types")
    validation_max: int | float | None = Field(None, description="Max value for numeric types")
    validation_pattern: str | None = Field(None, description="Regex pattern for string types")
    validation_allowed: list[str] | None = Field(
        None, description="Allowed values for enum types"
    )


class ServiceConfig(BaseModel):
    """Complete configuration for a single service."""

    model_config = ConfigDict(extra="forbid")

    service: str = Field(..., description="Service name")
    config: dict[str, Any] = Field(..., description="Configuration key-value pairs")
    version: int = Field(default=1, description="Config version for optimistic locking")
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    config_epoch: str = Field(..., description="Database epoch identifier")


class ConfigItem(BaseModel):
    """Individual configuration key-value for search/history."""

    model_config = ConfigDict(extra="forbid")

    id: int | None = Field(None, description="Auto-increment primary key")
    service: str = Field(..., description="Service name")
    key: str = Field(..., description="Configuration key")
    value_json: str = Field(..., description="Value as JSON string")
    type: ConfigType = Field(..., description="Value type")
    complexity: ConfigComplexity = Field(...)
    description: str = Field(...)
    help_text: str = Field(default="")
    is_secret: bool = Field(default=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: str | None = Field(None, description="User identifier")


class SchemaVersion(BaseModel):
    """Schema version tracking for compatibility."""

    model_config = ConfigDict(extra="forbid")

    id: Literal[1] = 1  # Singleton record
    version: int = Field(..., description="Schema version number")
    model_hash: str = Field(..., description="SHA256 hash of Pydantic model schemas")
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ConfigEpochMetadata(BaseModel):
    """Database epoch for split-brain prevention."""

    model_config = ConfigDict(extra="forbid")

    config_epoch: str = Field(..., description="Unique epoch identifier (UUID)")
    schema_version: int = Field(..., description="Current schema version")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_rebuild: datetime | None = Field(None, description="Last rebuild timestamp")


class LKGCache(BaseModel):
    """Last-known-good cache structure."""

    model_config = ConfigDict(extra="forbid")

    payload: dict[str, dict[str, Any]] = Field(..., description="Service -> config mapping")
    config_epoch: str = Field(..., description="Epoch at cache generation")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    signature: str = Field(..., description="HMAC-SHA256 signature")
    algorithm: Literal["hmac-sha256"] = "hmac-sha256"


class ConfigProfile(BaseModel):
    """Named configuration profile for quick switching."""

    model_config = ConfigDict(extra="forbid")

    profile_name: str = Field(..., description="Unique profile name", min_length=1, max_length=100)
    description: str = Field(default="", description="Optional profile description")
    config_snapshot: dict[str, dict[str, Any]] = Field(..., description="Service -> config mapping")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = Field(None, description="User identifier")
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: str | None = Field(None, description="User identifier")


class ConfigHistory(BaseModel):
    """Configuration change history entry."""

    model_config = ConfigDict(extra="forbid")

    id: int | None = Field(None, description="Auto-increment ID")
    service: str = Field(..., description="Service name")
    key: str = Field(..., description="Configuration key that changed")
    old_value_json: str | None = Field(None, description="Previous value as JSON")
    new_value_json: str = Field(..., description="New value as JSON")
    changed_at: datetime = Field(default_factory=datetime.utcnow)
    changed_by: str | None = Field(None, description="User identifier")
    change_reason: str | None = Field(None, description="Optional reason for change")


# Service-Specific Configuration Models


class STTWorkerConfig(BaseModel):
    """Configuration for STT Worker service."""

    model_config = ConfigDict(extra="forbid")

    whisper_model: Literal["tiny", "tiny.en", "base", "base.en", "small", "small.en", "medium", "medium.en", "large", "large-v2", "large-v3"] = Field(
        default="base.en",
        description="Whisper model size (tiny, base, small, medium, large)",
        json_schema_extra={"complexity": "simple", "type": "enum"},
    )
    stt_backend: Literal["whisper", "ws", "openai"] = Field(
        default="whisper",
        description="STT backend (whisper=local, ws=WebSocket server, openai=OpenAI API)",
        json_schema_extra={"complexity": "simple", "type": "enum"},
    )
    ws_url: str | None = Field(
        None,
        pattern=r"^wss?://[^\s]+$",
        description="WebSocket backend URL (required if stt_backend=ws)",
        json_schema_extra={"complexity": "advanced", "type": "string"},
    )
    streaming_partials: bool = Field(
        default=False,
        description="Enable streaming partial transcriptions",
        json_schema_extra={"complexity": "advanced", "type": "boolean"},
    )
    vad_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Voice activity detection threshold (0.0-1.0)",
        json_schema_extra={"complexity": "advanced", "type": "float"},
    )
    vad_speech_pad_ms: int = Field(
        default=300,
        ge=0,
        le=1000,
        description="Speech padding in milliseconds",
        json_schema_extra={"complexity": "advanced", "type": "integer"},
    )
    vad_silence_duration_ms: int = Field(
        default=500,
        ge=0,
        le=2000,
        description="Silence duration before utterance end (ms)",
        json_schema_extra={"complexity": "advanced", "type": "integer"},
    )
    sample_rate: int = Field(
        default=16000,
        gt=0,
        description="Audio sample rate (Hz)",
        json_schema_extra={"complexity": "advanced", "type": "integer"},
    )
    channels: int = Field(
        default=1,
        ge=1,
        le=2,
        description="Audio channels (1=mono, 2=stereo)",
        json_schema_extra={"complexity": "advanced", "type": "integer"},
    )
    
    @field_validator("ws_url")
    @classmethod
    def validate_ws_url_format(cls, v: str | None) -> str | None:
        """Validate WebSocket URL format."""
        if v is not None:
            return validators.validate_ws_url(v)
        return v


class TTSWorkerConfig(BaseModel):
    """Configuration for TTS Worker service."""

    model_config = ConfigDict(extra="forbid")

    piper_voice: str = Field(
        default="en_US-lessac-medium",
        min_length=1,
        max_length=100,
        description="Piper voice model name",
        json_schema_extra={"complexity": "simple", "type": "string"},
    )
    tts_streaming: bool = Field(
        default=False,
        description="Enable streaming TTS output",
        json_schema_extra={"complexity": "advanced", "type": "boolean"},
    )
    tts_pipeline: bool = Field(
        default=True,
        description="Enable TTS pipeline processing",
        json_schema_extra={"complexity": "advanced", "type": "boolean"},
    )
    tts_aggregate_by_utt: bool = Field(
        default=True,
        description="Aggregate TTS output by utterance ID",
        json_schema_extra={"complexity": "advanced", "type": "boolean"},
    )
    tts_aggregate_timeout_sec: float = Field(
        default=2.0,
        ge=0.1,
        le=10.0,
        description="Timeout for utterance aggregation (seconds)",
        json_schema_extra={"complexity": "advanced", "type": "float"},
    )
    volume_percent: int = Field(
        default=100,
        ge=0,
        le=200,
        description="Output volume percentage (0-200%)",
        json_schema_extra={"complexity": "simple", "type": "integer"},
    )


class RouterConfig(BaseModel):
    """Configuration for Router service."""

    model_config = ConfigDict(extra="forbid")

    router_llm_tts_stream: bool = Field(
        default=True,
        description="Enable streaming from LLM to TTS",
        json_schema_extra={"complexity": "simple", "type": "boolean"},
    )
    router_stream_min_chars: int = Field(
        default=30,
        ge=1,
        le=500,
        description="Minimum characters before sending to TTS",
        json_schema_extra={"complexity": "advanced", "type": "integer"},
    )
    router_stream_max_chars: int = Field(
        default=200,
        ge=1,
        le=1000,
        description="Maximum characters before forcing flush to TTS",
        json_schema_extra={"complexity": "advanced", "type": "integer"},
    )
    router_stream_boundary_only: bool = Field(
        default=True,
        description="Only flush on sentence boundaries",
        json_schema_extra={"complexity": "advanced", "type": "boolean"},
    )
    router_stream_boundary_regex: str = Field(
        default=r"[.!?…]+[\"')\\]]?\\s",
        min_length=1,
        max_length=200,
        description="Regex pattern for sentence boundaries",
        json_schema_extra={"complexity": "advanced", "type": "string"},
    )
    
    @field_validator("router_stream_boundary_regex")
    @classmethod
    def validate_boundary_regex(cls, v: str) -> str:
        """Validate regex pattern for sentence boundaries."""
        return validators.validate_regex_pattern(v, "boundary regex")


class LLMWorkerConfig(BaseModel):
    """Configuration for LLM Worker service."""

    model_config = ConfigDict(extra="forbid")

    llm_provider: Literal["openai", "anthropic", "ollama"] = Field(
        default="openai",
        description="LLM provider (openai, anthropic, ollama)",
        json_schema_extra={"complexity": "simple", "type": "enum"},
    )
    openai_api_key: str | None = Field(
        None,
        min_length=10,
        description="OpenAI API key (secret)",
        json_schema_extra={"complexity": "simple", "type": "secret", "is_secret": True},
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        min_length=1,
        max_length=100,
        description="OpenAI model name",
        json_schema_extra={"complexity": "simple", "type": "string"},
    )
    rag_enabled: bool = Field(
        default=True,
        description="Enable Retrieval-Augmented Generation",
        json_schema_extra={"complexity": "simple", "type": "boolean"},
    )
    llm_timeout_sec: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="LLM request timeout (seconds)",
        json_schema_extra={"complexity": "advanced", "type": "float"},
    )
    
    @field_validator("openai_api_key")
    @classmethod
    def validate_api_key(cls, v: str | None) -> str | None:
        """Validate API key format (basic check)."""
        if v is not None and len(v) > 0:
            # Basic validation: should start with sk- for OpenAI keys
            if not (v.startswith("sk-") or v.startswith("OPENAI_")):
                # Allow placeholder values for configuration without actual keys
                if v not in ["placeholder", "your-api-key-here"]:
                    # Log warning but don't fail - key might be from another provider
                    pass
        return v


class MemoryWorkerConfig(BaseModel):
    """Configuration for Memory Worker service."""

    model_config = ConfigDict(extra="forbid")

    memory_dir: str = Field(
        default="/data/memory",
        min_length=1,
        max_length=500,
        description="Memory data directory path",
        json_schema_extra={"complexity": "advanced", "type": "path"},
    )
    memory_file: str = Field(
        default="memory.pickle.gz",
        min_length=1,
        max_length=255,
        pattern=r"^[\w\-\.]+$",
        description="Memory database filename",
        json_schema_extra={"complexity": "advanced", "type": "string"},
    )
    character_name: str = Field(
        default="TARS",
        min_length=1,
        max_length=50,
        description="Character/persona name",
        json_schema_extra={"complexity": "simple", "type": "string"},
    )
    character_dir: str = Field(
        default="/config/characters",
        min_length=1,
        max_length=500,
        description="Characters configuration directory",
        json_schema_extra={"complexity": "advanced", "type": "path"},
    )
    embed_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        min_length=1,
        max_length=200,
        description="Embedding model name",
        json_schema_extra={"complexity": "advanced", "type": "string"},
    )
    rag_strategy: Literal["hybrid", "semantic", "keyword"] = Field(
        default="hybrid",
        description="Retrieval strategy for RAG",
        json_schema_extra={"complexity": "simple", "type": "enum"},
    )
    memory_top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of top results to retrieve",
        json_schema_extra={"complexity": "advanced", "type": "integer"},
    )
    
    @field_validator("memory_dir", "character_dir")
    @classmethod
    def validate_directory_paths(cls, v: str) -> str:
        """Validate directory paths are absolute."""
        return validators.validate_absolute_path(v, "directory path")


class WakeActivationConfig(BaseModel):
    """Configuration for Wake Activation service."""

    model_config = ConfigDict(extra="forbid")

    wake_model_path: str = Field(
        default="/models/openwakeword/hey_tars.tflite",
        min_length=1,
        max_length=500,
        description="Path to wake word detection model",
        json_schema_extra={"complexity": "advanced", "type": "path"},
    )
    wake_detection_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Wake word detection confidence threshold (0.0-1.0)",
        json_schema_extra={"complexity": "simple", "type": "float"},
    )
    wake_min_retrigger_sec: float = Field(
        default=0.8,
        ge=0.1,
        le=5.0,
        description="Minimum time between wake word triggers (seconds)",
        json_schema_extra={"complexity": "advanced", "type": "float"},
    )
    wake_speex_noise_suppression: bool = Field(
        default=True,
        description="Enable Speex noise suppression",
        json_schema_extra={"complexity": "advanced", "type": "boolean"},
    )
    wake_vad_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Voice activity detection threshold (0.0-1.0)",
        json_schema_extra={"complexity": "advanced", "type": "float"},
    )
    wake_energy_boost_factor: float = Field(
        default=1.2,
        ge=0.5,
        le=3.0,
        description="Audio energy boost factor",
        json_schema_extra={"complexity": "advanced", "type": "float"},
    )
    
    @field_validator("wake_model_path")
    @classmethod
    def validate_model_path(cls, v: str) -> str:
        """Validate model path is absolute."""
        return validators.validate_absolute_path(v, "model path")

