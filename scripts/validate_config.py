import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"

REQUIRED_ALIASES = [
    "orchestrator", "researcher", "builder", "synthesizer", "verifier", "fallback"
]

REQUIRED_TOOLSETS = [
    "researcher", "builder", "synthesizer", "verifier"
]

REQUIRED_PROVIDERS = [
    "orchestrator", "researcher", "builder", "synthesizer", "verifier", "fallback"
]


def main():
    cfg = yaml.safe_load(CONFIG_PATH.read_text())
    models = cfg.get("models", {})
    toolsets = cfg.get("toolsets", {})
    providers = cfg.get("providers", {})

    missing_models = [k for k in REQUIRED_ALIASES if not models.get(k)]
    missing_toolsets = [k for k in REQUIRED_TOOLSETS if not toolsets.get(k)]

    errors = []
    if missing_models:
        errors.append(f"Missing model aliases: {', '.join(missing_models)}")
    if missing_toolsets:
        errors.append(f"Missing toolsets: {', '.join(missing_toolsets)}")

    # Providers are optional; just ensure keys exist if providers block is present
    if providers:
        missing_provider_keys = [k for k in REQUIRED_PROVIDERS if k not in providers]
        if missing_provider_keys:
            errors.append(f"Missing provider keys: {', '.join(missing_provider_keys)}")

    if errors:
        raise SystemExit("\n".join(errors))

    print("config.yaml OK")


if __name__ == "__main__":
    main()
