"""Submission builder — PLACEHOLDER until the 27/11 data drop.

The Zindi page does NOT specify the submission format (no sample file, no
column list). `build_submission` therefore REFUSES to write a file until the
real schema is registered via `register_schema()`. This is deliberate: a
guessed format would burn one of the 300 submissions and could score 0.

On 27/11: read the task data's sample submission / answer spec, fill in
`SCHEMA` below, delete the guard, and re-run the tests.
"""
import csv
import json
import os

# Filled in from the real spec on 27/11. Until then, building is blocked.
SCHEMA = None  # e.g. {"columns": ["task_id", "answer", ...], "format": "csv"}


class SubmissionNotReady(Exception):
    pass


def register_schema(schema):
    global SCHEMA
    SCHEMA = schema


def build_submission(results, out_file):
    """results: list of agent run dicts (see agent.Agent.run return value)."""
    if SCHEMA is None:
        raise SubmissionNotReady(
            "Submission format is TBD until the 27/11 data drop. "
            "Register the real schema with register_schema() first — "
            "see docs/RESEARCH.md §5.")
    os.makedirs(os.path.dirname(out_file) or ".", exist_ok=True)
    cols = SCHEMA["columns"]
    with open(out_file, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in results:
            row = {"task_id": r["task_id"]}
            row.update({k: json.dumps(v) if isinstance(v, (dict, list)) else v
                        for k, v in r["answer"].items()})
            w.writerow({c: row.get(c, "") for c in cols})
    return out_file
