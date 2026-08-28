from ..schemas import *

class ProductAnalyst:
    def run(self, _):
        facts=["支持主动降噪", "单次续航约8小时"]
        return facts,[Evidence(claim=x,source="product-fixture:v1",confidence=.95) for x in facts]
class CompetitorAnalyst:
    def run(self,_): return ["竞品强调通勤场景"]
class AudienceAnalyst:
    def run(self,c): return [f"{c.target_audience}在学习时需要降低环境噪音"]
class TrendAnalyst:
    def run(self,_): return ["真实使用场景内容更易收藏"]
class EvidenceReviewer:
    def run(self,p): return p
class StrategyAgent:
    def run(self,c,r): return CampaignBrief(goal=c.goal,audience=c.target_audience,core_selling_point=r.product_facts[0],creative_angles=["宿舍学习","通勤降噪","真实续航"],platform=c.platform,cta="查看真实使用体验",success_metrics=["CTR","CVR"],test_hypothesis="真实场景提升点击",evidence_refs=[e.source for e in r.evidence])
class CopyAgent:
    def run(self,b):
        variants=[CreativeVariant(angle=a,title=f"{a}也能更专注",body=f"围绕{b.core_selling_point}分享真实{a}体验。",cta=b.cta,hashtags=["#学习好物"],evidence_refs=b.evidence_refs,target_metric="CTR") for a in b.creative_angles]
        return CreativePackage(variants=variants,visual_brief="真实场景，商品清晰露出",video_script="场景引入、体验、CTA")
class PlatformAdapterAgent:
    def run(self,c,platform):
        v=c.variants[0]; return PlatformPayload(platform=platform,title=v.title,body=v.body,media=["product-scene-1.jpg"],cta=v.cta)
class ComplianceAgent:
    def run(self,p,errors): return ComplianceReport(passed=not errors,status="passed" if not errors else "revision_required",risks=errors,suggestions=["删除违规表达"] if errors else [])
class AnalyticsAgent:
    def run(self,m):
        d={"CTR":m.clicks/m.impressions if m.impressions else 0,"CVR":m.conversions/m.clicks if m.clicks else 0,"CPA":m.cost/m.conversions if m.conversions else 0,"ROAS":m.revenue/m.cost if m.cost else 0}
        return PerformanceReport(metrics=m,derived=d,observations=[f"CTR为{d['CTR']:.2%}"],hypotheses=["素材承诺与落地页可能不一致"],recommendations=["测试学习场景标题"],evidence=["metrics-fixture:v1"])
class OptimizationAgent:
    def run(self,p): return OptimizationBrief(observation=p.observations[0],hypothesis=p.hypotheses[0],change_variable="标题",keep_constant="目标人群和平台",next_action="生成两版学习场景文案",success_metric="CVR")
