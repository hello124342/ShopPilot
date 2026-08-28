from pydantic import BaseModel

class RuntimeConfig(BaseModel):
    model_version: str = "deterministic-mock"
    prompt_version: str = "v1"
    scenario_version: str = "canonical-v1"
    fixture_version: str = "fixtures-v1"
    policy_version: str = "xiaohongshu-v1"
    side_effect_mode: str = "mock"
