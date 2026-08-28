from enum import StrEnum
from pydantic import BaseModel

class RuntimeMode(StrEnum):
    MOCK = "mock"
    AGNO = "agno"

class SideEffectMode(StrEnum):
    DISABLED = "disabled"
    MOCK = "mock"
    REAL = "real"

class RuntimeSettings(BaseModel):
    runtime_mode: RuntimeMode = RuntimeMode.MOCK
    side_effect_mode: SideEffectMode = SideEffectMode.MOCK
    retry_budget: int = 2
    model_id: str | None = None
    provider: str = "openai"
    base_url: str | None = None
    api_key: str | None = None
    provider_timeout: float = 60
