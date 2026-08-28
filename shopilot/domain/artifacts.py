from .schemas import Artifact

REQUIRED_CAMPAIGN_ARTIFACTS = {
    "ResearchPackage", "CampaignBrief", "CreativePackage",
    "PlatformPayload", "ComplianceReport",
}
COMPLETED_CAMPAIGN_ARTIFACTS = REQUIRED_CAMPAIGN_ARTIFACTS | {
    "PerformanceReport", "OptimizationBrief",
}

