import uuid
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class TargetCreate(BaseModel):
    """Schema for creating a new target."""

    name: str
    interval: int
    timeout: int

    # interval should be greater than timeout
    @model_validator(mode="after")
    def check_interval(self):
        if self.interval < self.timeout:
            raise ValueError("Interval must be equal to or greater than timeout")
        return self


class Target(TargetCreate):
    """Internal representation of a target with ID."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)


class TargetStatus(BaseModel):
    """Status of a monitoring target."""

    last_check: float | None = None
    last_value: int | None = None
    check_count: int = 0
    error_count: int = 0


class TargetWithStatus(Target):
    """Target with its current status."""

    status: TargetStatus = Field(default_factory=TargetStatus)


class TargetResult(BaseModel):
    target_id: uuid.UUID
    value: int
    # Optional metadata if needed downstream
    timestamp: float = Field(default_factory=lambda: 0.0)


class SystemStats(BaseModel):
    """Statistics about the monitoring system."""

    active_targets: int
    processed_messages: int
    uptime_seconds: float
    queue_size: int = 0
    total_errors: int = 0


class OutputConfig(BaseModel):
    """Configuration for output handling."""

    type: Literal["console", "file"] = "console"

    # File output settings (only used when type is "file")
    file_path: str | None = None
    file_format: str = "{timestamp} - {target_name} - {value}"
    file_max_bytes: int = 10 * 1024 * 1024  # 10MB
    file_backup_count: int = 5

    @model_validator(mode="after")
    def validate_file_output(self):
        """Ensure file_path is provided when type is 'file'."""
        if self.type == "file" and not self.file_path:
            raise ValueError("file_path must be provided when output type is 'file'")
        return self
