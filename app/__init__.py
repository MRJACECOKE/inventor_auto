"""Photo-to-IPT Builder - desktop front-end over the inventor_auto pipeline.

Scope: Phase E-I (validate -> plan -> Inventor build -> verify -> report).
Phase A-C (photo -> structure) stays in Claude Code; this package consumes the
measurement-request.json + feature-intent.json it produces.

Modules:
  app.resources  - path resolution (frozen vs source), script/schema locations
  app.pipeline   - headless wrapper: run_validate / run_plan / run_build / form I/O
  app.ipt_builder - PySide6 GUI (see handoff.md; not implemented in the CORE run)
"""

__version__ = "0.1.0"
