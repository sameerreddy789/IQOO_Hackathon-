# Demo Runbook

Exact commands for the screen recording that goes into the pitch deck and the
optional Video Walkthrough URL field. Run everything from `prototype/`.

Two versions below. **Record the fast one.** The slow one is the honest full
pipeline, but a 9-minute silence while a CPU grinds through 450 tokens is not a
demo — that latency is precisely what the on-site NPU work exists to fix.

---

## Version A — fast, for the recording (about 20 seconds)

Starts from a node graph, so no model inference. Shows SCOUT and COMPILE live and
produces the complete artifact.

```bash
# 1. Show there is nothing there yet
rm -rf ./brain-out

# 2. Compile the project brain
python -m devcontext.pipeline --graph examples/graph_audio.json --target ./brain-out --offline

# 3. Show what landed
find ./brain-out -type f          # Windows: Get-ChildItem ./brain-out -Recurse -File

# 4. Show the ledger - this is the payoff shot
cat ./brain-out/.devcontext/context.json

# 5. Show the generated bootstrap is real, runnable bash
bash -n ./brain-out/init.sh && echo "init.sh: valid"
cat ./brain-out/init.sh
```

With an `EXA_API_KEY` in `.env`, drop `--offline` from step 2 and the recording
also shows real scouted repositories and real Reddit threads landing in
`trends_report.md`. That is the more persuasive version — get a key if you can.

---

## Version B — the honest full chain (about 10 minutes)

Runs the local quantized SLM. Use this to capture *evidence*, not as the live demo.

```bash
python -m devcontext.pipeline --request "Build an audio streaming app using Node.js and a fast canvas frontend with offline sync" --target ./brain-out
```

Expect roughly 550-700 seconds on laptop CPU for the DECOMPOSE stage. Screenshot
the final summary rather than recording the wait.

---

## Proving the offline claim

The deck states that decomposition runs with no network. To demonstrate that
rather than assert it, point the process at a dead proxy so any outbound HTTP
fails, and confirm generation still completes:

```bash
# Windows PowerShell
$env:HTTP_PROXY="http://127.0.0.1:9"; $env:HTTPS_PROXY="http://127.0.0.1:9"
python -m devcontext.decompose --request "small cli tool to dedupe photos by hash"
Remove-Item Env:HTTP_PROXY, Env:HTTPS_PROXY
```

```bash
# macOS / Linux
HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 \
  python -m devcontext.decompose --request "small cli tool to dedupe photos by hash"
```

Airplane mode on the demo laptop makes the same point more viscerally for a judge
standing at the table.

> **Verified.** The dead-proxy check above has been executed. With `HTTP_PROXY`
> and `HTTPS_PROXY` both pointed at `127.0.0.1:9` and `HF_HUB_OFFLINE=1`, the
> decomposition still produced a schema-valid graph on attempt 1 in 248 seconds.
> This claim is safe to make on stage.

---

## Running the tests on camera

Fast, and it lands well with technical judges:

```bash
python -m tests.test_compile_brain      # 34 checks
python -m tests.test_decompose_logic    # 36 checks
```

Both finish in seconds, need no model, and need no network.

---

## What to say while it runs

1. **The problem** — every project starts with the same hour lost in browser tabs,
   and juniors at Indian service companies do it without a senior architect to ask.
2. **The input** — voice or a photo of a whiteboard, processed on the phone.
3. **The brain** — a quantized SLM on the Snapdragon NPU turns that into an
   architecture graph, offline.
4. **The vetting** — Exa scouts repositories and pulls the Reddit thread that says
   your chosen library has been unmaintained for a year.
5. **The handoff** — Office Kit carries the payload to the laptop, where
   `.devcontext/` lands in the project root and `init.sh` bootstraps everything.
6. **The artifact** — `context.json` outlives the session and tells the next
   developer, human or AI, why this stack was chosen.

Land on point 6. The differentiator is not that an AI suggested a stack; it is
that the reasoning persists in the repository.

---

## Do not forget

- [ ] `rm -rf ./brain-out` before recording, so the folder appearing is visible
- [ ] Terminal font size up, window narrow enough that lines do not wrap
- [ ] If recording on Windows, run `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`
      first, or accept the ASCII tree output (already the default)
- [ ] Keep it under 90 seconds for the submission video field
