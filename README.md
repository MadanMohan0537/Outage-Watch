# Outage Watch

A local, self-hosted demo of automated outage detection and diagnosis:
a sample web app you can crash on purpose, a log-matching diagnosis
engine, and an [OpenClaw](https://github.com/) skill that watches for
outages on a heartbeat and reports a diagnosis + recommended fix.

Runs entirely on your own machine (tested for a MacBook Air M4, 16GB RAM,
using [Ollama](https://ollama.com) + Qwen 2.5 7B). No cloud services
required, and it never auto-executes a fix — diagnosis and recommendation
only, human applies the fix.

## How it works

1. **`app/`** — a small Flask site with a `/health` endpoint and a
   `/crash/<kind>` endpoint that intentionally triggers one of five
   failure types (`db`, `memory`, `timeout`, `nullref`, `disk`), logging
   a realistic error + stack trace each time.
2. **`scripts/crash_trigger.py`** — hits `/crash/<kind>` to generate a
   test outage on demand.
3. **`incidents/incident_history.json`** — the "memory": a growing JSON
   archive of past incidents, each with an error signature, diagnosis,
   and the fix that was confirmed to work. Seeded with 5 example records.
4. **`scripts/diagnose.py`** — the core loop: checks `/health`, and on
   failure reads the latest log entry, matches it against
   `incident_history.json` by error type + keyword overlap, and prints
   a diagnosis and recommended fix. If nothing matches, it logs the
   outage as "unconfirmed" so a human can fill in the real diagnosis
   later — that's how the match quality improves over time.
5. **`openclaw/outage_skill.md`** — how to wire `diagnose.py` into
   OpenClaw's heartbeat scheduler, with permissions scoped to
   read-only + diagnose-only (no remediation, no network beyond
   localhost).

## Quick start

```bash
cd app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 app.py            # serves on http://localhost:5001
```

In another terminal:

```bash
cd scripts
python3 crash_trigger.py db          # trigger a test outage
python3 diagnose.py --use-llm        # detect it, match it, diagnose it
```

Reset the site back to healthy:

```bash
curl -X POST http://localhost:5001/recover
```

See `SETUP_GUIDE.md` for full install steps (Ollama, Qwen 2.5 7B,
OpenClaw) and RAM/feasibility notes for 16GB machines.

## Design principle: recommend, don't auto-fix

This project intentionally never takes remediation action on its own —
no restarts, no redeploys, no code changes. It only ever surfaces a
diagnosis and a fix a human has previously confirmed worked, and asks a
human to apply it. See `openclaw/outage_skill.md` for the reasoning and
how to keep any future auto-remediation narrowly scoped if you build it.

## Growing the incident history

Every time a real (or drilled) outage gets fixed, update its entry in
`incidents/incident_history.json` with the actual diagnosis, the actual
fix, and `"confirmed_resolution": true`. The matching only ever
recommends fixes that have been human-verified, and gets more useful
the more incidents get logged.
