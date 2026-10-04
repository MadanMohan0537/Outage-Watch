# Outage Watch

A local outage-triage demo that checks a Flask service, extracts an error signature and recommends a response from incident history.

**Recommend-only:** the diagnosis script does not execute a fix. It can append an unconfirmed incident record for human review. Monitoring runs each time the script is invoked; recurring checks require an external scheduler.

## How it works

1. Check the sample application's `/health` endpoint.
2. If unhealthy, read the latest outage block from the local log.
3. Match the error type and keywords against [incident history](incidents/incident_history.json).
4. Show a matching diagnosis and recommended fix, or flag an unknown incident.
5. Optionally use local Ollama to polish a matched diagnosis into a short summary.

The fault endpoints simulate outages; they do not intentionally exhaust your real database pool, memory or disk.

## Quick start

Use Python 3.10 or later. From the repository root:

```bash
git clone https://github.com/MadanMohan0537/Outage-Watch.git
cd Outage-Watch
python -m venv .venv
source .venv/bin/activate
python -m pip install -r app/requirements.txt
python app/app.py
```

On Windows, activate with `.venv\Scripts\activate`. Keep this terminal running. The sample service listens at http://localhost:5001.

In a second terminal, open the same repository and activate the same virtual environment:

```bash
python scripts/crash_trigger.py db
python scripts/diagnose.py
curl -X POST http://localhost:5001/recover
python scripts/diagnose.py
```

The final check should report a healthy service. Read the diagnostic output before using any suggested remediation on another system.

## Simulated failures

| Kind | Scenario |
| --- | --- |
| `db` | Database connection-pool exhaustion |
| `memory` | Memory threshold exceeded |
| `timeout` | Downstream payment timeout |
| `nullref` | Missing object access |
| `disk` | Disk write failure |

Replace `db` in the trigger command to explore another scenario.

## Optional local model

With Ollama, the Python Ollama package and a compatible local model configured, run:

```bash
python scripts/diagnose.py --use-llm --model qwen2.5:7b
```

If the optional model is unavailable, the script falls back to the stored diagnosis. An unmatched incident still needs human triage; a polished narrative does not confirm a root cause.

## Configuration and integration

- `--url` selects the target service URL; the demo's local log remains the diagnosis source.
- [SETUP_GUIDE.md](SETUP_GUIDE.md) covers additional setup details.
- [OpenClaw skill definition](openclaw/outage_skill.md) describes heartbeat integration. Including this file does not automatically install or schedule monitoring.
- [scripts/diagnose.py](scripts/diagnose.py) contains health checks, matching and incident-history updates.

## Boundaries

The repository is a local demonstration, not a complete observability platform. It has no distributed tracing or verified production incident benchmark. Protect logs and incident records, review unknown entries, and validate a recommended fix before applying it.

## Contributions and license

Start with tests for known and unknown signatures, unhealthy endpoints and unavailable model runtimes. No license file is currently included.
