"""Download the quantized ONNX SLM used by the DECOMPOSE component.

Target: microsoft/Phi-3-mini-4k-instruct-onnx, the `cpu_and_mobile` int4 build.
That variant is Microsoft's own mobile-targeted quantization and is the same
artifact family that runs on-device via onnxruntime-genai Android bindings,
so the prompt/schema work done against it on the laptop transfers to the phone.

Usage:
    python prototype/scripts/fetch_model.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from huggingface_hub import snapshot_download

REPO_ID = "microsoft/Phi-3-mini-4k-instruct-onnx"
VARIANT = "cpu_and_mobile/cpu-int4-rtn-block-32-acc-level-4"
DEST = Path(__file__).resolve().parents[2] / "models"


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    print(f"repo    : {REPO_ID}")
    print(f"variant : {VARIANT}")
    print(f"dest    : {DEST}")
    print("downloading (multi-GB, resumable)...", flush=True)

    path = snapshot_download(
        repo_id=REPO_ID,
        allow_patterns=[f"{VARIANT}/*"],
        local_dir=DEST / "phi3-mini-4k-int4",
    )

    model_dir = Path(path) / VARIANT
    files = sorted(p.name for p in model_dir.glob("*"))
    total = sum(p.stat().st_size for p in model_dir.glob("*") if p.is_file())

    print(f"\nDONE -> {model_dir}")
    print(f"files: {files}")
    print(f"size : {total / 1e9:.2f} GB")

    if not (model_dir / "genai_config.json").exists():
        print("ERROR: genai_config.json missing; not an ORT-GenAI model dir", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
