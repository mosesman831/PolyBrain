#!/usr/bin/env python3
"""
PolyBrain — Multi-model orchestration for Hermes Agent.

Decomposes an objective into subtasks, routes to specialized models,
runs researcher/builder tasks in parallel, then synthesizes and verifies.

Usage:
  python orchestrate.py
  # or pipe:
  echo "Your objective" | python orchestrate.py
"""

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config.yaml"


def extract_json(text: str) -> str:
    """Try to salvage JSON from text that may contain prose or markdown."""
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


def load_config():
    if not CONFIG_PATH.exists():
        raise SystemExit(f"Config not found: {CONFIG_PATH}\nRun: python scripts/validate_config.py")
    return yaml.safe_load(CONFIG_PATH.read_text())


def run_cmd(cmd, timeout=300):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)


def build_chat_cmd(prompt, model, provider, timeout=None):
    """Build a hermes chat command string."""
    provider_flag = f" --provider {provider}" if provider else ""
    # Escape prompt for shell: use json.dumps which handles quotes/newlines
    return f"hermes chat -q {json.dumps(prompt)} -m {model}{provider_flag} -Q --source polybrain"


def run_chat(prompt, model, provider, label, timeout=300, retry_count=1):
    """Run hermes chat with retry, return stdout string."""
    cmd = build_chat_cmd(prompt, model, provider)
    last_out = ""
    for attempt in range(1, retry_count + 2):
        try:
            print(f"  [{label}] attempt {attempt}...", file=sys.stderr)
            res = run_cmd(cmd, timeout=timeout)
            last_out = res.stdout.strip()
            if last_out:
                return last_out, res.returncode
        except subprocess.TimeoutExpired:
            print(f"  [{label}] timeout after {timeout}s", file=sys.stderr)
            last_out = ""
        except Exception as e:
            print(f"  [{label}] error: {e}", file=sys.stderr)
            last_out = ""
    return last_out, -1


# ── Prompts ──────────────────────────────────────────────────────────────────

def build_orchestrator_prompt(objective):
    return (
        "Return JSON only.\n"
        "Schema: {tasks:[{id,role,goal,context,toolsets,expected_output}],notes}.\n"
        "role must be one of: researcher, builder, synthesizer, verifier.\n"
        "2 to 5 tasks. No markdown, no code fences.\n"
        f"Objective: {objective}"
    )


def build_orchestrator_prompt_retry(objective):
    return (
        "JSON ONLY. No other text.\n"
        "{\n"
        '  "tasks": [\n'
        "    {\n"
        '      "id": "t1",\n'
        '      "role": "researcher",\n'
        '      "goal": "...",\n'
        '      "context": "...",\n'
        '      "toolsets": ["web"],\n'
        '      "expected_output": "..."\n'
        "    }\n"
        "  ],\n"
        '  "notes": "..."\n'
        "}\n"
        f"Objective: {objective}"
    )


def build_researcher_prompt(goal, context):
    return (
        "You are the Researcher. You MUST use web tools.\n"
        "Return results ONLY from evidence you found during this run.\n"
        "Output format (strict):\n"
        "- Bullet list of claims, each with a citation in parentheses: (URL)\n"
        "- After bullets, include a Sources section with exact URLs used.\n"
        f"Task: {goal}\nContext: {context}"
    )


def build_builder_prompt(goal, context):
    return (
        "You are the Builder. Use terminal/file tools as needed.\n"
        "Provide steps and outputs with clear documentation.\n"
        f"Task: {goal}\nContext: {context}"
    )


def build_synthesizer_prompt(objective, outputs_joined):
    return (
        "Combine subtask outputs into a unified deliverable.\n"
        "Rules:\n"
        "- ONLY use claims that already include citations in the subtask outputs.\n"
        "- Preserve citations inline (URL in parentheses).\n"
        "- If a claim lacks a citation, omit it.\n"
        f"Objective: {objective}\n\nSubtask outputs:\n{outputs_joined}"
    )


def build_verifier_prompt(synth_output, outputs_joined):
    return (
        "Verify the synthesized output ONLY against cited sources in the subtask outputs.\n"
        "Rules:\n"
        "- If a claim has no citation, mark it INVALID.\n"
        "- If citation does not support the claim, mark it INVALID.\n"
        "Output format:\n"
        "- PASS/FAIL per bullet with short justification.\n"
        "- If any FAIL, provide a corrected bullet using ONLY cited evidence.\n\n"
        f"Synthesized output:\n{synth_output}\n\n"
        f"Subtask outputs:\n{outputs_joined}"
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    cfg = load_config()
    settings = cfg.get("settings", {})
    max_parallel = settings.get("max_parallel", 3)
    timeout = settings.get("timeout_sec", 300)
    retry_count = settings.get("retry_count", 1)
    orch_timeout = settings.get("orchestrator_timeout_sec", 120)
    orch_retry = settings.get("orchestrator_retry_count", 1)
    artifacts_root = Path(settings.get("artifacts_dir", ".hermes/plans/polybrain"))

    run_id = time.strftime("%Y%m%d_%H%M%S")
    run_dir = artifacts_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Get objective from stdin or prompt
    if not sys.stdin.isatty():
        objective = sys.stdin.read().strip()
    else:
        objective = input("Objective: ").strip()

    if not objective:
        raise SystemExit("No objective provided.")

    # ── Phase 0: Orchestrate ──────────────────────────────────────────────

    orch_model = cfg["models"]["orchestrator"]
    orch_provider = cfg.get("providers", {}).get("orchestrator", "").strip()

    task_spec = None
    for attempt in range(orch_retry + 1):
        prompt = build_orchestrator_prompt(objective) if attempt == 0 else build_orchestrator_prompt_retry(objective)
        print(f"[orchestrator] attempt {attempt + 1}...", file=sys.stderr)
        orch_out, rc = run_chat(prompt, orch_model, orch_provider, "orchestrator", timeout=orch_timeout, retry_count=1)
        (run_dir / f"orchestrator_raw_{attempt}.txt").write_text(orch_out)

        try:
            task_spec = json.loads(orch_out)
            break
        except json.JSONDecodeError:
            try:
                task_spec = json.loads(extract_json(orch_out))
                break
            except json.JSONDecodeError:
                task_spec = None
                continue

    if task_spec is None:
        raise SystemExit("Orchestrator did not return valid JSON after retries.")

    (run_dir / "orchestrator.json").write_text(json.dumps(task_spec, indent=2))

    tasks = task_spec.get("tasks", [])
    print(f"[orchestrator] {len(tasks)} tasks parsed.", file=sys.stderr)

    # ── Phase 1: Run researchers + builders in parallel ───────────────────

    parallel_tasks = [t for t in tasks if t["role"] in ("researcher", "builder")]
    sequential_tasks = [t for t in tasks if t["role"] in ("synthesizer", "verifier")]

    task_outputs = {}  # task_id -> {"role": ..., "stdout": ...}

    def execute_parallel_task(task):
        role = task["role"]
        model = cfg["models"].get(role) or cfg["models"].get("fallback")
        provider = cfg.get("providers", {}).get(role, "").strip()
        goal = task["goal"]
        context = task.get("context", "")

        if role == "researcher":
            prompt = build_researcher_prompt(goal, context)
        else:  # builder
            prompt = build_builder_prompt(goal, context)

        stdout, rc = run_chat(prompt, model, provider, f"task_{task['id']}_{role}", timeout=timeout, retry_count=retry_count)
        return task["id"], {"role": role, "stdout": stdout, "returncode": rc}

    if parallel_tasks:
        print(f"[executor] Running {len(parallel_tasks)} tasks in parallel (max {max_parallel})...", file=sys.stderr)
        with ThreadPoolExecutor(max_workers=max_parallel) as ex:
            futures = [ex.submit(execute_parallel_task, t) for t in parallel_tasks]
            for f in futures:
                tid, result = f.result()
                task_outputs[tid] = result
                (run_dir / f"task_{tid}.md").write_text(result["stdout"])
                print(f"  [task_{tid}] done (rc={result['returncode']}, {len(result['stdout'])} chars)", file=sys.stderr)

    # ── Phase 2: Run synthesizer + verifier sequentially ──────────────────

    some_output = next(iter(task_outputs.values()), {})
    all_outputs_text = "\n\n".join(v["stdout"] for v in task_outputs.values())

    all_sequential_outputs = {}  # collect all outputs for verifier

    for task in sequential_tasks:
        role = task["role"]
        model = cfg["models"].get(role) or cfg["models"].get("fallback")
        provider = cfg.get("providers", {}).get(role, "").strip()

        if role == "synthesizer":
            prompt = build_synthesizer_prompt(objective, all_outputs_text)
        elif role == "verifier":
            synth_out = all_sequential_outputs.get("synthesizer", "")
            prompt = build_verifier_prompt(synth_out, all_outputs_text)
        else:
            continue

        print(f"[{role}] running...", file=sys.stderr)
        stdout, rc = run_chat(prompt, model, provider, f"task_{task['id']}_{role}", timeout=timeout, retry_count=retry_count)
        task_outputs[task["id"]] = {"role": role, "stdout": stdout, "returncode": rc}
        all_sequential_outputs[role] = stdout
        (run_dir / f"task_{task['id']}.md").write_text(stdout)
        print(f"  [task_{task['id']}] done (rc={rc}, {len(stdout)} chars)", file=sys.stderr)

    # ── Save final outputs ────────────────────────────────────────────────

    synth_out = all_sequential_outputs.get("synthesizer", "")
    verify_out = all_sequential_outputs.get("verifier", "")

    if synth_out:
        (run_dir / "synthesis.md").write_text(synth_out)
    if verify_out:
        (run_dir / "verification.md").write_text(verify_out)

    print(f"\nRun complete. Artifacts in {run_dir}", file=sys.stderr)

    # Print final synthesis to stdout
    if synth_out:
        print(synth_out)


if __name__ == "__main__":
    main()