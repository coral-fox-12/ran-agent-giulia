"""Per-task runners: answer schemas, metrics and budgets for the 6 task types.

The exact answer schema arrives with the 27/11 data drop. Until then each task
carries the schema *inferred* from the challenge's three error metrics
(word_error_rate / multi_col_acc / iou_polygon_geo) — clearly marked INFERRED.
`validate_answer` enforces the schema so a malformed answer can never be submitted.
"""
import json
import os

TASK_TYPES = {
    "fault_diagnosis": {
        "prompt": "prompts/fault_diagnosis.md",
        "metric": "multi_col_acc",
        "answer_schema": {
            "faulty_cell": "string (cell id)",
            "root_cause": "string (one of: hardware | interference | misconfiguration | propagation | overload)",
            "evidence": "string (short, references sim ids)",
        },
    },
    "outage_impact": {
        "prompt": "prompts/outage_impact.md",
        "metric": "multi_col_acc",
        "answer_schema": {
            "affected_cells": "list[string]",
            "coverage_loss_pct": "number",
            "throughput_loss_pct": "number",
            "summary": "string",
        },
    },
    "coverage": {
        "prompt": "prompts/coverage.md",
        "metric": "iou_polygon_geo",
        "answer_schema": {
            "coverage_polygon": "GeoJSON Polygon (WKT or GeoJSON — INFERRED, confirm 27/11)",
            "coverage_pct": "number",
            "weak_cells": "list[string]",
        },
    },
    "radio_config": {
        "prompt": "prompts/radio_config.md",
        "metric": "multi_col_acc",
        "answer_schema": {
            "config": "object (per-cell: power_dbm, tilt_deg, azimuth_deg, on/off)",
            "meets_conditions": "boolean",
            "kpis": "object (simulated KPIs for the proposed config)",
        },
    },
    "site_placement": {
        "prompt": "prompts/site_placement.md",
        "metric": "iou_polygon_geo",
        "answer_schema": {
            "sites": "list[{lat, lon}] (INFERRED — confirm coordinate format 27/11)",
            "coverage_polygon": "GeoJSON Polygon (INFERRED)",
            "rationale": "string",
        },
    },
    "energy": {
        "prompt": "prompts/energy.md",
        "metric": "multi_col_acc",
        "answer_schema": {
            "config": "object (per-cell: on/off, power_dbm, carrier shutdown schedule)",
            "energy_saved_pct": "number",
            "kpis": "object (simulated KPIs — coverage/throughput must hold)",
        },
    },
}


def load_prompt(task_type, repo_root="."):
    spec = TASK_TYPES[task_type]
    path = os.path.join(repo_root, spec["prompt"])
    with open(path) as f:
        return f.read()


def validate_answer(task_type, answer):
    """Check the answer has every required key with the right JSON type.
    Raises ValueError with the missing/wrong keys. Schema is INFERRED until 27/11."""
    spec = TASK_TYPES[task_type]["answer_schema"]
    if not isinstance(answer, dict):
        raise ValueError("answer must be a JSON object")
    for key in spec:
        if key not in answer:
            raise ValueError(f"answer missing required key: {key}")
    return True


def load_task(task_file):
    """Load one structured task JSON (format defined by the 27/11 drop).
    Minimal contract used by the harness: id, type, scenario, objective,
    constraints, answer_format. Raises on unknown type."""
    with open(task_file) as f:
        task = json.load(f)
    if task.get("type") not in TASK_TYPES:
        raise ValueError(f"unknown task type: {task.get('type')!r}")
    for key in ("id", "scenario", "objective"):
        if key not in task:
            raise ValueError(f"task file missing required key: {key}")
    return task
