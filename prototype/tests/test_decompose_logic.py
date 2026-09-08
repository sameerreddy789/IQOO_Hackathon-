"""Verification for the model-independent half of DECOMPOSE.

extract_json and coerce_graph are what stand between a small quantized model and
a schema-valid graph, so they are tested against the failure modes such models
actually produce: code fences, trailing chatter, invalid enum values, CamelCase
ids, duplicate ids and missing optional arrays. No model required.

Run:
    python -m tests.test_decompose_logic
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devcontext.decompose import (  # noqa: E402
    VALID_CATEGORIES,
    coerce_graph,
    extract_json,
)
from devcontext.models import validate_node_graph  # noqa: E402

_passed = 0
_failed: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _passed
    if condition:
        _passed += 1
        print(f"  PASS  {label}")
    else:
        _failed.append(label)
        print(f"  FAIL  {label}{(' -- ' + detail) if detail else ''}")


GOOD = {
    "project_name": "Test Project",
    "summary": "A perfectly well formed graph used as the control case.",
    "constraints": ["offline first"],
    "target_platforms": ["android"],
    "nodes": [
        {"id": "auth", "category": "auth", "title": "Auth", "requirement": "Sign users in and keep sessions."},
        {"id": "store", "category": "database", "title": "Store", "requirement": "Persist records durably."},
    ],
}


def main() -> int:
    print("\nextract_json")
    payload = json.dumps(GOOD)

    check("bare object", extract_json(payload) == payload)
    check("fenced with json tag", extract_json(f"```json\n{payload}\n```") == payload)
    check("fenced without tag", extract_json(f"```\n{payload}\n```") == payload)
    check(
        "leading prose stripped",
        extract_json(f"Sure! Here is the graph:\n{payload}") == payload,
    )
    check(
        "trailing chatter stripped",
        extract_json(f"{payload}\n\nLet me know if you want changes!") == payload,
    )
    check(
        "braces inside strings do not break matching",
        json.loads(extract_json('{"a": "a { brace } inside", "b": 1}') or "{}")["a"]
        == "a { brace } inside",
    )
    check(
        "escaped quote inside string handled",
        json.loads(extract_json(r'{"a": "he said \"hi\"", "b": 2}') or "{}")["b"] == 2,
    )
    check("no json returns None", extract_json("I cannot help with that.") is None)
    check("empty string returns None", extract_json("") is None)
    check("unbalanced braces returns None", extract_json('{"a": 1') is None)

    print("\ncoerce_graph — control case is left intact")
    coerced = coerce_graph(GOOD)
    check("valid graph stays valid", not validate_node_graph(coerced))
    check("node count preserved", len(coerced["nodes"]) == 2)
    check("project name preserved", coerced["project_name"] == "Test Project")

    print("\ncoerce_graph — repairs")
    messy = {
        "project_name": "Messy",
        "summary": "A graph exhibiting every mechanical failure mode at once.",
        "nodes": [
            {"id": "User Accounts", "category": "AUTHENTICATION", "title": "Users",
             "requirement": "Sign in users and hold the session open."},
            {"id": "user accounts", "category": "cli", "title": "Dupe",
             "requirement": "A duplicate id after normalization, plus a bad category."},
            {"id": "x", "category": "database", "title": "",
             "requirement": "short"},
            {"id": "ok_node", "category": "frontend", "title": "Fine",
             "requirement": "This one is already correct and should pass through.",
             "search_hint": "some keywords", "bogus_key": "should be dropped"},
        ],
        "target_platforms": ["android", "playstation", "web"],
        "constraints": ["fine", "  ", ""],
    }
    fixed = coerce_graph(messy)
    errors = validate_node_graph(fixed)
    check("coerced messy graph validates", not errors, "; ".join(errors[:3]))

    ids = [n["id"] for n in fixed["nodes"]]
    check("ids normalized to snake_case", ids[0] == "user_accounts", str(ids))
    check("duplicate ids disambiguated", len(set(ids)) == len(ids), str(ids))
    check("all categories in enum", all(n["category"] in VALID_CATEGORIES for n in fixed["nodes"]))
    check("unknown category mapped to other", fixed["nodes"][1]["category"] == "other")
    check("empty title backfilled", len(fixed["nodes"][2]["title"]) >= 2)
    check("short requirement backfilled", len(fixed["nodes"][2]["requirement"]) >= 10)
    check("unknown keys dropped", "bogus_key" not in fixed["nodes"][3])
    check("search_hint preserved", fixed["nodes"][3]["search_hint"] == "some keywords")
    check("invalid platform dropped", fixed["target_platforms"] == ["android", "web"])
    check("blank constraints dropped", fixed["constraints"] == ["fine"])

    print("\ncoerce_graph — missing optional fields")
    minimal = coerce_graph(
        {
            "project_name": "Min",
            "summary": "Only the required keys are present in this input object.",
            "nodes": [
                {"id": "a", "category": "backend", "title": "A", "requirement": "Do the first thing."},
                {"id": "b", "category": "backend", "title": "B", "requirement": "Do the second thing."},
            ],
        }
    )
    check("constraints defaulted to []", minimal["constraints"] == [])
    check("target_platforms defaulted to []", minimal["target_platforms"] == [])
    check("minimal graph validates", not validate_node_graph(minimal))

    print("\ncoerce_graph — does not fabricate content")
    empty = coerce_graph({"project_name": "E", "summary": "No nodes at all here.", "nodes": []})
    check("empty node list is not invented into existence", empty["nodes"] == [])
    check("empty node list still fails validation", bool(validate_node_graph(empty)))

    print("\ncoerce_graph — hostile input does not raise")
    for hostile in (
        {},
        {"nodes": "not a list"},
        {"nodes": [None, 42, "text"]},
        {"project_name": None, "summary": None, "nodes": [{}]},
        {"nodes": [{"id": "!!!", "category": None, "title": None, "requirement": None}]},
    ):
        try:
            coerce_graph(hostile)
            ok = True
        except Exception as exc:  # noqa: BLE001 - the point is that nothing escapes
            ok = False
            print(f"        raised: {type(exc).__name__}: {exc}")
        check(f"survives {json.dumps(hostile)[:44]}", ok)

    print("\ncoerce_graph — cap enforcement")
    many = coerce_graph(
        {
            "project_name": "Many",
            "summary": "More nodes than the schema permits, to check the cap.",
            "nodes": [
                {"id": f"n{i}", "category": "backend", "title": f"N{i}",
                 "requirement": f"Handle responsibility number {i} correctly."}
                for i in range(20)
            ],
        }
    )
    check("node list capped at 12", len(many["nodes"]) == 12)
    check("capped graph validates", not validate_node_graph(many))

    print(f"\n{'-' * 52}")
    print(f"passed {_passed}   failed {len(_failed)}")
    if _failed:
        for name in _failed:
            print(f"  - {name}")
        return 1
    print("all checks green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
