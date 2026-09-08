"""Verification for COMPILE.

Asserts the produced tree matches documentation/PROJECT_DEVCONTEXT_SPEC.md section 6,
that the generated init.sh is valid bash, and that the vector store is a readable
SQLite database with the expected schema. Writes only into a temp directory.

Run:
    python -m tests.test_compile_brain
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devcontext.compile_brain import compile_brain  # noqa: E402
from devcontext.models import BrainPayload, validate_node_graph  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "sample_payload.json"

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


def bash_syntax_check(script_text: str) -> tuple[bool, str]:
    """Syntax-check a bash script by piping it over stdin.

    Passing a Windows path to Git Bash mangles the backslashes, so the script
    content goes through stdin instead of being referenced by path.
    """
    bash = shutil.which("bash")
    if not bash:
        return True, "skipped"
    # Bytes, not text: text mode would rewrite LF as CRLF on Windows and bash
    # would then choke on the carriage returns.
    proc = subprocess.run(
        [bash, "-n"],
        input=script_text.encode("utf-8"),
        capture_output=True,
    )
    return proc.returncode == 0, proc.stderr.decode("utf-8", "replace").strip()


def main() -> int:
    payload_dict = json.loads(FIXTURE.read_text(encoding="utf-8"))

    print("\nnode graph contract")
    graph_view = {
        "project_name": payload_dict["project_name"],
        "summary": payload_dict["summary"],
        "constraints": payload_dict["constraints"],
        "target_platforms": payload_dict["target_platforms"],
        "nodes": [
            {k: n[k] for k in ("id", "category", "title", "requirement", "search_hint") if k in n}
            for n in payload_dict["nodes"]
        ],
    }
    errors = validate_node_graph(graph_view)
    check("fixture satisfies node_graph.schema.json", not errors, "; ".join(errors[:3]))

    bad = {"project_name": "x", "summary": "too short", "nodes": []}
    check("validator rejects a malformed graph", bool(validate_node_graph(bad)))

    dupe = json.loads(json.dumps(graph_view))
    dupe["nodes"][1]["id"] = dupe["nodes"][0]["id"]
    check("validator catches duplicate node ids", any("duplicate" in e for e in validate_node_graph(dupe)))

    payload = BrainPayload.from_dict(payload_dict)
    tmp = Path(tempfile.mkdtemp(prefix="devcontext-test-"))
    try:
        print("\ncompile output tree")
        result = compile_brain(payload, tmp)
        brain = result.brain_dir

        for rel in ("context.json", "semantic_cache.db", "open_source_maps", "trends_report.md"):
            check(f".devcontext/{rel} exists", (brain / rel).exists())
        check("init.sh exists at project root", (tmp / "init.sh").is_file())
        check("open_source_maps has one file per node + index",
              len(list((brain / "open_source_maps").glob("*.md"))) == result.node_count + 1)

        print("\ncontext.json ledger")
        context = json.loads((brain / "context.json").read_text(encoding="utf-8"))
        check("records every node", len(context["nodes"]) == result.node_count)
        check("records a rationale per node", all(n["rationale"] for n in context["nodes"]))
        check("records the selected candidate", context["nodes"][0]["selected"] is not None)
        check("preserves the source prompt", context["source_prompt"] == payload.source_prompt)
        check("honours explicit selection over rank order",
              context["nodes"][0]["selected"]["name"] == "lucia-auth/lucia")
        check("derives a clone url", context["nodes"][0]["selected"]["clone_url"].endswith(".git"))

        print("\nsemantic_cache.db")
        conn = sqlite3.connect(brain / "semantic_cache.db")
        try:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            check("has meta/requirements/candidates/trends tables",
                  {"meta", "requirements", "candidates", "trends"} <= tables, str(sorted(tables)))
            req_count = conn.execute("SELECT COUNT(*) FROM requirements").fetchone()[0]
            check("one requirement row per node", req_count == result.node_count)
            cand_count = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
            check("candidate rows persisted", cand_count == result.candidate_count)
            sel = conn.execute("SELECT COUNT(*) FROM candidates WHERE selected=1").fetchone()[0]
            check("exactly one selection per node with candidates", sel == result.node_count)
            status = conn.execute("SELECT value FROM meta WHERE key='embedding_status'").fetchone()[0]
            check("embedding status is declared, not faked", "pending" in status)
            null_vecs = conn.execute("SELECT COUNT(*) FROM requirements WHERE embedding IS NULL").fetchone()[0]
            check("no fabricated embedding vectors", null_vecs == req_count)
        finally:
            conn.close()

        print("\ntrends_report.md")
        trends = (brain / "trends_report.md").read_text(encoding="utf-8")
        check("reports the signal count", f"**Signals collected**: {result.trend_count}" in trends)
        check("includes a real signal title", "Local-first sync is the hardest part" in trends)

        print("\ninit.sh")
        init_text = (tmp / "init.sh").read_text(encoding="utf-8")
        check("sets strict mode", "set -euo pipefail" in init_text)
        check("clones shallow", "--depth 1" in init_text)
        check("clones into reference/ only", 'REFERENCE_DIR="$ROOT/reference"' in init_text)
        check("uses LF line endings", "\r\n" not in init_text)

        if shutil.which("bash"):
            ok, err = bash_syntax_check(init_text)
            check("passes bash -n syntax check", ok, err)
        else:
            print("  SKIP  bash -n (bash not on PATH)")

        print("\nidempotence")
        second = compile_brain(payload, tmp)
        check("re-running does not error or duplicate", second.node_count == result.node_count)
        check("cache rebuilt cleanly", (brain / "semantic_cache.db").stat().st_size > 0)

        print("\nempty-scouting path")
        bare = BrainPayload.from_dict(
            {
                "project_name": "Bare",
                "summary": "A graph with no scouting results attached at all.",
                "nodes": [
                    {"id": "a", "category": "backend", "title": "A", "requirement": "Do the first thing well."},
                    {"id": "b", "category": "frontend", "title": "B", "requirement": "Do the second thing well."},
                ],
            }
        )
        tmp2 = Path(tempfile.mkdtemp(prefix="devcontext-bare-"))
        try:
            bare_result = compile_brain(bare, tmp2)
            check("compiles with zero candidates", bare_result.candidate_count == 0)
            check("still emits init.sh", bare_result.init_script.is_file())
            bare_init = bare_result.init_script.read_text(encoding="utf-8")
            check("init.sh handles no-repo case", "no vetted repositories recorded" in bare_init)
            if shutil.which("bash"):
                ok, err = bash_syntax_check(bare_init)
                check("empty-case init.sh is valid bash", ok, err)
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

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
