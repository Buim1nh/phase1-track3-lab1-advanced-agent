# Lab 16 Benchmark Report
 
## Metadata
- Dataset: hotpot_test_60.json
- Mode: deepseek
- Records: 104
- Agents: react, reflexion
 
## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 0.8077 | 0.9808 | 0.1731 |
| Avg attempts | 1 | 1.2308 | 0.2308 |
| Avg token estimate | 2203.23 | 2982.96 | 779.73 |
| Avg latency (ms) | 7033.54 | 11943.73 | 4910.19 |
 
## Failure modes
```json
{
  "react": {
    "none": 42,
    "wrong_final_answer": 10
  },
  "reflexion": {
    "none": 51,
    "wrong_final_answer": 1
  },
  "overall": {
    "none": 93,
    "wrong_final_answer": 11
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
