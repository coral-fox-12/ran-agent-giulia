"""Tool schemas the agent may call (OpenAI function-calling format).

These mirror the challenge description ("use dedicated tools to inspect and
simulate the network"). The real tools API arrives with the 27/11 data drop;
these schemas are the harness contract the agent is built against, and will be
re-mapped 1:1 onto the organisers' tools when they land.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "inspect_network",
            "description": "Inspect the scenario: cells/sites, current configuration, "
                           "reported symptoms and constraints. No simulation budget used.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scenario_id": {"type": "string"},
                    "detail": {"type": "string",
                               "description": "what to focus on, e.g. a cell id or KPI"},
                },
                "required": ["scenario_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_simulation",
            "description": "Run Giulia with a proposed configuration and return KPIs. "
                           "Each call consumes 1 simulation from the task budget.",
            "parameters": {
                "type": "object",
                "properties": {
                    "config": {
                        "type": "object",
                        "description": "Proposed network configuration (cells, power, "
                                       "tilt, azimuth, on/off, ...).",
                    },
                    "hypothesis": {
                        "type": "string",
                        "description": "What this experiment is testing.",
                    },
                },
                "required": ["config", "hypothesis"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_kpis",
            "description": "Fetch KPI table for a previous simulation id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sim_id": {"type": "integer"},
                },
                "required": ["sim_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_answer",
            "description": "Submit the final structured answer for the task. Ends the run.",
            "parameters": {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "object",
                        "description": "Typed answer matching the task's answer schema.",
                    },
                    "reasoning_summary": {
                        "type": "string",
                        "description": "Short trace: hypothesis, experiments, conclusion.",
                    },
                },
                "required": ["answer", "reasoning_summary"],
            },
        },
    },
]

TOOL_NAMES = {t["function"]["name"] for t in TOOLS}
