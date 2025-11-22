from typing import Literal

from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class ConsoleOutput(BaseModel):
    type: Literal["console"] = "console"
    format: str = "{timestamp} - {target_name} - {value}"


class FileOutput(BaseModel):
    type: Literal["file"] = "file"
    path: str
    format: str = "{timestamp} - {target_name} - {value}"
    max_bytes: int = 10485760
    backup_count: int = 5


class NatsOutput(BaseModel):
    type: Literal["nats"] = "nats"
    url: str
    subject: str
    format: str = "{timestamp} - {target_name} - {value}"


class PrometheusOutput(BaseModel):
    type: Literal["prometheus"] = "prometheus"
    url: str
    job: str
    format: str = "{timestamp} - {target_name} - {value}"


class APISettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class Settings(BaseSettings):
    model_config = SettingsConfigDict(yaml_file="config.yaml")
    # Single output configuration for now, can be expanded to list later if needed
    output: ConsoleOutput | FileOutput | NatsOutput | PrometheusOutput = ConsoleOutput()
    api: APISettings = APISettings()
    log_level: str = "INFO"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (YamlConfigSettingsSource(settings_cls),)


settings = Settings()
