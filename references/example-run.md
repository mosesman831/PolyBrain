# PolyBrain Example Run

## Objective
"Create a market brief on Apple with three bullets on revenue trends and two competitors."

## Orchestrator Output (JSON)
```json
{
  "tasks": [
    {"id": "t1", "role": "researcher", "goal": "Research Apple's revenue trends", ...},
    {"id": "t2", "role": "researcher", "goal": "Identify Apple's top competitors", ...},
    {"id": "t3", "role": "synthesizer", "goal": "Combine into market brief", ...},
    {"id": "t4", "role": "verifier", "goal": "Verify all claims", ...}
  ]
}
```

## Parallel Phase: Researchers

**t1 (Researcher)** — Revenue data with citations:
- Used `web_search` and `web_extract`
- Found FY2023-FY2025 data with URLs from Macrotrends, Apple Newsroom, SEC filings
- Returned specific figures: $383.3B → $391.0B → $416.2B

**t2 (Researcher)** — Competitor profiles with citations:
- Used `web_search` and `web_extract`
- Identified Samsung (smartphones) and Microsoft (cloud/AI)
- Each competitor profile included revenue data and competitive dynamics

## Sequential Phase

**t3 (Synthesizer)** — Final brief:
- Merged revenue trends + competitor profiles
- Preserved inline citations from researcher outputs
- Dropped any uncited claims

**t4 (Verifier)** — Source verification:
- Checked each claim against cited sources
- Flagged one Azure revenue mismatch (PASS on other claims)
- Provided corrected bullet using cited evidence

## Artifacts Created
```
.hermes/plans/polybrain/20260528_191548/
├── orchestrator.json
├── orchestrator_raw_0.txt
├── task_t1.md  (revenue research)
├── task_t2.md  (competitor research)
├── task_t3.md  (synthesis)
├── task_t4.md  (verification)
├── synthesis.md
└── verification.md
```

## Key Observations
- Total runtime: ~4 minutes (parallel phase ~2min, synthesis ~30s, verification ~2min)
- All researchers used web tools and cited sources
- Synthesizer preserved citations and dropped uncited claims
- Verifier caught a real data discrepancy