from __future__ import annotations

from pathlib import Path
from typing import Any
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .runtime.providers import RuntimeMode, RuntimeSettings, SideEffectMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SHOPILOT_",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    app_name: str = "ShopPilot AI 运营工作台"
    environment: str = "development"
    runtime_mode: RuntimeMode = RuntimeMode.MOCK
    side_effect_mode: SideEffectMode = SideEffectMode.MOCK
    provider: str = "openai"
    model_id: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    api_key: SecretStr | None = None
    data_dir: Path = Path(".shopilot")
    retry_budget: int = Field(default=2, ge=0, le=10)
    provider_timeout: float = Field(default=60, gt=0, le=600)
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)

    @property
    def is_ready(self) -> bool:
        return self.runtime_mode == RuntimeMode.MOCK or bool(self.api_key and self.api_key.get_secret_value())

    @property
    def readiness_error(self) -> str | None:
        if self.runtime_mode == RuntimeMode.AGNO and not self.is_ready:
            return "agno_api_key_missing"
        return None

    def runtime_settings(self) -> RuntimeSettings:
        return RuntimeSettings(
            runtime_mode=self.runtime_mode,
            side_effect_mode=self.side_effect_mode,
            retry_budget=self.retry_budget,
            model_id=self.model_id,
            provider=self.provider,
            base_url=self.base_url,
            api_key=self.api_key.get_secret_value() if self.api_key else None,
            provider_timeout=self.provider_timeout,
        )

    def safe_diagnostics(self) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "runtime_mode": self.runtime_mode.value,
            "side_effect_mode": self.side_effect_mode.value,
            "provider": self.provider,
            "model_id": self.model_id,
            "base_url": self.base_url,
            "data_dir": str(self.data_dir),
            "api_key_configured": bool(self.api_key and self.api_key.get_secret_value()),
            "ready": self.is_ready,
            "readiness_error": self.readiness_error,
        }
