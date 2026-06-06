---
name: polybrain
description: "Use when you need multi-model orchestration: decompose a high-level objective into subtasks, route each to a specialized model, run in parallel, synthesize, then verify."
version: 1.1.0
author: "Moses / LatticeAG"
license: GPL-3.0
metadata:
  hermes:
    tags: [orchestration, multi-model, subagents, parallel, routing, research]
    related_skills: [model-selection, model-routed-subagents]
---

# PolyBrain

Multi-model orchestration for Hermes Agent. Decomposes an objective into subtasks,
routes each to a specialized model, runs researchers/builders in parallel,
synthesizes the results, then verifies against cited sources.

Inspired by the orchestration pattern behind Perplexity Computer — built as a
local, config-driven, reproducible skill for any Hermes-compatible model.

## When to Use

- Objective requires research + analysis + writing (e.g., market briefs, reports).
- You want different models for different subtasks.
- You need citations and source verification.
- A single model can't handle the full workflow well.
- **The user invokes the skill** (via `/skill polybrain`, `hermes -s polybrain`, or by attaching `[IMPORTANT: The user has invoked the "polybrain" skill...]` to a message).

Do NOT use when:
- A single model can handle it end-to-end.
- You need persistent state across sessions.
- You need hours-long autonomous workflows.

### Agent Invocation Rule (critical)

When the user invokes this skill, you MUST run the orchestration script via the terminal tool. Do NOT fall back to ad-hoc `web_search` / `web_extract` / other tool calls.

**CRITICAL: Use `background: true` + `notify_on_complete: true` for the terminal call.** The orchestrator runs multiple sequential LLM calls (orchestrator → researchers in parallel → synthesizer → verifier), which takes 4–10 minutes total. A foreground `timeout: 300` will kill the entire process before researchers finish. Here is the correct invocation pattern:

```python
terminal(
    command='echo "<objective>" | python ~/.hermes/skills/research/polybrain/scripts/orchestrate.py',
    background=True,
    notify_on_complete=True
)
```

Then periodically poll with `process(action='poll')` or wait for the notification. Do NOT use a foreground timeout — the orchestrator itself handles per-task timeouts internally via `config.yaml`.

For debugging (sequential, verbose logging):
```python
terminal(
    command='echo "<objective>" | python ~/.hermes/skills/research/polybrain/scripts/orchestrate_debug.py',
    background=True,
    notify_on_complete=True
)
```

After completion, read the synthesis from the artifacts directory (`~/.hermes/plans/polybrain/<run-id>/synthesis.md`) or from stdout, and present it to the user.

**Timeout notes:**
- The orchestrator handles its own per-task timeouts via `config.yaml` (`timeout_sec`: 600s per researcher, `orchestrator_timeout_sec`: 120s for orchestrator).
- Total wall-clock time is approximately: orchestrator (~1 min) + max(researcher_1, researcher_2) (~5–10 min) + synthesizer (~2–3 min) ≈ 8–15 min.
- Using `background: true` avoids the agent's terminal timeout killing the process.

## Installation

### Option A: Hermes skills directory (recommended)
```bash
cp -r polybrain ~/.hermes/skills/research/
```

### Option B: From GitHub
```bash
hermes skills install https://github.com/<your-org>/polybrain
```

### After installation — configure your models
Edit `~/.hermes/skills/research/polybrain/config.yaml`:
```yaml
models:
  orchestrator: "your-model"
  researcher: "your-model"
  builder: "your-model"
  synthesizer: "your-model"
  verifier: "your-model"
  fallback: "your-model"
```

Then validate:
```bash
python ~/.hermes/skills/research/polybrain/scripts/validate_config.py
```

## Usage Modes

PolyBrain has two usage modes:

### Mode 1: Standalone Script (run directly)
The user runs the orchestration script directly without the agent. It uses
`hermes chat` as a subprocess to call models.

```bash
echo "Create a market brief on Apple" | python ~/.hermes/skills/research/polybrain/scripts/orchestrate.py
```

Or interactively:
```bash
python ~/.hermes/skills/research/polybrain/scripts/orchestrate.py
# prompts: Objective: ...
```

This is the primary usage mode. No agent interaction needed.

### Mode 2: Agent-Loaded Skill (Hermes uses it contextually)
The skill's SKILL.md is loaded by Hermes Agent (via `/skill polybrain` or
`hermes -s polybrain`). The agent, reading the skill's instructions, may
invoke the orchestration script via the terminal tool when a user request
matches the skill's trigger conditions.

This mode requires:
1. The skill directory copied to `~/.hermes/skills/research/`.
2. A run like `hermes -s polybrain` or `/skill polybrain` in-session.
3. The agent must then decide to spawn the script via terminal.

**Note:** Mode 2 is secondary. The core value is the standalone script.

## How It Works

```
Objective
  ├─ Orchestrator → JSON task list (schema enforced)
  │
  ├─ Parallel ─┬─ Researcher 1 (web search + citations)
  │            ├─ Researcher 2 (web search + citations)
  │            └─ Builder (terminal/file ops)
  │
  ├─ Synthesizer → unified brief (citations-only claims)
  │
  └─ Verifier → PASS/FAIL per claim + corrections
```

All outputs saved to `settings.artifacts_dir/<run-id>/`:
- `orchestrator.json` — parsed task list
- `task_<id>.md` — per-agent output
- `synthesis.md` — final deliverable
- `verification.md` — source verification report

## Roles

| Role | Purpose | Toolsets |
|-----------|------|---------|
| Orchestrator | Decompose objective, route tasks | none (text only) |
| Researcher | Web research with citations | web, browser |
| Builder | Code/tools, file ops | terminal, file |
| Synthesizer | Merge outputs into final deliverable | file |
| Verifier | Verify claims against sources | web |

## Citation & Verification Rules

- Researchers MUST use web tools and cite URLs.
- Synthesizer only uses cited claims — uncited claims are omitted.
- Verifier checks each claim against cited sources — INVALID if uncited or unsupported.

## Configuration Reference

See `config.yaml` for all options. Key settings:

| Key | Default | Description |
|-----|---------|-------------|
| `models.*` | (required) | Model alias for each role |
| `providers.*` | (optional) | Provider override per role |
| `toolsets.*` | (optional) | Toolsets per role (informational) |
| `settings.max_parallel` | 3 | Max parallel subagent tasks |
| `settings.timeout_sec` | 600 | Per-task timeout (bumped from 300 — researchers need more time for web tool calls) |
| `settings.orchestrator_timeout_sec` | 120 | Orchestrator-specific timeout |
| `settings.artifacts_dir` | `.hermes/plans/polybrain` | Where run artifacts are saved |

## Common Pitfalls

1. **Missing model aliases** — Run `validate_config.py` before first use.
2. **Model hangs/timeouts** — Some models struggle with `hermes chat` in subagent mode.
   Test with `hermes chat -q "ping" -m your-model` first.
3. **Orchestrator returns prose instead of JSON** — Handled automatically (retry + JSON extraction).
4. **No citations in output** — Check that researchers used web tools. See Debugging below.
5. **Verifier truncates numbers** — Known issue with some models; results are still valid structurally.
6. **Iterative testing pattern** — Test-as-you-build: validate config first, then run a small objective (e.g., 3 bullets), verify citations appear in output, then run the full workflow. Don't try to validate everything at once. Use `orchestrate_debug.py` for verbose sequential logging, `orchestrate.py` for production.
7. **Debug vs production runner** — `orchestrate_debug.py` runs all tasks sequentially with full verbose logging (ideal for debugging). `orchestrate.py` runs researchers/builders in parallel, then synthesis/verification sequentially (ideal for production). The prompts in both should be kept in sync.
8. **Skill is Hermes-only** — Uses `hermes chat` as a subprocess. Not compatible with OpenClaw or other agents. For OpenClaw compatibility, a separate command wrapper would be needed.
9. **Terminal foreground timeout kills the entire orchestration** — The orchestrator takes 8–15 minutes total. If you run it as a foreground terminal command with `timeout: 300`, the process is killed before any researcher finishes. ALWAYS use `background: true` + `notify_on_complete: true`. The orchestrator handles its own per-task timeouts internally via `config.yaml`. This is the single most common failure mode when agents invoke the skill — the process appears to hang or timeout, but it's actually the agent's terminal timeout, not the orchestrator.

## Debugging & Tool-Use Verification

See `references/pitfalls-terminal-timeout.md` for the terminal timeout pitfall and correct invocation pattern.

To verify tool calls happened:
```bash
hermes sessions list
hermes sessions export /tmp/polybrain_sessions.jsonl
# Then inspect for "web_search", "web_extract" calls in the JSONL
```

Use the debug runner for verbose output:
```bash
python scripts/orchestrate_debug.py
```

## Test Run

Validate config, then test with a simple objective. Use `background: true` for all runs:
```bash
python scripts/validate_config.py
```

Then run via terminal with `background: true` + `notify_on_complete: true`:
```python
terminal(
    command='echo "Summarize Apple\'s latest quarterly earnings in 3 bullets with sources" | python scripts/orchestrate.py',
    background=True,
    notify_on_complete=True
)
```
