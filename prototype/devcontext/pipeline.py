"""The DevContext AI pipeline, wired end to end.

    request --> DECOMPOSE --> SCOUT --> COMPILE --> .devcontext/ + init.sh

Every stage can be entered directly so the chain stays demonstrable when an
upstream dependency is unavailable. That is not defensive padding: the on-site
build has a Red Light window where the laptop is restricted and the model may
not yet be running on device, and a demo that only works in the happy path is
a demo that fails in front of a judge.

    --request "..."   full chain, local SLM decomposition
    --graph g.json    skip DECOMPOSE, start from an existing node graph
    --payload p.json  skip DECOMPOSE and SCOUT, compile a finished payload
    --offline         skip SCOUT (no network, no API key needed)

Usage:
    python -m devcontext.pipeline --request "build an audio streaming app" --target ./out
    python -m devcontext.pipeline --graph examples/graph_audio.json --target ./out
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import enable_utf8_stdout
from .compile_brain import compile_brain
from .models import BrainPayload, validate_node_graph
from .scout import ExaClient, scout_payload

STAGE_WIDTH = 58


def _banner(step: int, total: int, name: str, detail: str = "") -> None:
    print()
    print("=" * STAGE_WIDTH)
    print(f"  [{step}/{total}] {name}")
    if detail:
        print(f"        {detail}")
    print("=" * STAGE_WIDTH)


def _load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def run(
    *,
    request: str | None,
    graph_path: str | None,
    payload_path: str | None,
    target: Path,
    offline: bool,
    model_dir: str | None,
    max_attempts: int,
    repos_per_node: int,
    trends_per_node: int,
) -> int:
    stages = 3 if (request or graph_path) else 1
    step = 0

    # ---------------------------------------------------------------- DECOMPOSE
    if payload_path:
        payload = BrainPayload.from_dict(_load_json(payload_path))
        print(f"Loaded finished payload: {payload.project_name}")

    elif graph_path:
        step += 1
        _banner(step, stages, "DECOMPOSE (skipped)", f"reading node graph from {graph_path}")
        graph = _load_json(graph_path)
        problems = validate_node_graph(graph)
        if problems:
            print("error: node graph does not satisfy the schema:", file=sys.stderr)
            for problem in problems[:8]:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        payload = BrainPayload.from_node_graph(
            graph,
            source_prompt=str(graph.get("source_prompt", "")),
            model="supplied node graph (no model invoked)",
        )
        print(f"  project : {payload.project_name}")
        print(f"  nodes   : {len(payload.nodes)}")

    elif request:
        step += 1
        _banner(step, stages, "DECOMPOSE", "local quantized SLM, offline")
        from .decompose import DecomposeError, Decomposer  # imported lazily: heavy

        decomposer = Decomposer(
            Path(model_dir) if model_dir else None,
            max_attempts=max_attempts,
        )
        try:
            result = decomposer.decompose(request, verbose=True)
        except DecomposeError as exc:
            print(f"\nerror: {exc}", file=sys.stderr)
            print(
                "\nhint: pass --graph with a node graph JSON to run the rest of the "
                "pipeline without the model.",
                file=sys.stderr,
            )
            return 1

        if not result.ok or result.graph is None:
            print(f"\nerror: no schema-valid graph after {result.attempts} attempts", file=sys.stderr)
            for err in result.errors[-3:]:
                print(f"  - {err}", file=sys.stderr)
            return 1

        payload = BrainPayload.from_node_graph(
            result.graph,
            source_prompt=request,
            model=decomposer.model_label,
        )
        print(f"\n  project  : {payload.project_name}")
        print(f"  nodes    : {len(payload.nodes)}")
        print(f"  attempts : {result.attempts}")
        print(f"  elapsed  : {result.elapsed_s:.1f}s")
    else:
        print("error: one of --request, --graph or --payload is required", file=sys.stderr)
        return 1

    # -------------------------------------------------------------------- SCOUT
    if not payload_path:
        step += 1
        if offline:
            _banner(step, stages, "SCOUT (skipped)", "--offline requested")
        else:
            _banner(step, stages, "SCOUT", "Exa neural search: repos + community signal")
            client = ExaClient()
            if not client.enabled:
                print("  EXA_API_KEY not set — continuing without scouting.")
                print("  Add EXA_API_KEY to .env to populate candidates and trends.")
            stats = scout_payload(
                payload,
                client,
                repos_per_node=repos_per_node,
                trends_per_node=trends_per_node,
            )
            print(f"\n  {stats.render()}")
            for err in stats.errors[:4]:
                print(f"  ! {err}")

    # ------------------------------------------------------------------ COMPILE
    step += 1
    _banner(step, stages, "COMPILE", f"writing .devcontext/ into {target}")
    try:
        result_brain = compile_brain(payload, target)
    except OSError as exc:
        print(f"error: could not write brain folder: {exc}", file=sys.stderr)
        return 1

    print(f"  nodes      : {result_brain.node_count}")
    print(f"  candidates : {result_brain.candidate_count}")
    print(f"  signals    : {result_brain.trend_count}")
    print(f"  files      : {len(result_brain.files_written)}")

    print()
    print("-" * STAGE_WIDTH)
    print(f"  Project brain compiled: {payload.project_name}")
    print("-" * STAGE_WIDTH)
    print(f"  {result_brain.brain_dir.parent}")
    print("  +-- .devcontext/")
    print("  |   +-- context.json")
    print("  |   +-- semantic_cache.db")
    print("  |   +-- open_source_maps/")
    print("  |   `-- trends_report.md")
    print("  `-- init.sh")
    print()
    print(f"  Next: cd {result_brain.brain_dir.parent} && bash init.sh")
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdout()
    parser = argparse.ArgumentParser(
        prog="devcontext.pipeline",
        description="Run the DevContext AI pipeline: decompose, scout, compile.",
    )
    entry = parser.add_mutually_exclusive_group(required=True)
    entry.add_argument("--request", help="natural language project request (runs the local SLM)")
    entry.add_argument("--graph", help="node graph JSON, skipping DECOMPOSE")
    entry.add_argument("--payload", help="finished payload JSON, skipping DECOMPOSE and SCOUT")

    parser.add_argument("--target", default="./brain-out", help="project root to write into")
    parser.add_argument("--offline", action="store_true", help="skip the SCOUT network stage")
    parser.add_argument("--model-dir", help="override the ORT-GenAI model directory")
    parser.add_argument("--max-attempts", type=int, default=3, help="DECOMPOSE repair attempts")
    parser.add_argument("--repos", type=int, default=4, help="repo candidates per node")
    parser.add_argument("--trends", type=int, default=3, help="community signals per node")

    args = parser.parse_args(argv)

    try:
        return run(
            request=args.request,
            graph_path=args.graph,
            payload_path=args.payload,
            target=Path(args.target),
            offline=args.offline,
            model_dir=args.model_dir,
            max_attempts=args.max_attempts,
            repos_per_node=args.repos,
            trends_per_node=args.trends,
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
