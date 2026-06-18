from __future__ import annotations
import os
import re
import time
import json
import urllib.request
from dotenv import load_dotenv
from .schemas import QAExample, JudgeResult, ReflectionEntry
from .utils import normalize_answer
from .prompts import ACTOR_SYSTEM, EVALUATOR_SYSTEM, REFLECTOR_SYSTEM

load_dotenv()
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

FIRST_ATTEMPT_WRONG = {"hp2": "London", "hp4": "Atlantic Ocean", "hp6": "Red Sea", "hp8": "Andes"}
FAILURE_MODE_BY_QID = {"hp2": "incomplete_multi_hop", "hp4": "wrong_final_answer", "hp6": "entity_drift", "hp8": "entity_drift"}

def clean_json_string(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

def extract_answer(content: str) -> str:
    match = re.search(r"<answer>(.*?)</answer>", content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    lines = content.split("\n")
    for line in reversed(lines):
        if line.strip().lower().startswith("answer:"):
            return line.strip()[7:].strip()
    non_empty_lines = [l.strip() for l in lines if l.strip()]
    if non_empty_lines:
        return non_empty_lines[-1]
    return content.strip()

def call_deepseek_api(system_prompt: str, user_prompt: str, json_mode: bool = False) -> tuple[str, int, int]:
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.0
    }
    if json_mode:
        data["response_format"] = {"type": "json_object"}

    req_body = json.dumps(data).encode("utf-8")
    
    max_retries = 3
    base_delay = 2
    for attempt in range(max_retries):
        start_time = time.time()
        try:
            req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as response:
                latency = int((time.time() - start_time) * 1000)
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body)
                content = res_json["choices"][0]["message"]["content"]
                usage = res_json.get("usage", {})
                tokens = usage.get("total_tokens", 0)
                return content, tokens, latency
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            sleep_time = base_delay * (2 ** attempt)
            print(f"API call failed: {e}. Retrying in {sleep_time}s...")
            time.sleep(sleep_time)
    raise RuntimeError("API call failed after max retries")

def actor_answer(example: QAExample, attempt_id: int, agent_type: str, reflection_memory: list[str], use_mock: bool = True) -> tuple[str, int, int]:
    if use_mock:
        if example.qid not in FIRST_ATTEMPT_WRONG:
            return example.gold_answer, 200, 100
        if agent_type == "react":
            return FIRST_ATTEMPT_WRONG[example.qid], 200, 100
        if attempt_id == 1 and not reflection_memory:
            return FIRST_ATTEMPT_WRONG[example.qid], 200, 100
        return example.gold_answer, 200, 100
    
    # Live API implementation
    context_str = "\n\n".join([f"Document: {c.title}\n{c.text}" for c in example.context])
    user_prompt = f"Context:\n{context_str}\n\nQuestion: {example.question}\n"
    if reflection_memory:
        user_prompt += "\nReflections from previous failed attempts:\n"
        for ref in reflection_memory:
            user_prompt += f"- {ref}\n"
        user_prompt += "\nAvoid the mistakes detailed above and try another strategy.\n"
        
    content, tokens, latency = call_deepseek_api(ACTOR_SYSTEM, user_prompt, json_mode=False)
    answer = extract_answer(content)
    return answer, tokens, latency

def evaluator(example: QAExample, answer: str, use_mock: bool = True) -> tuple[JudgeResult, int, int]:
    if use_mock:
        if normalize_answer(example.gold_answer) == normalize_answer(answer):
            return JudgeResult(score=1, reason="Final answer matches the gold answer after normalization."), 100, 50
        if normalize_answer(answer) == "london":
            return JudgeResult(score=0, reason="The answer stopped at the birthplace city and never completed the second hop to the river.", missing_evidence=["Need to identify the river that flows through London."], spurious_claims=[]), 100, 50
        return JudgeResult(score=0, reason="The final answer selected the wrong second-hop entity.", missing_evidence=["Need to ground the answer in the second paragraph."], spurious_claims=[answer]), 100, 50

    # Live API implementation
    user_prompt = f"Question: {example.question}\nGold Answer: {example.gold_answer}\nPredicted Answer: {answer}\n"
    content, tokens, latency = call_deepseek_api(EVALUATOR_SYSTEM, user_prompt, json_mode=True)
    try:
        parsed = json.loads(clean_json_string(content))
    except Exception as e:
        print(f"Failed to parse Evaluator JSON: {content}. Error: {e}")
        is_correct = normalize_answer(example.gold_answer) == normalize_answer(answer)
        parsed = {
            "score": 1 if is_correct else 0,
            "reason": f"Fallback evaluation. Raw response: {content}",
            "missing_evidence": [],
            "spurious_claims": []
        }
    judge = JudgeResult(
        score=int(parsed.get("score", 0)),
        reason=str(parsed.get("reason", "")),
        missing_evidence=list(parsed.get("missing_evidence", [])),
        spurious_claims=list(parsed.get("spurious_claims", []))
    )
    return judge, tokens, latency

def reflector(example: QAExample, attempt_id: int, judge: JudgeResult, use_mock: bool = True) -> tuple[ReflectionEntry, int, int]:
    if use_mock:
        strategy = "Do the second hop explicitly: birthplace city -> river through that city." if example.qid == "hp2" else "Verify the final entity against the second paragraph before answering."
        ref = ReflectionEntry(attempt_id=attempt_id, failure_reason=judge.reason, lesson="A partial first-hop answer is not enough; the final answer must complete all hops.", next_strategy=strategy)
        return ref, 150, 80

    # Live API implementation
    user_prompt = (
        f"Question: {example.question}\n"
        f"Failed Attempt ID: {attempt_id}\n"
        f"Evaluator Reason: {judge.reason}\n"
        f"Missing Evidence: {', '.join(judge.missing_evidence)}\n"
        f"Spurious Claims: {', '.join(judge.spurious_claims)}\n"
    )
    content, tokens, latency = call_deepseek_api(REFLECTOR_SYSTEM, user_prompt, json_mode=True)
    try:
        parsed = json.loads(clean_json_string(content))
    except Exception as e:
        print(f"Failed to parse Reflector JSON: {content}. Error: {e}")
        parsed = {
            "attempt_id": attempt_id,
            "failure_reason": judge.reason,
            "lesson": "Attempt failed to meet matching criteria.",
            "next_strategy": "Try re-reading the context carefully."
        }
    ref = ReflectionEntry(
        attempt_id=int(parsed.get("attempt_id", attempt_id)),
        failure_reason=str(parsed.get("failure_reason", judge.reason)),
        lesson=str(parsed.get("lesson", "")),
        next_strategy=str(parsed.get("next_strategy", ""))
    )
    return ref, tokens, latency
