# JSON Output Parsing (PolyBrain)

## Problem
Some models prepend prose or wrap output in code fences even when instructed to output JSON only. This breaks the orchestration pipeline.

## How PolyBrain Handles It

1. **Orchestrator prompt** — strict "JSON only, no markdown, no code fences"
2. **`-Q` (quiet) flag** — reduces extra model preamble
3. **Strict JSON parse** — try `json.loads(output)` first
4. **JSON extraction fallback** — find first `{` to last `}` substring and retry parse
5. **Retry with example** — if both fail, send a retry prompt with a full JSON example
6. **`--source polybrain`** — helps with session tracking for debug

## Code Pattern

```python
def extract_json(text: str) -> str:
    """Salvage JSON from text that may contain prose or markdown."""
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text
```

## Debugging

If the orchestrator consistently fails to return valid JSON:
1. Check the raw output saved to `orchestrator_raw_0.txt` in the artifacts directory.
2. Try a simpler/smaller model — some models handle JSON instructions better than others.
3. Run `hermes chat -q 'Return JSON only: {"test": true}' -m your-model -Q` to verify the model supports JSON output.
4. If the orchestrator times out repeatedly (default 120s), check if the model is hanging. Try `hermes chat -q "ping" -m your-model -Q` — if it returns in <10s, the model is fine.