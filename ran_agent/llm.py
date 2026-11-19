"""LLM client: OpenAI-compatible chat completions over stdlib urllib.

Production use talks to a local llama.cpp / vLLM / SGLang server serving
Qwen3.6-35B-A3B. `MockLLM` is for offline harness development only — its
outputs must NEVER be submitted (config.py pins the model name, but the mock
does not call any model at all; the agent loop records which backend ran).
"""
import json
import urllib.request
import urllib.error


class LLMError(Exception):
    pass


class OpenAIClient:
    """Minimal OpenAI-compatible client (chat/completions, optional tools)."""

    def __init__(self, base_url, model, api_key="", temperature=0.2,
                 max_tokens=4096, seed=42, timeout_s=300):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.seed = seed
        self.timeout_s = timeout_s
        self.tokens_used = 0

    def chat(self, messages, tools=None):
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "seed": self.seed,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        req = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                resp = json.load(r)
        except urllib.error.HTTPError as e:
            raise LLMError(f"LLM HTTP {e.code}: {e.read()[:500]!r}")
        except urllib.error.URLError as e:
            raise LLMError(f"LLM unreachable at {self.base_url}: {e}")
        usage = resp.get("usage") or {}
        self.tokens_used += int(usage.get("total_tokens") or 0)
        return resp["choices"][0]["message"]


class MockLLM:
    """Deterministic stand-in for harness tests. Returns a fixed tool-call plan:
    inspect -> simulate -> propose_answer. Records that it is a mock."""

    backend = "mock"

    # Schema-valid placeholder answers per task type (mock values only).
    MOCK_ANSWERS = {
        "fault_diagnosis": {"faulty_cell": "cell_B", "root_cause": "interference",
                            "evidence": "mock sim 2: SINR collapse isolated to cell_B"},
        "outage_impact": {"affected_cells": ["cell_B"], "coverage_loss_pct": 12.5,
                          "throughput_loss_pct": 20.0, "summary": "mock"},
        "coverage": {"coverage_polygon": {"type": "Polygon", "coordinates": [
                         [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
                     "coverage_pct": 95.0, "weak_cells": []},
        "radio_config": {"config": {}, "meets_conditions": True, "kpis": {}},
        "site_placement": {"sites": [{"lat": 0.0, "lon": 0.0}],
                           "coverage_polygon": {}, "rationale": "mock"},
        "energy": {"config": {}, "energy_saved_pct": 10.0, "kpis": {}},
    }

    def __init__(self, plan=None):
        self.tokens_used = 0
        self.calls = 0
        # plan: list of tool names to call in order, then a final answer.
        self.plan = plan or ["inspect_network", "run_simulation"]
        self.task_type = "fault_diagnosis"

    def set_task(self, task_type):
        self.task_type = task_type

    def chat(self, messages, tools=None):
        self.calls += 1
        self.tokens_used += 120  # nominal, keeps token accounting exercised
        if self.calls <= len(self.plan):
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": f"call-{self.calls}",
                    "type": "function",
                    "function": {
                        "name": self.plan[self.calls - 1],
                        "arguments": "{}",
                    },
                }],
            }
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": f"call-{self.calls}",
                "type": "function",
                "function": {
                    "name": "propose_answer",
                    "arguments": json.dumps({
                        "answer": self.MOCK_ANSWERS[self.task_type],
                        "reasoning_summary": "mock: hypothesis confirmed by simulation",
                    }),
                },
            }],
        }


def build_llm(cfg):
    llm_cfg = cfg["llm"]
    if not llm_cfg.get("base_url"):
        return MockLLM()
    return OpenAIClient(
        base_url=llm_cfg["base_url"],
        model=llm_cfg["model"],
        api_key=llm_cfg.get("api_key", ""),
        temperature=llm_cfg.get("temperature", 0.2),
        max_tokens=llm_cfg.get("max_tokens", 4096),
        seed=llm_cfg.get("seed", 42),
        timeout_s=llm_cfg.get("timeout_s", 300),
    )
