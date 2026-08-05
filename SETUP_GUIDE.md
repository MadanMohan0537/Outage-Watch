# Setup Guide: Local Outage-Detection Agent (MacBook Air M4, 16GB RAM)

This runs entirely on your friend's Mac: a sample site you crash on purpose,
a local LLM via Ollama, and OpenClaw watching for outages and diagnosing
them by matching against past incidents. Nothing leaves the machine.

## 0. Feasibility notes for 16GB RAM (read this first)

16GB is workable but has real limits. Guidance to keep things stable:

- **Model choice: Qwen 2.5 7B, not a larger variant.** At Q4 quantization
  it's ~4.5GB on disk and leaves headroom for OpenClaw's daemon, the
  sample Flask app, and normal OS/browser overhead. A 14B model technically
  fits at Q4 but only if you close nearly everything else — not realistic
  for something meant to run in the background 24/7.
- Don't run a browser with many tabs, Docker Desktop, or other heavy apps
  at the same time as Ollama + OpenClaw while testing.
- If you see swapping/slowdowns, the first thing to try is dropping to a
  smaller quantization (Q4_K_M is a reasonable default) before dropping
  the parameter count further.
- OpenClaw itself is a fast-growing, very new open-source project. Give it
  the narrowest permissions you can (see `openclaw/outage_skill.md`) — for
  this project it should only ever read logs and print a diagnosis, never
  execute remediation or reach outside localhost.

## 1. Install Ollama

```bash
brew install ollama
brew services start ollama
```

Pull the model:

```bash
ollama pull qwen2.5:7b
```

Verify it works:

```bash
ollama run qwen2.5:7b "reply with just: ok"
```

## 2. Install OpenClaw

Follow OpenClaw's own install instructions for macOS (it changes fast, so
check their current docs rather than relying on a fixed command here).
At a high level you'll:

1. Install the OpenClaw runtime.
2. Point it at Ollama as the LLM provider, model `qwen2.5:7b`.
3. Confirm the heartbeat/scheduler is running (`openclaw status` or
   equivalent).

## 3. Set up the sample site

```bash
cd outage-agent/app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

The site runs on `http://localhost:5001`. Leave this running in its own
terminal tab.

## 4. Trigger a test outage

In another terminal:

```bash
cd outage-agent/scripts
python3 crash_trigger.py db
```

This hits `/crash/db` on the sample site, which logs a fake database
connection failure to `outage-agent/logs/app.log` and flips the site's
`/health` endpoint to return 503.

## 5. Run the diagnosis script manually first

Before wiring it into OpenClaw, confirm it works standalone:

```bash
pip install ollama   # only needed if you want --use-llm
python3 diagnose.py --url http://localhost:5001 --use-llm
```

You should see it detect the outage, match it against
`incidents/incident_history.json` (seeded with 5 example past incidents:
db, memory, timeout, nullref, disk), and print a diagnosis + recommended
fix. It will not do anything else — no restarts, no code changes.

Reset the site back to healthy when you're done testing:

```bash
curl -X POST http://localhost:5001/recover
```

## 6. Wire it into OpenClaw

See `openclaw/outage_skill.md` for the skill definition and how to
register it with OpenClaw's heartbeat scheduler. Use an absolute path to
`diagnose.py` in the command.

## 7. Closing the loop over time

Every time a real outage happens (drilled or genuine) and gets fixed,
update its entry in `incidents/incident_history.json` with the real
diagnosis, the real fix, and `"confirmed_resolution": true`. That's the
"memory" the matching relies on — it only ever recommends fixes a human
has actually verified, and it gets more useful the more incidents you log.

## What this does NOT do (by design)

- It does not auto-restart services, redeploy, or modify code.
- It does not reach outside localhost.
- It always requires a human to review and apply the recommended fix.

If you later want a narrow auto-remediation step (e.g. auto-restarting a
known-safe local service for a known-safe error signature), that should be
built as a separate, explicitly scoped skill with its own permission
grant — not by loosening this one.
