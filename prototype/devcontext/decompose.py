"""DECOMPOSE — turn a natural-language project request into a node graph.

Runs a quantized Phi-3-mini through onnxruntime-genai entirely offline. On-site
this same prompt, schema and validator run against onnxruntime-genai's Android
bindings on the Snapdragon NPU; only the runtime handle changes, which is why
the uncertain part (schema adherence) is worth proving on the laptop first.

Small quantized models drift on structured output, so generation is wrapped in a
validate-and-repair loop rather than trusted on the first pass.

Usage:
    python -m devcontext.decompose --request "build an audio streaming app"
    python -m devcontext.decompose --suite          # run the 5-prompt validation suite
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import validate_node_graph

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "decompose_prompt.md"
MODEL_DIR = (
    Path(__file__).resolve().parents[2]
    / "models"
    / "phi3-mini-4k-int4"
    / "cpu_and_mobile"
    / "cpu-int4-rtn-block-32-acc-level-4"
)

VALID_CATEGORIES = {
    "auth", "database", "backend", "frontend", "realtime", "storage",
    "ml", "infra", "payments", "testing", "observability", "other",
}
VALID_PLATFORMS = {"android", "ios", "web", "desktop", "server", "cli"}

# The suite that gates this component. Deliberately varied in domain and phrasing,
# including one terse lowercase request and one with an embedded stack preference.
VALIDATION_SUITE: list[str] = [
    "Build an audio streaming app using Node.js and a fast canvas frontend with offline sync",
    "I need a telemedicine booking platform where patients book video consults with doctors and pay online",
    "small cli tool to dedupe photos on my nas by perceptual hash",
    "Build a college attendance system for a tier-2 engineering college. Faculty mark attendance from their phone, works offline in classrooms with no wifi, students see their percentage.",
    "real time multiplayer quiz game for android, needs leaderboards and anti-cheat",
]


class DecomposeError(RuntimeError):
    """Raised when the model cannot be loaded or produces nothing usable."""


@dataclass
class DecomposeResult:
    """One decomposition attempt chain, including repairs."""

    request: str
    graph: dict[str, Any] | None
    attempts: int
    elapsed_s: float
    errors: list[str] = field(default_factory=list)
    raw_outputs: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.graph is not None


# --------------------------------------------------------------------------- #
# JSON recovery
# --------------------------------------------------------------------------- #

def extract_json(text: str) -> str | None:
    """Pull the first balanced JSON object out of raw model output.

    Small models routinely wrap JSON in a code fence or add a closing remark, so
    brace-matching is more reliable than trusting the whole response.
    """
    if not text:
        return None

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)

    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def coerce_graph(graph: dict[str, Any]) -> dict[str, Any]:
    """Repair the mechanical mistakes small models make, without inventing content.

    Only normalizes: missing optional arrays, out-of-enum categories and
    platforms, non-snake_case ids, over-long strings, and stray unknown keys.
    Never fabricates nodes or requirements.
    """
    cleaned: dict[str, Any] = {}

    cleaned["project_name"] = str(graph.get("project_name") or "Untitled Project")[:80]
    summary = str(graph.get("summary") or "").strip()
    cleaned["summary"] = (summary or "No summary produced by the model.")[:400]

    constraints = graph.get("constraints")
    cleaned["constraints"] = (
        [str(c)[:120] for c in constraints if str(c).strip()][:10]
        if isinstance(constraints, list)
        else []
    )

    platforms = graph.get("target_platforms")
    if isinstance(platforms, list):
        cleaned["target_platforms"] = [
            p for p in (str(x).strip().lower() for x in platforms) if p in VALID_PLATFORMS
        ][:6]
    else:
        cleaned["target_platforms"] = []

    nodes_in = graph.get("nodes")
    nodes_out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    if isinstance(nodes_in, list):
        for raw in nodes_in:
            if not isinstance(raw, dict):
                continue

            node_id = re.sub(r"[^a-z0-9_]", "_", str(raw.get("id") or "").strip().lower())
            node_id = re.sub(r"_+", "_", node_id).strip("_")
            if not node_id or len(node_id) < 2:
                node_id = f"node_{len(nodes_out) + 1}"
            base = node_id[:40]
            node_id, suffix = base, 2
            while node_id in seen_ids:
                node_id = f"{base[:37]}_{suffix}"
                suffix += 1
            seen_ids.add(node_id)

            category = str(raw.get("category") or "").strip().lower()
            if category not in VALID_CATEGORIES:
                category = "other"

            title = str(raw.get("title") or node_id.replace("_", " ").title()).strip()[:60]
            if len(title) < 2:
                title = node_id.replace("_", " ").title()[:60]

            requirement = " ".join(str(raw.get("requirement") or "").split())[:300]
            if len(requirement) < 10:
                requirement = f"Provide the {title} capability for this project."[:300]

            node: dict[str, Any] = {
                "id": node_id,
                "category": category,
                "title": title,
                "requirement": requirement,
            }
            hint = " ".join(str(raw.get("search_hint") or "").split())[:120]
            if hint:
                node["search_hint"] = hint
            nodes_out.append(node)

    cleaned["nodes"] = nodes_out[:12]
    return cleaned


# --------------------------------------------------------------------------- #
# model runtime
# --------------------------------------------------------------------------- #

class Decomposer:
    """Wraps onnxruntime-genai. The model is loaded once and reused."""

    def __init__(
        self,
        model_dir: Path | None = None,
        *,
        max_new_tokens: int = 1100,
        temperature: float = 0.2,
        max_attempts: int = 3,
    ) -> None:
        self.model_dir = model_dir or MODEL_DIR
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.max_attempts = max_attempts
        self._model: Any = None
        self._tokenizer: Any = None
        self._genai: Any = None
        self.template = PROMPT_PATH.read_text(encoding="utf-8")

    # -- loading ----------------------------------------------------------- #

    def load(self) -> None:
        if self._model is not None:
            return

        try:
            import onnxruntime_genai as genai
        except ImportError as exc:  # pragma: no cover
            raise DecomposeError(
                "onnxruntime-genai is not installed. pip install onnxruntime-genai"
            ) from exc

        if not (self.model_dir / "genai_config.json").is_file():
            raise DecomposeError(
                f"No ORT-GenAI model at {self.model_dir}\n"
                "Run: python prototype/scripts/fetch_model.py"
            )

        self._genai = genai
        try:
            self._model = genai.Model(str(self.model_dir))
            self._tokenizer = genai.Tokenizer(self._model)
        except Exception as exc:  # noqa: BLE001 - surface any runtime load failure
            raise DecomposeError(f"Failed to load model: {exc}") from exc

    @property
    def model_label(self) -> str:
        return f"phi3-mini-4k-instruct/{self.model_dir.name} (onnxruntime-genai)"

    # -- generation -------------------------------------------------------- #

    def _build_prompt(self, request: str, repair_note: str = "") -> str:
        body = self.template.replace("{{REQUEST}}", request.strip())
        if repair_note:
            body += (
                "\n\nYour previous answer was rejected for these reasons:\n"
                f"{repair_note}\n"
                "Emit the corrected JSON object only."
            )
        return f"<|user|>\n{body}<|end|>\n<|assistant|>\n"

    def _generate(self, prompt: str) -> str:
        genai = self._genai
        params = genai.GeneratorParams(self._model)

        config: dict[str, Any] = {
            "max_length": self.max_new_tokens + len(self._tokenizer.encode(prompt)),
            "temperature": self.temperature,
            "top_p": 0.9,
            "do_sample": self.temperature > 0,
        }
        try:
            params.set_search_options(**config)
        except TypeError:
            params.set_search_options(max_length=config["max_length"])

        generator = genai.Generator(self._model, params)
        stream = self._tokenizer.create_stream()
        chunks: list[str] = []
        try:
            generator.append_tokens(self._tokenizer.encode(prompt))
            while not generator.is_done():
                generator.generate_next_token()
                chunks.append(stream.decode(generator.get_next_tokens()[0]))
        except AttributeError:
            # Older onnxruntime-genai used input_ids on params plus compute_logits().
            params.input_ids = self._tokenizer.encode(prompt)
            generator = genai.Generator(self._model, params)
            chunks = []
            while not generator.is_done():
                generator.compute_logits()
                generator.generate_next_token()
                chunks.append(stream.decode(generator.get_next_tokens()[0]))
        finally:
            del generator

        return "".join(chunks)

    # -- public API -------------------------------------------------------- #

    def decompose(self, request: str, *, verbose: bool = False) -> DecomposeResult:
        """Generate, validate, and repair until the graph satisfies the schema."""
        self.load()
        started = time.perf_counter()
        errors: list[str] = []
        raw_outputs: list[str] = []
        repair_note = ""

        for attempt in range(1, self.max_attempts + 1):
            if verbose:
                print(f"    attempt {attempt}/{self.max_attempts}", flush=True)

            raw = self._generate(self._build_prompt(request, repair_note))
            raw_outputs.append(raw)

            candidate = extract_json(raw)
            if candidate is None:
                repair_note = "- No JSON object was found in your reply."
                errors.append(f"attempt {attempt}: no JSON object in output")
                continue

            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError as exc:
                repair_note = f"- The JSON did not parse: {exc.msg} near position {exc.pos}."
                errors.append(f"attempt {attempt}: JSON parse error ({exc.msg})")
                continue

            if not isinstance(parsed, dict):
                repair_note = "- Top level value must be a JSON object."
                errors.append(f"attempt {attempt}: top-level value was {type(parsed).__name__}")
                continue

            graph = coerce_graph(parsed)
            problems = validate_node_graph(graph)
            if not problems:
                return DecomposeResult(
                    request=request,
                    graph=graph,
                    attempts=attempt,
                    elapsed_s=time.perf_counter() - started,
                    errors=errors,
                    raw_outputs=raw_outputs,
                )

            repair_note = "\n".join(f"- {p}" for p in problems[:6])
            errors.append(f"attempt {attempt}: {len(problems)} schema error(s): {problems[0]}")

        return DecomposeResult(
            request=request,
            graph=None,
            attempts=self.max_attempts,
            elapsed_s=time.perf_counter() - started,
            errors=errors,
            raw_outputs=raw_outputs,
        )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def run_suite(decomposer: Decomposer, requests: list[str]) -> int:
    """Run the gating suite. Every prompt must yield a schema-valid graph."""
    print(f"Validation suite — {len(requests)} prompts")
    print(f"model: {decomposer.model_label}\n")

    passed = 0
    for index, request in enumerate(requests, start=1):
        preview = request if len(request) <= 78 else request[:75] + "..."
        print(f"[{index}/{len(requests)}] {preview}")
        try:
            result = decomposer.decompose(request, verbose=True)
        except DecomposeError as exc:
            print(f"    ERROR {exc}\n")
            return 1

        if result.ok and result.graph is not None:
            passed += 1
            nodes = result.graph["nodes"]
            print(
                f"    VALID  {len(nodes)} nodes · {result.attempts} attempt(s) · "
                f"{result.elapsed_s:.1f}s"
            )
            print(f"    name   {result.graph['project_name']}")
            print(f"    nodes  {', '.join(n['id'] for n in nodes)}")
        else:
            print(f"    INVALID after {result.attempts} attempts · {result.elapsed_s:.1f}s")
            for err in result.errors[-2:]:
                print(f"      {err}")
        print()

    print("-" * 52)
    print(f"schema-valid: {passed}/{len(requests)}")
    if passed == len(requests):
        print("suite green")
        return 0
    if passed >= 4:
        print("above the 4/5 gate — acceptable, note the failure in the README")
        return 0
    print("below the 4/5 gate — add few-shot examples rather than tuning further")
    return 1


def main(argv: list[str] | None = None) -> int:
    from . import enable_utf8_stdout

    enable_utf8_stdout()
    parser = argparse.ArgumentParser(
        prog="devcontext.decompose",
        description="Decompose a project request into a node graph using a local ONNX SLM.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--request", help="the project request to decompose")
    group.add_argument("--suite", action="store_true", help="run the 5-prompt validation suite")
    parser.add_argument("--out", help="write the resulting node graph JSON here")
    parser.add_argument("--model-dir", help="override the ORT-GenAI model directory")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--show-raw", action="store_true", help="print raw model output on failure")
    args = parser.parse_args(argv)

    decomposer = Decomposer(
        Path(args.model_dir) if args.model_dir else None,
        max_attempts=args.max_attempts,
    )

    if args.suite:
        try:
            return run_suite(decomposer, VALIDATION_SUITE)
        except DecomposeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    try:
        result = decomposer.decompose(args.request, verbose=True)
    except DecomposeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not result.ok or result.graph is None:
        print(f"\nFailed to produce a schema-valid graph in {result.attempts} attempts.")
        for err in result.errors:
            print(f"  {err}")
        if args.show_raw and result.raw_outputs:
            print("\n--- last raw output ---")
            print(result.raw_outputs[-1][:2000])
        return 1

    serialized = json.dumps(result.graph, indent=2, ensure_ascii=False)
    print(
        f"\nVALID after {result.attempts} attempt(s) in {result.elapsed_s:.1f}s "
        f"({len(result.graph['nodes'])} nodes)"
    )
    if args.out:
        Path(args.out).write_text(serialized + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print()
        print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
