# PHASE_1_SUBMISSION_DRAFT: Portal Text Fields Copy-Paste Resource

> [!IMPORTANT]
> Every field below is final copy, ready to paste straight into the Reskilll portal. Submission must be made by the **Team Leader account only**. Cross-check against the field table in [PHASE_1_SUBMISSION_REQUIREMENTS.md](./PHASE_1_SUBMISSION_REQUIREMENTS.md) before hitting submit.

---

## 1. Idea / Project Title

**Primary choice:**

```text
DevContext AI: Your Project's Brain, Built Before You Code
```

**Alternate (more literal, if the jury pool skews technical):**

```text
DevContext AI: On-Device Architecture Blueprinting for Developers
```

> [!NOTE]
> The original draft — "DevContext AI: Local Memory Engine & Semantic Architecture Blueprint" — stacks two subtitles and runs long. The form guidance asks for short, punchy and memorable, reflecting the core value proposition. Both options above satisfy the 5-character minimum and survive being read aloud on a slide. Pick whichever the team prefers.

---

## 2. Selected Track

```text
Track #6: Developer Tools (Eligible for City Battles + National Grand Finale)
```

---

## 3. Project Description (Comprehensive Maximizer Field)

DevContext AI is a phone-first developer orchestration canvas built with Flutter that fixes the pre-coding blueprint phase for early-career developers and engineering students across India. Rather than shipping another cramped mobile IDE, it works as an architecture companion running beside the developer's desktop workspace.

Input is multi-modal and on-device. A developer dictates app requirements into the microphone, or points the phone camera at a whiteboard architecture sketch and lets Google ML Kit's on-device OCR read the layout. A quantized Small Language Model, served through ONNX Runtime on the Snapdragon NPU, turns that input into a structured architecture JSON node tree. Because the model runs locally, decomposition keeps working with no network at all — which matters directly under the hackathon's Red Light constraint, when the laptop is locked and connectivity is unreliable.

The Flutter client then calls the Exa AI Neural Search API over HTTPS with no desktop localhost dependency in the path. Parallel semantic queries scout high-quality open-source boilerplates, libraries, and UI component structures across GitHub, GitLab, and Bitbucket, while a second domain-filtered pass pulls live community sentiment and open bug complaints from developer channels on Reddit. This is the signal that junior developers currently miss: the thread explaining that a library they are about to adopt has been unmaintained for fourteen months.

The developer works through an animated node-graph interface on the phone: swipe between requirement nodes, review repository health metrics, open documentation in an embedded webview, and approve the final stack. On confirmation the phone renders the compiled brain on screen, then pushes the packed schema across the iQOO Office Kit bridge using shared clipboard and file transfer. A lightweight CLI listener on the laptop receives that payload and writes a persistent Brain Folder (`.devcontext/`) plus an automated bootstrap script (`init.sh`) into the IDE root. The developer runs `bash init.sh` and their dependencies, module clones, and path mappings resolve instantly — leaving a private, local, vector-backed context anchor for the entire build lifecycle.

---

## 4. Prior Builds, Projects & Hackathons (Crucial Shortlisting Gate)

Our team consists of experienced product builders with a track record of shipping fast, performant applications across web and mobile platforms:

- **MohanaMantra 2K26 Production Portal**: Architected and launched the official production web infrastructure for Mohan Babu University's (MBU) national cultural festival, managing concurrent asset preloading pipelines, Zustand global state architecture, and complex GSAP / Framer Motion interactive UI layers. The live system passed rigorous RapidScan security audits across 80+ critical vulnerability vectors with zero exposed infrastructure flaws.

- **AIStream Real-Time Research Suite**: Designed a localized Streamlit processing application wrapping multi-modal research tools, parsing and structuring external documentation patterns through automated semantic index routing.

- **Custom Drone Navigation System Integration**: Contributed custom autonomous ArduPilot workspace modules inside WSL/Ubuntu environments, handling local bash script compilation workflows and mathematical vector trajectory alignment in simulator environments.

---

## 5. What Makes Our Team Stand Out?

Our team combines advanced frontend design expertise with low-level local system automation skills — a rare pairing. Having built the production framework for MohanaMantra 2K26, we are experienced in managing complex client state engines, rendering smooth canvas interactions, and writing bulletproof responsive layouts in React; Flutter is our deliberate choice for this build, giving us one high-performance codebase targeting the phone as the primary surface.

We pair that with deep familiarity with open-source automation, local API wrappers, and shell-level script execution, drawn directly from our ArduPilot and WSL toolchain work. We build tools that don't just look good but solve real infrastructure problems for working engineers. We design with a constraint-first mindset, which is why this submission ships a deliberately reduced five-component architecture instead of an ambitious fifteen-module one: we would rather demo something that fully works than describe something that doesn't.

---

## 6. Proficiency Declarations

| Field | Selection |
| :--- | :--- |
| **Android Proficiency** | *Team to confirm — recommend Beginner or Intermediate based on honest self-assessment* |
| **LLM Proficiency** | *Team to confirm — recommend Intermediate given the AIStream multi-modal work* |

> [!WARNING]
> Do not inflate these. They are self-assessed and a mismatch between a declared "Advanced" and on-site output is far more damaging than an honest "Beginner".

---

## 7. Optional Bonus Fields

| Field | Status |
| :--- | :--- |
| **Video Walkthrough URL** | Delegated — concept walkthrough with voiceover over the node-canvas mock |
| **Prototype URL** | GitHub repo, see [ONSITE_BUILD_PLAN.md](./ONSITE_BUILD_PLAN.md) for what ships tonight vs. on-site |
| **Deck / Document** | Delegated — PDF/PPT under 25 MB, or Drive link with open link permissions |

---

## 8. Pre-Submit Checklist

- [ ] Title selected from section 1
- [ ] Description pasted, verified over 50 characters, reads cleanly
- [ ] Prior builds pasted
- [ ] Team standout pasted
- [ ] Android proficiency selected
- [ ] LLM proficiency selected
- [ ] Deck uploaded (<25 MB) or link permissions confirmed open to anyone
- [ ] Prototype URL added if repo is public
- [ ] Video URL added if recorded
- [ ] Originality confirmation checkbox ticked
- [ ] Submitted from the Team Leader account

---

## Appendix: Changes Applied to the Original Draft

Recorded for transparency — veto any of these and the original wording goes back in.

| # | Change | Reason |
| :--- | :--- | :--- |
| 1 | Closed the unmatched parens on `.devcontext/` and `init.sh` | Original had a closing paren with no opener, twice |
| 2 | `userflow` → `user flow` | Spelling |
| 3 | Named the CLI listener as the component that writes the folder | Original implied the clipboard bridge creates directories, which a technical judge would flag as impossible |
| 4 | Added offline capability as an explicit benefit, tied to Red Light | Strongest consequence of the on-device model choice, absent from the original |
| 5 | Added Office Kit **file transfer** alongside shared clipboard | HackTracker telemetry measures clipboard, file transfer and remote control — mentioning only one undersells it |
| 6 | Trimmed ~15% and reduced noun stacking | Phrases like "on-device multi-modal sensory hardware layers" and "processes the incoming sensory arrays" read as machine-generated to a shortlisting reviewer |
| 7 | Softened "layouts in Flutter and React" to React, with Flutter as a deliberate choice | Nothing in the prior-builds section evidences Flutter; an unsupported claim causes a reviewer to discount the supported ones |
| 8 | Expanded MBU to Mohan Babu University on first use | Out-of-context reviewer will not know the acronym |
