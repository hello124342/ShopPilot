# Research Team Baseline Benchmark

Deterministic fixture benchmark（2026-08-28）：

| 模式 | 证据覆盖 | 专业视角 | 模型成本 | 本地延迟样例 |
|---|---:|---:|---:|---:|
| Research Team | 2 | 4 | 0 | 0.031 ms |
| Single-agent baseline | 1 | 1 | 0 | 0.006 ms |

结论：固定 Research Team 在当前 fixture 中以更高的本地编排延迟换取两倍证据覆盖和四个独立专业视角。该结果只证明 Harness 的比较机制有效；接入真实模型后必须重新记录 token、成本、时延和质量评分，不能把 mock benchmark 当作线上效果结论。
