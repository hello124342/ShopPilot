import time
from ..schemas import Evidence,ResearchPackage
from ..teams import ResearchTeam
def compare_research(campaign):
    start=time.perf_counter(); team=ResearchTeam().run(campaign); team_ms=(time.perf_counter()-start)*1000
    start=time.perf_counter(); baseline=ResearchPackage(product_facts=["支持主动降噪"],evidence=[Evidence(claim="支持主动降噪",source="product-fixture:v1",confidence=.9)]); baseline_ms=(time.perf_counter()-start)*1000
    return {"team":{"latency_ms":team_ms,"evidence_coverage":len(team.evidence),"perspectives":4,"cost":0},"single_agent":{"latency_ms":baseline_ms,"evidence_coverage":len(baseline.evidence),"perspectives":1,"cost":0}}
