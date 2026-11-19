"""Budget-aware ReAct loop.

Plan: hypothesis -> cheapest informative experiment -> observe -> answer.
Hard stops: max_steps iterations, max_simulations sims, max_tokens_per_task.
Every run returns a trace (for the code review) and a typed answer.
"""
import json

from . import tasks
from .tools import TOOLS, TOOL_NAMES


class BudgetExceeded(Exception):
    pass


class Agent:
    def __init__(self, llm, simulator, cfg, task):
        self.llm = llm
        self.sim = simulator
        self.cfg = cfg
        self.task = task
        self.task_type = task["type"]
        self.max_steps = cfg["agent"]["max_steps"]
        self.max_sims = cfg["agent"]["max_simulations"]
        per_task = (cfg.get("tasks") or {}).get(self.task_type) or {}
        self.max_sims = int(per_task.get("max_simulations", self.max_sims))
        self.sims_used = 0
        self.trace = []
        self.llm_backend = getattr(llm, "backend", "real")
        self.sim_backend = getattr(simulator, "backend", "giulia")
        set_task = getattr(llm, "set_task", None)
        if callable(set_task):
            set_task(self.task_type)

    def _log(self, kind, payload):
        self.trace.append({"step": len(self.trace) + 1, "kind": kind,
                           "payload": payload})

    def _dispatch(self, name, args):
        if name == "inspect_network":
            return self.sim.inspect_network(
                {"id": self.task["id"], **self.task.get("scenario", {})})
        if name == "run_simulation":
            if self.sims_used >= self.max_sims:
                raise BudgetExceeded(
                    f"simulation budget exhausted ({self.max_sims})")
            self.sims_used += 1
            return self.sim.run_simulation(args.get("config") or {})
        if name == "get_kpis":
            return self.sim.get_kpis(args.get("sim_id"))
        if name == "propose_answer":
            return {"accepted": True}
        raise ValueError(f"unknown tool: {name}")

    def run(self):
        prompt = tasks.load_prompt(self.task_type)
        messages = [
            {"role": "system",
             "content": prompt + "\n\nYou are a radio-network engineering agent. "
                      "Use tools to investigate; respect the simulation budget; "
                      "answer only in the required schema."},
            {"role": "user", "content": json.dumps(self.task, indent=2)},
        ]
        for _ in range(self.max_steps):
            if getattr(self.llm, "tokens_used", 0) > self.cfg["agent"]["max_tokens_per_task"]:
                raise BudgetExceeded("token budget exceeded")
            msg = self.llm.chat(messages, tools=TOOLS)
            messages.append(msg)
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                content = msg.get("content") or ""
                self._log("final_text", content)
                return self._finish({"text": content})
            for call in tool_calls:
                fn = call["function"]
                name = fn["name"]
                if name not in TOOL_NAMES:
                    raise ValueError(f"LLM called unknown tool: {name}")
                args = json.loads(fn.get("arguments") or "{}")
                self._log("tool_call", {"name": name, "args": args})
                if name == "propose_answer":
                    return self._finish(args.get("answer") or {})
                try:
                    result = self._dispatch(name, args)
                except BudgetExceeded:
                    raise
                except Exception as e:  # noqa: BLE001 — tool errors go back to the LLM
                    result = {"error": str(e)}
                self._log("tool_result", {"name": name, "result": result})
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": json.dumps(result)[:8000]})
        raise BudgetExceeded(f"max_steps ({self.max_steps}) reached without an answer")

    def _finish(self, answer):
        if isinstance(answer, dict) and answer:
            tasks.validate_answer(self.task_type, answer)
        return {
            "task_id": self.task["id"],
            "task_type": self.task_type,
            "answer": answer,
            "sims_used": self.sims_used,
            "llm_tokens": getattr(self.llm, "tokens_used", 0),
            "llm_backend": self.llm_backend,
            "sim_backend": self.sim_backend,
            "trace": self.trace,
        }
