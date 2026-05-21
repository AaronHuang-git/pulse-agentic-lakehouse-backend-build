"""Tool specifications exposed to the LLM.

These JSON schemas are part of the prompt; the LLM picks tool calls based
on the descriptions. Quality of description directly impacts quality of
tool use. Be concrete and prescriptive.
"""
from __future__ import annotations

TOOL_SPECS: list[dict] = [
    {
        "name": "list_datasets",
        "description": (
            "List all datasets available to the current tenant. Returns each "
            "dataset's name, total row count, upload count, and last-ingested "
            "timestamp. Call this FIRST when you don't know what data exists. "
            "Has no parameters."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "describe_dataset",
        "description": (
            "Get the schema (column names and SQL types) and total row count "
            "of one dataset. Call this BEFORE constructing a run_query call "
            "to know which columns exist."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Exact dataset name returned by list_datasets.",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "run_query",
        "description": (
            "Execute a structured query and return up to 100 rows. This is "
            "your ONLY way to access actual data values, counts, or aggregates. "
            "Every numeric claim in your final answer MUST come from a "
            "run_query result. Use group_by + aggregate for summaries. "
            "Use filters to restrict rows. Returns rows in JSON; results are "
            "tenant-scoped automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset": {"type": "string", "description": "Dataset name."},
                "select": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Columns to return. Omit for all columns. Ignored when "
                        "aggregate is given."
                    ),
                },
                "filters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "column": {"type": "string"},
                            "op": {
                                "type": "string",
                                "enum": [
                                    "eq", "neq", "gt", "gte", "lt", "lte",
                                    "in", "contains", "between",
                                    "is_null", "not_null",
                                ],
                            },
                            "value": {},
                        },
                        "required": ["column", "op"],
                    },
                },
                "group_by": {"type": "array", "items": {"type": "string"}},
                "aggregate": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "fn": {
                                "type": "string",
                                "enum": [
                                    "count", "count_distinct",
                                    "sum", "avg", "min", "max",
                                ],
                            },
                            "column": {"type": "string"},
                            "as": {"type": "string"},
                        },
                        "required": ["fn", "as"],
                    },
                },
                "order_by": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "column": {"type": "string"},
                            "dir": {"type": "string", "enum": ["asc", "desc"]},
                        },
                        "required": ["column"],
                    },
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["dataset"],
        },
    },
    {
        "name": "get_distinct_values",
        "description": (
            "Return up to 100 distinct values from one column. Use this to "
            "DISCOVER what values exist in a column before constructing a "
            "filter — e.g. before filtering on geolocation_state, call this "
            "to confirm 'SP' is a valid value."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset": {"type": "string"},
                "column": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["dataset", "column"],
        },
    },
]
