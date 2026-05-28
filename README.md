# PolyBrain

Multi-model orchestration skill for [Hermes Agent](https://github.com/nousresearch/hermes-agent).

Decomposes a high-level objective into parallel subtasks, routes each to a specialized model,
runs them concurrently, synthesizes the results, and verifies claims against cited sources.

Inspired by the orchestration pattern behind Perplexity Computer — built as a local,
config-driven, reproducible skill.

## Quick Start

```bash
# 1. Copy to your Hermes skills directory
cp -r polybrain ~/.hermes/skills/research/

# 2. Edit config.yaml with your model aliases
#    (orchestrator, researcher, builder, synthesizer, verifier, fallback)

# 3. Validate config
python ~/.hermes/skills/research/polybrain/scripts/validate_config.py

# 4. Run
echo "Summarize Apple's latest quarterly earnings with sources" | \
  python ~/.hermes/skills/research/polybrain/scripts/orchestrate.py
```

## How It Works

```
Objective → Orchestrator (JSON task list)
                │
        ┌───────┴───────┐
        │ Parallel        │
        ├─ Researcher 1   │
        ├─ Researcher 2   │
        ├─ Builder        │
        └───────┬───────┘
                │
         Synthesizer → unified brief (citations only)
                │
          Verifier → PASS/FAIL per claim
```

## Features

- **Citation enforcement** — Researchers must cite URLs; synthesizer drops uncited claims.
- **Source verification** — Verifier checks each claim against cited sources (PASS/FAIL).
- **Parallel execution** — Researcher + builder tasks run concurrently via ThreadPoolExecutor.
- **JSON repair** — Orchestrator output is auto-parsed even if the model adds prose or markdown.
- **Retry logic** — Both orchestrator and subtask failures trigger retries before giving up.
- **Model/provider routing** — Per-role model + provider overrides via config.yaml.
- **Full artifact logging** — Every run creates a timestamped folder with all inputs/outputs.

## Roles

| Role | Purpose | Toolsets |
|------|---------|----------|
| **Orchestrator** | Decompose objective into JSON task list | text-only |
| **Researcher** | Web search + citations (enforced) | web, browser |
| **Builder** | Code/terminal/file operations | terminal, file |
| **Synthesizer** | Merge outputs into final deliverable | (optional) |
| **Verifier** | Verify claims against cited sources | web |

## Configuration

Edit `config.yaml`:

```yaml
models:
  orchestrator: "your-model"
  researcher: "your-model"
  builder: "your-model"
  synthesizer: "your-model"
  verifier: "your-model"
  fallback: "your-model"

providers:
  orchestrator: "your-provider"  # optional, set per-role if needed
  researcher: "your-provider"

settings:
  max_parallel: 3
  timeout_sec: 300
  orchestrator_timeout_sec: 120
  artifacts_dir: ".hermes/plans/polybrain"
```

See [`config.yaml`](config.yaml) for all options.

## File Tree

```
polybrain/
├── SKILL.md                          # Skill definition (Hermes)
├── README.md                         # This file
├── config.yaml                       # User-editable model configuration
├── references/
│   ├── architecture.md               # Design docs + data flow
│   ├── prompts.md                    # Versioned prompt templates
│   ├── schema.json                   # JSON schema for orchestrator output
│   ├── json-output-parsing.md        # JSON robustness strategy
│   └── example-run.md                # Example objective → final output
└── scripts/
    ├── orchestrate.py                # Production runner (parallel + sequential)
    ├── orchestrate_debug.py          # Debug runner (all sequential, verbose)
    └── validate_config.py            # Config validator
```

## Known Issues

- **Model-specific hangs** — Some models (e.g., gpt-5-mini via certain providers) hang
  in `hermes chat` subagent calls. If a model hangs for 300s+, try a different model
  or provider. Test with `hermes chat -q "ping" -m your-model` first.
- **Verifier may truncate numbers** — Some models strip leading digits from dollar
  amounts in verification reports. The PASS/FAIL verdicts remain structurally valid.

## License

MIT