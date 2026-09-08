"""COMPILE — materialize a `.devcontext/` brain folder from a payload.

This is the component that runs on the laptop as the CLI listener. On-site it is
fed by the Office Kit bridge (shared clipboard or transferred file); tonight it is
fed by the local pipeline. Either way the input is the same JSON payload, which is
why the handoff is a transport detail rather than an architectural one.

Usage:
    python -m devcontext.compile_brain --payload examples/sample_payload.json --target ./out
    python -m devcontext.compile_brain --stdin --target ./out
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .models import BrainPayload, ScoutedNode

BRAIN_DIRNAME = ".devcontext"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requirements (
    node_id         TEXT PRIMARY KEY,
    category        TEXT NOT NULL,
    title           TEXT NOT NULL,
    requirement     TEXT NOT NULL,
    embedding       BLOB,
    embedding_model TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
    node_id  TEXT NOT NULL,
    name     TEXT NOT NULL,
    url      TEXT NOT NULL,
    host     TEXT,
    score    REAL,
    selected INTEGER NOT NULL DEFAULT 0,
    summary  TEXT,
    PRIMARY KEY (node_id, url)
);

CREATE TABLE IF NOT EXISTS trends (
    node_id   TEXT NOT NULL,
    title     TEXT NOT NULL,
    url       TEXT NOT NULL,
    source    TEXT,
    excerpt   TEXT,
    published TEXT,
    PRIMARY KEY (node_id, url)
);

CREATE INDEX IF NOT EXISTS idx_requirements_category ON requirements (category);
CREATE INDEX IF NOT EXISTS idx_candidates_node ON candidates (node_id);
CREATE INDEX IF NOT EXISTS idx_trends_node ON trends (node_id);
"""


@dataclass
class BrainWriteResult:
    """What was produced, for reporting and for tests to assert against."""

    brain_dir: Path
    init_script: Path
    files_written: list[Path]
    node_count: int
    candidate_count: int
    trend_count: int


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(value: str) -> str:
    keep = [c if (c.isalnum() or c in "-_") else "-" for c in value.strip().lower()]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "node"


# --------------------------------------------------------------------------- #
# context.json
# --------------------------------------------------------------------------- #

def _build_context(payload: BrainPayload) -> dict[str, object]:
    """The structural ledger. Records what was chosen and why."""
    return {
        "schema_version": 1,
        "generated_at": _now(),
        "generator": payload.generator,
        "decomposition_model": payload.model or "unknown",
        "project": {
            "name": payload.project_name,
            "summary": payload.summary,
            "constraints": payload.constraints,
            "target_platforms": payload.target_platforms,
        },
        "source_prompt": payload.source_prompt,
        "nodes": [
            {
                "id": node.id,
                "category": node.category,
                "title": node.title,
                "requirement": node.requirement,
                "rationale": node.rationale,
                "selected": (
                    {
                        "name": node.chosen.name,
                        "url": node.chosen.url,
                        "host": node.chosen.host,
                        "clone_url": node.chosen.clone_url,
                        "score": node.chosen.score,
                    }
                    if node.chosen
                    else None
                ),
                "alternatives": [
                    {"name": c.name, "url": c.url, "score": c.score}
                    for c in node.candidates
                    if node.chosen is None or c.url != node.chosen.url
                ],
                "community_signals": len(node.trends),
            }
            for node in payload.nodes
        ],
    }


# --------------------------------------------------------------------------- #
# semantic_cache.db
# --------------------------------------------------------------------------- #

def _write_semantic_cache(db_path: Path, payload: BrainPayload) -> None:
    """Create the portable vector store.

    Embedding vectors are left NULL tonight and `embedding_status` records why.
    The on-device ONNX embedder that fills them is scheduled for the on-site
    build; writing fake vectors here would make the artifact untrustworthy.
    """
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.executemany(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            [
                ("project_name", payload.project_name),
                ("generated_at", _now()),
                ("generator", payload.generator),
                ("decomposition_model", payload.model or "unknown"),
                ("embedding_model", ""),
                ("embedding_status", "pending: on-device ONNX embedder lands in the on-site build"),
                ("vector_dim", "0"),
            ],
        )
        conn.executemany(
            "INSERT OR REPLACE INTO requirements "
            "(node_id, category, title, requirement, embedding, embedding_model, created_at) "
            "VALUES (?, ?, ?, ?, NULL, NULL, ?)",
            [(n.id, n.category, n.title, n.requirement, _now()) for n in payload.nodes],
        )
        conn.executemany(
            "INSERT OR REPLACE INTO candidates "
            "(node_id, name, url, host, score, selected, summary) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    n.id,
                    c.name,
                    c.url,
                    c.host,
                    c.score,
                    1 if (n.chosen is not None and c.url == n.chosen.url) else 0,
                    c.summary,
                )
                for n in payload.nodes
                for c in n.candidates
            ],
        )
        conn.executemany(
            "INSERT OR REPLACE INTO trends "
            "(node_id, title, url, source, excerpt, published) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (n.id, t.title, t.url, t.source, t.excerpt, t.published)
                for n in payload.nodes
                for t in n.trends
            ],
        )
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# open_source_maps/
# --------------------------------------------------------------------------- #

def _write_open_source_maps(maps_dir: Path, payload: BrainPayload) -> list[Path]:
    maps_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for node in payload.nodes:
        lines = [
            f"# {node.title}",
            "",
            f"- **Node id**: `{node.id}`",
            f"- **Category**: `{node.category}`",
            f"- **Requirement**: {node.requirement}",
            "",
            "## Decision",
            "",
            node.rationale,
            "",
        ]

        if node.candidates:
            lines += [
                "## Vetted candidates",
                "",
                "| # | Candidate | Host | Score | Selected |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ]
            chosen_url = node.chosen.url if node.chosen else ""
            for i, c in enumerate(node.candidates, start=1):
                mark = "yes" if c.url == chosen_url else ""
                lines.append(
                    f"| {i} | [{c.name}]({c.url}) | {c.host or '-'} | {c.score:.3f} | {mark} |"
                )
            lines.append("")
            for c in node.candidates:
                if c.summary:
                    lines += [f"### {c.name}", "", c.summary.strip(), "", f"<{c.url}>", ""]
        else:
            lines += ["## Vetted candidates", "", "_No candidates scouted for this node yet._", ""]

        path = maps_dir / f"{_slug(node.id)}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        written.append(path)

    index = ["# Open Source Maps", "", f"Vetted tooling per node for **{payload.project_name}**.", ""]
    index += [f"- [{n.title}](./{_slug(n.id)}.md) — `{n.category}`" for n in payload.nodes]
    index.append("")
    index_path = maps_dir / "README.md"
    index_path.write_text("\n".join(index), encoding="utf-8")
    written.append(index_path)
    return written


# --------------------------------------------------------------------------- #
# trends_report.md
# --------------------------------------------------------------------------- #

def _write_trends_report(path: Path, payload: BrainPayload) -> None:
    total = sum(len(n.trends) for n in payload.nodes)
    lines = [
        "# Community Trends & Risk Report",
        "",
        f"**Project**: {payload.project_name}  ",
        f"**Generated**: {_now()}  ",
        f"**Signals collected**: {total}",
        "",
        "> Community signal gathered from developer channels during the SCOUT phase.",
        "> This is the context that normally gets missed during early planning: the thread",
        "> explaining that a library you are about to adopt has been unmaintained for a year.",
        "",
    ]

    if total == 0:
        lines += [
            "## No signals collected",
            "",
            "SCOUT returned no community results for this run. Either the Exa API key was",
            "absent or the queries matched nothing. Re-run with `EXA_API_KEY` set to populate",
            "this report.",
            "",
        ]
    else:
        for node in payload.nodes:
            if not node.trends:
                continue
            lines += [f"## {node.title} (`{node.category}`)", "", f"_Requirement: {node.requirement}_", ""]
            for t in node.trends:
                lines.append(f"### [{t.title}]({t.url})")
                lines.append("")
                meta = [bit for bit in (t.source, t.published) if bit]
                if meta:
                    lines += [f"`{' · '.join(meta)}`", ""]
                if t.excerpt:
                    excerpt = t.excerpt.strip().replace("\n", " ")
                    if len(excerpt) > 600:
                        excerpt = excerpt[:600].rstrip() + "..."
                    lines += ["> " + excerpt, ""]

    path.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------- #
# init.sh
# --------------------------------------------------------------------------- #

_DEP_HINTS: list[tuple[str, str, str]] = [
    ("package.json", "npm install", "Node"),
    ("pubspec.yaml", "flutter pub get", "Flutter"),
    ("requirements.txt", "pip install -r requirements.txt", "Python"),
    ("pyproject.toml", "pip install -e .", "Python"),
    ("go.mod", "go mod download", "Go"),
    ("Cargo.toml", "cargo fetch", "Rust"),
]


def _write_init_script(path: Path, payload: BrainPayload) -> None:
    """Generate the bootstrap script.

    Security posture, deliberate: repositories surfaced by semantic search are
    cloned shallow into `reference/` for reading, and are never auto-installed or
    executed. Dependency resolution only runs against the project's own manifest.
    """
    clones: list[tuple[str, str]] = []
    for node in payload.nodes:
        chosen = node.chosen
        if chosen and chosen.clone_url:
            clones.append((_slug(chosen.name), chosen.clone_url))

    lines = [
        "#!/usr/bin/env bash",
        "# ---------------------------------------------------------------",
        f"# {payload.project_name} — bootstrap",
        "# Generated by DevContext AI. Regenerate rather than hand-editing.",
        "# ---------------------------------------------------------------",
        "set -euo pipefail",
        "",
        'ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        'REFERENCE_DIR="$ROOT/reference"',
        "",
        'echo "=============================================="',
        f'echo "  {payload.project_name}"',
        f'echo "  {len(payload.nodes)} nodes · {len(clones)} vetted repos"',
        'echo "=============================================="',
        "echo",
        "",
        "# --- Vetted open-source references ---------------------------",
        "# Shallow clones for reading only. Nothing here is installed or executed.",
        'mkdir -p "$REFERENCE_DIR"',
        "",
    ]

    if clones:
        for name, url in clones:
            lines += [
                f'if [ -d "$REFERENCE_DIR/{name}/.git" ]; then',
                f'  echo "[skip]  {name} already cloned"',
                "else",
                f'  echo "[clone] {name}"',
                f'  git clone --depth 1 --quiet "{url}" "$REFERENCE_DIR/{name}" \\',
                f'    || echo "[warn]  clone failed: {url}"',
                "fi",
                "",
            ]
    else:
        lines += ['echo "[info]  no vetted repositories recorded for this build"', ""]

    lines += [
        "# --- Project dependencies ------------------------------------",
        "# Only the project's own manifests are resolved. Third-party manifests",
        "# inside reference/ are intentionally ignored.",
        "",
    ]
    for manifest, command, label in _DEP_HINTS:
        lines += [
            f'if [ -f "$ROOT/{manifest}" ]; then',
            f'  echo "[deps]  {label} detected -> {command}"',
            f'  ( cd "$ROOT" && {command} )',
            "fi",
            "",
        ]

    lines += [
        "echo",
        'echo "Bootstrap complete."',
        'echo "  Architecture ledger : .devcontext/context.json"',
        'echo "  Vetted tooling      : .devcontext/open_source_maps/"',
        'echo "  Community risks     : .devcontext/trends_report.md"',
        'echo "  Reference clones    : reference/"',
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    try:
        path.chmod(0o755)
    except (OSError, NotImplementedError):
        pass  # Windows filesystems ignore the exec bit; harmless


# --------------------------------------------------------------------------- #
# entry points
# --------------------------------------------------------------------------- #

def compile_brain(payload: BrainPayload, target: Path) -> BrainWriteResult:
    """Write the full `.devcontext/` tree plus `init.sh` into ``target``."""
    target = target.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)

    brain_dir = target / BRAIN_DIRNAME
    brain_dir.mkdir(exist_ok=True)

    written: list[Path] = []

    context_path = brain_dir / "context.json"
    context_path.write_text(
        json.dumps(_build_context(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    written.append(context_path)

    cache_path = brain_dir / "semantic_cache.db"
    _write_semantic_cache(cache_path, payload)
    written.append(cache_path)

    written.extend(_write_open_source_maps(brain_dir / "open_source_maps", payload))

    trends_path = brain_dir / "trends_report.md"
    _write_trends_report(trends_path, payload)
    written.append(trends_path)

    init_path = target / "init.sh"
    _write_init_script(init_path, payload)
    written.append(init_path)

    return BrainWriteResult(
        brain_dir=brain_dir,
        init_script=init_path,
        files_written=written,
        node_count=len(payload.nodes),
        candidate_count=sum(len(n.candidates) for n in payload.nodes),
        trend_count=sum(len(n.trends) for n in payload.nodes),
    )


def _load_payload(args: argparse.Namespace) -> BrainPayload:
    if args.stdin:
        return BrainPayload.from_dict(json.load(sys.stdin))
    with Path(args.payload).expanduser().open(encoding="utf-8") as fh:
        return BrainPayload.from_dict(json.load(fh))


def main(argv: list[str] | None = None) -> int:
    from . import enable_utf8_stdout

    enable_utf8_stdout()
    parser = argparse.ArgumentParser(
        prog="devcontext.compile_brain",
        description="Materialize a .devcontext/ brain folder from a payload.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--payload", help="path to a brain payload JSON file")
    source.add_argument(
        "--stdin",
        action="store_true",
        help="read the payload from stdin (used by the Office Kit clipboard handoff)",
    )
    parser.add_argument(
        "--target",
        default=".",
        help="project root that should receive .devcontext/ and init.sh (default: cwd)",
    )
    args = parser.parse_args(argv)

    try:
        payload = _load_payload(args)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"error: could not read payload: {exc}", file=sys.stderr)
        return 1

    try:
        result = compile_brain(payload, Path(args.target))
    except OSError as exc:
        print(f"error: could not write brain folder: {exc}", file=sys.stderr)
        return 1

    print(f"Compiled project brain for: {payload.project_name}")
    print(f"  target      : {result.brain_dir.parent}")
    print(f"  nodes       : {result.node_count}")
    print(f"  candidates  : {result.candidate_count}")
    print(f"  signals     : {result.trend_count}")
    print(f"  files       : {len(result.files_written)}")
    print()
    print("  .devcontext/")
    print("  +-- context.json")
    print("  +-- semantic_cache.db")
    print("  +-- open_source_maps/")
    print("  `-- trends_report.md")
    print("  init.sh")
    print()
    print(f"Next: cd {result.brain_dir.parent} && bash init.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
