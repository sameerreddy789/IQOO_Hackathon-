# ONSITE_BUILD_PLAN: Chennai City Battle — 19-Hour Execution Schedule

> [!IMPORTANT]
> This plan assumes the Red/Green cycle pattern below. Organizers announce the actual interval boundaries at the Saturday keynote. **The task ordering is what matters, not the exact clock times** — if the announced pattern differs, resequence tasks by their Red/Green tag and keep the dependency order intact.

- **Event window**: Sat 12 – Sun 13 September 2026
- **Active build time**: 19 hours (Red 55% ≈ 10.5 hrs · Green 45% ≈ 8.5 hrs)
- **Reference**: [Rules & Scoring](./HACKATHON_RULES_AND_SCORING.md) · [Office Kit Strategy](./OFFICE_KIT_AND_RED_LIGHT_STRATEGY.md) · [Architecture Spec](./PROJECT_DEVCONTEXT_SPEC.md)

---

## 1. The One Rule That Protects the Whole Plan

> [!WARNING]
> **Set up hot-reload during the FIRST Green window, before Red Light ever starts.** Every hour of Red Light without live reload is an hour of dead time, and Red Light is 55% of the build. This single setup task is worth more than any feature.

```bash
# Run during Green Light 1, verify it works, never touch it again
adb reverse tcp:3000 tcp:3000
flutter run --hot          # confirm a hot reload lands on the mirrored phone screen
```

Once this works, you edit on the laptop and the change appears on the mirrored iQOO screen without touching phone controls — which keeps you productive during Red Light while staying inside the Office Kit interface.

---

## 2. Pre-Flight: Before the Clock Starts

| Time | Activity | Deliverable |
| :--- | :--- | :--- |
| 08:00–10:00 | Check-in, loaner iQOO handover | Phone in hand, OriginOS 6 confirmed, developer options + USB debugging enabled |
| 10:00–11:00 | Opening keynote + Office Kit teach-in | **Pair the Office Kit bridge during the teach-in itself.** Verify screen mirroring, shared clipboard round-trip, and file drag-and-drop all work before the clock starts. |

> [!TIP]
> Telemetry for the Office Kit category (10 points) is measured across the whole event. Pairing at 10:00 instead of 14:00 is four free hours of bridge uptime.

Also confirm before 11:00: repo cloned on the build laptop, `models/phi3-mini-4k-int4/` present (pre-downloaded — do **not** burn event bandwidth on a multi-GB pull), and the Phase 1 prototype pipeline runs end to end.

---

## 3. Hour-by-Hour Schedule

### Saturday

| Window | Mode | Duration | Tasks | Exit Criteria |
| :--- | :---: | :---: | :--- | :--- |
| 11:00–13:30 | 🟢 GREEN | 2.5 h | Flutter project scaffold · Android SDK + toolchain · **`adb reverse` hot-reload setup** · push ONNX model artifact to device storage · repo init and first push | Hot reload lands on mirrored phone screen; app builds and installs |
| 13:30–15:30 | 🔴 RED | 2.0 h | Node-graph canvas UI on the phone, driven by hot reload from the mock delivered in Phase 1 | Canvas renders with hardcoded nodes, taps register with visible feedback |
| 15:30–16:00 | — | — | **Mentor Round 1** | Show the canvas + the Phase 1 pipeline. Ask specifically about NPU delegate configuration. |
| 16:00–19:00 | 🔴 RED | 3.0 h | Camera capture + ML Kit on-device OCR · microphone capture + on-device STT · wire both into the capture layer | Photograph a whiteboard sketch, see extracted text on screen |
| 19:00–19:45 | — | — | **Evaluation Round 1 (checkpoint)** | See [section 5](#5-checkpoint-deliverables) |
| 19:45–22:45 | 🟢 GREEN | 3.0 h | **The hard one:** ONNX Runtime Android bridge via platform channels · load Phi-3-mini int4 on device · first on-device inference · NPU delegate config | Model loads and returns tokens on the phone, even if slow |
| 22:45–01:15 | 🔴 RED | 2.5 h | Port `decompose_prompt.md` to the on-device runtime · tune for schema-valid JSON at on-device context limits · canvas polish | On-device inference emits valid node-graph JSON |
| 01:15–05:15 | 💤 | — | Sleep rotation — stagger it, do not have the whole team down at once | — |

### Sunday

| Window | Mode | Duration | Tasks | Exit Criteria |
| :--- | :---: | :---: | :--- | :--- |
| 05:15–08:15 | 🔴 RED | 3.0 h | Office Kit handoff: pack payload → clipboard + file transfer → CLI listener writes `.devcontext/` · live sensor testing · full-loop integration | Speak an idea into the phone, get a brain folder on the laptop |
| 08:15–09:00 | 🟢 GREEN | 0.75 h | Repo push · stage the judging build · screenshot pass | Clean build installed on the phone for judging |
| 09:00–10:00 | — | — | **Evaluation Round 2 (table judging)** | See [section 5](#5-checkpoint-deliverables) |
| 10:00–12:00 | 🟢 GREEN | 2.0 h | Final polish · bug triage · README and repo hygiene · **final push before lock** | Everything committed |
| **12:00** | 🔒 | — | **CODE FREEZE & REPO LOCK** | No commits after this point |
| 12:00–13:45 | — | — | Demo rehearsal only. Run the pitch three times on the actual phone. | 3–5 min pitch timed and rehearsed |
| 13:45 | 🎤 | — | **Live pitches to full jury** | — |

**Budget check:** Green 8.25 h · Red 10.5 h · Total 18.75 h ≈ 19 h ✓

---

## 4. Office Kit Telemetry Protocol (10 Points)

Bridge activity is measured continuously in the background by HackTracker. Build these into muscle memory rather than doing them performatively at the end:

1. **Never disconnect the bridge.** Keep Office Kit connected across the entire event, including sleep rotations.
2. **Move every string through the shared clipboard.** API keys, JSON payloads, prompt revisions, stack traces — copy on laptop, paste on phone. The product's own handoff step already does this, so the core loop generates telemetry for free.
3. **Transfer builds by drag-and-drop.** Push APKs across the bridge rather than over USB or a cloud link.
4. **Drive phone text fields with the laptop keyboard** through screen mirroring instead of tapping on glass.

---

## 5. Checkpoint Deliverables

What must be demoable at each judged checkpoint. Anything beyond this list is optional at that point in time.

### Evaluation Round 1 — Saturday 19:00

- [ ] Node-graph canvas rendering on the phone with real taps
- [ ] Camera OCR extracting text from a whiteboard sketch, live
- [ ] Voice capture producing a transcript
- [ ] The Phase 1 pipeline running on the laptop: prompt → local SLM → scouted repos → `.devcontext/`
- [ ] A clear verbal answer to "where does the model run?" — the honest answer at this stage is *laptop now, phone by morning*

### Evaluation Round 2 — Sunday 09:00

- [ ] **On-device inference working.** This is the headline claim; it must be true by now.
- [ ] Full loop: speak or photograph an idea → node graph → curate → compile → `.devcontext/` lands on the laptop
- [ ] Office Kit handoff performed live in front of the judge
- [ ] Offline demo: enable airplane mode, show decomposition still working

---

## 6. Risk Register & Fallbacks

| Risk | Likelihood | Fallback |
| :--- | :--- | :--- |
| **ONNX Runtime Android bridge fights us** (highest risk — nobody on the team has shipped mobile inference) | High | Drop to the on-device **embedding** model only for the local vector cache and keep decomposition on the laptop via the Office Kit bridge. Still a truthful local-model claim, weaker Technical Depth. Decide by **Sunday 01:00** — do not let this consume the night. |
| Phi-3-mini int4 too heavy for comfortable on-device latency (3.8B params) | Medium | Swap to a smaller instruct model in ORT-GenAI format and re-run the 5-prompt validation suite from Phase 1. The prompt and schema are model-agnostic by design. |
| Flutter canvas eats more time than budgeted (no prior Flutter on the team) | Medium | Ship a simpler vertical card list instead of a force-directed graph. The canvas is a presentation choice; the pipeline is the product. |
| Exa API rate limits or key exhaustion mid-demo | Medium | Cache every scouting response to disk on first call. The demo replays from cache if the API is unavailable. Build this caching in during Green Light 1, not during the demo. |
| Camera OCR unreliable on messy handwriting | Medium | Demo with a clean printed diagram or a laptop screen as the OCR target. Keep text entry available as the visible fallback path. |
| Office Kit bridge drops during judging | Low | Pre-record a 30-second handoff clip as insurance. Lead with live, fall back to video. |

---

## 7. What Phase 1 Already Delivered

Carried in from the pre-event night so it does not consume on-site hours:

| Artifact | Status |
| :--- | :--- |
| `decompose_prompt.md` + `node_graph.schema.json` + validator | Proven against local quantized inference, model-agnostic |
| Exa scouting (repo search + Reddit sentiment) | Working, with real data |
| `.devcontext/` brain generator + `init.sh` | Working end to end |
| Phi-3-mini int4 ONNX artifact | Downloaded, on disk, ready to push to device |
| Node-canvas visual design | Mock delivered by the deck owner |

The schedule above therefore starts from a working pipeline and spends its 19 hours on the phone layer — capture, canvas, on-device runtime, and the Office Kit handoff — rather than on discovery.
