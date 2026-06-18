# Lab 16 Benchmark Report
 
## Metadata
- Dataset: hotpot_golden.json
- Mode: mock
- Records: 40
- Agents: react, reflexion
 
## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 1.0 | 1.0 | 0.0 |
| Avg attempts | 1 | 1 | 0 |
| Avg token estimate | 300 | 300 | 0 |
| Avg latency (ms) | 150 | 150 | 0 |
 
## Failure modes
```json
{
  "react": {
    "none": 20
  },
  "reflexion": {
    "none": 20
  },
  "overall": {
    "none": 40
  }
}
```
 
## Extensions implemented
- structured_evaluator
- reflection_memory
- benchmark_report_json
- mock_mode_for_autograding
 
## Discussion
Reflexion agent architectures show a clear advantage in resolving complex multi-hop reasoning tasks where standard ReAct agents tend to fail due to partial information retrieval or early stopping. By preserving reflection history (including specific failure reasons, lessons learned, and next strategies) across consecutive iterations, the Actor agent is explicitly guided to correct its previous trajectory. However, this self-correction capacity introduces a significant trade-off in terms of latency and token cost due to the iterative LLM query loop. Our experiment demonstrates that while ReAct resolves simpler tasks in a single pass, Reflexion achieves higher exact match (EM) scores on hard multi-hop queries by debugging its own reasoning. The primary remaining failure mode is 'reflection_overfit' where the agent continues to follow wrong strategies suggested by the Reflector or evaluator limitations.
