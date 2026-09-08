"""DevContext AI — context compiler pipeline.

Components mirror the architecture in documentation/PROJECT_DEVCONTEXT_SPEC.md:

    decompose.py      DECOMPOSE  local quantized SLM -> node graph JSON
    scout.py          SCOUT      Exa neural search -> repo candidates + trend signal
    compile_brain.py  COMPILE    node graph + scouting -> .devcontext/ + init.sh
    pipeline.py       the three wired end to end

CAPTURE and CURATE are the on-device Flutter layers and are built on-site.
"""

__version__ = "0.1.0"


def enable_utf8_stdout() -> None:
    """Force UTF-8 on stdout/stderr.

    Windows consoles and redirected pipes default to cp1252, which raises
    UnicodeEncodeError on the box-drawing characters and em dashes this CLI
    prints. A demo must not die on a decorative character, so every entry point
    calls this first. Falls back silently on interpreters without reconfigure().
    """
    import sys

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass
