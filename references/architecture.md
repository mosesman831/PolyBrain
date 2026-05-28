# PolyBrain Architecture

## Core Loop

```
Objective
  │
  ▼
┌─────────────────┐
│   Orchestrator   │  → JSON task list (2-5 tasks)
│   (1 model)      │
└──────┬──────────┘
       │
       ▼
┌──────────────────────────────────┐
│  Parallel Execution               │
│                                    │
│  ┌──────────┐  ┌──────────┐      │
│  │Researcher │  │Researcher │      │
│  │(web+cite) │  │(web+cite) │     │
│  └────┬─────┘  └─────┬────┘      │
│       │              │             │
│  ┌────┴─────┐        │             │
│  │ Builder  │        │             │
│  │(code/ops)│        │             │
│  └────┬─────┘        │             │
└───────┼──────────────┼─────────────┘
        │              │
        ▼              ▼
  ┌─────────────────────────┐
  │      Synthesizer         │  → unified brief (citations only)
  │      (1 model)           │
  └───────────┬─────────────┘
              │
              ▼
  ┌─────────────────────────┐
  │       Verifier           │  → PASS/FAIL per claim
  │       (1 model)          │
  └───────────┬─────────────┘
              │
              ▼
         Final Output
```

## Execution Model

1. **Orchestrator** produces a JSON task list from the objective (2-5 tasks).
2. **Router** maps each task's role to the configured model alias.
3. **Executor** runs researcher/builder tasks in parallel (ThreadPoolExecutor).
4. **Synthesizer** merges parallel outputs into a final deliverable, preserving only cited claims.
5. **Verifier** checks each synthesized claim against the cited sources. Invalid claims get corrected.

## Task Ordering

- Researcher + Builder tasks run in parallel.
- Synthesizer runs after parallel tasks complete.
- Verifier runs after synthesizer (sequential dependency).

The debug runner (orchestrate_debug.py) does all tasks sequentially for easier debugging. The production runner (orchestrate.py) uses parallelism for researcher + builder phases.

## Artifacts

Per-run outputs are saved under:
```
<artifacts_dir>/<run-id>/
├── orchestrator.json          # Parsed task list
├── orchestrator_raw_0.txt     # Raw orchestrator output (attempt 0)
├── orchestrator_raw_1.txt     # Raw orchestrator output (retry, if needed)
├── task_<id>.md               # Per-agent output
├── synthesis.md               # Final synthesized
└── verification.md            # Source verification report
```

## Citation Pipeline

```
Researcher → bullet claims + (URL) citations
     ↓
Synthesizer → preserves only cited claims, drops uncited
     ↓
Verifier → PASS/FAIL per claim against cited URLs
```

## Non-Goals

- Long-running autonomy (hours/days)
- Persistent state across sessions
- Cloud deployment
- OpenClaw compatibility (future)