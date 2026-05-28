import json
import subprocess
import time
from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config.yaml"

def load_config():
    return yaml.safe_load(CONFIG_PATH.read_text())


def run_cmd(label, cmd, timeout=120):
    print(f"\n[START] {label}")
    print(f"CMD: {cmd}")
    start = time.time()
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        dur = time.time() - start
        print(f"[DONE] {label} (rc={res.returncode}, {dur:.1f}s)")
        if res.stdout:
            print(f"--- STDOUT ({label}) ---\n{res.stdout}\n--- END STDOUT ---")
        if res.stderr:
            print(f"--- STDERR ({label}) ---\n{res.stderr}\n--- END STDERR ---")
        return {"stdout": res.stdout, "stderr": res.stderr, "returncode": res.returncode, "timeout": False}
    except subprocess.TimeoutExpired:
        dur = time.time() - start
        print(f"[TIMEOUT] {label} after {dur:.1f}s")
        return {"stdout": "", "stderr": "", "returncode": -1, "timeout": True}


def main():
    cfg = load_config()
    settings = cfg.get("settings", {})
    timeout = settings.get("timeout_sec", 300)
    orch_timeout = settings.get("orchestrator_timeout_sec", 120)
    artifacts_root = Path(settings.get("artifacts_dir", ".hermes/plans/polybrain"))

    run_id = time.strftime("%Y%m%d_%H%M%S")
    run_dir = artifacts_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    objective = input("Objective: ").strip()

    # Orchestrator prompt (short)
    parser_prompt = (
        "Return JSON only. Schema: {tasks:[{id,role,goal,context,toolsets,expected_output}],notes}. "
        "role must be one of: researcher, builder, synthesizer, verifier. 2 to 5 tasks. "
        "No markdown, no code fences. "
        f"Objective: {objective}"
    )

    orch_model = cfg["models"]["orchestrator"]
    orch_provider = cfg.get("providers", {}).get("orchestrator", "").strip()
    orch_provider_flag = f" --provider {orch_provider}" if orch_provider else ""
    orch_cmd = f"hermes chat -q {json.dumps(parser_prompt)} -m {orch_model}{orch_provider_flag} -Q --source polybrain"
    orch_res = run_cmd("orchestrator", orch_cmd, timeout=orch_timeout)
    (run_dir / "orchestrator_raw.txt").write_text(orch_res.get("stdout", ""))

    if orch_res.get("timeout"):
        print("Orchestrator timed out. Exiting.")
        return

    try:
        task_spec = json.loads(orch_res.get("stdout", "").strip())
    except json.JSONDecodeError:
        print("Orchestrator returned non-JSON. Exiting.")
        return

    (run_dir / "orchestrator.json").write_text(json.dumps(task_spec, indent=2))

    tasks = task_spec.get("tasks", [])

    task_outputs = []

    for i, task in enumerate(tasks, start=1):
        role = task["role"]
        model = cfg["models"].get(role) or cfg["models"].get("fallback")
        provider = cfg.get("providers", {}).get(role, "").strip()
        provider_flag = f" --provider {provider}" if provider else ""
        goal = task["goal"]
        context = task.get("context", "")

        if role == "researcher":
            prompt = (
                "You are the Researcher. You MUST use web tools.\n"
                "Return results ONLY from evidence you found during this run.\n"
                "Output format (strict):\n"
                "- Bullet list of claims, each with a citation in parentheses: (URL)\n"
                "- After bullets, include a Sources section with exact URLs used.\n"
                f"Task: {goal}\nContext: {context}"
            )
        elif role == "synthesizer":
            outputs_joined = "\n\n".join(o.get("stdout", "") for o in task_outputs)
            prompt = (
                "Combine subtask outputs into a unified deliverable.\n"
                "Rules:\n"
                "- ONLY use claims that already include citations in the subtask outputs.\n"
                "- Preserve citations inline (URL in parentheses).\n"
                "- If a claim lacks a citation, omit it.\n"
                f"Objective: {objective}\n\nSubtask outputs:\n{outputs_joined}"
            )
        elif role == "verifier":
            outputs_joined = "\n\n".join(o.get("stdout", "") for o in task_outputs)
            synth_out = task_outputs[-1].get("stdout", "") if task_outputs else ""
            prompt = (
                "Verify the synthesized output ONLY against cited sources in the subtask outputs.\n"
                "Rules:\n"
                "- If a claim has no citation, mark it INVALID.\n"
                "- If citation does not support the claim, mark it INVALID.\n"
                "Output format:\n"
                "- PASS/FAIL per bullet with short justification.\n"
                "- If any FAIL, provide a corrected bullet using ONLY cited evidence.\n\n"
                f"Synthesized output:\n{synth_out}\n\n"
                f"Subtask outputs:\n{outputs_joined}"
            )
        else:
            prompt = f"Role: {role}. Task: {goal}. Context: {context}"

        cmd = f"hermes chat -q {json.dumps(prompt)} -m {model}{provider_flag} -Q --source polybrain"
        res = run_cmd(f"task_{i}_{role}", cmd, timeout=timeout)
        (run_dir / f"task_{i}.md").write_text(res.get("stdout", ""))
        task_outputs.append({"role": role, "stdout": res.get("stdout", "")})

    print(f"\nDebug run complete. Artifacts in {run_dir}")


if __name__ == "__main__":
    main()
