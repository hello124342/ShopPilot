from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from agno.agent import Agent
from agno.team import Team
from agno.workflow import Step, Workflow
from agno.workflow.types import StepOutput
from agno.models.openai import OpenAIChat

from ..schemas import CampaignBrief, ComplianceReport, CreativePackage, OptimizationBrief, PerformanceReport, ResearchPackage
from .errors import ProviderError
from .providers import RuntimeSettings

@dataclass(frozen=True)
class AgnoComponents:
    agents: dict[str, Agent]
    research_team: Team
    campaign_workflow: Workflow

class AgnoRuntimeFactory:
    """Creates Agno primitives; ShopPilot retains only domain contracts and tools."""
    @staticmethod
    def _agent(name: str, role: str, output_schema: type | None = None, model: Any = None) -> Agent:
        return Agent(name=name, role=role, model=model, instructions=["只使用提供的证据", "输出必须符合结构化契约"], output_schema=output_schema, telemetry=False)

    def build_model(self, settings: RuntimeSettings) -> OpenAIChat:
        if settings.provider.lower() not in {"openai", "openai-compatible"}:
            raise ProviderError("provider_unsupported", f"不支持的模型 provider: {settings.provider}")
        if not settings.api_key:
            raise ProviderError("agno_api_key_missing", "Agno 模式需要 SHOPILOT_API_KEY")
        return OpenAIChat(
            id=settings.model_id or "gpt-4o-mini",
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=settings.provider_timeout,
            max_retries=settings.retry_budget,
        )

    def build_from_settings(self, settings: RuntimeSettings) -> AgnoComponents:
        return self.build(self.build_model(settings))

    def provider_metadata(self, settings: RuntimeSettings) -> dict[str, str]:
        return {"framework": "agno", "provider": settings.provider, "model_id": settings.model_id or "unknown"}

    def build(self, model: Any = None) -> AgnoComponents:
        agents = {
            "product": self._agent("Product Analyst", "提取商品事实", ResearchPackage, model),
            "competitor": self._agent("Competitor Analyst", "分析竞品表达", ResearchPackage, model),
            "audience": self._agent("Audience Analyst", "分析目标人群", ResearchPackage, model),
            "trend": self._agent("Trend Analyst", "分析平台趋势", ResearchPackage, model),
            "evidence": self._agent("Evidence Reviewer", "核验来源与冲突", ResearchPackage, model),
            "strategy": self._agent("Strategy Agent", "生成营销策略", CampaignBrief, model),
            "creative": self._agent("Creative Agent", "生成多模态创意", CreativePackage, model),
            "compliance": self._agent("Compliance Agent", "依据确定性规则解释风险并给出修改建议", ComplianceReport, model),
            "analytics": self._agent("Analytics Agent", "解释确定性指标", PerformanceReport, model),
            "optimization": self._agent("Optimization Agent", "生成下一轮实验", OptimizationBrief, model),
        }
        team = Team(
            name="ShopPilot Research Team",
            members=[agents[k] for k in ("product", "competitor", "audience", "trend", "evidence")],
            model=model,
            instructions=["并行研究后由 Evidence Reviewer 汇总", "不得静默消解证据冲突"],
            output_schema=ResearchPackage,
            telemetry=False,
        )

        def runtime_smoke(_: Any) -> StepOutput:
            return StepOutput(step_name="runtime-smoke", content={"framework": "agno", "ready": True})

        workflow = Workflow(
            name="ShopPilot Campaign Workflow",
            steps=[Step(name="runtime-smoke", executor=runtime_smoke)],
            input_schema=dict,
            telemetry=False,
        )
        return AgnoComponents(agents=agents, research_team=team, campaign_workflow=workflow)
