# Outage Watch

**A local outage-triage demo. It checks a sample Flask service, reads the latest outage from its log when the health check fails, scores that log against past incidents, and recommends a fix for a person to review. It never applies the fix itself.**

## Problem and who it's for

During an outage, the first few minutes go to rediscovering things the team already knew: what this error means and what fixed it last time. This demo is aimed at small teams, on-call engineers, and IT or ops project managers who want to see how an incident-history lookup could speed up first response without letting an agent take risky actions.

## Approach

1. Call the sample app's `GET /health` endpoint. The default base URL is `http://localhost:5001`. HTTP 200 means healthy. Any other result, including a connection error, is treated as an outage.
2. On an outage, read the latest `---- OUTAGE START ----` / `---- OUTAGE END ----` block from `logs/app.log`. If that block is missing, the script prints `No log entry found to diagnose. Manual investigation needed.` and exits with status 1. It does not write a record in that case.
3. Take `error_type` and the traceback from that block and score every record in `incidents/incident_history.json`. An equal `error_type` scores 5. Each of that record's keywords found in the traceback adds 1. A score of at least 5 is a match. The highest score wins, and a tie stays with the earlier record. Equal error types match on their own.
4. On a match, print the stored diagnosis and the recommended fix under the heading `Recommended fix (human review required)`. With `--use-llm`, a local Ollama model can also print a short summary. If the `ollama` package is missing or the model call fails, the script prints the stored text.
5. With no match, the raw trace is already printed. The script flags a new incident and appends an unconfirmed record for someone to complete later. That record sets `diagnosis` and `recommended_fix` to `UNCONFIRMED - needs human triage` and `confirmed_resolution` to false.

The script calls `/health`, reads the log, and writes `incidents/incident_history.json` only when an outage block has no match. It does not restart services, edit application code, or apply the recommended fix.

## What exists today

Checked by reading the source and running the quick start below with Python 3.12.3. A live Ollama rewrite was not run.

- `app/app.py` listens on `0.0.0.0` port 5001. It exposes `GET /`, `GET /health`, `GET` or `POST /crash/<kind>`, and `POST /recover`. The crash kinds `db`, `memory`, `timeout`, `nullref`, and `disk` append a fake stack trace to `logs/app.log`, set health to down (HTTP 503), and return HTTP 500. They do not exhaust a database, memory, or disk. An unknown kind returns HTTP 400 and leaves health up. `GET /recover` returns HTTP 405.
- `scripts/crash_trigger.py` takes a kind of `db`, `memory`, `timeout`, `nullref`, `disk`, or `random`, plus `--url` (default `http://localhost:5001`). It sends `POST /crash/<kind>`.
- `scripts/diagnose.py` takes `--url`, `--use-llm`, and `--model` (default `qwen2.5:7b`).
- `incidents/incident_history.json` has 5 seed incidents, `seed-001` through `seed-005`, each with `confirmed_resolution` true.
- Demo run from this tree: `python scripts/crash_trigger.py db` returned HTTP 500, and `python scripts/diagnose.py` matched `seed-001` and printed the stored diagnosis and recommended fix. `POST /recover` returned `{"status":"up"}`. The next `python scripts/diagnose.py` printed `[OK] Site is healthy. No outage detected.` Separate runs matched `memory` to `seed-002`, `timeout` to `seed-003`, `nullref` to `seed-004`, and `disk` to `seed-005`. Those matches left the incident file unchanged.
- An outage block whose `error_type` matches none of the seeds is appended as an unconfirmed record. The five built-in crash kinds all match a seed, so the sample app does not produce that case by itself.
- `python scripts/diagnose.py --use-llm --model qwen2.5:7b` was run with no `ollama` package and no Ollama daemon. It printed the stored diagnosis and no AI summary.
- `openclaw/outage_skill.md` is an example heartbeat-skill definition for the OpenClaw agent runtime. The example lists read access to `outage-agent/logs/app.log`, read-write access to `outage-agent/incidents/incident_history.json`, and localhost network access. Adding the file does not install or schedule anything.
- [SETUP_GUIDE.md](SETUP_GUIDE.md) is a walkthrough for a MacBook Air M4 with 16 GB of RAM and a local Qwen 2.5 7B model. Its sample-site commands use an `outage-agent/app` directory and run `python3 app.py` from there.

## How success would be measured

| Measure | Status |
|---|---|
| Share of outages matched to the right historical incident | Not yet measured. The history file contains 5 seed incidents. |
| Time from outage to first useful diagnosis | Not yet measured |
| Unknown incidents that get a confirmed fix recorded afterward | Not yet measured |

## Limitations

- A local demo, with one sample service, one log file, and no distributed tracing.
- Scoring is equal `error_type` plus keyword overlap against five seed incidents. Equal error type is enough for a match, so two incidents that share an error type are not separated. The lookup stays limited to incidents a person has confirmed.
- The script runs only when invoked. Recurring checks need cron or another scheduler. The OpenClaw file is an example schedule, not a running one.
- If `/health` cannot be reached and `logs/app.log` still holds an older outage block, the script diagnoses that block.
- An LLM-polished narrative does not confirm a root cause. Validate any suggested fix before applying it elsewhere. That narrative path has not been run here.
- There are no test files, no CI workflow, and no license file.

## Quick start

Requires Python 3.10 or newer. The commands below were run with Python 3.12.3.

```bash
git clone https://github.com/MadanMohan0537/Outage-Watch.git
cd Outage-Watch
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -r app/requirements.txt
python app/app.py                  # keep running; serves http://localhost:5001
```

`app/requirements.txt` installs Flask 3.0.3 and requests 2.32.3.

In a second terminal, with the same virtual environment active:

```bash
python scripts/crash_trigger.py db
python scripts/diagnose.py
curl -X POST http://localhost:5001/recover
python scripts/diagnose.py         # prints: [OK] Site is healthy. No outage detected.
```

Optional, when the Ollama daemon is running, the separate `ollama` Python package is installed, and a model is pulled. Those are outside `app/requirements.txt`. If the package or the daemon is missing, the command prints the stored diagnosis:

```bash
python scripts/diagnose.py --use-llm --model qwen2.5:7b
```

## Deployment

Cloudflare Workers is the planned deployment target. It is not configured yet, and this repository is not deployed. There is no `wrangler.toml`, no Worker entry point, and no workers.dev URL.

Publishing, once that exists, is `npx wrangler deploy`. Getting there still requires:

- a `wrangler.toml`
- a Worker entry point
- for this Python code, either Cloudflare Python Workers or a JavaScript/TypeScript port

```bash
npx wrangler deploy
```

## License

No license file is included yet.
