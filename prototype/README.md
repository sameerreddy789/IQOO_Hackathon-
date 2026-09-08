# DevContext AI — Prototype Pipeline

Phase 1 prototype slice for **iQOO City Battles 2026**, Track #6 Developer Tools.

This is the laptop-side half of DevContext AI: the context compiler that turns a
natural-language project request into a persistent `.devcontext/` "brain folder".
The phone-side Flutter layers (CAPTURE, CURATE) are built on-site — see
[ONSITE_BUILD_PLAN.md](../documentation/ONSITE_BUILD_PLAN.md).

- Architecture spec: [PROJECT_DEVCONTEXT_SPEC.md](../documentation/PROJECT_DEVCONTEXT_SPEC.md)
- Submission copy: [PHASE_1_SUBMISSION_DRAFT.md](../documentation/PHASE_1_SUBMISSION_DRAFT.md)

---

## What runs today

```
request --> DECOMPOSE --> SCOUT --> COMPILE --> .devcontext/ + init.sh
            local SLM     Exa AI    ledger
            offline       HTTPS     + init script
```

| Stage | Status | Notes |
| :--- | :--- | :--- |
| **DECOMPOSE** | Verified working, offline proven | Quantized Phi-3-mini int4 via `onnxruntime-genai`. 5/5 schema-valid, all first-attempt. See [verified results](#verified-decompose-results). |
| **SCOUT** | Code complete, **unverified against the live API** | Needs an `EXA_API_KEY`. Degrades cleanly to zero candidates without one. See [Known gaps](#known-gaps). |
| **COMPILE** | Verified working | 34 checks green. Writes the full brain folder plus a syntax-valid `init.sh`. |
| **CAPTURE** | Not started | Camera OCR + mic STT, scheduled for the on-site build. |
| **CURATE** | Not started | Flutter node canvas, scheduled for the on-site build. |

### Verified DECOMPOSE results

The gating suite is five deliberately varied requests, including one terse
lowercase prompt and one with an embedded stack preference. Reproduce with
`python -m devcontext.decompose --suite`.

| # | Request | Result | Nodes | Attempts | Time |
| :--- | :--- | :--- | :---: | :---: | :---: |
| 1 | Audio streaming app, Node.js, canvas frontend, offline sync | VALID | 4 | 1 of 3 | 546 s |
| 2 | Telemedicine booking with video consults and online payment | VALID | 4 | 1 of 3 | 549 s |
| 3 | `small cli tool to dedupe photos on my nas by perceptual hash` | VALID | 2 | 1 of 3 | 477 s |
| 4 | Offline-capable attendance system for a tier-2 college | VALID | 3 | 1 of 3 | 467 s |
| 5 | Real-time multiplayer quiz game for Android with anti-cheat | VALID | 4 | 1 of 3 | 420 s |

**5/5 schema-valid, every one on the first attempt.** The repair loop never had to
fire, which is a stronger result than the 4/5 gate required. Verbatim output from
run 1 is committed at
[`examples/graph_audio_model_output.json`](./examples/graph_audio_model_output.json).

Two honest notes on this table:

- **Run 3 produced 2 nodes while the prompt asks for 3 to 7.** The schema permits
  a minimum of 2, so it passed validation. For a single-purpose dedupe CLI, two
  nodes is arguably the right answer, so this is recorded as a prompt/schema
  tension rather than patched over. Worth revisiting if node counts skew low on
  richer requests.
- **The repair loop is therefore untested against real model failure.** It is
  covered by 36 unit checks against synthetic malformed output, but no live
  generation has yet needed it.

### Offline execution: proven, not asserted

The "runs with no network" claim was verified empirically rather than argued from
the absence of HTTP imports. With `HTTP_PROXY` and `HTTPS_PROXY` both pointed at a
dead port (`127.0.0.1:9`) and `HF_HUB_OFFLINE=1` set, decomposition still produced
a schema-valid graph on attempt 1 in 248 seconds. Reproduce with the commands in
[DEMO.md](./DEMO.md#proving-the-offline-claim).

### The latency finding

Average generation was **492 seconds on laptop CPU**. That figure is the point of
the on-site work, not a footnote: a 3.8B int4 model on CPU is far from usable
interactive latency. NPU-accelerated inference through `onnxruntime-genai`'s
Android bindings is what makes this loop viable on the phone, and it is the first
Green Light task in the [on-site plan](../documentation/ONSITE_BUILD_PLAN.md).

---

## Setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r prototype/requirements.txt   # Windows
# .venv/bin/python -m pip install -r prototype/requirements.txt     # macOS/Linux
```

Fetch the model artifact (~2.73 GB, resumable, gitignored):

```bash
python prototype/scripts/fetch_model.py
```

Optional, to enable SCOUT — create `.env` at the repo root:

```
EXA_API_KEY=your_key_here
```

Get a key at <https://dashboard.exa.ai/api-keys>. Without it the pipeline still
runs end to end; nodes just carry no scouted candidates.

---

## Usage

Full chain, local model does the decomposition:

```bash
python -m devcontext.pipeline --request "Build an audio streaming app with offline sync" --target ./brain-out
```

Skip the model and start from a node graph (useful when the weights are not on disk):

```bash
python -m devcontext.pipeline --graph examples/graph_audio.json --target ./brain-out --offline
```

Compile a finished payload directly:

```bash
python -m devcontext.pipeline --payload examples/sample_payload.json --target ./brain-out
```

Individual stages:

```bash
python -m devcontext.decompose --request "..." --out graph.json
python -m devcontext.decompose --suite                      # 5-prompt validation suite
python -m devcontext.scout --payload graph.json --out scouted.json
python -m devcontext.compile_brain --payload scouted.json --target ./brain-out
```

Every entry point works from the `prototype/` directory.

---

## Output

```
brain-out/
+-- .devcontext/
|   +-- context.json          structural ledger: what was chosen and why
|   +-- semantic_cache.db      SQLite vector store (schema + text; vectors pending)
|   +-- open_source_maps/      one markdown brief per node, plus an index
|   `-- trends_report.md       community signal and risk log
`-- init.sh                    bootstrap: shallow-clones vetted repos, resolves deps
```

### `context.json`

The architecture ledger. Records each node's requirement, the selected candidate,
the alternatives that lost, and a rationale. The rationale is **composed from
scouting evidence, not generated by the model** — a hallucinated justification in
a file that outlives the project would be worse than no justification.

### `semantic_cache.db`

Real SQLite with four tables (`meta`, `requirements`, `candidates`, `trends`).
Embedding columns are deliberately `NULL` and `meta.embedding_status` records why:
the on-device ONNX embedder that fills them is scheduled for the on-site build.
Writing placeholder vectors would make the artifact untrustworthy.

### `init.sh`

Shallow-clones the selected repositories into `reference/` for reading, then
resolves dependencies **only** from the project's own manifests. Third-party
manifests inside `reference/` are intentionally ignored: repositories surfaced by
semantic search are untrusted input, and auto-installing from them would be a
supply-chain hazard.

---

## Tests

```bash
python -m tests.test_compile_brain      # 34 checks — output tree, ledger, SQLite, init.sh
python -m tests.test_decompose_logic    # 36 checks — JSON recovery and graph coercion
```

Both run without the model and without network access. `test_decompose_logic`
covers the failure modes small quantized models actually produce: code fences,
trailing chatter, invalid enum values, CamelCase and duplicate ids, missing
optional arrays, and hostile input.

---

## Design decisions worth knowing

**No backend service.** The Flutter client calls Exa directly over HTTPS. A
FastAPI orchestration layer was in the original design and was cut: a localhost
dependency cannot function during Red Light windows, which are 55% of the on-site
build.

**Model choice was constrained, not free.** `microsoft/Llama-3.2-1B-Instruct-ONNX`
is gated (401) and the `onnx-community` Llama export ships no `genai_config.json`,
so it is not ORT-GenAI format. `microsoft/Phi-3-mini-4k-instruct-onnx` is MIT and
ungated, and its `cpu_and_mobile` int4 variant is Microsoft's own mobile target.

**Phi-3-mini is 3.8B — heavier than ideal for a phone.** Proving the prompt on a
larger model is the optimistic direction, not the conservative one. If the on-site
build drops to a smaller model for latency, the 5-prompt suite must be re-run.
The prompt, schema and validator are model-agnostic by design, so that swap costs
a re-validation rather than a rewrite.

**Generation is wrapped in a repair loop.** Small models drift on structured
output, so `decompose.py` extracts JSON by brace-matching, coerces mechanical
mistakes, validates against the schema, and feeds specific errors back for up to
three attempts. Coercion never fabricates nodes or requirements.

**Exa responses are cached to disk.** Not just a dev convenience: it means a live
demo can replay without the API if the key rate-limits during judging, which is
the documented fallback in the on-site plan.

---

## Known gaps

| Gap | Impact | Plan |
| :--- | :--- | :--- |
| **No `EXA_API_KEY` available** | SCOUT is code-complete but has never run against the live API. Request shaping, auth header, pagination and error paths are written to the published contract and unit-tested against synthetic responses, but not confirmed end to end. | Obtain a key and run `python -m devcontext.scout --payload examples/graph_audio.json`. This is the highest-priority verification item. |
| Embedding vectors not generated | `semantic_cache.db` carries text and schema but no vectors | On-device ONNX embedder, on-site Green Light window |
| No Flutter client | Phone layers absent | On-site, first Green Light window |
| CPU-only inference at 702 s per graph | Far too slow to demo interactively | NPU acceleration via onnxruntime-genai Android bindings, first Green Light task on-site |
| Model artifact download took 3 h 21 min | Cannot be repeated on event wifi | Pre-download to the build laptop before travelling to Chennai |

---

## Layout

```
prototype/
+-- devcontext/
|   +-- models.py          data contracts, schema validation
|   +-- decompose.py       DECOMPOSE  local SLM -> node graph
|   +-- scout.py           SCOUT      Exa search -> candidates + trends
|   +-- compile_brain.py   COMPILE    payload -> .devcontext/
|   `-- pipeline.py        the three wired together
+-- prompts/
|   `-- decompose_prompt.md    the locked prompt, with few-shot examples
+-- schemas/
|   `-- node_graph.schema.json the contract between all stages
+-- examples/              node graph and payload fixtures
+-- scripts/fetch_model.py model download
`-- tests/                 verification suites
```

The schema and prompt are plain files rather than embedded strings specifically
so the Flutter client can consume the identical contract on device.
