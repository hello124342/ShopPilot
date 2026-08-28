from ..agents import ProductAnalyst,CompetitorAnalyst,AudienceAnalyst,TrendAnalyst,EvidenceReviewer
from ..schemas import ResearchPackage
class ResearchTeam:
    def run(self,c):
        facts,evidence=ProductAnalyst().run(c)
        return EvidenceReviewer().run(ResearchPackage(product_facts=facts,audience_insights=AudienceAnalyst().run(c),competitor_observations=CompetitorAnalyst().run(c),trend_signals=TrendAnalyst().run(c),opportunities=["真实学习场景"],risks=["不得夸大降噪效果"],evidence=evidence))
